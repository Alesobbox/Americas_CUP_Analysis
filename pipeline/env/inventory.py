"""AC38 regatta environment inventory reconciling raw AC40 telemetry files and replay metadata."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pipeline.projection import metric_to_wgs84
from pipeline.run_pipeline import infer_race_metadata

from .contracts import resolve_env_cache_dir
from .registry import resolve_venue_policy


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


def _infer_ac38_from_replay(replay_path: Path) -> dict[str, Any] | None:
    if not replay_path.is_file():
        return None
    doc = json.loads(replay_path.read_text(encoding="utf-8"))
    chrono = doc.get("chronology") or {}
    course = doc.get("course") or {}
    origin = course.get("origin") or {}
    proj = course.get("projection") or {}
    lat0, lon0 = origin.get("lat"), origin.get("lon")
    k_lat_raw, k_lon_raw = proj.get("k_lat"), proj.get("k_lon")
    k_lat = float(k_lat_raw) if k_lat_raw is not None else None
    k_lon = float(k_lon_raw) if k_lon_raw is not None else None
    lats: list[float] = []
    lons: list[float] = []
    if lat0 is not None and lon0 is not None:
        lats.append(float(lat0))
        lons.append(float(lon0))
    for mk in (course.get("marks") or {}).values():
        if not isinstance(mk, dict):
            continue
        target = mk.get("target")
        if (
            isinstance(target, list)
            and len(target) == 2
            and lat0 is not None
            and lon0 is not None
            and target[0] is not None
            and target[1] is not None
        ):
            mlat, mlon = metric_to_wgs84(
                float(target[0]),
                float(target[1]),
                float(lat0),
                float(lon0),
                k_lat=k_lat,
                k_lon=k_lon,
            )
            if abs(mlat - float(lat0)) <= 2.0 and abs(mlon - float(lon0)) <= 2.0:
                lats.append(mlat)
                lons.append(mlon)
    tel = doc.get("telemetry") or {}
    boats = tel.get("boats") or {}
    if lat0 is not None and lon0 is not None and isinstance(boats, dict):
        for bdata in boats.values():
            xs = bdata.get("x") or []
            ys = bdata.get("y") or []
            step = max(1, len(xs) // 40)
            for idx in range(0, len(xs), step):
                xv, yv = xs[idx], ys[idx]
                if xv is None or yv is None:
                    continue
                la, lo = metric_to_wgs84(
                    float(xv),
                    float(yv),
                    float(lat0),
                    float(lon0),
                    k_lat=k_lat,
                    k_lon=k_lon,
                )
                lats.append(la)
                lons.append(lo)
    return {
        "window_start_ms": chrono.get("window_start"),
        "window_end_ms": chrono.get("window_end"),
        "gun_ms": chrono.get("gun_time"),
        "boat_ids": [str(c["id"]) for c in (doc.get("competitors") or []) if isinstance(c, dict) and c.get("id")],
        "bbox": _extract_bbox_from_coords(lats, lons),
        "session_id": str((doc.get("provenance") or {}).get("session_id") or doc.get("id")),
    }


def _infer_ac38_source_meta(root: Path, file_path: Path) -> tuple[dict[str, Any], str]:
    info = infer_race_metadata(file_path.name)
    rid = str(info["race_id"])
    size_bytes = file_path.stat().st_size
    is_practice = bool(re.search(r"\bpr(?:\d+|-[a-z]+)\b|\bpractice\b", file_path.name.lower()))
    replay_rel = f"public/data/replays/{rid}.json"
    replay_path = root / replay_rel
    rep_meta = _infer_ac38_from_replay(replay_path)
    if rep_meta is not None and rep_meta.get("bbox") and rep_meta.get("window_start_ms") is not None:
        return (
            {
                "race_id": rid,
                "date": info.get("race_date") or _ms_to_iso_utc(int(rep_meta["window_start_ms"]))[:10],
                "window_start_ms": rep_meta["window_start_ms"],
                "window_end_ms": rep_meta["window_end_ms"],
                "gun_ms": rep_meta["gun_ms"],
                "practice": is_practice,
                "session_id": rep_meta["session_id"],
                "boat_ids": rep_meta["boat_ids"],
                "bbox": rep_meta["bbox"],
                "source_sha256": None,
                "bytes": size_bytes,
            },
            replay_rel,
        )

    session_id: str | None = None
    ws_ms: int | None = None
    we_ms: int | None = None
    gun_ms: int | None = None
    boat_ids: list[str] = []
    lats: list[float] = []
    lons: list[float] = []
    ts_min: int | None = None
    ts_max: int | None = None
    full_scan = size_bytes < 10_000_000
    digest = hashlib.sha256() if full_scan else None

    def _consume_line(raw: bytes) -> None:
        nonlocal session_id, ws_ms, we_ms, gun_ms, is_practice, boat_ids, ts_min, ts_max
        if b'"session"' not in raw and b'"gnss_position"' not in raw:
            return
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        sess = obj.get("session")
        if isinstance(sess, dict):
            if sess.get("id"):
                session_id = str(sess["id"])
            if sess.get("window_start"):
                ws_ms = int(sess["window_start"])
            if sess.get("window_end"):
                we_ms = int(sess["window_end"])
            if sess.get("race_start"):
                gun_ms = int(sess["race_start"])
            if sess.get("race_type") == "RACE_TYPE_PRACTICE":
                is_practice = True
            comps = sess.get("competitors")
            if isinstance(comps, list) and comps:
                boat_ids = [str(c["asset_id"]) for c in comps if isinstance(c, dict) and c.get("asset_id")]
        tel = obj.get("telemetry")
        if isinstance(tel, dict) and isinstance(tel.get("gnss_position"), dict):
            gnss = tel["gnss_position"]
            lat, lon = gnss.get("latitude"), gnss.get("longitude")
            if lat is not None and lon is not None:
                lats.append(float(lat))
                lons.append(float(lon))
            if tel.get("timestamp") is not None:
                tval = int(tel["timestamp"])
                ts_min = tval if ts_min is None else min(ts_min, tval)
                ts_max = tval if ts_max is None else max(ts_max, tval)

    with file_path.open("rb") as fh:
        if full_scan:
            for raw_line in fh:
                assert digest is not None
                digest.update(raw_line)
                _consume_line(raw_line)
        else:
            for raw_line in fh.read(524_288).splitlines():
                _consume_line(raw_line)
            if size_bytes > 524_288:
                fh.seek(max(0, size_bytes - 524_288))
                tail_lines = fh.read(524_288).splitlines()[1:]
                for raw_line in tail_lines:
                    _consume_line(raw_line)

    ws_final = ws_ms if ws_ms is not None else ts_min
    we_final = we_ms if we_ms is not None else ts_max
    bbox = _extract_bbox_from_coords(lats, lons)
    utc_date = info.get("race_date") or (_ms_to_iso_utc(gun_ms or ws_final)[:10] if (gun_ms or ws_final) is not None else None)
    return (
        {
            "race_id": rid,
            "date": utc_date,
            "window_start_ms": ws_final,
            "window_end_ms": we_final,
            "gun_ms": gun_ms,
            "practice": is_practice,
            "session_id": session_id or rid,
            "boat_ids": boat_ids,
            "bbox": bbox,
            "source_sha256": digest.hexdigest() if digest is not None else None,
            "bytes": size_bytes,
        },
        file_path.relative_to(root).as_posix(),
    )


def _load_public_replay_ids(root: Path) -> set[str]:
    public_ids: set[str] = set()
    man_p = root / "public" / "data" / "manifests.json"
    if man_p.is_file():
        man = _read_json(man_p)
        for reg in man.get("regattas", []):
            for race in reg.get("races", []):
                if race.get("id"):
                    public_ids.add(str(race["id"]))
    return public_ids


def _reconcile_ac38_file(
    root: Path,
    file_path: Path,
    public_ids: set[str],
) -> dict[str, Any]:
    rel = file_path.relative_to(root).as_posix()
    meta, pos_src = _infer_ac38_source_meta(root, file_path)
    rid = str(meta["race_id"])
    bbox = meta.get("bbox")
    ws_ms = meta.get("window_start_ms")
    we_ms = meta.get("window_end_ms")
    policy = resolve_venue_policy(bbox["center_lat"], bbox["center_lon"]) if bbox else None
    is_practice = bool(meta.get("practice", False))
    boat_races = len(meta.get("boat_ids") or [])
    return {
        "source_file": file_path.name,
        "relative_path": rel,
        "source_bytes": int(meta["bytes"]),
        "source_sha256": meta["source_sha256"],
        "cycle": "ac38",
        "boat_class": "AC40",
        "domain": "practice" if is_practice else "competitive",
        "stage": "ac38_practice" if is_practice else "ac38_prelim_fleet_match",
        "session_id": str(meta["session_id"]),
        "attempt_id": rid,
        "family_id": rid,
        "race_id": rid,
        "in_public_replay_catalog": rid in public_ids,
        "boat_races": int(boat_races),
        "venue_id": policy.venue_id if policy else "unknown",
        "utc_date": meta.get("date"),
        "window_start_ms": ws_ms,
        "window_end_ms": we_ms,
        "window_start_utc": _ms_to_iso_utc(ws_ms) if ws_ms is not None else None,
        "window_end_utc": _ms_to_iso_utc(we_ms) if we_ms is not None else None,
        "gun_ms": meta.get("gun_ms"),
        "bbox": bbox,
        "position_source": pos_src,
        "acquisition_status": "ready" if (bbox and policy and ws_ms is not None and we_ms is not None) else "excluded_missing_location_time",
        "training_eligibility": "ac38_practice_excluded" if is_practice else "ac38_ac40_eligible",
    }


def build_environment_inventory(
    root: Path | str | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Reconcile raw AC38 telemetry files and public replay metadata into one inventory."""
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    ac38_dir = root_path / "Data" / "AC38"
    raw_files = sorted([p for p in ac38_dir.rglob("*.jsonl") if p.is_file()]) if ac38_dir.is_dir() else []
    public_ids = _load_public_replay_ids(root_path)

    sources = [_reconcile_ac38_file(root_path, path, public_ids) for path in raw_files]
    counts = {
        "raw_source_files": len(sources),
        "ac38_ac40_files": len(sources),
        "ac37_ac40_files": 0,
        "ac37_ac75_jsonl_files": 0,
        "ac37_ac75_binary_files": 0,
        "unique_sessions": len({s["session_id"] for s in sources if s.get("session_id")}),
        "attempts": len({s["attempt_id"] for s in sources if s.get("attempt_id")}),
        "canonical_families": len({s["family_id"] for s in sources if s.get("family_id")}),
        "boat_races_from_telemetry": sum(int(s.get("boat_races") or 0) for s in sources),
        "public_replay_catalog_races": len(public_ids),
        "result_only_records": 0,
        "result_only_with_binary_raw_file_records": 0,
        "result_only_without_raw_file_records": 0,
        "result_only_boat_races": 0,
        "by_acquisition_status": dict(Counter(s["acquisition_status"] for s in sources)),
        "by_training_eligibility": dict(Counter(s["training_eligibility"] for s in sources)),
        "by_domain": dict(Counter(s.get("domain", "unknown") for s in sources)),
        "by_venue": dict(Counter(s.get("venue_id", "unknown") for s in sources)),
    }
    doc = {
        "schema_version": "environment-inventory-1",
        "counts": counts,
        "sources": sources,
        "result_only_records": [],
    }
    if write:
        out_path = resolve_env_cache_dir(root_path) / "inventory.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(out_path)
    return doc
