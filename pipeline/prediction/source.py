"""Stream raw measurements once; retain 1 Hz last-observed samples, never interpolation.

Samples retain their actual timestamps and source ordinals. Their modeled publication
time is event time + 6000ms, because the archive has no receipt-time clock. Session
and competitor snapshots are retained separately with effective availability.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from pipeline.identity import resolve_identity
from pipeline.run_pipeline import infer_race_metadata
from .contracts import atomic_json, content_hash

BUFFER_MS = 6000
PARSER_VERSION = "raw-causal-2"
FIELDS = ("gnss_position", "speed_over_ground", "course_over_ground", "heading",
          "true_wind_speed", "true_wind_direction")


def _metadata_hash(metadata: dict) -> str:
    return content_hash({key: value for key, value in metadata.items() if key != "metadata_sha256"})


def _seal_metadata(metadata: dict, table_path: Path) -> dict:
    sealed = dict(metadata, derived_table_sha256=digest(table_path))
    sealed["metadata_sha256"] = _metadata_hash(sealed)
    return sealed


def _validate_cache(metadata: dict, table_path: Path, expected: dict | None = None) -> None:
    """Authenticate actual derived bytes, not just their claimed raw input hash."""
    if not metadata.get("derived_table_sha256") or not metadata.get("metadata_sha256"):
        raise ValueError("Unsealed forecasting dataset; rebuild with dataset --force or explicitly seal the freshly generated cache")
    if metadata["metadata_sha256"] != _metadata_hash(metadata):
        raise ValueError("Forecasting dataset metadata content hash mismatch; rebuild the dataset")
    if metadata["derived_table_sha256"] != digest(table_path):
        raise ValueError("Forecasting dataset Parquet content hash mismatch; rebuild the dataset")
    if expected is not None and any(expected.get(key) != metadata[key] for key in ("metadata_sha256", "derived_table_sha256")):
        raise ValueError("Forecasting dataset index/cache content hash mismatch; rebuild or explicitly seal the fresh dataset")


def _index_entry(rid: str, metadata: dict) -> dict:
    return {"race_id": rid, "date": metadata["date"], "source_file": metadata["source_file"],
            "sha256": metadata["sha256"], "bytes": metadata["bytes"],
            "records": metadata["records"], "practice": metadata["practice"],
            "max_disorder_ms": metadata["max_disorder_ms"],
            "derived_table_sha256": metadata["derived_table_sha256"], "metadata_sha256": metadata["metadata_sha256"]}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_source(path: Path) -> tuple[dict, list[dict]]:
    buckets, sessions, events = {}, [], []
    h, maximum, disorder, count = hashlib.sha256(), 0, 0, 0
    tracked = set()
    with path.open("rb", buffering=4*1024*1024) as stream:
        for ordinal, line in enumerate(stream, 1):
            h.update(line)
            count = ordinal
            record = json.loads(line)
            kind = next((k for k in ("session", "competitor", "telemetry") if record.get(k)), None)
            if not kind:
                continue
            value = record[kind]
            t = int(value.get("timestamp", 0))
            if kind == "session":
                tracked.update(c["asset_id"] for c in value.get("competitors", []))
                tracked.update(a["id"] for a in value.get("assets", []) if a.get("type") == "ASSET_TYPE_RACE_MARK")
                tracked.add(value.get("official_wind_asset_id"))
            if kind == "telemetry" and value.get("asset_id") not in tracked:
                continue
            if kind == "telemetry":
                disorder = max(disorder, maximum - t)
                maximum = max(maximum, t)
            if kind != "telemetry":
                value = dict(value, source_ordinal=ordinal, available_at_ms=t+BUFFER_MS)
                (sessions if kind == "session" else events).append(value)
                continue
            aid = value.get("asset_id")
            field = next((f for f in FIELDS if f in value), None)
            if not field:
                continue
            key = (aid, field, t//1000)
            prior = buckets.get(key)
            if prior and (prior["timestamp_ms"], prior["source_ordinal"]) >= (t, ordinal):
                continue
            measurement = value[field]
            row = {"asset_id": aid, "field": field, "timestamp_ms": t,
                   "bucket_closed_at_ms": (t//1000+1)*1000,
                   "available_at_ms": (t//1000+1)*1000+BUFFER_MS, "source_ordinal": ordinal,
                   "value": None, "latitude": None, "longitude": None}
            if field == "gnss_position":
                row.update(latitude=measurement.get("latitude"), longitude=measurement.get("longitude"))
            else:
                row["value"] = measurement.get("value")
            buckets[key] = row
    if not sessions:
        raise ValueError(f"No session metadata: {path.name}")
    sessions.sort(key=lambda x: (int(x["timestamp"]), x["source_ordinal"]))
    events.sort(key=lambda x: (int(x["timestamp"]), x["source_ordinal"]))
    final = sessions[-1]
    assets = {a["id"]: a for a in final["assets"]}
    field = [c["asset_id"] for c in final["competitors"]]
    marks = {g for s in final["race_course"]["sequences"] for g in
             (s["gate"]["port_asset_id"], s["gate"]["starboard_asset_id"])}
    keep = set(field) | marks | {final.get("official_wind_asset_id")}
    rows = sorted((r for r in buckets.values() if r["asset_id"] in keep),
                  key=lambda r: (r["timestamp_ms"], r["source_ordinal"]))
    gun = int(final["race_start"])
    metadata = infer_race_metadata(str(path))
    metadata.update(date=datetime.fromtimestamp(gun/1000, timezone.utc).date().isoformat(),
                    source_file=path.name, sha256=h.hexdigest(), bytes=path.stat().st_size, parser_version=PARSER_VERSION,
                    records=count, max_disorder_ms=disorder,
                    reorder_contract_valid=disorder <= BUFFER_MS,
                    sessions=sessions, competitor_events=events,
                    boat_ids=field, identities={aid: resolve_identity(aid, assets,
                        timestamp_ms=int(final["timestamp"])) for aid in field},
                    gun_ms=gun, window_start_ms=int(final["window_start"]),
                    window_end_ms=int(final["window_end"]),
                    practice=any(x.startswith("pr") for x in path.stem.lower().split()) or "practice" in path.stem.lower(),
                    boat_class="AC40", time_basis="event-time reconstruction with modeled latency")
    return metadata, rows


def source_dataset(root: Path, *, race: str | None = None, force=False) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    cache = root / ".forecast" / "dataset"
    cache.mkdir(parents=True, exist_ok=True)
    entries = []
    raw_candidates = list((root / "Data").glob("*.jsonl"))
    if not raw_candidates and (root / "Data" / "AC38").exists():
        raw_candidates = list((root / "Data" / "AC38").glob("*.jsonl"))
    for path in sorted(raw_candidates):
        rid = infer_race_metadata(str(path))["race_id"]
        if race and race != rid:
            continue
        meta_path, data_path = cache/f"{rid}.json", cache/f"{rid}.parquet"
        stat = path.stat()
        cached = json.loads(meta_path.read_text()) if meta_path.exists() else None
        # Authenticate both source identity and the actual derived bytes.
        # Old unsealed caches are rebuilt by this explicit dataset command;
        # ordinary load_dataset never silently seals/trusts them.
        reusable = False
        if (not force and cached and cached.get("parser_version") == PARSER_VERSION and data_path.exists()
                and cached.get("bytes") == stat.st_size and cached.get("sha256") == digest(path)):
            try:
                _validate_cache(cached, data_path)
                reusable = True
            except ValueError:
                reusable = False
        if reusable:
            metadata = cached
        else:
            metadata, rows = read_source(path)
            pq.write_table(pa.Table.from_pylist(rows), data_path, compression="zstd")
            metadata = _seal_metadata(dict(metadata, cache_seal_method="source_dataset_raw_parse"), data_path)
            atomic_json(meta_path, metadata)
        entries.append(_index_entry(rid, metadata))
    if race and not entries:
        raise ValueError(f"Unknown source race: {race}")
    result = {"schema_version": "prediction-dataset-1", "races": entries}
    if not race:
        atomic_json(cache/"index.json", result)
    elif (cache/"index.json").exists():
        # A single-race rebuild must not leave an existing archive index bound
        # to the previous version of that race's cache.
        prior = json.loads((cache/"index.json").read_text())
        replacements = {entry["race_id"]: entry for entry in entries}
        merged = [replacements.pop(entry["race_id"], entry) for entry in prior["races"]]
        merged.extend(replacements.values())
        atomic_json(cache/"index.json", dict(prior, races=sorted(merged, key=lambda entry: entry["race_id"])))
    return result


def load_dataset(root: Path, rid: str) -> tuple[dict, list[dict]]:
    import pyarrow.parquet as pq
    base = root/".forecast"/"dataset"
    metadata = json.loads((base/f"{rid}.json").read_text())
    expected = None
    if (base/"index.json").exists():
        index = json.loads((base/"index.json").read_text())
        expected = next((entry for entry in index["races"] if entry["race_id"] == rid), None)
        if expected is None:
            raise ValueError("Requested race is not part of the sealed forecasting dataset index")
    _validate_cache(metadata, base/f"{rid}.parquet", expected)
    rows=pq.read_table(base/f"{rid}.parquet").to_pylist()
    # Deterministic availability migration for caches made before closed-bin
    # publication was explicit. Values/ordinals/raw timestamps are unchanged.
    for row in rows:
        row["bucket_closed_at_ms"]=(row["timestamp_ms"]//1000+1)*1000
        row["available_at_ms"]=row["bucket_closed_at_ms"]+BUFFER_MS
    return metadata, rows


def seal_existing_dataset(root: Path) -> dict:
    """Explicit migration of a just-generated, trusted pre-seal conversion.

    This function must never run implicitly on ordinary loads. The caller must
    know the derived files came from the completed conversion in this session.
    All raw hashes and cache structure are checked before any metadata/index is
    rewritten. This avoids a second full JSON parsing pass while preserving an
    auditable distinction from caches generated normally with sealing enabled.
    """
    import pyarrow.parquet as pq
    base = root/".forecast"/"dataset"
    index = json.loads((base/"index.json").read_text())
    raw_files = list((root / "Data").glob("*.jsonl"))
    if not raw_files and (root / "Data" / "AC38").exists():
        raw_files = list((root / "Data" / "AC38").glob("*.jsonl"))
    raw_paths = {infer_race_metadata(str(path))["race_id"]: path for path in raw_files}
    if set(raw_paths) != {entry["race_id"] for entry in index["races"]}:
        raise ValueError("Explicit sealing requires a complete index matching every current raw source")
    staged = []
    for entry in index["races"]:
        rid = entry["race_id"]
        meta_path, table_path = base/f"{rid}.json", base/f"{rid}.parquet"
        metadata = json.loads(meta_path.read_text())
        raw_path = raw_paths[rid]
        if (metadata.get("race_id") != rid or metadata.get("source_file") != raw_path.name
                or metadata.get("sha256") != entry.get("sha256")
                or metadata.get("bytes") != raw_path.stat().st_size
                or metadata.get("sha256") != digest(raw_path)):
            raise ValueError(f"Cannot seal {rid}: current raw source identity does not match the conversion")
        schema = pq.read_schema(table_path)
        if not {"asset_id", "field", "timestamp_ms", "source_ordinal"} <= set(schema.names):
            raise ValueError(f"Cannot seal {rid}: malformed derived table")
        sealed = _seal_metadata(dict(metadata, cache_seal_method="explicit_fresh_conversion_migration_raw_hash_verified"), table_path)
        staged.append((rid, meta_path, sealed))
    entries = []
    for rid, meta_path, sealed in staged:
        atomic_json(meta_path, sealed)
        entries.append(_index_entry(rid, sealed))
    atomic_json(base/"index.json", dict(index, races=entries))
    return {"races": len(entries), "source_bytes_verified": sum(entry["bytes"] for entry in entries),
            "seal_method": "explicit_fresh_conversion_migration_raw_hash_verified"}
