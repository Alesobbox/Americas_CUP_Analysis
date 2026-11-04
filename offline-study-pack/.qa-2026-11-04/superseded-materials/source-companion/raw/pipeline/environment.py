"""Acquire retrospective environmental context, never causal forecast inputs.

Run ``python -m pipeline.environment`` to cache Open-Meteo hourly air/marine
model data for the replay catalog. No API request is made during verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 20
ENDPOINTS = {
    "air": "https://archive-api.open-meteo.com/v1/archive",
    "marine": "https://marine-api.open-meteo.com/v1/marine",
}
VARIABLES = {
    "air": {"temperature_2m": ("air_temperature_c", "°C")},
    "marine": {
        "wave_height": ("wave_height_m", "m"),
        "sea_surface_temperature": ("water_temperature_c", "°C"),
    },
}
OUTPUT_FIELDS = ("air_temperature_c", "wave_height_m", "water_temperature_c")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".environment-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_retrieved(value):
    if not isinstance(value, str):
        raise ValueError("Missing response retrieval timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Response retrieval timestamp must use UTC")
    return value


def replay_metadata(path: Path):
    """Decode only top-level metadata from a bounded prefix, before telemetry.

    All current catalog metadata ends before 112 KiB. A layout exceeding the
    1 MiB contract fails explicitly rather than loading replay telemetry arrays.
    """
    with path.open("rb") as stream:
        prefix = stream.read(MAX_METADATA_BYTES).decode("utf-8")
    decoder = json.JSONDecoder()
    position = 0
    result = {}
    wanted = {"id", "course", "chronology"}
    try:
        position = len(prefix) - len(prefix.lstrip())
        if prefix[position] != "{":
            raise ValueError("Replay metadata must be an object")
        position += 1
        while wanted - result.keys():
            while prefix[position].isspace() or prefix[position] == ",":
                position += 1
            key, position = decoder.raw_decode(prefix, position)
            if not isinstance(key, str):
                raise ValueError("Invalid replay metadata key")
            if key == "telemetry":
                raise ValueError("Required replay metadata must precede telemetry")
            while prefix[position].isspace():
                position += 1
            if prefix[position] != ":":
                raise ValueError("Invalid replay metadata separator")
            position += 1
            while prefix[position].isspace():
                position += 1
            value, position = decoder.raw_decode(prefix, position)
            if key in wanted:
                if key in result:
                    raise ValueError("Duplicate required replay metadata")
                result[key] = value
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("Required replay metadata exceeds bounded prefix or is malformed") from exc
    return validate_metadata(result)


def validate_metadata(metadata):
    race_id = metadata.get("id")
    if not isinstance(race_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", race_id):
        raise ValueError("Invalid race ID")
    origin = metadata.get("course", {}).get("origin", {})
    latitude, longitude = origin.get("lat"), origin.get("lon")
    if (not _finite(latitude) or not -90 <= latitude <= 90
            or not _finite(longitude) or not -180 <= longitude <= 180):
        raise ValueError("Replay course origin must contain valid latitude/longitude")
    chronology = metadata.get("chronology", {})
    start, end = chronology.get("window_start"), chronology.get("window_end")
    if (not _finite(start) or not _finite(end) or int(start) != start or int(end) != end
            or end < start or end - start > 7 * 86400000):
        raise ValueError("Invalid replay UTC window")
    try:
        start_date = datetime.fromtimestamp(start / 1000, timezone.utc).date().isoformat()
        end_date = datetime.fromtimestamp(end / 1000, timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Replay UTC window is out of range") from exc
    return {"race_id": race_id, "latitude": latitude, "longitude": longitude,
            "start_date": start_date, "end_date": end_date,
            "window_start_ms": int(start), "window_end_ms": int(end)}


def request_url(source, metadata):
    parameters = {
        "latitude": str(metadata["latitude"]), "longitude": str(metadata["longitude"]),
        "start_date": metadata["start_date"], "end_date": metadata["end_date"],
        "hourly": ",".join(VARIABLES[source]), "timezone": "GMT", "timeformat": "unixtime",
        "temperature_unit": "celsius",
    }
    if source == "marine":
        parameters["cell_selection"] = "sea"
    return ENDPOINTS[source] + "?" + urlencode(parameters)


def fetch_bytes(url, timeout=TIMEOUT_SECONDS):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "AC40Replay/1.0 historical-context"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if response.status != 200:
                raise ValueError(f"Weather provider returned HTTP {response.status}")
            if content_type != "application/json":
                raise ValueError("Weather provider response is not JSON")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ValueError(f"Weather provider returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Weather provider request failed: {exc}") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Weather provider response exceeds size limit")
    return data


def parse_response(data: bytes, source: str, metadata):
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Weather provider response exceeds size limit")
    try:
        body = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Weather provider returned malformed JSON") from exc
    if not isinstance(body, dict) or body.get("error"):
        reason = body.get("reason", "Invalid provider object") if isinstance(body, dict) else "Invalid provider object"
        raise ValueError(f"Weather provider error: {str(reason)[:240]}")
    lat, lon = body.get("latitude"), body.get("longitude")
    if (not _finite(lat) or not -90 <= lat <= 90 or not _finite(lon) or not -180 <= lon <= 180):
        raise ValueError("Weather provider grid location is invalid")
    if type(body.get("utc_offset_seconds")) is not int or body["utc_offset_seconds"] != 0:
        raise ValueError("Weather provider response is not aligned to UTC")
    hourly, units = body.get("hourly"), body.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict) or units.get("time") != "unixtime":
        raise ValueError("Missing hourly data or Unix-time units")
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise ValueError("Missing hourly timestamps")
    start = int(datetime.fromisoformat(metadata["start_date"]).replace(tzinfo=timezone.utc).timestamp())
    end = int(datetime.fromisoformat(metadata["end_date"]).replace(tzinfo=timezone.utc).timestamp()) + 86400
    if (any(not isinstance(t, int) or isinstance(t, bool) or t % 3600 or not start <= t < end for t in times)
            or any(a >= b for a, b in zip(times, times[1:]))):
        raise ValueError("Hourly timestamps must be unique ascending UTC hours inside the requested days")
    columns = {}
    for variable, (field, unit) in VARIABLES[source].items():
        values = hourly.get(variable)
        if units.get(variable) != unit:
            raise ValueError(f"Unexpected units for {variable}")
        if not isinstance(values, list) or len(values) != len(times):
            raise ValueError(f"Misaligned hourly values for {variable}")
        if any(v is not None and (not _finite(v) or (variable == "wave_height" and v < 0)) for v in values):
            raise ValueError(f"Invalid finite values for {variable}")
        columns[field] = dict(zip((t * 1000 for t in times), values))
    return columns, {"latitude": lat, "longitude": lon}


def acquire_source(source, metadata, public_directory, cache_directory, *, fetcher=None, force=False, clock=None):
    fetcher, clock = fetcher or fetch_bytes, clock or _utc_now
    url = request_url(source, metadata)
    cache_path = cache_directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    record, data = None, None
    if not force and cache_path.exists():
        record = json.loads(cache_path.read_bytes())
        if record.get("request_url") != url or not re.fullmatch(r"[0-9a-f]{64}", record.get("response_sha256", "")):
            raise ValueError("Historical weather cache request/hash mismatch; rebuild with --force")
        _parse_retrieved(record.get("retrieved_at"))
        data = (public_directory / "responses" / (record["response_sha256"] + ".json")).read_bytes()
        if hashlib.sha256(data).hexdigest() != record["response_sha256"]:
            raise ValueError("Historical weather cache content hash mismatch; rebuild with --force")
    if data is None:
        data = fetcher(url, timeout=TIMEOUT_SECONDS)
        record = {"request_url": url, "response_sha256": hashlib.sha256(data).hexdigest(),
                  "retrieved_at": _parse_retrieved(clock())}
    columns, grid = parse_response(data, source, metadata)
    response_file = "responses/" + record["response_sha256"] + ".json"
    _write_bytes(public_directory / response_file, data)
    _write_bytes(cache_path, _json_bytes(record))
    provenance = {"provider": "Open-Meteo", "product": "historical_model", **record,
                  "response_file": response_file, "grid_location": grid}
    return columns, provenance


def build_race(metadata, public_directory, cache_directory, *, fetcher=None, force=False, clock=None):
    sources, errors, columns = {}, {}, {}
    for source in VARIABLES:
        try:
            source_columns, provenance = acquire_source(source, metadata, public_directory, cache_directory,
                                                        fetcher=fetcher, force=force, clock=clock)
            columns.update(source_columns)
            sources[source] = provenance
        except (ValueError, OSError, TypeError) as exc:
            errors[source] = str(exc)[:360]
    times = sorted({t for column in columns.values() for t in column})
    artifact = {
        "schema_version": "environment-1", "race_id": metadata["race_id"],
        "context": "historical_replay_only",
        "requested_location": {"latitude": metadata["latitude"], "longitude": metadata["longitude"]},
        "replay_window": {"start_ms": metadata["window_start_ms"], "end_ms": metadata["window_end_ms"]},
        "units": {"time_ms": "Unix milliseconds UTC", "air_temperature_c": "°C", "wave_height_m": "m",
                  "water_temperature_c": "°C"},
        "hourly": {"time_ms": times, **{f: [columns.get(f, {}).get(t) for t in times] for f in OUTPUT_FIELDS}},
        "sources": sources, "errors": errors,
    }
    _write_bytes(public_directory / (metadata["race_id"] + ".json"), _json_bytes(artifact))
    return artifact


def catalog_metadata(root, race_id=None):
    data_directory = root / "public" / "data"
    catalog = json.loads((data_directory / "manifests.json").read_bytes())
    races = catalog.get("races") or [r for regatta in catalog.get("regattas", []) for r in regatta["races"]]
    seen = set()
    for race in races:
        if race_id and race.get("id") != race_id:
            continue
        path = (data_directory / (race.get("replay_file") or race["file"])).resolve()
        if not path.is_relative_to((data_directory / "replays").resolve()) or path.suffix != ".json":
            raise ValueError("Catalog replay path must remain within public/data/replays")
        metadata = replay_metadata(path)
        if metadata["race_id"] != race["id"] or metadata["race_id"] in seen:
            raise ValueError("Catalog replay ID mismatch or duplicate")
        seen.add(metadata["race_id"])
        yield metadata
    if not seen:
        raise ValueError("No matching replay races in catalog")


def build_archive(root: Path, *, race_id=None, force=False, fetcher=None, clock=None):
    output = root / "public" / "data" / "environment"
    cache = root / ".forecast" / "environment"
    artifacts = [build_race(metadata, output, cache, fetcher=fetcher, force=force, clock=clock)
                 for metadata in catalog_metadata(root, race_id)]
    counts = {field: sum(any(v is not None for v in a["hourly"][field]) for a in artifacts) for field in OUTPUT_FIELDS}
    return {"races": len(artifacts), "races_with_available_field": counts,
            "races_with_source_errors": {a["race_id"]: a["errors"] for a in artifacts if a["errors"]}}


def verify_archive(root: Path, *, race_id=None):
    """Verify every catalog artifact and its original response bytes, offline."""
    output = root / "public" / "data" / "environment"
    counts = dict.fromkeys(OUTPUT_FIELDS, 0)
    response_hashes, races, source_errors = set(), 0, {}
    for metadata in catalog_metadata(root, race_id):
        artifact = json.loads((output / (metadata["race_id"] + ".json")).read_bytes())
        if (artifact.get("schema_version") != "environment-1" or artifact.get("race_id") != metadata["race_id"]
                or artifact.get("context") != "historical_replay_only"
                or artifact.get("requested_location") != {"latitude": metadata["latitude"], "longitude": metadata["longitude"]}
                or artifact.get("replay_window") != {"start_ms": metadata["window_start_ms"], "end_ms": metadata["window_end_ms"]}
                or artifact.get("units") != {"time_ms": "Unix milliseconds UTC", "air_temperature_c": "°C",
                                            "wave_height_m": "m", "water_temperature_c": "°C"}):
            raise ValueError(f"Environment metadata/unit mismatch: {metadata['race_id']}")
        sources, errors = artifact.get("sources"), artifact.get("errors")
        if (not isinstance(sources, dict) or not isinstance(errors, dict)
                or set(sources) & set(errors) or set(sources) | set(errors) != set(VARIABLES)
                or any(not isinstance(reason, str) or not reason for reason in errors.values())):
            raise ValueError(f"Environment source/error contract mismatch: {metadata['race_id']}")
        columns = {}
        for source, provenance in sources.items():
            if (not isinstance(provenance, dict) or provenance.get("provider") != "Open-Meteo"
                    or provenance.get("product") != "historical_model"
                    or provenance.get("request_url") != request_url(source, metadata)
                    or not re.fullmatch(r"[0-9a-f]{64}", provenance.get("response_sha256", ""))
                    or provenance.get("response_file") != "responses/" + provenance["response_sha256"] + ".json"):
                raise ValueError(f"Environment response provenance mismatch: {metadata['race_id']}/{source}")
            _parse_retrieved(provenance.get("retrieved_at"))
            data = (output / provenance["response_file"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != provenance["response_sha256"]:
                raise ValueError(f"Environment response hash mismatch: {metadata['race_id']}/{source}")
            source_columns, grid = parse_response(data, source, metadata)
            if provenance.get("grid_location") != grid:
                raise ValueError(f"Environment grid location mismatch: {metadata['race_id']}/{source}")
            columns.update(source_columns)
            response_hashes.add(provenance["response_sha256"])
        times = sorted({t for values in columns.values() for t in values})
        expected = {"time_ms": times, **{f: [columns.get(f, {}).get(t) for t in times] for f in OUTPUT_FIELDS}}
        if artifact.get("hourly") != expected:
            raise ValueError(f"Environment hourly values differ from original responses: {metadata['race_id']}")
        for field in OUTPUT_FIELDS:
            counts[field] += any(v is not None for v in expected[field])
        races += 1
        if errors:
            source_errors[metadata["race_id"]] = errors
    return {"status": "pass", "races": races, "verified_response_objects": len(response_hashes),
            "races_with_available_field": counts, "races_with_source_errors": source_errors}


def main():
    parser = argparse.ArgumentParser(description="Cache historical replay environmental context from Open-Meteo")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--race")
    parser.add_argument("--force", action="store_true", help="Refetch responses instead of using verified request caches")
    parser.add_argument("--verify", action="store_true", help="Verify exported data and raw response hashes offline")
    args = parser.parse_args()
    if args.verify:
        if args.force:
            parser.error("--verify cannot be combined with --force")
        result = verify_archive(args.root.resolve(), race_id=args.race)
    else:
        result = build_archive(args.root.resolve(), race_id=args.race, force=args.force)
        if (args.root / "public" / "data" / "analysis" / "index.json").is_file():
            from scripts.build_artifact_inventory import build_inventory
            build_inventory(args.root.resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
