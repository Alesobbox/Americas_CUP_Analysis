"""Native partitioned Parquet dataset writer and bounded sorting engine for AC75.

Enforces:
- Bounded memory batching (50,000 rows max in memory).
- Deterministic sorting of out-of-order streams.
- Schema conformity: ac75-native-1.
- Exact content-addressed metadata sealing.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from .source import (
    DEFAULT_AVAILABILITY_BASIS,
    DEFAULT_CAUSAL_LATENCY_MS,
    iter_source_packets,
    extract_session_header,
    normalize_telemetry_packet,
    NormalizationErrorReport,
    _parse_session_dict,
    _parse_competitor_dict,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
NATIVE_DIR = FORECAST_DIR / "native"
PARSER_VERSION = "ac75-native-parser-2"

NATIVE_ARROW_SCHEMA = pa.schema([
    pa.field("line_ordinal", pa.int64()),
    pa.field("offset", pa.int64()),
    pa.field("timestamp_ms", pa.int64()),
    pa.field("available_at_ms", pa.int64()),
    pa.field("availability_basis", pa.string()),
    pa.field("correlation_id", pa.string()),
    pa.field("sequence_id", pa.int64()),
    pa.field("asset_id", pa.string()),
    pa.field("team_alias", pa.string()),
    pa.field("channel", pa.string()),
    pa.field("source", pa.string()),
    pa.field("lat_deg", pa.float64()),
    pa.field("lon_deg", pa.float64()),
    pa.field("alt_m", pa.float64()),
    pa.field("heading_deg", pa.float64()),
    pa.field("sog_mps", pa.float64()),
    pa.field("cog_deg", pa.float64()),
    pa.field("tws_mps", pa.float64()),
    pa.field("twd_deg", pa.float64()),
])


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        while chunk := fp.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def rows_to_record_batch(rows: list[dict[str, Any]]) -> pa.RecordBatch:
    """Convert a list of normalized row dictionaries to a PyArrow RecordBatch."""
    arrays = [
        pa.array([r.get("line_ordinal") for r in rows], type=pa.int64()),
        pa.array([r.get("offset") for r in rows], type=pa.int64()),
        pa.array([r.get("timestamp_ms") for r in rows], type=pa.int64()),
        pa.array([r.get("available_at_ms", (r.get("timestamp_ms") or 0) + DEFAULT_CAUSAL_LATENCY_MS) for r in rows], type=pa.int64()),
        pa.array([r.get("availability_basis", DEFAULT_AVAILABILITY_BASIS) for r in rows], type=pa.string()),
        pa.array([r.get("correlation_id", "") for r in rows], type=pa.string()),
        pa.array([r.get("sequence_id") for r in rows], type=pa.int64()),
        pa.array([r.get("asset_id") for r in rows], type=pa.string()),
        pa.array([r.get("team_alias") for r in rows], type=pa.string()),
        pa.array([r.get("channel") for r in rows], type=pa.string()),
        pa.array([r.get("source") for r in rows], type=pa.string()),
        pa.array([r.get("lat_deg") for r in rows], type=pa.float64()),
        pa.array([r.get("lon_deg") for r in rows], type=pa.float64()),
        pa.array([r.get("alt_m") for r in rows], type=pa.float64()),
        pa.array([r.get("heading_deg") for r in rows], type=pa.float64()),
        pa.array([r.get("sog_mps") for r in rows], type=pa.float64()),
        pa.array([r.get("cog_deg") for r in rows], type=pa.float64()),
        pa.array([r.get("tws_mps") for r in rows], type=pa.float64()),
        pa.array([r.get("twd_deg") for r in rows], type=pa.float64()),
    ]
    return pa.RecordBatch.from_arrays(arrays, schema=NATIVE_ARROW_SCHEMA)


def _iter_parquet_chunk(chunk_path: Path, *, read_batch_size: int = 2048) -> Iterator[dict[str, Any]]:
    """Iterate row dictionaries from a Parquet chunk file using bounded small batches."""
    pf = pq.ParquetFile(str(chunk_path))
    for batch in pf.iter_batches(batch_size=read_batch_size):
        batch_dict = batch.to_pydict()
        num_rows = batch.num_rows
        keys = list(batch_dict.keys())
        for i in range(num_rows):
            yield {k: batch_dict[k][i] for k in keys}


def _merge_chunk_group(
    group_paths: list[Path],
    dest_parquet: Path,
    *,
    write_batch_size: int = 10000,
    read_batch_size: int = 2048,
) -> None:
    """Merge a bounded group of sorted Parquet chunks into a single sorted Parquet file."""
    with pq.ParquetWriter(str(dest_parquet), NATIVE_ARROW_SCHEMA, compression="snappy") as writer:
        chunk_generators = [_iter_parquet_chunk(cp, read_batch_size=read_batch_size) for cp in group_paths]
        merged_stream = heapq.merge(
            *chunk_generators,
            key=lambda r: (r["timestamp_ms"], r["line_ordinal"])
        )
        merge_buffer: list[dict[str, Any]] = []
        for row in merged_stream:
            merge_buffer.append(row)
            if len(merge_buffer) >= write_batch_size:
                writer.write_batch(rows_to_record_batch(merge_buffer))
                merge_buffer.clear()
        if merge_buffer:
            writer.write_batch(rows_to_record_batch(merge_buffer))
            merge_buffer.clear()


def _bounded_multi_pass_merge(
    chunk_paths: list[Path],
    dest_parquet: Path,
    chunk_dir: Path,
    *,
    max_fan_in: int = 16,
    write_batch_size: int = 10000,
    read_batch_size: int = 2048,
) -> None:
    """Perform multi-pass external merge sort with bounded fan-in and small read buffers."""
    active_paths = list(chunk_paths)
    pass_idx = 0

    while len(active_paths) > max_fan_in:
        next_paths: list[Path] = []
        for g_idx in range(0, len(active_paths), max_fan_in):
            group = active_paths[g_idx : g_idx + max_fan_in]
            if len(group) == 1:
                next_paths.append(group[0])
                continue
            merged_path = chunk_dir / f"pass_{pass_idx:02d}_group_{g_idx // max_fan_in:04d}.parquet"
            _merge_chunk_group(
                group,
                merged_path,
                write_batch_size=write_batch_size,
                read_batch_size=read_batch_size,
            )
            for p in group:
                p.unlink(missing_ok=True)
            next_paths.append(merged_path)
        active_paths = next_paths
        pass_idx += 1

    temp_parquet = dest_parquet.with_suffix(".tmp.parquet")
    _merge_chunk_group(
        active_paths,
        temp_parquet,
        write_batch_size=write_batch_size,
        read_batch_size=read_batch_size,
    )
    if dest_parquet.exists():
        dest_parquet.unlink()
    os.replace(temp_parquet, dest_parquet)


def is_partition_cache_valid(
    out_parquet: Path,
    meta_json: Path,
    *,
    expected_source_bytes: int,
    expected_source_sha256: str,
    expected_parser_version: str = PARSER_VERSION,
) -> tuple[bool, dict[str, Any]]:
    """Verify whether an existing normalized Parquet partition and sidecar JSON are valid and fresh."""
    if not out_parquet.exists() or not meta_json.exists():
        return False, {}
    try:
        cached_meta = json.loads(meta_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, {}

    if cached_meta.get("source_bytes") != expected_source_bytes or cached_meta.get("source_sha256") != expected_source_sha256:
        return False, {}
    if cached_meta.get("parser_version") != expected_parser_version:
        return False, {}
    recorded_pq_hash = cached_meta.get("parquet_sha256")
    if not recorded_pq_hash or _sha256_file(out_parquet) != recorded_pq_hash:
        return False, {}
    return True, cached_meta


def normalize_and_write_partition(
    raw_path: Path | str,
    output_parquet_path: Path | str,
    *,
    max_lines: int | None = None,
    batch_size: int = 50000,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Normalize a JSONL source file into a bounded, globally sorted native Parquet partition."""
    source_file = Path(raw_path)
    dest_path = Path(output_parquet_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = dest_path.with_suffix(".json")

    t0 = time.perf_counter()
    header = extract_session_header(source_file)
    error_report = NormalizationErrorReport()
    src_digest = source_sha256 if source_sha256 is not None else _sha256_file(source_file)

    buffer: list[dict[str, Any]] = []
    total_rows = 0
    channel_counts: dict[str, int] = {}
    t_min_ms: int | None = None
    t_max_ms: int | None = None

    chunk_paths: list[Path] = []
    chunk_dir = Path(tempfile.mkdtemp(prefix="ac75_chunks_"))

    try:
        for raw_packet in iter_source_packets(source_file, max_lines=max_lines, error_report=error_report):
            if raw_packet.packet_type == "session":
                _parse_session_dict(raw_packet.data, header, line_ordinal=raw_packet.line_ordinal)
                continue
            elif raw_packet.packet_type == "competitor":
                _parse_competitor_dict(raw_packet.data, header, line_ordinal=raw_packet.line_ordinal)
                continue

            for norm_row in normalize_telemetry_packet(raw_packet, header):
                buffer.append(norm_row)
                ch = norm_row["channel"]
                channel_counts[ch] = channel_counts.get(ch, 0) + 1
                ts = norm_row["timestamp_ms"]
                if t_min_ms is None or ts < t_min_ms:
                    t_min_ms = ts
                if t_max_ms is None or ts > t_max_ms:
                    t_max_ms = ts

                if len(buffer) >= batch_size:
                    buffer.sort(key=lambda r: (r["timestamp_ms"], r["line_ordinal"]))
                    chunk_path = chunk_dir / f"chunk_{len(chunk_paths):05d}.parquet"
                    chunk_batch = rows_to_record_batch(buffer)
                    with pq.ParquetWriter(str(chunk_path), NATIVE_ARROW_SCHEMA, compression="snappy") as cw:
                        cw.write_batch(chunk_batch)
                    chunk_paths.append(chunk_path)
                    total_rows += len(buffer)
                    buffer.clear()

        # If no chunks were spilled, entire stream fits in memory
        if not chunk_paths:
            buffer.sort(key=lambda r: (r["timestamp_ms"], r["line_ordinal"]))
            total_rows = len(buffer)
            temp_parquet = dest_path.with_suffix(".tmp.parquet")
            with pq.ParquetWriter(str(temp_parquet), NATIVE_ARROW_SCHEMA, compression="snappy") as writer:
                if buffer:
                    writer.write_batch(rows_to_record_batch(buffer))
            if dest_path.exists():
                dest_path.unlink()
            os.replace(temp_parquet, dest_path)
        else:
            # Flush final buffer as the last chunk
            if buffer:
                buffer.sort(key=lambda r: (r["timestamp_ms"], r["line_ordinal"]))
                chunk_path = chunk_dir / f"chunk_{len(chunk_paths):05d}.parquet"
                chunk_batch = rows_to_record_batch(buffer)
                with pq.ParquetWriter(str(chunk_path), NATIVE_ARROW_SCHEMA, compression="snappy") as cw:
                    cw.write_batch(chunk_batch)
                chunk_paths.append(chunk_path)
                total_rows += len(buffer)
                buffer.clear()

            # Bounded multi-pass external merge sort across all spilled chunks
            _bounded_multi_pass_merge(
                chunk_paths,
                dest_path,
                chunk_dir,
                max_fan_in=16,
                write_batch_size=min(batch_size, 10000),
                read_batch_size=2048,
            )
    finally:
        shutil.rmtree(chunk_dir, ignore_errors=True)

    elapsed = time.perf_counter() - t0
    parquet_digest = _sha256_file(dest_path)

    metadata = {
        "schema_version": "ac75-native-1",
        "parser_version": PARSER_VERSION,
        "source_file": source_file.name,
        "source_bytes": source_file.stat().st_size,
        "source_sha256": src_digest,
        "availability_basis": DEFAULT_AVAILABILITY_BASIS,
        "causal_latency_ms": DEFAULT_CAUSAL_LATENCY_MS,
        "total_rows": total_rows,
        "t_min_ms": t_min_ms,
        "t_max_ms": t_max_ms,
        "channel_counts": channel_counts,
        "session_id": header.get("session_id"),
        "session_name": header.get("session_name"),
        "race_start_ms": header.get("race_start_ms"),
        "official_wind_asset_id": header.get("official_wind_asset_id"),
        "race_course": header.get("race_course", {}),
        "competitor_map": header.get("competitor_map"),
        "marks": header.get("marks", {}),
        "mark_count": len(header.get("marks", {})),
        "session_revisions": header.get("session_revisions", []),
        "competitor_summaries": header.get("competitor_summaries", {}),
        "malformed_lines_count": error_report.malformed_lines,
        "malformed_examples": error_report.bounded_examples,
        "parquet_sha256": parquet_digest,
        "elapsed_s": round(elapsed, 4),
    }

    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "status": "complete",
        "parquet_path": dest_path.as_posix(),
        "metadata_path": meta_path.as_posix(),
        "total_rows": total_rows,
        "parquet_sha256": parquet_digest,
        "source_sha256": src_digest,
        "elapsed_s": elapsed,
        "channel_counts": channel_counts,
    }


def build_native_dataset(dataset_id: str = "ac75_native_v1", max_files: int | None = None) -> dict[str, Any]:
    """Normalize all eligible AC75 JSONL sources into the native partitioned dataset."""
    manifest_files = list((FORECAST_DIR / "sources").glob("*/manifest.json"))
    if not manifest_files:
        raise FileNotFoundError("Manifest file not found. Run T02 first.")

    manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))
    eligible_sources = [
        s for s in manifest["sources"]
        if s["boat_class"] == "AC75" and s["format"] == "jsonl" and s.get("status", "").startswith("included")
    ]
    if max_files is not None:
        eligible_sources = eligible_sources[:max_files]

    target_dir = NATIVE_DIR / dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    partitions: list[dict[str, Any]] = []
    total_dataset_rows = 0
    total_source_bytes = 0

    print(f"Normalizing {len(eligible_sources)} eligible AC75 sources into {target_dir}...")
    for idx, s in enumerate(eligible_sources):
        src_path = ROOT / s["relative_path"]
        safe_name = re.sub(r"[^a-zA-Z0-9_\.]+", "_", s["filename"]).replace(".jsonl", ".parquet")
        partition_filename = f"part_{idx:04d}_{safe_name}"
        out_parquet = target_dir / partition_filename

        # Verify cache against source_bytes, source_sha256, parser_version, and on-disk parquet_sha256
        meta_json = out_parquet.with_suffix(".json")
        cache_ok, cached_meta = is_partition_cache_valid(
            out_parquet,
            meta_json,
            expected_source_bytes=int(s["bytes"]),
            expected_source_sha256=str(s["sha256"]),
        )
        if cache_ok:
            total_dataset_rows += cached_meta["total_rows"]
            total_source_bytes += s["bytes"]
            partitions.append({
                "partition_index": idx,
                "source_file": s["filename"],
                "relative_path": s["relative_path"],
                "source_sha256": s["sha256"],
                "parquet_file": partition_filename,
                "rows": cached_meta["total_rows"],
                "sha256": cached_meta["parquet_sha256"],
                "channels": cached_meta["channel_counts"],
            })
            continue

        res = normalize_and_write_partition(src_path, out_parquet, source_sha256=str(s["sha256"]))
        total_dataset_rows += res["total_rows"]
        total_source_bytes += s["bytes"]

        partitions.append({
            "partition_index": idx,
            "source_file": s["filename"],
            "relative_path": s["relative_path"],
            "source_sha256": s["sha256"],
            "parquet_file": partition_filename,
            "rows": res["total_rows"],
            "sha256": res["parquet_sha256"],
            "channels": res["channel_counts"],
        })
        if (idx + 1) % 5 == 0 or (idx + 1) == len(eligible_sources):
            print(f"  Processed {idx + 1}/{len(eligible_sources)} files ({total_dataset_rows} rows)...")

    # Dataset Manifest
    dataset_manifest = {
        "dataset_id": dataset_id,
        "schema_version": "ac75-native-1",
        "parser_version": PARSER_VERSION,
        "availability_basis": DEFAULT_AVAILABILITY_BASIS,
        "causal_latency_ms": DEFAULT_CAUSAL_LATENCY_MS,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_partitions": len(partitions),
        "total_rows": total_dataset_rows,
        "total_source_bytes": total_source_bytes,
        "partitions": partitions,
    }
    manifest_path = target_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(dataset_manifest, indent=2), encoding="utf-8")
    print(f"Dataset complete: {manifest_path} ({total_dataset_rows} rows across {len(partitions)} partitions)")

    return {
        "dataset_id": dataset_id,
        "dataset_dir": target_dir.relative_to(ROOT).as_posix(),
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "total_partitions": len(partitions),
        "total_rows": total_dataset_rows,
    }


if __name__ == "__main__":
    build_native_dataset()
