"""Deduplicated, content-addressed, concurrent subset acquisition and offline cache."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable

from .adapters_grid import SubsetTooLargeError
from .contracts import resolve_env_cache_dir
from .providers import expand_bbox, fetch_provider_subset, split_request_if_oversize
from .registry import (
    MAX_CONCURRENT_REQUESTS,
    MAX_RETRIES,
    PROVIDER_SPECS,
    ProviderSpec,
    REQUEST_TIMEOUT_SECONDS,
    SPLIT_THRESHOLD_BYTES,
    VENUE_POLICIES,
)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: Any) -> None:
    text = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write_bytes(path, text)


def _default_clock() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request_key(provider_id: str, req: dict[str, Any]) -> str:
    payload = {
        "provider_id": provider_id,
        "variables": list(req["variables"]),
        "bbox": req["bbox"],
        "start_ms": int(req["start_ms"]),
        "end_ms": int(req["end_ms"]),
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _union_bbox(bboxes: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "lat_min": min(float(b["lat_min"]) for b in bboxes),
        "lat_max": max(float(b["lat_max"]) for b in bboxes),
        "lon_min": min(float(b["lon_min"]) for b in bboxes),
        "lon_max": max(float(b["lon_max"]) for b in bboxes),
    }


def plan_acquisition_tasks(inventory_doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Group ready sessions into deduplicated venue/day/variable-group requests."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for src in inventory_doc.get("sources", []):
        if src.get("acquisition_status") != "ready":
            continue
        vid = str(src.get("venue_id") or "")
        date_str = str(src.get("utc_date") or "")
        if vid not in VENUE_POLICIES or not date_str or not src.get("bbox"):
            continue
        grouped.setdefault((vid, date_str), []).append(src)

    tasks: list[dict[str, Any]] = []
    for (vid, date_str), members in sorted(grouped.items()):
        policy = VENUE_POLICIES[vid]
        bbox = _union_bbox([m["bbox"] for m in members])
        t_start = min(int(m["window_start_ms"]) for m in members)
        t_end = max(int(m["window_end_ms"]) for m in members)
        race_ids = sorted({str(m["race_id"]) for m in members})
        for group, chain in policy.providers.items():
            tasks.append({
                "task_id": f"{vid}__{date_str}__{group}",
                "venue_id": vid,
                "utc_date": date_str,
                "group": group,
                "provider_chain": list(chain),
                "union_bbox": bbox,
                "start_ms": t_start,
                "end_ms": t_end,
                "covered_races": race_ids,
            })
    return tasks


def _build_group_request(spec: ProviderSpec, task: dict[str, Any]) -> dict[str, Any]:
    pad_ms = max(3_600_000, int(spec.native_step_s) * 1000)
    if spec.temporal_support == "daily_mean":
        day_start = int(datetime.fromisoformat(f"{task['utc_date']}T00:00:00+00:00").timestamp() * 1000)
        start_ms = day_start
        end_ms = day_start + 86_399_000
    else:
        start_ms = int(task["start_ms"]) - pad_ms
        end_ms = int(task["end_ms"]) + pad_ms
    return {
        "variables": list(spec.variables),
        "bbox": expand_bbox(task["union_bbox"], spec.approx_spacing_deg),
        "start_ms": start_ms,
        "end_ms": end_ms,
    }


def _fetch_chunk_with_retries(
    spec: ProviderSpec,
    chunk_req: dict[str, Any],
    *,
    max_retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[..., Any] | None = None,
    copernicus_client: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_provider_subset(
                spec,
                chunk_req,
                timeout=timeout,
                http_get=http_get,
                copernicus_client=copernicus_client,
            )
        except SubsetTooLargeError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep_fn(0.5 * attempt)
    raise RuntimeError(f"{spec.provider_id} failed after {max_retries} retries: {last_exc}")


def _acquire_chunk_tree(
    spec: ProviderSpec,
    req: dict[str, Any],
    cache_root: Path,
    *,
    force: bool = False,
    max_bytes: int = SPLIT_THRESHOLD_BYTES,
    http_get: Callable[..., Any] | None = None,
    copernicus_client: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], str] = _default_clock,
) -> list[dict[str, Any]]:
    chunks = split_request_if_oversize(spec, req, max_bytes=max_bytes)
    results: list[dict[str, Any]] = []
    for chunk in chunks:
        rkey = _request_key(spec.provider_id, chunk)
        req_file = cache_root / "requests" / f"{rkey}.json"
        if not force and req_file.is_file():
            rec = json.loads(req_file.read_text(encoding="utf-8"))
            obj_p = cache_root / rec["object_relpath"]
            if obj_p.is_file():
                actual_sha = hashlib.sha256(obj_p.read_bytes()).hexdigest()
                if actual_sha != rec["raw_subset_sha256"]:
                    raise ValueError(f"Cached subset hash mismatch for {rec['object_relpath']}")
                results.append(rec)
                continue
        try:
            fetched = _fetch_chunk_with_retries(
                spec,
                chunk,
                http_get=http_get,
                copernicus_client=copernicus_client,
                sleep_fn=sleep_fn,
            )
        except SubsetTooLargeError:
            sub_chunks = split_request_if_oversize(spec, chunk, max_bytes=max_bytes, est_bytes=max_bytes * 2)
            if len(sub_chunks) <= 1:
                raise
            for sub in sub_chunks:
                results.extend(
                    _acquire_chunk_tree(
                        spec,
                        sub,
                        cache_root,
                        force=force,
                        max_bytes=max_bytes,
                        http_get=http_get,
                        copernicus_client=copernicus_client,
                        sleep_fn=sleep_fn,
                        clock=clock,
                    )
                )
            continue
        sha = fetched["raw_subset_sha256"]
        ext = fetched["format"]
        obj_rel = f"objects/{sha[:2]}/{sha}.{ext}"
        _atomic_write_bytes(cache_root / obj_rel, fetched["raw_bytes"])
        rec = {
            "request_key": rkey,
            "provider_id": spec.provider_id,
            "dataset_id": spec.dataset_id,
            "dataset_version": spec.dataset_version,
            "request_spec": chunk,
            "object_relpath": obj_rel,
            "format": ext,
            "retrieval_time_utc": clock(),
            "raw_subset_sha256": sha,
            "metadata_sha256": fetched["metadata_sha256"],
            "uncompressed_bytes": fetched["uncompressed_bytes"],
            "depth_m": fetched["depth_m"],
            "temperature_convention": spec.temperature_convention,
            "returned_coordinates": fetched["returned_coordinates"],
            "spatial_support": fetched["spatial_support"],
            "product_classification": spec.product_classification,
            "initialization_time_utc": fetched["initialization_time_utc"],
            "availability_time_utc": fetched["availability_time_utc"],
        }
        _atomic_write_json(req_file, rec)
        results.append(rec)
    return results


def _run_one_task(
    task: dict[str, Any],
    cache_root: Path,
    *,
    force: bool = False,
    http_get: Callable[..., Any] | None = None,
    copernicus_client: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], str] = _default_clock,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    for idx, pid in enumerate(task["provider_chain"]):
        spec = PROVIDER_SPECS[pid]
        req = _build_group_request(spec, task)
        try:
            chunks = _acquire_chunk_tree(
                spec,
                req,
                cache_root,
                force=force,
                http_get=http_get,
                copernicus_client=copernicus_client,
                sleep_fn=sleep_fn,
                clock=clock,
            )
            fallback_used = idx > 0
            return {
                **task,
                "status": "fallback" if fallback_used else "available",
                "selected_provider_id": pid,
                "fallback_used": fallback_used,
                "fallback_reason": "; ".join(f"{e['provider_id']}: {e['error']}" for e in errors) if errors else None,
                "chunk_request_keys": [c["request_key"] for c in chunks],
                "chunks": chunks,
                "errors": errors,
            }
        except Exception as exc:
            errors.append({"provider_id": pid, "error": str(exc)})
    return {
        **task,
        "status": "unavailable",
        "selected_provider_id": None,
        "fallback_used": len(errors) > 1,
        "fallback_reason": "; ".join(f"{e['provider_id']}: {e['error']}" for e in errors),
        "chunk_request_keys": [],
        "chunks": [],
        "errors": errors,
    }


def acquire_all_tasks(
    root: Path | str,
    inventory_doc: dict[str, Any],
    *,
    force: bool = False,
    max_workers: int = MAX_CONCURRENT_REQUESTS,
    http_get: Callable[..., Any] | None = None,
    copernicus_client: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], str] = _default_clock,
) -> dict[str, Any]:
    """Execute deduplicated variable-group acquisition with bounded concurrency."""
    root_path = Path(root)
    cache_root = resolve_env_cache_dir(root_path) / "cache"
    tasks = plan_acquisition_tasks(inventory_doc)
    workers = max(1, min(int(max_workers), MAX_CONCURRENT_REQUESTS))
    outcomes: list[dict[str, Any]] = []
    if workers == 1:
        for task in tasks:
            outcomes.append(
                _run_one_task(
                    task,
                    cache_root,
                    force=force,
                    http_get=http_get,
                    copernicus_client=copernicus_client,
                    sleep_fn=sleep_fn,
                    clock=clock,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(
                    _run_one_task,
                    task,
                    cache_root,
                    force=force,
                    http_get=http_get,
                    copernicus_client=copernicus_client,
                    sleep_fn=sleep_fn,
                    clock=clock,
                )
                for task in tasks
            ]
            for fut in as_completed(futs):
                outcomes.append(fut.result())

    outcomes.sort(key=lambda t: t["task_id"])
    manifest = {
        "schema_version": "environment-cache-manifest-1",
        "generated_at_utc": clock(),
        "total_tasks": len(outcomes),
        "available_tasks": sum(1 for o in outcomes if o["status"] == "available"),
        "fallback_tasks": sum(1 for o in outcomes if o["status"] == "fallback"),
        "unavailable_tasks": sum(1 for o in outcomes if o["status"] == "unavailable"),
        "tasks": outcomes,
    }
    _atomic_write_json(cache_root / "manifest.json", manifest)
    return manifest


def verify_cache_offline(root: Path | str) -> dict[str, Any]:
    """Verify every cached subset hash offline without network access."""
    root_path = Path(root)
    cache_root = resolve_env_cache_dir(root_path) / "cache"
    manifest_path = cache_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Cache manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified_objects: set[str] = set()
    for task in manifest.get("tasks", []):
        for chunk in task.get("chunks", []):
            obj_p = cache_root / chunk["object_relpath"]
            if not obj_p.is_file():
                raise ValueError(f"Missing cached object: {chunk['object_relpath']}")
            actual = hashlib.sha256(obj_p.read_bytes()).hexdigest()
            if actual != chunk["raw_subset_sha256"]:
                raise ValueError(f"Hash mismatch for cached object {chunk['object_relpath']}")
            verified_objects.add(chunk["object_relpath"])
    return {
        "status": "pass",
        "verified_objects": len(verified_objects),
        "total_tasks": manifest.get("total_tasks", 0),
        "unavailable_tasks": manifest.get("unavailable_tasks", 0),
    }
