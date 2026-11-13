"""All-regatta environment inventory reconciling raw files, ledgers, and result records."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq

from .registry import resolve_venue_policy
from .stream_ac40_2023 import extract_ac40_2023_metadata


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ms_to_iso_utc(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_bbox_from_coords(lats: list[float], lons: list[float]) -> dict[str, Any] | None:
    if not lats or not lons:
        return None
    lat_min, lat_max = float(min(lats)), float(max(lats))
    lon_min, lon_max = float(min(lons)), float(max(lons))
    return {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
        "center_lat": 0.5 * (lat_min + lat_max),
        "center_lon": 0.5 * (lon_min + lon_max),
    }


def _ac38_bbox_and_marks(root: Path, race_id: str, pq_path: Path) -> dict[str, Any] | None:
    lats: list[float] = []
    lons: list[float] = []
    if pq_path.is_file():
        tbl = pq.read_table(pq_path, columns=["field", "latitude", "longitude"])
        mask = pc.equal(tbl["field"], "gnss_position")
        sub = tbl.filter(mask)
        if sub.num_rows > 0:
            lats.extend([float(v) for v in sub["latitude"].to_pylist() if v is not None])
            lons.extend([float(v) for v in sub["longitude"].to_pylist() if v is not None])
    replay_path = root / "public" / "data" / "replays" / f"{race_id}.json"
    if replay_path.is_file():
        raw_head = replay_path.read_bytes()[:1024 * 1024].decode("utf-8", errors="ignore")
        marker = '"telemetry"'
        idx = raw_head.find(marker)
        prefix = raw_head[:idx] + '"telemetry": {}}' if idx != -1 else raw_head
        try:
            rep = json.loads(prefix)
            course = rep.get("course")
            if isinstance(course, dict):
                origin = course.get("origin")
                if isinstance(origin, dict) and origin.get("lat") is not None and origin.get("lon") is not None:
                    lats.append(float(origin["lat"]))
                    lons.append(float(origin["lon"]))
                marks = course.get("marks")
                if isinstance(marks, dict):
                    for mk in marks.values():
                        if isinstance(mk, dict) and mk.get("lat") is not None and mk.get("lon") is not None:
                            lats.append(float(mk["lat"]))
                            lons.append(float(mk["lon"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return _extract_bbox_from_coords(lats, lons)


def _ac75_native_bbox(pq_path: Path, meta: dict[str, Any]) -> dict[str, Any] | None:
    lats: list[float] = []
    lons: list[float] = []
    marks = meta.get("marks")
    if isinstance(marks, dict):
        for mk in marks.values():
            if isinstance(mk, dict) and mk.get("lat") is not None and mk.get("lon") is not None:
                lats.append(float(mk["lat"]))
                lons.append(float(mk["lon"]))
    if pq_path.is_file():
        tbl = pq.read_table(pq_path, columns=["lat_deg", "lon_deg"])
        lat_min_s = pc.min(tbl["lat_deg"]).as_py()
        lat_max_s = pc.max(tbl["lat_deg"]).as_py()
        lon_min_s = pc.min(tbl["lon_deg"]).as_py()
        lon_max_s = pc.max(tbl["lon_deg"]).as_py()
        if all(v is not None for v in (lat_min_s, lat_max_s, lon_min_s, lon_max_s)):
            lats.extend([float(lat_min_s), float(lat_max_s)])
            lons.extend([float(lon_min_s), float(lon_max_s)])
    return _extract_bbox_from_coords(lats, lons)


def _load_ac38_lookups(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int], set[str]]:
    ds_dir = root / ".forecast" / "dataset"
    by_source: dict[str, dict[str, Any]] = {}
    if (ds_dir / "index.json").is_file():
        idx = _read_json(ds_dir / "index.json")
        for row in idx.get("races", []):
            meta_p = ds_dir / f"{row['race_id']}.json"
            if meta_p.is_file():
                meta = _read_json(meta_p)
                by_source[meta["source_file"]] = meta
    sched_counts: dict[str, int] = Counter()
    sched_p = root / ".forecast" / "scheduled_entry_ledger.json"
    if sched_p.is_file():
        for entry in _read_json(sched_p):
            rid = entry.get("race_id")
            if rid:
                sched_counts[str(rid)] += 1
    public_ids: set[str] = set()
    man_p = root / "public" / "data" / "manifests.json"
    if man_p.is_file():
        man = _read_json(man_p)
        for reg in man.get("regattas", []):
            for race in reg.get("races", []):
                if race.get("id"):
                    public_ids.add(str(race["id"]))
    return by_source, dict(sched_counts), public_ids


def _reconcile_ac38_file(
    root: Path,
    file_path: Path,
    ds_by_source: dict[str, dict[str, Any]],
    sched_counts: dict[str, int],
    public_ids: set[str],
) -> dict[str, Any]:
    rel = file_path.relative_to(root).as_posix()
    meta = ds_by_source.get(file_path.name)
    if meta is None:
        return {
            "source_file": file_path.name,
            "relative_path": rel,
            "source_bytes": file_path.stat().st_size,
            "cycle": "ac38",
            "boat_class": "AC40",
            "acquisition_status": "excluded_unmatched_ac38",
            "training_eligibility": "excluded_unmatched",
        }
    rid = str(meta["race_id"])
    pq_path = root / ".forecast" / "dataset" / f"{rid}.parquet"
    bbox = _ac38_bbox_and_marks(root, rid, pq_path)
    ws_ms = int(meta["window_start_ms"])
    we_ms = int(meta["window_end_ms"])
    policy = resolve_venue_policy(bbox["center_lat"], bbox["center_lon"]) if bbox else None
    is_practice = bool(meta.get("practice", False))
    sess_list = meta.get("sessions") or []
    sess_id = str(sess_list[-1]["session_id"]) if sess_list and sess_list[-1].get("session_id") else rid
    boat_races = sched_counts.get(rid) or len(meta.get("boat_ids") or [])
    return {
        "source_file": file_path.name,
        "relative_path": rel,
        "source_bytes": int(meta.get("bytes") or file_path.stat().st_size),
        "source_sha256": meta.get("sha256"),
        "cycle": "ac38",
        "boat_class": "AC40",
        "domain": "practice" if is_practice else "competitive",
        "stage": "ac38_practice" if is_practice else "ac38_prelim_fleet_match",
        "session_id": sess_id,
        "attempt_id": rid,
        "family_id": rid,
        "race_id": rid,
        "in_public_replay_catalog": rid in public_ids,
        "boat_races": int(boat_races),
        "venue_id": policy.venue_id if policy else "unknown",
        "utc_date": meta.get("date"),
        "window_start_ms": ws_ms,
        "window_end_ms": we_ms,
        "window_start_utc": _ms_to_iso_utc(ws_ms),
        "window_end_utc": _ms_to_iso_utc(we_ms),
        "gun_ms": meta.get("gun_ms"),
        "bbox": bbox,
        "position_source": pq_path.relative_to(root).as_posix() if pq_path.is_file() else None,
        "acquisition_status": "ready" if (bbox and policy) else "excluded_missing_location_time",
        "training_eligibility": "ac38_practice_excluded" if is_practice else "ac38_ac40_eligible",
    }


def _reconcile_ac40_2023_file(
    root: Path,
    file_path: Path,
    cache_dir: Path,
    abandoned_dates: set[str],
) -> dict[str, Any]:
    rel = file_path.relative_to(root).as_posix()
    info = extract_ac40_2023_metadata(file_path, cache_dir)
    bbox = info.get("bbox")
    ws_ms = info.get("window_start_ms")
    we_ms = info.get("window_end_ms")
    utc_date = _ms_to_iso_utc(ws_ms)[:10] if ws_ms is not None else None
    policy = resolve_venue_policy(bbox["center_lat"], bbox["center_lon"]) if bbox else None
    is_jeddah = policy is not None and policy.venue_id == "jeddah"
    is_abandoned = (not is_jeddah) and ("6 USA NZL" in file_path.name or (utc_date in abandoned_dates and "VNR 6" in file_path.name))
    domain = "abandoned" if is_abandoned else ("practice" if is_jeddah else "competitive")
    slug = "".join(ch if ch.isalnum() else "_" for ch in file_path.stem).strip("_").lower()
    rid = f"ac37_ac40_{slug}"
    comps = info.get("competitors")
    boat_races = len(comps) if isinstance(comps, dict) and comps else 0
    return {
        "source_file": file_path.name,
        "relative_path": rel,
        "source_bytes": info["source_bytes"],
        "source_sha256": info["source_sha256"],
        "cycle": "ac37",
        "boat_class": "AC40",
        "domain": domain,
        "stage": "ac37_ac40_prelim_2023",
        "session_id": info.get("session_id") or rid,
        "attempt_id": rid,
        "family_id": rid,
        "race_id": rid,
        "in_public_replay_catalog": False,
        "boat_races": boat_races,
        "venue_id": policy.venue_id if policy else "unknown",
        "utc_date": utc_date,
        "window_start_ms": ws_ms,
        "window_end_ms": we_ms,
        "window_start_utc": _ms_to_iso_utc(ws_ms),
        "window_end_utc": _ms_to_iso_utc(we_ms),
        "gun_ms": info.get("race_start_ms"),
        "bbox": bbox,
        "position_source": (cache_dir / str(info["tracks_1hz_parquet"])).relative_to(root).as_posix(),
        "acquisition_status": "ready" if (bbox and policy and ws_ms and we_ms) else "excluded_missing_location_time",
        "training_eligibility": "ac37_ac40_excluded_from_ac75",
    }


def _reconcile_ac75_file(
    root: Path,
    file_path: Path,
    attempt_by_file: dict[str, dict[str, Any]],
    native_by_file: dict[str, dict[str, Any]],
    holdout_families: set[str],
) -> dict[str, Any]:
    rel = file_path.relative_to(root).as_posix()
    att = attempt_by_file.get(file_path.name) or {}
    if file_path.suffix == ".ac37":
        fid = str(att.get("family_id") or file_path.stem)
        return {
            "source_file": file_path.name,
            "relative_path": rel,
            "source_bytes": file_path.stat().st_size,
            "cycle": "ac37",
            "boat_class": "AC75",
            "domain": "unsupported_binary",
            "stage": "semifinal",
            "session_id": att.get("session_id"),
            "attempt_id": att.get("attempt_id") or fid,
            "family_id": fid,
            "race_id": fid,
            "in_public_replay_catalog": False,
            "boat_races": 2,
            "venue_id": "unknown",
            "utc_date": None,
            "window_start_ms": None,
            "window_end_ms": None,
            "gun_ms": None,
            "bbox": None,
            "position_source": None,
            "acquisition_status": "excluded_unsupported_wire_schema",
            "acquisition_reason": "Protobuf schema absent; decoded GNSS coordinates and UTC window unavailable.",
            "training_eligibility": "excluded_unsupported_wire_schema",
        }

    nat_dir = root / ".forecast" / "ac75_learning" / "native" / "ac75_native_v1"
    part = native_by_file.get(file_path.name)
    if part is None:
        return {
            "source_file": file_path.name,
            "relative_path": rel,
            "source_bytes": file_path.stat().st_size,
            "cycle": "ac37",
            "boat_class": "AC75",
            "acquisition_status": "excluded_missing_native_partition",
            "training_eligibility": "excluded_unnormalized",
        }
    pq_path = nat_dir / part["parquet_file"]
    meta = _read_json(pq_path.with_suffix(".json"))
    bbox = _ac75_native_bbox(pq_path, meta)
    t_min_ms = meta.get("t_min_ms")
    t_max_ms = meta.get("t_max_ms")
    policy = resolve_venue_policy(bbox["center_lat"], bbox["center_lon"]) if bbox else None
    fid = str(att.get("family_id") or part["parquet_file"])
    is_practice = att.get("domain") == "practice"
    is_stopped = bool(att.get("is_stopped_race"))
    is_resail = bool(att.get("is_resail"))
    domain = "practice" if is_practice else ("stopped" if is_stopped else ("resail" if is_resail else "competitive"))
    if is_practice:
        train_elig = "ac75_practice_excluded_from_comp"
    elif fid in holdout_families:
        train_elig = "ac75_reserved_holdout"
    else:
        train_elig = "ac75_dev_eligible"
    comps = meta.get("competitor_map")
    boat_races = len(comps) if isinstance(comps, dict) and comps else 2
    return {
        "source_file": file_path.name,
        "relative_path": rel,
        "source_bytes": int(meta.get("source_bytes") or file_path.stat().st_size),
        "source_sha256": meta.get("source_sha256") or part.get("source_sha256"),
        "cycle": "ac37",
        "boat_class": "AC75",
        "domain": domain,
        "stage": str(att.get("stage") or "unknown"),
        "session_id": meta.get("session_id") or att.get("session_id") or fid,
        "attempt_id": str(att.get("attempt_id") or fid),
        "family_id": fid,
        "race_id": fid,
        "in_public_replay_catalog": False,
        "boat_races": int(boat_races),
        "venue_id": policy.venue_id if policy else "unknown",
        "utc_date": _ms_to_iso_utc(t_min_ms)[:10] if t_min_ms is not None else None,
        "window_start_ms": t_min_ms,
        "window_end_ms": t_max_ms,
        "window_start_utc": _ms_to_iso_utc(t_min_ms),
        "window_end_utc": _ms_to_iso_utc(t_max_ms),
        "gun_ms": int(meta["race_start_ms"]) if meta.get("race_start_ms") is not None else None,
        "bbox": bbox,
        "position_source": pq_path.relative_to(root).as_posix(),
        "acquisition_status": "ready" if (bbox and policy and t_min_ms and t_max_ms) else "excluded_missing_location_time",
        "training_eligibility": train_elig,
    }


def _reconcile_result_only_records(root: Path, binary_family_ids: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ac75_res = _read_json(root / "docs" / "ac37_results.json")
    for r in ac75_res.get("races", []):
        if r.get("stage") not in ("match", "lvc_semifinal_1", "lvc_semifinal_2"):
            continue
        has_loc_time = bool(r.get("location") and r.get("race_start_utc"))
        has_raw = r["race_id"] in binary_family_ids
        records.append({
            "race_id": r["race_id"],
            "source_doc": "docs/ac37_results.json",
            "cycle": "ac37",
            "boat_class": "AC75",
            "stage": r.get("stage"),
            "status": r.get("status"),
            "has_raw_file": has_raw,
            "raw_schema_status": "unsupported_binary_ac37" if has_raw else "no_raw_file",
            "boat_races": 2,
            "location": r.get("location"),
            "race_start_utc": r.get("race_start_utc"),
            "acquisition_status": "ready" if has_loc_time else "excluded_missing_location_time",
            "reason": None if has_loc_time else "Result-only record lacks supported location and UTC start time.",
        })
    ac40_res = _read_json(root / "docs" / "ac37_ac40_2023_results.json")
    for r in ac40_res.get("races", []):
        if "Jeddah" not in str(r.get("event", "")):
            continue
        has_loc_time = bool(r.get("location") and r.get("race_start_utc"))
        records.append({
            "race_id": r["race_id"],
            "source_doc": "docs/ac37_ac40_2023_results.json",
            "cycle": "ac37",
            "boat_class": "AC40",
            "stage": "jeddah_official_prelim",
            "status": r.get("status"),
            "has_raw_file": False,
            "raw_schema_status": "no_raw_file",
            "boat_races": len(r.get("official_order") or []) or 2,
            "location": r.get("location"),
            "race_start_utc": r.get("race_start_utc"),
            "acquisition_status": "ready" if has_loc_time else "excluded_missing_location_time",
            "reason": None if has_loc_time else "No raw telemetry file; result-only record lacks supported coordinates and UTC start window.",
        })
    return records


def build_environment_inventory(
    root: Path | str | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Reconcile all 160 raw telemetry files and result-only records into one inventory."""
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    data_dir = root_path / "Data"
    raw_files = sorted([p for p in data_dir.rglob("*") if p.is_file() and p.suffix in (".jsonl", ".ac37")])

    ds_by_source, sched_counts, public_ids = _load_ac38_lookups(root_path)
    attempts_p = root_path / ".forecast" / "ac75_learning" / "attempt_ledger.json"
    attempts_doc = _read_json(attempts_p) if attempts_p.is_file() else {"attempts": []}
    attempt_by_file = {str(a["source_file"]): a for a in attempts_doc.get("attempts", [])}

    native_man_p = root_path / ".forecast" / "ac75_learning" / "native" / "ac75_native_v1" / "dataset_manifest.json"
    native_doc = _read_json(native_man_p) if native_man_p.is_file() else {"partitions": []}
    native_by_file = {str(p["source_file"]): p for p in native_doc.get("partitions", [])}

    frozen_p = root_path / ".forecast" / "ac75_learning" / "frozen_evaluation_families.json"
    frozen_doc = _read_json(frozen_p) if frozen_p.is_file() else {}
    holdout_families = set(frozen_doc.get("reserved_holdout_families", []))

    cache_2023 = root_path / ".forecast" / "environment" / "ac40_2023_cache"
    abandoned_dates = {"2023-09-17"}

    sources: list[dict[str, Any]] = []
    for path in raw_files:
        rel = path.relative_to(data_dir).as_posix()
        if rel.startswith("AC38/"):
            sources.append(_reconcile_ac38_file(root_path, path, ds_by_source, sched_counts, public_ids))
        elif rel.startswith("AC37/prelims_ac40_2023/"):
            sources.append(_reconcile_ac40_2023_file(root_path, path, cache_2023, abandoned_dates))
        else:
            sources.append(_reconcile_ac75_file(root_path, path, attempt_by_file, native_by_file, holdout_families))

    binary_family_ids = {str(s["family_id"]) for s in sources if s["source_file"].endswith(".ac37") and s.get("family_id")}
    result_only = _reconcile_result_only_records(root_path, binary_family_ids)
    counts = {
        "raw_source_files": len(sources),
        "ac38_ac40_files": sum(1 for s in sources if s.get("cycle") == "ac38" and s.get("boat_class") == "AC40"),
        "ac37_ac40_files": sum(1 for s in sources if s.get("cycle") == "ac37" and s.get("boat_class") == "AC40"),
        "ac37_ac75_jsonl_files": sum(1 for s in sources if s.get("boat_class") == "AC75" and s["source_file"].endswith(".jsonl")),
        "ac37_ac75_binary_files": sum(1 for s in sources if s.get("boat_class") == "AC75" and s["source_file"].endswith(".ac37")),
        "unique_sessions": len({s["session_id"] for s in sources if s.get("session_id")}),
        "attempts": len({s["attempt_id"] for s in sources if s.get("attempt_id")}),
        "canonical_families": len({s["family_id"] for s in sources if s.get("family_id")}),
        "boat_races_from_telemetry": sum(int(s.get("boat_races") or 0) for s in sources),
        "public_replay_catalog_races": len(public_ids),
        "result_only_records": len(result_only),
        "result_only_with_binary_raw_file_records": sum(1 for r in result_only if r.get("has_raw_file")),
        "result_only_without_raw_file_records": sum(1 for r in result_only if not r.get("has_raw_file")),
        "result_only_boat_races": sum(int(r.get("boat_races") or 0) for r in result_only),
        "by_acquisition_status": dict(Counter(s["acquisition_status"] for s in sources)),
        "by_training_eligibility": dict(Counter(s["training_eligibility"] for s in sources)),
        "by_domain": dict(Counter(s.get("domain", "unknown") for s in sources)),
        "by_venue": dict(Counter(s.get("venue_id", "unknown") for s in sources)),
    }
    doc = {
        "schema_version": "environment-inventory-1",
        "counts": counts,
        "sources": sources,
        "result_only_records": result_only,
    }
    if write:
        out_path = root_path / ".forecast" / "environment" / "inventory.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(out_path)
    return doc
