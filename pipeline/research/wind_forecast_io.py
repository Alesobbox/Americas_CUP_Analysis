"""Cache independent raw official-wind measurements for the AC38 benchmark."""

import hashlib
import json
from pathlib import Path

from pipeline.config import OFFICIAL_WIND_ASSET_ID


def _source_reference(detail):
    tactical = detail.get("tactical_insights", {})
    provenance = tactical.get("source_provenance", {})
    relative_path = provenance.get("source_file")
    if not relative_path:
        raise ValueError(f"Official-wind source path unavailable for {detail['race']['id']}")
    return relative_path


def _read_directions(source, root):
    asset = OFFICIAL_WIND_ASSET_ID.encode("ascii")
    hasher, samples = hashlib.sha256(), []
    with source.open("rb", buffering=1024 * 1024) as stream:
        for line in stream:
            hasher.update(line)
            if asset not in line or b'"true_wind_direction"' not in line:
                continue
            telemetry = json.loads(line).get("telemetry", {})
            if telemetry.get("asset_id") != OFFICIAL_WIND_ASSET_ID:
                continue
            if "true_wind_direction" in telemetry:
                samples.append(
                    {
                        "timestamp_ms": int(telemetry["timestamp"]),
                        "twd_deg": float(telemetry["true_wind_direction"]["value"]),
                    }
                )
    provenance = {
        "source_file": source.relative_to(root).as_posix(),
        "source_sha256": hasher.hexdigest(),
        "source_size_bytes": source.stat().st_size,
        "official_wind_asset_id": OFFICIAL_WIND_ASSET_ID,
    }
    return samples, provenance


def _cache_entry(source, root, cached):
    stat = source.stat()
    identity = {"source_size_bytes": stat.st_size, "source_mtime_ns": stat.st_mtime_ns}
    if cached and cached.get("identity") == identity:
        return cached
    samples, provenance = _read_directions(source, root)
    return {"identity": identity, "samples": samples, "source_provenance": provenance}


def load_wind_records(details_by_race, root):
    """Read or reuse sparse source data; cache validity uses source size and mtime."""
    root = Path(root).resolve()
    cache_path = root / ".cache" / "ac38_research" / "official_wind.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    records, refreshed = {}, {}
    for race_id, detail in sorted(details_by_race.items()):
        source = (root / _source_reference(detail)).resolve()
        if not source.is_relative_to(root / "Data" / "AC38"):
            raise ValueError(f"Official-wind source is outside the AC38 archive: {source}")
        entry = _cache_entry(source, root, cache.get(race_id))
        refreshed[race_id] = entry
        race = detail["race"]
        records[race_id] = {
            "id": race_id,
            "date": race["date"],
            "gun_time_ms": race["gun_time_ms"],
            "window_end_ms": race.get("window_end_ms"),
            "samples": entry["samples"],
            "source_provenance": entry["source_provenance"],
        }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(refreshed, separators=(",", ":"), allow_nan=False), encoding="utf-8"
    )
    temporary.replace(cache_path)
    return records
