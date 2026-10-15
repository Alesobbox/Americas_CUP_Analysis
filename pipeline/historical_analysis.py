"""Deterministic, compact post-race statistics from synchronized source data.

The replay's fixed-axis VMG is intentionally left untouched. All averages here
use an explicit leg or wind direction and each boat's observed racing window.
"""

from __future__ import annotations

import json
import math
import os
from bisect import bisect_left, bisect_right
from collections import defaultdict
from statistics import median

from pipeline.reconstruction import compute_bow_position
from pipeline.config import UUID_TO_MARK

SCHEMA_VERSION = "2.0"
METHOD_VERSION = "historical-2"
EVENT_FEED_SCHEMA_VERSION = "1.0"
EVENT_FEED_METHOD_VERSION = "event-feed-1"
WIND_SHIFT_THRESHOLD_DEG = 10.0
WIND_SHIFT_MIN_INTERVAL_MS = 30_000
KT_TO_MPS = 1 / 1.94384449


DEFINITIONS = {
    "sog_mean_kt": ("Mean speed", "kt", "Time-weighted mean SOG", "active race", "valid seconds", "interpolated boat SOG"),
    "course_vmg_kt": ("Leg-directed course VMG", "kt", "SOG × cos(COG − active leg bearing)", "active leg", "valid seconds", "interpolated SOG and COG; reconstructed leg"),
    "course_vmg_p10_kt": ("Course VMG 10th percentile", "kt", "Time-weighted 10th percentile of leg-directed course VMG", "active leg", "valid seconds", "interpolated SOG and COG"),
    "course_vmg_p90_kt": ("Course VMG 90th percentile", "kt", "Time-weighted 90th percentile of leg-directed course VMG", "active leg", "valid seconds", "interpolated SOG and COG"),
    "wind_vmg_kt": ("Wind-relative VMG", "kt", "SOG × cos(COG − true wind-from bearing) on upwind legs; negative of this on downwind legs", "active leg", "valid wind seconds", "interpolated boat SOG, COG and TWD"),
    "wind_vmg_p10_kt": ("Wind VMG 10th percentile", "kt", "Time-weighted 10th percentile of wind-relative VMG", "active leg", "valid wind seconds", "interpolated boat SOG, COG and TWD"),
    "wind_vmg_p90_kt": ("Wind VMG 90th percentile", "kt", "Time-weighted 90th percentile of wind-relative VMG", "active leg", "valid wind seconds", "interpolated boat SOG, COG and TWD"),
    "distance_m": ("Distance sailed", "m", "Sum of projected GNSS point-to-point distances, clipped at reconstructed crossings", "active race or leg", "valid path segments", "interpolated projected GNSS"),
    "elapsed_s": ("Leg time", "s", "End crossing − previous crossing", "completed leg", "one leg", "official event time or reconstructed fallback"),
    "route_ratio": ("Geometric route ratio", "ratio", "Direct distance between observed leg endpoints ÷ distance sailed; geometric reference only, not a feasible tactical route", "completed leg", "one leg", "interpolated projected GNSS"),
    "abs_twa_mean_deg": ("Absolute true wind angle", "°", "Time-weighted mean |signed TWA|; port/starboard are not averaged as signed angles", "active leg", "valid wind seconds", "derived TWA from boat heading and TWD"),
    "port_abs_twa_median_deg": ("Port absolute TWA median", "°", "Time-weighted median |TWA| during stable port periods", "active leg", "stable port seconds", "derived TWA"),
    "starboard_abs_twa_median_deg": ("Starboard absolute TWA median", "°", "Time-weighted median |TWA| during stable starboard periods", "active leg", "stable starboard seconds", "derived TWA"),
    "port_time_s": ("Port tack time", "s", "Stable samples with signed TWA below −15° excluding ±3 s around manoeuvres", "active leg", "valid stable seconds", "derived TWA and detected manoeuvres"),
    "starboard_time_s": ("Starboard tack time", "s", "Stable samples with signed TWA above +15° excluding ±3 s around manoeuvres", "active leg", "valid stable seconds", "derived TWA and detected manoeuvres"),
    "port_distance_m": ("Port tack distance", "m", "Projected path length during stable port samples", "active leg", "valid stable segments", "interpolated GNSS and derived TWA"),
    "starboard_distance_m": ("Starboard tack distance", "m", "Projected path length during stable starboard samples", "active leg", "valid stable segments", "interpolated GNSS and derived TWA"),
    "boundary_nearest_m": ("Nearest race boundary", "m", "Minimum signed distance from boat centre to active race-boundary polygon; negative is outside", "active race", "valid 100 ms samples", "interpolated GNSS; timestamped session race boundary"),
    "boundary_buffer_s": ("Within 25 m of race boundary", "s", "Time with signed distance from 0 to 25 m", "active race", "valid 100 ms samples", "interpolated GNSS; timestamped session race boundary"),
    "boundary_outside_s": ("Outside race boundary", "s", "Time with negative signed distance; sampled exposure, not a rules ruling", "active race", "valid 100 ms samples", "interpolated GNSS; timestamped session race boundary"),
    "start_distance_m": ("Bow distance to start line at gun", "m", "Signed bow distance to moving start line; positive is course side", "gun instant", "one observation", "interpolated GNSS/heading and dynamic marks"),
    "start_along_line": ("Start line location", "fraction", "Bow projection along the source sequence-0 port to starboard marks; 0 and 1 are line ends; outside range is beyond an end", "gun instant", "one observation", "interpolated GNSS/heading and dynamic marks"),
    "start_sog_kt": ("Speed at gun", "kt", "Interpolated SOG at gun", "gun instant", "one observation", "interpolated boat SOG"),
    "start_closing_kt": ("Speed toward line at gun", "kt", "SOG component along start-line course-side normal; signed", "gun instant", "one observation", "interpolated SOG and COG; dynamic marks"),
    "tack_loss_median_kt": ("Median tack speed loss", "kt", "Median detector entry SOG − minimum SOG", "active race", "detected tack events", "reconstructed manoeuvres"),
    "tack_count": ("Tack count", "events", "Number of detected tack events", "active race", "detected events", "reconstructed manoeuvres"),
    "gybe_loss_median_kt": ("Median gybe speed loss", "kt", "Median detector entry SOG − minimum SOG", "active race", "detected gybe events", "reconstructed manoeuvres"),
    "gybe_count": ("Gybe count", "events", "Number of detected gybe events", "active race", "detected events", "reconstructed manoeuvres"),
    "tack_recovery_median_s": ("Median tack recovery", "s", "Median recovered-event time to 95% entry SOG, within 15 s", "active race", "recovered tack events", "interpolated SOG; reconstructed manoeuvres"),
    "gybe_recovery_median_s": ("Median gybe recovery", "s", "Median recovered-event time to 95% entry SOG, within 15 s", "active race", "recovered gybe events", "interpolated SOG; reconstructed manoeuvres"),
}


def circular_delta_deg(a, b):
    """Signed shortest rotation from a to b, in [-180, 180)."""
    return ((b - a + 180) % 360) - 180


def leg_course_vmg_kt(sog_kt, cog_deg, axis_deg, leg):
    if not isinstance(leg, int) or leg < 1:
        raise ValueError("leg must be a positive integer")
    bearing = axis_deg if leg % 2 else axis_deg + 180
    return sog_kt * math.cos(math.radians(circular_delta_deg(bearing, cog_deg)))


def wind_relative_vmg_kt(sog_kt, cog_deg, twd_deg, upwind):
    value = sog_kt * math.cos(math.radians(circular_delta_deg(twd_deg, cog_deg)))
    return value if upwind else -value


def _segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    u = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def signed_polygon_distance_m(point, polygon):
    """Positive inside; negative outside; zero on edge."""
    if len(polygon) < 3:
        return None
    inside = False
    nearest = math.inf
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        nearest = min(nearest, _segment_distance(point, a, b))
        if (a[1] > point[1]) != (b[1] > point[1]):
            cross_x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if cross_x > point[0]:
                inside = not inside
    return nearest if inside else -nearest


def start_line_geometry(bow, port, starboard, axis_deg):
    """Signed course-side distance, port-to-starboard fraction, normal x/y."""
    dx, dy = starboard[0] - port[0], starboard[1] - port[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        raise ValueError("start line has zero length")
    nx, ny = -dy / length, dx / length
    axis = (math.sin(math.radians(axis_deg)), math.cos(math.radians(axis_deg)))
    if nx * axis[0] + ny * axis[1] < 0:
        nx, ny = -nx, -ny
    return ((bow[0] - port[0]) * nx + (bow[1] - port[1]) * ny,
            ((bow[0] - port[0]) * dx + (bow[1] - port[1]) * dy) / (length * length), nx, ny)


def _weighted_quantile(observations, fraction):
    if not observations:
        return None
    ordered = sorted(observations, key=lambda x: x[0])
    target = sum(weight for _, weight in ordered) * fraction
    total = 0.0
    for value, weight in ordered:
        total += weight
        if total >= target:
            return value
    return ordered[-1][0]


def _metric(value, unit, quality="derived", coverage_s=None, reason=None, sample_count=None):
    if value is not None and not math.isfinite(value):
        value, quality, reason = None, "unavailable", "non-finite source value"
    result = {"value": value if value is not None else None, "unit": unit,
              "quality": quality if value is not None else "unavailable", "coverage_s": round(coverage_s, 3) if coverage_s is not None else None}
    if reason:
        result["reason"] = reason
    if sample_count is not None:
        result["sample_count"] = sample_count
    return result


def _interp(t, times, values, circular=False):
    if not times or not values or t < times[0] or t > times[-1]:
        return None
    i = bisect_right(times, t)
    if i == 0:
        return values[0]
    if i >= len(times):
        return values[-1]
    p = i - 1
    if times[p] == t:
        return values[p]
    u = (t - times[p]) / (times[i] - times[p])
    return (values[p] + u * circular_delta_deg(values[p], values[i])) % 360 if circular else values[p] + u * (values[i] - values[p])


def _source_valid(boat, t, fields=("gnss", "heading", "sog", "cog")):
    coverage = getattr(boat, "source_coverage", None)
    if coverage is None:  # simple synthetic fixtures without raw timestamp metadata
        return True
    for field in fields:
        info = coverage.get(field, {})
        if info.get("first_ms") is None or t < info["first_ms"] or t > info["last_ms"]:
            return False
        if any(a < t < b for a, b in info.get("gaps", [])):
            return False
    return True


def _boat_at(t, times, boat):
    if not _source_valid(boat, t):
        return None
    values = (_interp(t, times, boat.x), _interp(t, times, boat.y),
              _interp(t, times, boat.heading, True), _interp(t, times, boat.cog, True),
              _interp(t, times, boat.sog_kt), _interp(t, times, boat.twd_deg, True))
    return values if all(v is not None and math.isfinite(v) for v in values) else None


def _mark_at(t, times, mark):
    x, y = _interp(t, times, mark.x), _interp(t, times, mark.y)
    return (x, y) if x is not None and y is not None else None


def _active_polygon(t, timeline, fallback):
    if not timeline:
        return fallback
    idx = bisect_right([item["t"] for item in timeline], t) - 1
    return timeline[idx]["race"] if idx >= 0 else fallback


def _race_window(comp, chronology, times):
    if comp.start.ocs or comp.classification == "RET" or comp.start.crossing_time is None:
        return None
    start = max(comp.start.crossing_time, chronology.gun_time, times[0])
    end = min(comp.finish_time_ms or times[-1], chronology.window_end, times[-1])
    return (start, end) if end > start else None


def _samples_between(start, end, times):
    """Sample intervals with exact endpoint interpolation and their actual seconds."""
    if end <= start:
        return
    interior = times[bisect_right(times, start):bisect_left(times, end)]
    points = [start, *interior, end]
    for a, b in zip(points, points[1:]):
        if b > a:
            yield a, b, (b - a) / 1000


def _unavailable_leg(reason):
    units = {"elapsed_s": "s", "distance_m": "m", "route_ratio": "ratio",
             "sog_mean_kt": "kt", "course_vmg_kt": "kt", "wind_vmg_kt": "kt",
             "abs_twa_mean_deg": "°", "port_time_s": "s", "starboard_time_s": "s",
             "port_distance_m": "m", "starboard_distance_m": "m"}
    return {key: _metric(None, unit, reason=reason) for key, unit in units.items()}


def _leg_metrics(start, end, leg, times, boat, axis, manoeuvres):
    if start is None or end is None or end <= start:
        return _unavailable_leg("crossing set incomplete")
    elapsed = (end - start) / 1000
    accum = defaultdict(float)
    path = 0.0
    n = 0
    distributions = defaultdict(list)
    bins = {"0–45°": 0.0, "45–90°": 0.0, "90–135°": 0.0, "135–180°": 0.0}
    for a, b, dt in _samples_between(start, end, times):
        va, vb = _boat_at(a, times, boat), _boat_at(b, times, boat)
        if va is None or vb is None or dt > 2:
            continue
        mid = (a + b) // 2
        vm = _boat_at(mid, times, boat)
        if vm is None or vm[4] < 0 or vm[4] > 80:
            continue
        d = math.hypot(vb[0] - va[0], vb[1] - va[1])
        path += d
        n += 1
        accum["valid_s"] += dt
        accum["sog"] += vm[4] * dt
        course_vmg = leg_course_vmg_kt(vm[4], vm[3], axis, leg)
        accum["course"] += course_vmg * dt
        distributions["course"].append((course_vmg, dt))
        if _source_valid(boat, mid, ("twd",)) and 0 <= vm[5] < 360:
            accum["wind_s"] += dt
            wind_vmg = wind_relative_vmg_kt(vm[4], vm[3], vm[5], leg % 2 == 1)
            accum["wind"] += wind_vmg * dt
            distributions["wind"].append((wind_vmg, dt))
            twa = circular_delta_deg(vm[2], vm[5])
            accum["abs_twa"] += abs(twa) * dt
            bins[["0–45°", "45–90°", "90–135°", "135–180°"][min(3, int(abs(twa) // 45))]] += dt
            transition = any(abs(mid - m.timestamp) <= 3000 for m in manoeuvres)
            if not transition and abs(twa) > 15:
                side = "starboard" if twa > 0 else "port"
                accum[side + "_time"] += dt
                accum[side + "_distance"] += d
                distributions[side + "_twa"].append((abs(twa), dt))
    if not n:
        missing = _unavailable_leg("no valid track segments")
        missing["elapsed_s"] = _metric(elapsed, "s", "reconstructed")
        return missing
    start_pos, end_pos = _boat_at(start, times, boat), _boat_at(end, times, boat)
    direct = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]) if start_pos and end_pos else None
    coverage = accum["valid_s"]
    quality = "derived" if coverage >= 0.95 * elapsed else "partial"
    route_ok = direct is not None and path > 0 and direct <= path + 1e-6 and quality == "derived"
    m = {
        "elapsed_s": _metric(elapsed, "s", "reconstructed"),
        "distance_m": _metric(path, "m", quality, coverage),
        "route_ratio": _metric(direct / path if route_ok else None, "ratio", quality, coverage, "geometric reference only" if route_ok else "incomplete path or endpoints"),
        "sog_mean_kt": _metric(accum["sog"] / coverage, "kt", quality, coverage),
        "course_vmg_kt": _metric(accum["course"] / coverage, "kt", quality, coverage),
        "course_vmg_p10_kt": _metric(_weighted_quantile(distributions["course"], 0.1), "kt", quality, coverage),
        "course_vmg_p90_kt": _metric(_weighted_quantile(distributions["course"], 0.9), "kt", quality, coverage),
        "wind_vmg_kt": _metric(accum["wind"] / accum["wind_s"] if accum["wind_s"] else None, "kt", "derived" if accum["wind_s"] >= 0.95 * elapsed else "partial", accum["wind_s"], "boat wind unavailable" if not accum["wind_s"] else None),
        "wind_vmg_p10_kt": _metric(_weighted_quantile(distributions["wind"], 0.1), "kt", "derived" if accum["wind_s"] >= 0.95 * elapsed else "partial", accum["wind_s"], "boat wind unavailable" if not accum["wind_s"] else None),
        "wind_vmg_p90_kt": _metric(_weighted_quantile(distributions["wind"], 0.9), "kt", "derived" if accum["wind_s"] >= 0.95 * elapsed else "partial", accum["wind_s"], "boat wind unavailable" if not accum["wind_s"] else None),
        "abs_twa_mean_deg": _metric(accum["abs_twa"] / accum["wind_s"] if accum["wind_s"] else None, "°", "derived" if accum["wind_s"] >= 0.95 * elapsed else "partial", accum["wind_s"], "boat wind unavailable" if not accum["wind_s"] else None),
    }
    for side in ("port", "starboard"):
        m[side + "_abs_twa_median_deg"] = _metric(_weighted_quantile(distributions[side + "_twa"], 0.5), "°", quality, accum[side + "_time"], "no stable samples" if not distributions[side + "_twa"] else None)
        m[side + "_time_s"] = _metric(accum[side + "_time"], "s", quality, coverage)
        m[side + "_distance_m"] = _metric(accum[side + "_distance"], "m", quality, coverage)
    return m, bins


def _event_analysis(event, times, boat, legs, marks):
    t = event.timestamp
    idx = bisect_left(times, t)
    leg = legs[min(idx, len(legs) - 1)] if legs else 0
    pos = _boat_at(t, times, boat)
    finish = min(t + 15000, times[-1])
    base = event.entry_speed_kt
    recovery = None
    min_time = t
    min_speed = math.inf
    for i in range(max(0, idx - 20), min(len(times), bisect_right(times, t + 5000))):
        if _source_valid(boat, times[i], ("sog",)) and boat.sog_kt[i] < min_speed:
            min_speed, min_time = boat.sog_kt[i], times[i]
    for i in range(bisect_left(times, min_time), bisect_right(times, finish)):
        if _source_valid(boat, times[i], ("sog",)) and boat.sog_kt[i] >= 0.95 * base:
            recovery = (times[i] - min_time) / 1000
            break
    near_gate = any(abs(t - gate.crossing_time) < 5000 for gate in marks)
    return {"type": event.type, "timestamp": t, "leg": leg,
            "position": {"x": round(pos[0], 2), "y": round(pos[1], 2)} if pos else None,
            "entry_speed_kt": event.entry_speed_kt, "min_speed_kt": event.min_speed_kt,
            "speed_loss_kt": event.speed_loss_kt, "recovery_time_s": recovery,
            "acceleration_kt_s": round((0.95 * base - min_speed) / recovery, 3) if recovery and min_speed < math.inf else None,
            "quality": "ambiguous_rounding" if near_gate else "reconstructed",
            "recovery_reason": None if recovery is not None else "95% entry speed not reached within 15 s"}


def _gate_analysis(gate, times, boat, marks):
    t = gate.crossing_time
    mark = marks.get(gate.mark_chosen)
    at = _boat_at(t, times, boat)
    approach = _boat_at(t - 20000, times, boat)
    target = _mark_at(t - 20000, times, mark) if mark else None
    angle = None
    distance = None
    if approach and target:
        bearing = math.degrees(math.atan2(target[0] - approach[0], target[1] - approach[1]))
        angle = abs(circular_delta_deg(approach[3], bearing))
        distance = math.hypot(target[0] - approach[0], target[1] - approach[1])
    before = _boat_at(t - 5000, times, boat)
    after = _boat_at(t + 5000, times, boat)
    return {"leg": gate.leg, "crossing_time_ms": t, "mark_chosen": gate.mark_chosen,
            "side": gate.side, "source": "official" if gate.is_official else "reconstructed",
            "position": {"x": round(at[0], 2), "y": round(at[1], 2)} if at else None,
            "approach_20s_distance_m": round(distance, 2) if distance is not None else None,
            "approach_angle_deg": round(angle, 2) if angle is not None else None,
            "entry_speed_kt": round(before[4], 2) if before else None,
            "exit_speed_kt": round(after[4], 2) if after else None,
            "rounding_time_s": None, "rounding_reason": "no stable entry/exit boundary in source"}


def build_event_feed(detail):
    """Select timestamped source/reconstruction events from one analysis detail.

    The official-wind samples in ``wind.timeline`` are a bounded subset of the
    raw official stream. A shift is emitted only when the shortest circular
    change from the last emitted reference reaches 10 degrees and 30 seconds
    have elapsed. Missing event times never receive a synthetic timestamp.
    """
    race = detail["race"]
    race_id = race["id"]
    events = []

    def add(event_id, timestamp, kind, label, source, quality, boat_id=None):
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            return
        event = {"id": event_id, "timestamp_ms": timestamp, "type": kind,
                 "label": label, "source": source, "quality": quality}
        if boat_id is not None:
            event["boat_id"] = boat_id
        events.append(event)

    add(f"{race_id}:gun", race.get("gun_time_ms"), "gun", "Start gun",
        "source session race-start timestamp", "source")
    total_legs = max((leg.get("leg", 0) for boat in detail["boats"]
                      for leg in boat.get("legs", [])), default=0)
    for boat in detail["boats"]:
        boat_id = boat["id"]
        team = boat["team_code"]
        start = boat.get("start") or {}
        add(f"{race_id}:start:{boat_id}", start.get("crossing_time_ms"),
            "start", f"{team} start crossing", "reconstructed bow-line crossing",
            "source_conflict" if boat.get("source_conflicts") else "reconstructed", boat_id)
        for gate in boat.get("gates", []):
            leg = gate.get("leg")
            if not isinstance(leg, int) or leg < 1:
                continue
            is_finish = (boat.get("classification", "").startswith("RANK_")
                         and leg == total_legs)
            add(f"{race_id}:gate:{boat_id}:{leg}", gate.get("crossing_time_ms"),
                "finish" if is_finish else "gate",
                f"{team} {'finish' if is_finish else f'gate {leg}'} crossing",
                "source leg timing" if gate.get("source") == "official"
                else "geometric crossing fallback",
                "source_timing" if gate.get("source") == "official"
                else "reconstructed", boat_id)
        manoeuvre_counts = defaultdict(int)
        for manoeuvre in boat.get("manoeuvres", []):
            kind = manoeuvre.get("type", "").lower()
            timestamp = manoeuvre.get("timestamp")
            if kind not in ("tack", "gybe") or not isinstance(timestamp, int):
                continue
            key = (timestamp, kind)
            manoeuvre_counts[key] += 1
            add(f"{race_id}:{kind}:{boat_id}:{timestamp}:{manoeuvre_counts[key]}",
                timestamp, kind, f"{team} {kind}",
                "manoeuvre detector on synchronized boat telemetry",
                manoeuvre.get("quality", "reconstructed"), boat_id)

    wind = detail.get("wind") or {}
    samples = [sample for sample in wind.get("timeline", [])
               if isinstance(sample.get("timestamp"), int)
               and not isinstance(sample.get("timestamp"), bool)
               and isinstance(sample.get("shift_deg"), (int, float))
               and math.isfinite(sample["shift_deg"])]
    samples.sort(key=lambda sample: sample["timestamp"])
    if samples:
        reference = samples[0]["shift_deg"]
        last_emitted = samples[0]["timestamp"]
        for sample in samples[1:]:
            timestamp = sample["timestamp"]
            change = circular_delta_deg(reference, sample["shift_deg"])
            if (abs(change) < WIND_SHIFT_THRESHOLD_DEG
                    or timestamp - last_emitted < WIND_SHIFT_MIN_INTERVAL_MS):
                continue
            add(f"{race_id}:wind_shift:{timestamp}", timestamp, "wind_shift",
                f"Official wind shift {change:+.1f}°", "official wind asset",
                "measured_sample")
            reference = sample["shift_deg"]
            last_emitted = timestamp

    events.sort(key=lambda event: (event["timestamp_ms"], event["id"]))
    return {"schema_version": EVENT_FEED_SCHEMA_VERSION,
            "method_version": EVENT_FEED_METHOD_VERSION, "events": events}


def build_race_analysis(ingest_result, reconstruction_result, manoeuvres_by_boat,
                        leg_by_boat, race_id, race_name, race_date, venue):
    sess = ingest_result.session
    course_sequences = getattr(sess, "course_sequences", None)
    total_legs = len(course_sequences) - 1 if course_sequences else 4
    times = ingest_result.grid_timestamps_ms
    chronology = reconstruction_result.chronology
    comps = reconstruction_result.competitors
    start_order = {c.team_code: i + 1 for i, c in enumerate(sorted(
        (c for c in comps.values() if c.start.crossing_time is not None and not c.start.ocs),
        key=lambda c: c.start.crossing_time))}
    definitions = {key: {"label": d[0], "unit": d[1], "formula": d[2], "window": d[3],
                         "denominator": d[4], "source": d[5], "display": d[0]} for key, d in DEFINITIONS.items()}
    result = {"schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
              "race": {"id": race_id, "name": race_name, "date": race_date, "venue": venue,
                       "boat_class": sess.boat_class, "race_type": sess.race_type,
                       "gun_time_ms": chronology.gun_time, "boat_count": len(ingest_result.boats),
                       "result_provenance": "Reconstructed from source leg timings and geometric fallbacks; source classifications are not verified official results."},
              "definitions": definitions, "boats": [], "wind": {}, "pairs": [],
              "limitations": ["No measured target TWA or polar: tactical laylines unavailable.",
                              "Route ratio is a geometric reference, not a feasible tactical route."]}
    gun = chronology.gun_time
    start_port_code = "RM8"
    start_stbd_code = "RM6"
    if hasattr(sess, "course_sequences") and sess.course_sequences:
        g0 = sess.course_sequences[0].get("gate", {})
        p_id = g0.get("port_asset_id")
        s_id = g0.get("starboard_asset_id")
        p_code = UUID_TO_MARK.get(p_id)
        s_code = UUID_TO_MARK.get(s_id)
        if not p_code:
            for c, m in ingest_result.marks.items():
                if getattr(m, "asset_id", None) == p_id:
                    p_code = c
                    break
        if not s_code:
            for c, m in ingest_result.marks.items():
                if getattr(m, "asset_id", None) == s_id:
                    s_code = c
                    break
        if p_code and p_code in ingest_result.marks:
            start_port_code = p_code
        if s_code and s_code in ingest_result.marks:
            start_stbd_code = s_code

    for code, boat in ingest_result.boats.items():
        boat.source_coverage = ingest_result.stream_coverage.get(code) if getattr(ingest_result, "stream_coverage", None) else None
        comp = comps[code]
        active = _race_window(comp, chronology, times)
        events = [event for event in manoeuvres_by_boat.get(code, [])
                  if active and active[0] <= event.timestamp <= active[1]]
        item = {"id": boat.asset_id, "team_code": code, "team_name": boat.name,
                "color": boat.color, "classification": comp.classification,
                "official_rank": comp.official_rank if comp.classification.startswith("RANK_") else None,
                "official_elapsed_s": comp.elapsed_s if comp.classification.startswith("RANK_") else None,
                "metrics": {}, "start": {}, "legs": [], "manoeuvres": [], "gates": [], "boundary_periods": [],
                "source_coverage": boat.source_coverage, "source_conflicts": []}
        raw_events = getattr(ingest_result, "competitor_events", {}).get(boat.asset_id, [])
        nested_started = [e.get("start_state", {}).get("started") for e in raw_events if isinstance(e.get("start_state"), dict) and isinstance(e["start_state"].get("started"), bool)]
        if nested_started and not any(nested_started) and comp.start.crossing_time is not None:
            item["source_conflicts"].append("source start_state.started is false, but a start crossing was reconstructed")
            result["limitations"].append(f"{code}: source start state conflicts with reconstructed crossing; result requires adjudication.")
        at_gun = _boat_at(gun, times, boat)
        port = _mark_at(gun, times, ingest_result.marks[start_port_code]) if start_port_code in ingest_result.marks else None
        stbd = _mark_at(gun, times, ingest_result.marks[start_stbd_code]) if start_stbd_code in ingest_result.marks else None
        gun_metrics = {}
        if at_gun and port and stbd:
            bow = compute_bow_position(at_gun[0], at_gun[1], at_gun[2])
            distance, fraction, nx, ny = start_line_geometry(bow, port, stbd, sess.course_axis_deg)
            velx = at_gun[4] * KT_TO_MPS * math.sin(math.radians(at_gun[3]))
            vely = at_gun[4] * KT_TO_MPS * math.cos(math.radians(at_gun[3]))
            gun_metrics = {"start_distance_m": _metric(distance, "m"),
                           "start_along_line": _metric(fraction, "fraction"),
                           "start_sog_kt": _metric(at_gun[4], "kt"),
                           "start_closing_kt": _metric((velx * nx + vely * ny) / KT_TO_MPS, "kt")}
        item["metrics"].update(gun_metrics)
        item["start"] = {"crossing_time_ms": comp.start.crossing_time, "crossing_order": start_order.get(code),
                         "ocs": comp.start.ocs, "gun": {"timestamp": gun, "metrics": gun_metrics}}
        gates = sorted(comp.gates, key=lambda g: g.leg)
        item["gates"] = [_gate_analysis(g, times, boat, ingest_result.marks) for g in gates]
        previous = comp.start.crossing_time if active else None
        leg_bins = {}
        for leg in range(1, total_legs + 1):
            gate = next((g for g in gates if g.leg == leg), None)
            end = gate.crossing_time if gate and previous is not None else None
            if end is None and leg == max((g.leg for g in gates), default=0) + 1 and active:
                end = active[1]  # one partial, observed leg for non-finishers
            if previous is not None and end is not None and end > previous:
                values = _leg_metrics(previous, end, leg, times, boat, sess.course_axis_deg, events)
                metrics, bins = values if isinstance(values, tuple) else (values, {})
                leg_bins[leg] = bins
                if gate is None:
                    for metric in metrics.values():
                        if metric["value"] is not None:
                            metric["quality"] = "partial"
                            metric["reason"] = "observed incomplete leg through telemetry end"
            else:
                metrics = _unavailable_leg("previous or current gate missing")
            item["legs"].append({"leg": leg, "start_ms": previous, "end_ms": end,
                                 "complete": gate is not None and previous is not None,
                                 "metrics": metrics, "gate": next((g for g in item["gates"] if g["leg"] == leg), None),
                                 "twa_bins_s": leg_bins.get(leg, {})})
            previous = gate.crossing_time if gate and previous is not None else None
        item["manoeuvres"] = [_event_analysis(m, times, boat, leg_by_boat.get(code, []), gates) for m in events]
        for kind in ("TACK", "GYBE"):
            group = [m for m in item["manoeuvres"] if m["type"] == kind]
            losses = [m["speed_loss_kt"] for m in group if m["speed_loss_kt"] is not None]
            recoveries = [m["recovery_time_s"] for m in group if m["recovery_time_s"] is not None]
            stem = kind.lower()
            item["metrics"][stem + "_count"] = _metric(len(group), "events", "reconstructed", sample_count=len(group))
            item["metrics"][stem + "_loss_median_kt"] = _metric(median(losses) if losses else None, "kt", "reconstructed", reason="no detected events" if not losses else None, sample_count=len(losses))
            item["metrics"][stem + "_recovery_median_s"] = _metric(median(recoveries) if recoveries else None, "s", "derived", reason="no recovered events" if not recoveries else None, sample_count=len(recoveries))
        if active:
            observed = [l["metrics"] for l in item["legs"] if l["metrics"].get("distance_m", {}).get("value") is not None]
            distance = sum(m["distance_m"]["value"] for m in observed)
            duration = sum(m["sog_mean_kt"]["coverage_s"] or 0 for m in observed)
            for metric_id in ("distance_m", "sog_mean_kt", "course_vmg_kt", "wind_vmg_kt"):
                if metric_id == "distance_m":
                    item["metrics"][metric_id] = _metric(distance if observed else None, "m", "derived" if comp.finish_time_ms is not None and duration >= 0.95 * ((active[1] - active[0]) / 1000) else "partial", duration, "no valid track" if not observed else ("race did not finish" if comp.finish_time_ms is None else None))
                else:
                    weight = sum((m[metric_id]["coverage_s"] or 0) for m in observed if m.get(metric_id, {}).get("value") is not None)
                    value = sum(m[metric_id]["value"] * (m[metric_id]["coverage_s"] or 0) for m in observed if m.get(metric_id, {}).get("value") is not None) / weight if weight else None
                    item["metrics"][metric_id] = _metric(value, "kt", "derived" if comp.finish_time_ms is not None and weight >= 0.95 * ((active[1] - active[0]) / 1000) else "partial", weight, "insufficient valid samples" if value is None else ("race did not finish" if comp.finish_time_ms is None else None))
            timeline = sorted(sess.boundary_timeline, key=lambda x: x["t"])
            boundary_min = math.inf
            buffer_s = outside_s = valid_s = 0.0
            outside_start = None
            outside_end = None
            for a, b, dt in _samples_between(*active, times):
                mid = (a + b) // 2
                state = _boat_at(mid, times, boat)
                if state is None:
                    if outside_start is not None and outside_end - outside_start >= 1000:
                        item["boundary_periods"].append({"start_ms": outside_start, "end_ms": outside_end})
                    outside_start = outside_end = None
                    continue
                polygon = _active_polygon(mid, timeline, sess.race_boundary)
                d = signed_polygon_distance_m((state[0], state[1]), polygon)
                if d is None:
                    continue
                valid_s += dt
                boundary_min = min(boundary_min, d)
                if 0 <= d <= 25:
                    buffer_s += dt
                if d < 0:
                    outside_s += dt
                    outside_start = a if outside_start is None else outside_start
                    outside_end = b
                elif outside_start is not None:
                    if outside_end - outside_start >= 1000:
                        item["boundary_periods"].append({"start_ms": outside_start, "end_ms": outside_end})
                    outside_start = outside_end = None
            if outside_start is not None and outside_end - outside_start >= 1000:
                item["boundary_periods"].append({"start_ms": outside_start, "end_ms": outside_end})
            bquality = "derived" if valid_s >= 0.95 * ((active[1] - active[0]) / 1000) else "partial"
            item["metrics"].update({"boundary_nearest_m": _metric(boundary_min if valid_s else None, "m", bquality, valid_s, "no valid position or race polygon" if not valid_s else None),
                                    "boundary_buffer_s": _metric(buffer_s if valid_s else None, "s", bquality, valid_s, "no valid position or race polygon" if not valid_s else None),
                                    "boundary_outside_s": _metric(outside_s if valid_s else None, "s", bquality, valid_s, "no valid position or race polygon" if not valid_s else None)})
        else:
            for key, unit in (("distance_m", "m"), ("sog_mean_kt", "kt"), ("course_vmg_kt", "kt"), ("wind_vmg_kt", "kt"),
                              ("boundary_nearest_m", "m"), ("boundary_buffer_s", "s"), ("boundary_outside_s", "s")):
                item["metrics"][key] = _metric(None, unit, reason="no valid racing window (OCS/RET or missing start)")
        result["boats"].append(item)
    # Shared checkpoint deltas use actual crossing timestamps, not continuous progress estimates.
    for leg in range(1, total_legs + 1):
        times_at_gate = [b["legs"][leg - 1]["end_ms"] for b in result["boats"] if b["legs"][leg - 1]["complete"]]
        if not times_at_gate:
            continue
        leader = min(times_at_gate)
        ranking = {t: i + 1 for i, t in enumerate(sorted(times_at_gate))}
        for b in result["boats"]:
            g = b["legs"][leg - 1]["gate"]
            if g and b["legs"][leg - 1]["complete"]:
                g["split_to_leader_s"] = round((g["crossing_time_ms"] - leader) / 1000, 3)
                g["checkpoint_rank"] = ranking[g["crossing_time_ms"]]
                previous_gate = b["legs"][leg - 2]["gate"] if leg > 1 else None
                if previous_gate and previous_gate.get("split_to_leader_s") is not None:
                    g["split_change_s"] = round(g["split_to_leader_s"] - previous_gate["split_to_leader_s"], 3)
                    g["rank_change"] = g["checkpoint_rank"] - previous_gate["checkpoint_rank"]
                else:
                    g["split_change_s"] = None
                    g["rank_change"] = None
    result["boats"].sort(key=lambda b: (b["official_rank"] is None, b["official_rank"] or 999, b["team_code"]))
    # Official wind is a roughly 1 Hz asset. Use circular differences from first valid sample.
    raw_wind = [w for w in ingest_result.official_wind.raw_timeline if chronology.gun_time <= w["t"] <= chronology.window_end and 0 <= w["twd_deg"] < 360]
    if raw_wind:
        baseline = raw_wind[0]["twd_deg"]
        shifts = [circular_delta_deg(baseline, w["twd_deg"]) for w in raw_wind]
        local_by_boat = defaultdict(list)
        fleet = []
        for w in raw_wind:
            t = w["t"]
            local = []
            for code, source_boat in ingest_result.boats.items():
                window = _race_window(comps[code], chronology, times)
                if not window or not window[0] <= t <= window[1] or not _source_valid(source_boat, t, ("twd",)):
                    continue
                state = _boat_at(t, times, source_boat)
                if state is None:
                    continue
                delta = circular_delta_deg(w["twd_deg"], state[5])
                if abs(delta) > 60:  # sensor outlier relative to official asset
                    continue
                local.append(delta)
                local_by_boat[code].append(delta)
            if len(local) >= 2:
                fleet.append({"timestamp": t, "active_boats": len(local),
                              "spread_deg": round(max(local) - min(local), 2)})
        result["wind"] = {"source": "official wind asset", "baseline_twd_deg": baseline,
                          "sample_count": len(raw_wind), "shift_min_deg": round(min(shifts), 2),
                          "shift_max_deg": round(max(shifts), 2), "timeline": [
                              {"timestamp": w["t"], "shift_deg": round(circular_delta_deg(baseline, w["twd_deg"]), 2),
                               "tws_kt": w["tws_kt"]} for w in raw_wind[::max(1, len(raw_wind) // 180)]],
                          "fleet_timeline": fleet[::max(1, len(fleet) // 180)],
                          "boat_exposure": [{"team_code": code, "sample_count": len(values),
                                             "median_local_minus_official_deg": round(median(values), 2)}
                                            for code, values in sorted(local_by_boat.items())]}
    else:
        result["wind"] = {"source": "official wind asset", "reason": "no official wind in race window",
                          "baseline_twd_deg": None, "sample_count": 0, "shift_min_deg": None,
                          "shift_max_deg": None, "timeline": [], "fleet_timeline": [], "boat_exposure": []}
    # One-second pairwise samples in common active windows; same-leg only.
    boats = result["boats"]
    for i, a in enumerate(boats):
        for b in boats[i + 1:]:
            wa = _race_window(comps[a["team_code"]], chronology, times)
            wb = _race_window(comps[b["team_code"]], chronology, times)
            if not wa or not wb:
                continue
            start, end = max(wa[0], wb[0]), min(wa[1], wb[1])
            by_leg = defaultdict(list)
            for t in range(((start + 999) // 1000) * 1000, end, 1000):
                idx = min(len(times) - 1, bisect_left(times, t))
                la = leg_by_boat.get(a["team_code"], [])
                lb = leg_by_boat.get(b["team_code"], [])
                if not la or not lb or not 1 <= la[idx] <= total_legs or la[idx] != lb[idx]:
                    continue
                pa = _boat_at(t, times, ingest_result.boats[a["team_code"]])
                pb = _boat_at(t, times, ingest_result.boats[b["team_code"]])
                if pa and pb:
                    axis = math.radians(sess.course_axis_deg)
                    lateral = (pb[0] - pa[0]) * math.cos(axis) - (pb[1] - pa[1]) * math.sin(axis)
                    by_leg[la[idx]].append((math.hypot(pb[0] - pa[0], pb[1] - pa[1]), abs(lateral)))
            if by_leg:
                result["pairs"].append({"boat_a": a["team_code"], "boat_b": b["team_code"],
                                        "legs": [{"leg": leg, "sample_count": len(vals),
                                                  "median_spatial_m": round(median(v[0] for v in vals), 2),
                                                  "median_lateral_m": round(median(v[1] for v in vals), 2)}
                                                 for leg, vals in sorted(by_leg.items())]})
    result["event_feed"] = build_event_feed(result)
    return result


def build_historical_index(catalog_path="public/data/manifests.json", analysis_dir="public/data/analysis"):
    """Build from catalog entries only; count boat-races, not telemetry frames."""
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    entries = [r for group in catalog.get("regattas", []) for r in group.get("races", [])]
    if not entries:
        entries = catalog.get("races", [])
    races = []
    groups = defaultdict(list)
    event_groups = defaultdict(list)
    for entry in sorted(entries, key=lambda r: (r.get("date", ""), r.get("id", ""))):
        race_id = entry.get("id")
        if not race_id or not race_id.replace("_", "").replace("-", "").isalnum():
            continue
        path = os.path.join(analysis_dir, race_id + ".json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            detail = json.load(f)
        if detail.get("schema_version") != SCHEMA_VERSION or detail.get("race", {}).get("id") != race_id:
            continue
        race = detail["race"]
        compact = []
        for boat in detail["boats"]:
            metrics = {key: boat["metrics"][key] for key in ("distance_m", "sog_mean_kt", "course_vmg_kt", "wind_vmg_kt",
                                                             "tack_loss_median_kt", "gybe_loss_median_kt") if key in boat["metrics"]}
            observation = {key: boat.get(key) for key in ("id", "team_code", "team_name", "color", "classification", "official_rank", "official_elapsed_s")}
            observation["metrics"] = metrics
            start = boat.get("start") or {}
            observation["start"] = {"crossing_time_ms": start.get("crossing_time_ms"),
                                    "delta_to_gun_s": (start["crossing_time_ms"] - race["gun_time_ms"]) / 1000
                                    if start.get("crossing_time_ms") is not None and race.get("gun_time_ms") is not None and not start.get("ocs") else None,
                                    "crossing_order": start.get("crossing_order"),
                                    "ocs": start.get("ocs", False)}
            observation["legs"] = [{"leg": leg["leg"], "complete": leg["complete"],
                                    **{metric_id: leg["metrics"].get(metric_id) for metric_id in
                                       ("elapsed_s", "course_vmg_kt", "wind_vmg_kt", "distance_m")}}
                                   for leg in boat.get("legs", [])]
            compact.append(observation)
            group_key = (boat["team_code"], race["boat_class"], race["race_type"])
            groups[group_key].append(
                {"race_id": race_id, "date": race["date"], "classification": boat["classification"],
                 "official_rank": boat["official_rank"], "metrics": metrics,
                 "start": observation["start"], "legs": observation["legs"]})
            event_groups[group_key].extend({"race_id": race_id, "type": event["type"],
                                            "loss_kt": event.get("speed_loss_kt"),
                                            "recovery_s": event.get("recovery_time_s")}
                                           for event in boat.get("manoeuvres", []))
        races.append({"id": race_id, "name": race["name"], "date": race["date"],
                      "boat_class": race["boat_class"], "race_type": race["race_type"],
                      "analysis_file": "analysis/" + race_id + ".json", "boat_count": len(compact),
                      "result_provenance": race.get("result_provenance"),
                      "limitations": detail.get("limitations", []), "boats": compact})
    histories = []
    for (team, boat_class, race_type), observations in sorted(groups.items()):
        summary = {}
        keys = sorted({key for o in observations for key in o["metrics"]})
        for key in keys:
            values = [o["metrics"][key]["value"] for o in observations if key in o["metrics"] and o["metrics"][key]["value"] is not None and o["metrics"][key]["quality"] not in ("partial", "unavailable")]
            if values:
                summary[key] = {"median": round(median(values), 4), "min": round(min(values), 4),
                                "max": round(max(values), 4), "count": len(values)}
        leg_summary = {}
        max_leg = max((leg["leg"] for obs in observations for leg in obs["legs"]), default=0)
        for leg_number in range(1, max_leg + 1):
            measured = {}
            for metric_id in ("elapsed_s", "course_vmg_kt", "wind_vmg_kt", "distance_m"):
                values = [leg[metric_id]["value"] for obs in observations for leg in obs["legs"]
                          if leg["leg"] == leg_number and leg["complete"] and leg.get(metric_id)
                          and leg[metric_id]["value"] is not None
                          and leg[metric_id]["quality"] not in ("partial", "unavailable")]
                if values:
                    measured[metric_id] = {"median": round(median(values), 4), "min": round(min(values), 4),
                                           "max": round(max(values), 4), "count": len(values)}
            if measured:
                leg_summary[str(leg_number)] = measured
        manoeuvre_summary = {}
        for kind in ("TACK", "GYBE"):
            events = [event for event in event_groups[(team, boat_class, race_type)] if event["type"] == kind]
            losses = [event["loss_kt"] for event in events if event["loss_kt"] is not None]
            recoveries = [event["recovery_s"] for event in events if event["recovery_s"] is not None]
            origins = defaultdict(int)
            for event in events:
                origins[event["race_id"]] += 1
            manoeuvre_summary[kind] = {"event_count": len(events), "race_count": len(origins),
                                        "origin_races": dict(sorted(origins.items())),
                                        "loss_p10_kt": round(_weighted_quantile([(v, 1) for v in losses], 0.1), 4) if losses else None,
                                        "loss_median_kt": round(median(losses), 4) if losses else None,
                                        "loss_p90_kt": round(_weighted_quantile([(v, 1) for v in losses], 0.9), 4) if losses else None,
                                        "recovery_median_s": round(median(recoveries), 4) if recoveries else None,
                                        "unrecovered_count": len(events) - len(recoveries)}
        histories.append({"team_code": team, "boat_class": boat_class, "race_type": race_type,
                          "race_count": len(observations), "observations": observations, "summary": summary,
                          "leg_summary": leg_summary, "manoeuvre_summary": manoeuvre_summary})
    return {"schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
            "races": races, "histories": histories}


def export_analysis_artifacts(detail, catalog_path="public/data/manifests.json", analysis_dir="public/data/analysis"):
    os.makedirs(analysis_dir, exist_ok=True)
    detail_path = os.path.join(analysis_dir, detail["race"]["id"] + ".json")
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, separators=(",", ":"), allow_nan=False)
    index = build_historical_index(catalog_path, analysis_dir)
    index_path = os.path.join(analysis_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), allow_nan=False)
    return detail_path, index_path
