"""Multi-phase kinematic match race simulator with 7-component counterfactual attribution.

Enforces:
1. Joint-finisher conditioning: time comparisons and attribution are evaluated strictly
   conditional on both boats finishing (E[Tb - Ta | both finished]).
2. Physical distance and speed scaling: leg durations are computed from physical course length
   and VMG speeds, scaling proportionally with course length.
3. Independent 7-component additive attribution:
   - pre_start_positioning_s
   - upwind_vmg_s
   - downwind_vmg_s
   - tack_execution_s
   - gybe_execution_s
   - boundary_avoidance_s
   - technical_reliability_advantage
4. Correct double non-finish handling (no_winner_probability).
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Any

import numpy as np

from .course_lvc import CoursePreset
from .models import EmpiricalPhaseDistributionModel


VALID_MODES = {
    "barcelona_2024_empirical",
    "barcelona_2024_empirical_with_ac38_rules",
    "ac40_empirical",
    "ac75_calibrated_transfer",
    "ac38_rule_explorer",
    "ac75_learned_v1",
    "ac75_learned_v2",
    "barcelona_2024_ac75_learned",
}


def simulate_kinematic_race(
    team_a: str,
    team_b: str,
    tws_kt: float,
    course_length_m: float = 2590.0,
    n_sims: int = 5000,
    seed: int = 42,
    team_effects: Mapping[str, float] | None = None,
    ac75_primitives: Mapping[str, Any] | None = None,
    course: CoursePreset | Mapping[str, Any] | None = None,
    rule_adjustments: Mapping[str, float] | None = None,
    mode: str = "barcelona_2024_empirical",
    model: EmpiricalPhaseDistributionModel | None = None,
) -> dict[str, Any]:
    """Simulates a match race between two teams with physical scaling, joint-finisher conditioning and attribution."""
    if n_sims < 1:
        raise ValueError("n_sims must be positive")
    if not math.isfinite(tws_kt) or tws_kt <= 0:
        raise ValueError("tws_kt must be finite and positive")
    if team_a == team_b:
        raise ValueError(f"Competitor teams must be distinct: got {team_a} vs {team_b}")

    rng = np.random.default_rng(seed)

    # 1. Resolve course preset
    if course is None:
        course = CoursePreset(
            preset_id="custom",
            name="Custom Match Course",
            venue="Barcelona",
            course_axis_deg=105.0,
            course_length_m=course_length_m,
            boundary_width_m=800.0,
            leg_count=6,
            default_wind_speed_kt=tws_kt,
            default_wind_dir_deg=105.0,
        )

    # 2. Build or use provided model
    if model is None:
        model = EmpiricalPhaseDistributionModel.load_from_primitives(
            primitives=ac75_primitives,
            team_effects=team_effects,
        )

    # 3. Non-finish sampling
    profile_a = model.get_profile(team_a)
    profile_b = model.get_profile(team_b)
    status_a = model.non_finish_model.sample_status(tws_kt, profile_a.reliability_factor, rng=rng, size=n_sims)
    status_b = model.non_finish_model.sample_status(tws_kt, profile_b.reliability_factor, rng=rng, size=n_sims)

    # 4. Sample independent physical time components
    comp_a = model.sample_race_components(team_a, tws_kt, course, rule_adjustments, rng=rng, size=n_sims)
    comp_b = model.sample_race_components(team_b, tws_kt, course, rule_adjustments, rng=rng, size=n_sims)

    time_a = comp_a["total_time"]
    time_b = comp_b["total_time"]

    # 5. Joint finisher mask
    both_finished = (status_a == "FINISHED") & (status_b == "FINISHED")
    n_both = int(np.sum(both_finished))

    # 6. Determine race winner per trial with strict double non-finish handling
    wins_a = np.zeros(n_sims, dtype=float)
    wins_b = np.zeros(n_sims, dtype=float)
    no_winner = np.zeros(n_sims, dtype=float)

    for i in range(n_sims):
        sa, sb = status_a[i], status_b[i]
        if sa == "FINISHED" and sb == "FINISHED":
            if time_a[i] < time_b[i]:
                wins_a[i] = 1.0
            elif time_b[i] < time_a[i]:
                wins_b[i] = 1.0
            else:
                wins_a[i] = 0.5
                wins_b[i] = 0.5
        elif sa == "FINISHED" and sb != "FINISHED":
            wins_a[i] = 1.0
        elif sb == "FINISHED" and sa != "FINISHED":
            wins_b[i] = 1.0
        else:
            # Neither boat finished
            wins_a[i] = 0.0
            wins_b[i] = 0.0
            no_winner[i] = 1.0

    # 7. Conditional time deltas & independent 7-component attribution (E[Tb - Ta | both finished])
    if n_both > 0:
        delta_times = time_b[both_finished] - time_a[both_finished]
        mean_delta = round(float(np.mean(delta_times)), 2)
        p10_delta = round(float(np.percentile(delta_times, 10)), 2)
        p50_delta = round(float(np.percentile(delta_times, 50)), 2)
        p90_delta = round(float(np.percentile(delta_times, 90)), 2)
        mean_time_a = round(float(np.mean(time_a[both_finished])), 1)
        mean_time_b = round(float(np.mean(time_b[both_finished])), 1)

        attr_pre = float(np.mean(comp_b["pre_start"][both_finished] - comp_a["pre_start"][both_finished]))
        attr_up = float(np.mean(comp_b["upwind_vmg"][both_finished] - comp_a["upwind_vmg"][both_finished]))
        attr_dn = float(np.mean(comp_b["downwind_vmg"][both_finished] - comp_a["downwind_vmg"][both_finished]))
        attr_tack = float(np.mean(comp_b["tacks"][both_finished] - comp_a["tacks"][both_finished]))
        attr_gybe = float(np.mean(comp_b["gybes"][both_finished] - comp_a["gybes"][both_finished]))
        attr_bound = float(np.mean((comp_b["boundary"][both_finished] + comp_b["finish"][both_finished]) -
                                   (comp_a["boundary"][both_finished] + comp_a["finish"][both_finished])))
        rel_adv = float(np.mean(status_a == "FINISHED") - np.mean(status_b == "FINISHED"))

        mean_attr = {
            "pre_start_positioning_s": round(attr_pre, 2),
            "upwind_vmg_s": round(attr_up, 2),
            "downwind_vmg_s": round(attr_dn, 2),
            "tack_execution_s": round(attr_tack, 2),
            "gybe_execution_s": round(attr_gybe, 2),
            "boundary_avoidance_s": round(attr_bound, 2),
            "technical_reliability_advantage": round(rel_adv, 4),
        }
    else:
        mean_delta = None
        p10_delta = p50_delta = p90_delta = None
        mean_attr = {}

    def status_summary(arr):
        return {
            "finished_rate": round(float(np.mean(arr == "FINISHED")), 4),
            "dns_rate": round(float(np.mean(arr == "DNS")), 4),
            "dnf_exogenous_rate": round(float(np.mean(arr == "DNF_exogenous")), 4),
            "ocs_dsq_rate": round(float(np.mean(arr == "OCS_DSQ")), 4),
        }

    course_dict = asdict(course) if isinstance(course, CoursePreset) else dict(course)
    course_len = float(course_dict.get("course_length_m", course_length_m))

    return {
        "schema_version": "kinematic-race-sim-1",
        "team_a": team_a,
        "team_b": team_b,
        "tws_kt": tws_kt,
        "course_length_m": course_len,
        "n_sims": n_sims,
        "mode": mode,
        "win_probability_a": round(float(np.mean(wins_a)), 4),
        "win_probability_b": round(float(np.mean(wins_b)), 4),
        "no_winner_probability": round(float(np.mean(no_winner)), 4),
        "joint_finisher_conditioning": {
            "both_finished_count": n_both,
            "both_finished_fraction": round(n_both / n_sims, 4),
            "mean_delta_t_s": mean_delta,
            "p10_delta_t_s": p10_delta,
            "p50_delta_t_s": p50_delta,
            "p90_delta_t_s": p90_delta,
            "mean_time_a_s": mean_time_a if n_both > 0 else None,
            "mean_time_b_s": mean_time_b if n_both > 0 else None,
            "scope": "Time deltas and attribution are conditioned strictly on both boats finishing; DNF excluded.",
        },
        "status_breakdown": {
            team_a: status_summary(status_a),
            team_b: status_summary(status_b),
        },
        "attribution_7_component": mean_attr,
        "course": course_dict,
        "rule_adjustments": dict(rule_adjustments) if rule_adjustments else {},
        "reproducibility": {
            "seed": seed,
            "model_contract": "student_t_nu_4_joint_finisher_physical_vmg",
        },
    }


simulate_match_trials = simulate_kinematic_race


def main():
    parser = argparse.ArgumentParser(description="AC75 Kinematic Match Simulator CLI")
    parser.add_argument("--json", type=str, required=True, help="JSON input payload")
    args = parser.parse_args()

    try:
        req = json.loads(args.json)
    except Exception as e:
        sys.stderr.write(json.dumps({"status": "unsupported_request", "error": f"Invalid JSON payload: {e}"}))
        sys.exit(2)

    team_a = req.get("team_a")
    team_b = req.get("team_b")
    tws_kt = req.get("tws_kt", 12.0)
    mode = req.get("mode", "barcelona_2024_empirical")

    if not team_a or not team_b or team_a == team_b:
        res = {"status": "unsupported_request", "error": "Invalid or identical competitors"}
        print(json.dumps(res))
        sys.exit(2)

    try:
        tws_kt = float(tws_kt)
    except (TypeError, ValueError):
        res = {"status": "unsupported_request", "error": "tws_kt must be a numeric value"}
        print(json.dumps(res))
        sys.exit(2)

    if not (6.0 <= tws_kt <= 24.0):
        res = {"status": "unsupported_request", "error": "Wind speed out of supported range [6, 24] kt"}
        print(json.dumps(res))
        sys.exit(2)

    if mode not in VALID_MODES:
        res = {"status": "unsupported_request", "error": f"Unsupported simulation mode '{mode}'"}
        print(json.dumps(res))
        sys.exit(2)

    course = req.get("course")
    rule_adjustments = req.get("rule_adjustments")
    if req.get("trial_count") is not None and req.get("n_sims") is not None:
        if int(req["trial_count"]) != int(req["n_sims"]):
            res = {"status": "unsupported_request", "error": "Contradictory trial_count and n_sims values"}
            print(json.dumps(res))
            sys.exit(2)
    trial_count_raw = req.get("trial_count") if req.get("trial_count") is not None else req.get("n_sims")
    is_v2_req = (
        mode in ("ac75_learned_v1", "ac75_learned_v2", "barcelona_2024_ac75_learned")
        or req.get("schema_version") in ("kinematic-race-sim-2", "ac75-scenario-request-1")
    )
    default_seed = 2027 if is_v2_req else 42
    seed = int(req["seed"]) if req.get("seed") is not None else default_seed

    try:
        if is_v2_req:
            from pipeline.kinematic_ml.loader import load_staged_ac75_bundle
            from pipeline.kinematic_ml.inference import PURPOSE_TRIALS, predict_scenario
            from pipeline.kinematic_ml.inventory import resolve_team_identity

            c_team_a = resolve_team_identity(str(team_a), cycle="AC37")
            c_team_b = resolve_team_identity(str(team_b), cycle="AC37")
            if c_team_a == c_team_b:
                raise ValueError(f"Competitor teams must be distinct: {c_team_a} vs {c_team_b}")

            installed_bundle = load_staged_ac75_bundle(Path(__file__).resolve().parents[2])
            if req.get("model_id") is not None and str(req["model_id"]).strip() != installed_bundle.model_id:
                raise ValueError(
                    f"Requested model_id '{req.get('model_id')}' does not match pinned installed model '{installed_bundle.model_id}'"
                )

            env_in = req.get("environment") if isinstance(req.get("environment"), dict) else {}
            tws_mps = float(
                env_in.get("tws_mps")
                if env_in.get("tws_mps") is not None
                else tws_kt * (1852.0 / 3600.0)
            )
            twd_deg = float(
                env_in.get("twd_deg")
                if env_in.get("twd_deg") is not None
                else (env_in.get("wind_from_deg") if env_in.get("wind_from_deg") is not None else req.get("twd_deg", 180.0))
            )
            twd_norm = twd_deg % 360.0
            if twd_norm == 0.0 or twd_norm == 360.0:
                twd_norm = 0.0
            course_id = str(
                req.get("course_id")
                or (course.get("preset_id") if isinstance(course, dict) else None)
                or (course.get("course_id") if isinstance(course, dict) else None)
                or "barcelona_lvc_4leg"
            )
            if req.get("purpose") is not None:
                purpose = str(req["purpose"]).strip()
                if purpose not in PURPOSE_TRIALS:
                    raise ValueError(f"Unsupported purpose '{purpose}'")
            else:
                purpose = "standard" if (trial_count_raw is not None and int(trial_count_raw) >= 10000) else "preview"
            n_sims = int(trial_count_raw) if trial_count_raw is not None else PURPOSE_TRIALS[purpose]

            scen_req = {
                "schema_version": "kinematic-race-sim-2",
                "model_id": installed_bundle.model_id,
                "team_a": c_team_a,
                "team_b": c_team_b,
                "course_id": course_id,
                "environment": {"tws_mps": tws_mps, "twd_deg": twd_norm},
                "purpose": purpose,
                "scenario_policy_id": str(req.get("scenario_policy_id", "training_observed_routes_v1")),
                "seed": seed,
                "trial_count": n_sims,
            }
            scen_res = predict_scenario(installed_bundle, scen_req)
            if scen_res.status != "available":
                res = {
                    "status": scen_res.status,
                    "reason_codes": scen_res.reason_codes,
                    "error": f"Scenario unavailable: {', '.join(scen_res.reason_codes)}",
                }
                print(json.dumps(res))
                sys.exit(2)
            print(json.dumps(scen_res.to_dict()))
            return

        n_sims = int(trial_count_raw) if trial_count_raw is not None else 1000
        out = simulate_kinematic_race(
            team_a=team_a,
            team_b=team_b,
            tws_kt=tws_kt,
            mode=mode,
            course=course,
            rule_adjustments=rule_adjustments,
            n_sims=n_sims,
            seed=seed,
        )
        print(json.dumps(out))
    except Exception as e:
        res = {"status": "unsupported_request", "error": str(e)}
        print(json.dumps(res))
        sys.exit(2)


if __name__ == "__main__":
    main()
