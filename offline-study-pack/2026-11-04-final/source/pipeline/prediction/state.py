"""Forward-only state filtering, geometry and empirical outage certification."""
from __future__ import annotations
import bisect
import math
import numpy as np


def transition(dt: float, q: float) -> tuple[np.ndarray, np.ndarray]:
    f = np.eye(4)
    f[:2, 2:] = np.eye(2)*dt
    covariance = q*np.block([[np.eye(2)*dt**3/3, np.eye(2)*dt**2/2],
                             [np.eye(2)*dt**2/2, np.eye(2)*dt]])
    return f, covariance


class PositionFilter:
    def __init__(self, *, q=0.8, r=9.0):
        self.q, self.r, self.t, self.mean, self.cov = q, r, None, None, None

    def predict(self, timestamp_ms):
        if self.t is None or timestamp_ms < self.t:
            raise ValueError("Prediction requires a past filtered observation")
        f, noise = transition((timestamp_ms-self.t)/1000, self.q)
        return f@self.mean, f@self.cov@f.T+noise

    def observe(self, timestamp_ms, xy):
        if self.t is None:
            self.mean = np.r_[xy, [0., 0.]]
            self.cov = np.diag([self.r, self.r, 400., 400.])
        else:
            m, p = self.predict(timestamp_ms)
            h = np.eye(2, 4)
            gain = np.linalg.solve(h@p@h.T+self.r*np.eye(2), h@p).T
            self.mean = m+gain@(np.asarray(xy)-h@m)
            # Joseph form preserves positive covariance under rounding.
            a = np.eye(4)-gain@h
            self.cov = a@p@a.T+self.r*gain@gain.T
        self.t = timestamp_ms


def project(latitude, longitude, origin):
    lat0, lon0 = origin
    return np.array([(longitude-lon0)*111320*math.cos(math.radians(lat0)),
                     (latitude-lat0)*111320])


class CausalRace:
    def __init__(self, metadata, rows, *, q=0.8, r=9.):
        self.meta, self.q, self.r = metadata, q, r
        self.by_stream = {}
        for row in rows:
            self.by_stream.setdefault((row["asset_id"], row["field"]), []).append(row)
        self.times = {k: [x.get("bucket_closed_at_ms",x["timestamp_ms"]) for x in v] for k, v in self.by_stream.items()}
        first = next((x for x in rows if x.get("latitude") is not None and x.get("longitude") is not None
                      and math.isfinite(x["latitude"]) and math.isfinite(x["longitude"])), None)
        self.origin = (first["latitude"], first["longitude"]) if first else (0., 0.)
        self.positions, self.position_available_times = {}, {}
        for (aid, field), stream in self.by_stream.items():
            if field != "gnss_position":
                continue
            filt, states, available_times = PositionFilter(q=q, r=r), [], []
            for row in stream:
                if (row.get("latitude") is None or row.get("longitude") is None or
                    not math.isfinite(row["latitude"]) or not math.isfinite(row["longitude"])):
                    continue
                filt.observe(row["timestamp_ms"], project(row["latitude"], row["longitude"], self.origin))
                states.append((filt.t, filt.mean.copy(), filt.cov.copy()))
                available_times.append(row.get("bucket_closed_at_ms",row["timestamp_ms"]))
            self.positions[aid] = states
            self.position_available_times[aid] = available_times

    def latest(self, aid, field, cutoff):
        key = (aid, field)
        index = bisect.bisect_right(self.times.get(key, []), cutoff)-1
        return self.by_stream[key][index] if index >= 0 else None

    def position(self, aid, cutoff):
        states = self.positions.get(aid, [])
        index = bisect.bisect_right(self.position_available_times.get(aid,[]), cutoff)-1
        if index < 0 or index >= len(states):
            return None
        t, mean, covariance = states[index]
        f, noise = transition((cutoff-t)/1000, self.q)
        m, p = f@mean, f@covariance@f.T+noise
        radius = math.sqrt(5.991*max(np.linalg.eigvalsh(p[:2, :2])))
        return {"xy": m[:2], "velocity": m[2:], "covariance": p,
                "source_age_ms": cutoff-t, "radius_95_m": radius}

    def session(self, cutoff):
        return next((s for s in reversed(self.meta["sessions"]) if int(s["timestamp"]) <= cutoff), None)

    def competitor(self, aid, cutoff):
        return next((e for e in reversed(self.meta["competitor_events"])
                     if e["asset_id"] == aid and int(e["timestamp"]) <= cutoff), None)

    def features(self, aid, cutoff, certificate=None):
        session, position = self.session(cutoff), self.position(aid, cutoff)
        event = self.competitor(aid, cutoff)
        classification = (event or {}).get("classification", "").upper()
        if session and event and cutoff >= int(session["race_start"]):
            for suffix, terminal in (("RETIRED", "ret"), ("DID_NOT_START", "dns")):
                if classification.endswith(suffix):
                    return {"quality":"available", "terminal_status":terminal,
                            "current_leg":0, "remaining_fraction":1.,
                            "elapsed_s":(cutoff-int(session["race_start"]))/1000,
                            "reason":"observed_source_terminal_classification"}
            if any(p.get("type") == "PENALTY_TYPE_DISQUALIFIED" and p.get("state") == "PENALTY_STATE_ACTIVE"
                   and int(p.get("awarded_at") or 0) <= cutoff for p in event.get("penalties", [])):
                return {"quality":"available", "terminal_status":"disqualified",
                        "current_leg":0, "remaining_fraction":1.,
                        "elapsed_s":(cutoff-int(session["race_start"]))/1000,
                        "reason":"observed_source_disqualification"}
        if not session or not position or (event is None and not self.meta.get("competitor_events")):
            return {"quality": "unavailable", "reason": "missing_causal_state"}
        event = event or {}
        sequences = session["race_course"]["sequences"]
        gates = {int(g["leg_number"]): int(g["gate_time"]) for g in event.get("leg_timings", [])
                 if g.get("gate_time") and int(g["gate_time"]) <= cutoff}
        final_leg = len(sequences)-1
        if len(gates) >= 1:
            for k in range(1, final_leg):
                upper_t = gates.get(k+1, cutoff+1)
                if k not in gates and (k-1 in gates) and gates[k-1] < upper_t:
                    gate_marks = {sequences[k]["gate"].get("port_asset_id"),
                                  sequences[k]["gate"].get("starboard_asset_id")}
                    evs = [e for e in self.meta.get("competitor_events", [])
                           if e["asset_id"] == aid and int(e["timestamp"]) <= cutoff]
                    zone_ev = next((ev for ev in evs
                                    if (ev.get("mark_zone_state") or {}).get("inside") is True
                                    and (ev.get("mark_zone_state") or {}).get("mark_id") in gate_marks
                                    and gates[k-1] < int(ev["timestamp"]) < upper_t), None)
                    leg_ev = next((ev for ev in evs
                                   if (ev.get("course_position") or {}).get("leg_number") == k+1
                                   and gates[k-1] < int(ev["timestamp"]) <= min(cutoff, upper_t)), None)
                    if zone_ev is not None and leg_ev is not None:
                        gates[k] = int(zone_ev["timestamp"])
        last_gate = max(gates, default=-1)
        result = {"source_age_ms": position["source_age_ms"], "radius_95_m": position["radius_95_m"],
                  "quality": "available" if position["source_age_ms"] <= 2000 else "estimated"}
        penalties = event.get("penalties", [])
        cleared_ocs = (0 in gates) and any(
            p.get("reason") == "PENALTY_REASON_OCS" and p.get("state") == "PENALTY_STATE_CLEARED"
            and p.get("cleared_at") and int(p["cleared_at"]) <= cutoff for p in penalties
        )
        started_valid = bool(event.get("start_state", {}).get("started")) or cleared_ocs
        race_start_ms = int(session["race_start"])
        if last_gate >= 1 and not started_valid:
            return dict(result, quality="gate_ambiguous", reason="start_not_validated")
        if last_gate < 1 and not started_valid:
            if cutoff - race_start_ms > 180000:
                if last_gate < 0:
                    return {"quality":"available", "terminal_status":"dns",
                            "current_leg":0, "remaining_fraction":1.,
                            "elapsed_s":(cutoff-race_start_ms)/1000,
                            "reason":"start_window_closed_dns"}
                return dict(result, quality="gate_ambiguous", reason="start_not_validated")
        if last_gate >= 0 and (last_gate >= len(sequences) or set(gates) != set(range(last_gate+1))
                or any(gates[i] >= gates[i+1] for i in range(last_gate))):
            return dict(result, quality="gate_ambiguous", reason="source_gate_chain_incomplete_or_reversed")
        if last_gate >= len(sequences)-1:
            return dict(result, terminal_status="finished", finished_at_s=(gates[last_gate]-race_start_ms)/1000,
                        current_leg=len(sequences)-2, remaining_fraction=0., reason="source_finish_timing")
        current = max(0, last_gate)  # simulator leg zero is start -> first course gate
        targets, mark_variances = [], []
        for seq in (sequences[current], sequences[current+1]):
            endpoints = []
            for mark in (seq["gate"]["port_asset_id"], seq["gate"]["starboard_asset_id"]):
                p = self.latest(mark, "gnss_position", cutoff)
                # Stationary race marks allow a bounded 30-second hold with inflating variance.
                if not p or cutoff-p["timestamp_ms"] > 30000:
                    return dict(result, quality="gate_ambiguous", reason="mark_state_missing_or_stale")
                mark_variances.append(9.+.25*(cutoff-p["timestamp_ms"])/1000)
                endpoints.append(project(p["latitude"], p["longitude"], self.origin))
            targets.append(np.array(endpoints))
        a, b = targets[0].mean(axis=0), targets[1].mean(axis=0)
        length = float(np.linalg.norm(b-a))
        if length < 1:
            return dict(result, quality="gate_ambiguous", reason="invalid_leg_geometry")
        axis = (b-a)/length
        along = float(np.dot(position["xy"]-a, axis))
        remaining = 1.0 if last_gate < 0 else (length-along)/length
        # A predicted line crossing cannot establish the next phase.
        mark_radius = math.sqrt(5.991*max(mark_variances)/2)
        if (remaining < 0 or (last_gate >= 0 and remaining > 1.3)
                or (position["source_age_ms"] > 2000 and position["radius_95_m"]+mark_radius >= abs(length-along))):
            return dict(result, quality="gate_ambiguous", reason="gate_phase_or_crossing_uncertain")
        cog, old = self.latest(aid, "course_over_ground", cutoff), self.latest(aid, "course_over_ground", cutoff-10000)
        turn = abs(((cog["value"]-old["value"]+180)%360)-180)/10 if cog and old else 0.
        speed, speed_old = self.latest(aid, "speed_over_ground", cutoff), self.latest(aid, "speed_over_ground", cutoff-10000)
        accel = ((speed["value"]-speed_old["value"])/10 if speed and speed_old
                 and cutoff-speed["timestamp_ms"] <= 2000 and cutoff-10000-speed_old["timestamp_ms"] <= 2000 else None)
        stratum = "gate" if remaining < .1 else "turn" if turn > 3 else "recovery" if accel is not None and accel > .3 else "steady"
        certified = (certificate or {}).get(stratum, {}).get("horizon_s", 0)
        if position["source_age_ms"] > max(2000, certified*1000):
            return dict(result, quality="unavailable", reason="outage_horizon_not_certified")
        if position["radius_95_m"] > min(50, .1*length):
            return dict(result, quality="unavailable", reason="position_uncertainty_exceeds_gate")
        return dict(result, current_leg=current, remaining_fraction=min(1., max(0., remaining)),
                    remaining_fraction_sd=math.sqrt(float(axis@position["covariance"][:2,:2]@axis)+max(mark_variances)/2)/length,
                    along_m=along, cross_m=float(axis[0]*(position["xy"]-a)[1]-axis[1]*(position["xy"]-a)[0]),
                    leg_length_m=length, mark_uncertainty_radius_95_m=mark_radius,
                    gate_width_m=float(np.linalg.norm(targets[1][1]-targets[1][0])),
                    vmg_mps=float(position["velocity"]@axis),
                    acceleration_mps2=accel,
                    turn_rate_deg_s=turn, stratum=stratum, elapsed_s=(cutoff-race_start_ms)/1000,
                    reason="causal_raw_state")


def fit_filter_parameters(races):
    """Conservative pooled innovation estimates from strictly earlier raw positions.

    GNSS noise and real acceleration cannot be fully separated at 1 Hz. Upper-quantile
    racing accelerations ensure 95% filter ellipses cover manoeuvres and short outages.
    """
    differences = []
    dates = set()
    for metadata, rows in races:
        if metadata.get("practice"):
            continue
        dates.add(metadata["date"])
        gun_ms = int(metadata.get("gun_ms", 0))
        end_ms = int(metadata.get("window_end_ms", 1 << 60))
        streams={}
        for row in rows:
            t_ms = int(row["timestamp_ms"])
            if (gun_ms <= t_ms <= end_ms and row["field"]=="gnss_position" and row["asset_id"] in metadata["boat_ids"]
                    and row.get("latitude") is not None and row.get("longitude") is not None
                    and math.isfinite(row["latitude"]) and math.isfinite(row["longitude"])):
                streams.setdefault(row["asset_id"],[]).append(row)
        for aid in metadata["boat_ids"]:
            stream=streams.get(aid,[])
            if len(stream)<3:
                continue
            times=np.array([r["timestamp_ms"] for r in stream],float)/1000
            origin=(stream[0]["latitude"],stream[0]["longitude"])
            xy=np.array([project(r["latitude"],r["longitude"],origin) for r in stream])
            dt=np.diff(times)
            valid=(dt[:-1]>=.5)&(dt[1:]>=.5)&(dt[:-1]<=1.5)&(dt[1:]<=1.5)
            velocity=np.diff(xy,axis=0)/np.maximum(dt[:,None],1e-6)
            accel=np.diff(velocity,axis=0)/np.maximum((dt[:-1]+dt[1:])[:,None]/2,1e-6)
            differences.extend((np.sum(accel[valid]**2,axis=1)/2).tolist())
    scale = float(np.percentile(differences, 96)) if differences else 8.4
    return {"q": max(.2, min(20., scale)), "r": max(.25, min(25., scale/4)),
            "training_dates": sorted(dates), "innovation_count": len(differences),
            "method": "pooled-p96-racing-second-difference; noise-motion-confounded; mask certification required"}


def certify_outages(races, *, horizons=(2, 5, 10, 20, 30, 60, 90), parameters=None):
    """Nonoverlapping position masks. Independent race dates and strata remain explicit.

    Only a contiguous passing prefix is certified. Unobserved strata never inherit
    the steady-state certificate. Natural outages are excluded from the truth set.
    """
    records = {s: {h: [] for h in horizons} for s in ("steady", "turn", "gate", "recovery")}
    by_date = {day: fit_filter_parameters([(m,r) for m,r in races if m["date"] < day])
               for day in sorted({m["date"] for m,r in races})}
    for metadata, rows in races:
        if metadata.get("practice"):
            continue
        # The hidden mask/date cannot fit its own process/noise parameters.
        prior_parameters = by_date[metadata["date"]]
        race = CausalRace(metadata, rows, **{k:v for k,v in prior_parameters.items() if k in ("q", "r")})
        for aid in metadata["boat_ids"]:
            states = race.positions.get(aid, [])
            times = [s[0] for s in states]
            raw_truth={r["timestamp_ms"]:r for r in race.by_stream.get((aid,"gnss_position"),[])
                       if r.get("latitude") is not None and r.get("longitude") is not None}
            next_start = 0
            for i in range(15, len(states)):
                t, mean, covariance = states[i]
                mask_start=race.position_available_times[aid][i]
                if mask_start < next_start or mask_start < metadata["gun_ms"]:
                    continue
                next_start = mask_start+max(horizons)*1000+10000
                feature = race.features(aid, mask_start)
                stratum = feature.get("stratum")
                if not stratum:
                    continue
                for h in horizons:
                    target=mask_start+h*1000
                    j = bisect.bisect_left(times, target)
                    if j >= len(times) or abs(times[j]-target) > 1100:
                        continue
                    # No observed gap inside the hidden block: genuine complete truth only.
                    if any(b-a > 2000 for a,b in zip(times[i:j], times[i+1:j+1])):
                        continue
                    f, q = transition((times[j]-t)/1000, race.q)
                    pred, p = f@mean, f@covariance@f.T+q
                    truth = raw_truth[times[j]]
                    delta = project(truth["latitude"], truth["longitude"], race.origin)-pred[:2]
                    metric = float(delta@np.linalg.solve(p[:2,:2]+race.r*np.eye(2), delta))
                    error = float(np.linalg.norm(delta))
                    records[stratum][h].append((metadata["date"], error, metric <= 5.991,
                                               error/feature["leg_length_m"]))
    result = {}
    for stratum, by_h in records.items():
        horizon, details, contiguous = 0, {}, True
        for h, values in by_h.items():
            count, dates = len(values), len({x[0] for x in values})
            coverage = sum(x[2] for x in values)/count if count else None
            error = float(np.median([x[1] for x in values])) if count else None
            normalized = float(np.median([x[3] for x in values])) if count else None
            passed = count >= 50 and dates >= 2 and coverage >= .9 and normalized < .1
            if contiguous and passed:
                horizon = h
            else:
                contiguous = False
            details[str(h)] = {"count": count, "dates": dates, "ellipse_coverage": coverage,
                               "median_error_m": error, "median_normalized_error": normalized, "passed": passed}
        result[stratum] = {"horizon_s": horizon, "masks": details,
                           "loss_modes": ["position", "position_and_velocity_channels"],
                           "velocity_measurement_updates": False}
    return result
