"""Single numerical inference entry point and learned race simulation engine (T14).

Contract (G3.2, G3.3, G3.4, G3.5, SCENARIO_INPUT_ALLOWLIST):
- predict_scenario(installed_model, normalized_request) is the single entry point.
- Purpose determines trial count: preview (2,000), standard (10,000), evaluation (20,000).
- Pure disjoint seconds accounting: straight, maneuver, start; reliability does not enter this sum.
- Probability scope: 'completion_assumed_on_water'.
- Pinned numerical reproducibility: seed and purpose determine the deterministic pseudo-random stream.
- Reversible: swapping competitor order cleanly reverses delta T and exchanges win probabilities.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from typing import Any, Mapping

import numpy as np

from pipeline.kinematic_ml.baselines import (
    BinnedPolarBaseline,
    RegularizedSplinePolarBaseline,
)
from pipeline.kinematic_ml.contracts import (
    ScenarioProbabilityDetail,
    ScenarioTimingDetail,
    ScenarioV2Result,
    validate_feature_separation,
)
from pipeline.kinematic_ml.events import (
    ManeuverDurationModel,
    StartBehaviorModel,
)
from pipeline.kinematic_ml.neural import numpy_forward_pass
from pipeline.kinematic_ml.routes import (
    LegRouteTemplate,
    RouteTemplateLibrary,
    transform_template_to_course,
)
from pipeline.kinematic_ml.uncertainty import (
    PairedResidualSampler,
    VarianceLedger,
)

PURPOSE_TRIALS = {
    "preview": 2000,
    "standard": 10000,
    "evaluation": 20000,
}

CANONICAL_TEAMS = [
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
]

COURSE_PRESETS: dict[str, dict[str, Any]] = {
    "barcelona_lvc_4leg": {
        "course_id": "barcelona_lvc_4leg",
        "label": "Barcelona 4-Leg Match (1500m)",
        "leg_count": 4,
        "leg_length_m": 1500.0,
        "course_axis_offset_deg": 0.0,
    },
    "barcelona_4leg_1500m": {
        "course_id": "barcelona_4leg_1500m",
        "label": "Barcelona 4-Leg Match (1500m)",
        "leg_count": 4,
        "leg_length_m": 1500.0,
        "course_axis_offset_deg": 0.0,
    },
    "barcelona_6leg_1500m": {
        "course_id": "barcelona_6leg_1500m",
        "label": "Barcelona 6-Leg Match (1500m)",
        "leg_count": 6,
        "leg_length_m": 1500.0,
        "course_axis_offset_deg": 0.0,
    },
    "barcelona_6leg_1852m": {
        "course_id": "barcelona_6leg_1852m",
        "label": "Barcelona 6-Leg Championship (1.0 nm)",
        "leg_count": 6,
        "leg_length_m": 1852.0,
        "course_axis_offset_deg": 0.0,
    },
    "barcelona_8leg_1852m": {
        "course_id": "barcelona_8leg_1852m",
        "label": "Barcelona 8-Leg Long Course (1.0 nm)",
        "leg_count": 8,
        "leg_length_m": 1852.0,
        "course_axis_offset_deg": 0.0,
    },
}


class InstalledModelBundle:
    """Encapsulates all fitted components required for scenario prediction."""

    def __init__(
        self,
        model_id: str,
        motion_weights: Mapping[str, np.ndarray],
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        template_library: RouteTemplateLibrary,
        *extra_pos: Any,
        **kwargs: Any,
    ) -> None:
        self.model_id = model_id
        self.motion_weights = motion_weights
        self.scaler_mean = scaler_mean
        self.scaler_scale = scaler_scale
        self.template_library = template_library
        maneuver_model = kwargs.get("maneuver_model", extra_pos[0] if len(extra_pos) > 0 else None)
        start_model = kwargs.get("start_model", extra_pos[1] if len(extra_pos) > 1 else None)
        residual_sampler = kwargs.get("residual_sampler", extra_pos[2] if len(extra_pos) > 2 else None)
        variance_ledger = kwargs.get("variance_ledger", extra_pos[3] if len(extra_pos) > 3 else None)
        self.maneuver_model: ManeuverDurationModel = maneuver_model
        self.start_model: StartBehaviorModel = start_model
        self.residual_sampler: PairedResidualSampler = residual_sampler
        self.variance_ledger = variance_ledger or VarianceLedger()
        self.selected_motion_model = str(kwargs.get("selected_motion_model", "neural"))
        self.empirical_model: BinnedPolarBaseline | None = kwargs.get("empirical_model")
        self.spline_model: RegularizedSplinePolarBaseline | None = kwargs.get("spline_model")

        motion_scale = kwargs.get("motion_residual_scale", 1.0)
        margin_scale = kwargs.get("margin_interval_scale", 1.0)
        if not isinstance(motion_scale, (int, float)) or isinstance(motion_scale, bool) or not math.isfinite(float(motion_scale)) or float(motion_scale) <= 0.0:
            raise ValueError(f"Invalid motion_residual_scale: {motion_scale}")
        if not isinstance(margin_scale, (int, float)) or isinstance(margin_scale, bool) or not math.isfinite(float(margin_scale)) or float(margin_scale) <= 0.0:
            raise ValueError(f"Invalid margin_interval_scale: {margin_scale}")
        self.motion_residual_scale: float = float(motion_scale)
        self.margin_interval_scale: float = float(margin_scale)
        cal_info = kwargs.get("calibration_info")
        self.calibration_info: dict[str, Any] = dict(cal_info) if isinstance(cal_info, Mapping) else {}
        self.schema_version: str = str(kwargs.get("schema_version", "ac75-model-1"))

    def predict_motion_distribution(
        self,
        features_dict: Mapping[str, Any],
    ) -> tuple[float, float]:
        """Returns (mu_log_sog, sigma_log_sog) in log-speed space."""
        validate_feature_separation(features_dict, task_type="motion")

        if self.selected_motion_model == "spline" and self.spline_model is not None:
            mu_log, log_sig = self.spline_model.predict_distribution(features_dict)
            raw_sig = max(0.05, math.exp(log_sig))
            return float(mu_log), float(max(0.05, raw_sig * self.motion_residual_scale))

        if self.selected_motion_model == "empirical" and self.empirical_model is not None:
            mu_log, log_sig = self.empirical_model.predict_distribution(features_dict)
            raw_sig = max(0.05, math.exp(log_sig))
            return float(mu_log), float(max(0.05, raw_sig * self.motion_residual_scale))

        if getattr(self, "schema_version", "ac75-model-1") == "ac75-model-2":
            from pipeline.kinematic_ml.feature_registry import encode_features_matrix, AC75_MODEL_SCHEMA_V2
            X, _, _ = encode_features_matrix(
                [features_dict],
                schema_version=AC75_MODEL_SCHEMA_V2,
                scaler_mean=self.scaler_mean,
                scaler_scale=self.scaler_scale,
            )
            mu, log_scale = numpy_forward_pass(X, self.motion_weights)
            raw_sig = max(0.05, math.exp(float(log_scale[0])))
            return float(mu[0]), float(max(0.05, raw_sig * self.motion_residual_scale))

        X = np.zeros((1, 14), dtype=np.float32)
        X[0, 0] = float(features_dict.get("tws_mps", 10.0))
        X[0, 1] = float(features_dict.get("twa_sin", 0.7071))
        X[0, 2] = float(features_dict.get("twa_cos", 0.7071))
        X[0, 3] = float(features_dict.get("tack_side", 1.0))
        X[0, 4] = float(features_dict.get("leg_type", 1.0))
        X[0, 5] = float(features_dict.get("heading_cog_offset_deg", 0.0))
        X[0, 6] = float(features_dict.get("course_wind_angle_deg", 0.0))
        X[0, 7] = float(features_dict.get("practice_domain", 0.0))

        tid = str(features_dict.get("team_id", ""))
        for t_idx, team in enumerate(CANONICAL_TEAMS):
            if tid == team:
                X[0, 8 + t_idx] = 1.0
                break

        X[0, :8] = (X[0, :8] - self.scaler_mean) / self.scaler_scale
        mu, log_scale = numpy_forward_pass(X, self.motion_weights)
        raw_sig = max(0.05, math.exp(float(log_scale[0])))
        return float(mu[0]), float(max(0.05, raw_sig * self.motion_residual_scale))


def _predict_sog_numpy(
    model: InstalledModelBundle,
    features_dict: Mapping[str, Any],
) -> tuple[float, float]:
    """Evaluates motion speed in m/s using pure NumPy forward pass. Returns (sog_mps, log_scale)."""
    mu_log, sigma_log = model.predict_motion_distribution(features_dict)
    sog_mps = math.exp(mu_log + 0.5 * (sigma_log ** 2))
    return float(sog_mps), float(math.log(sigma_log))


def _resolve_course_legs(
    course_id: str,
    twd_deg: float,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    """Resolves course_id (or inline spec 'custom_<legs>leg_<len>m_<axis>deg') into leg configs."""
    cid = (course_id or "barcelona_lvc_4leg").strip()
    if cid in COURSE_PRESETS:
        preset = COURSE_PRESETS[cid]
        leg_count = int(preset["leg_count"])
        leg_length_m = float(preset["leg_length_m"])
        upwind_bearing_deg = (twd_deg + float(preset.get("course_axis_offset_deg", 0.0))) % 360.0
    elif cid.startswith("custom_"):
        # Format: custom_{leg_count}leg_{length_m}m or custom_{leg_count}leg_{length_m}m_{axis_deg}deg
        parts = cid.split("_")
        try:
            leg_count = int(parts[1].replace("leg", ""))
            leg_length_m = float(parts[2].replace("m", ""))
            upwind_bearing_deg = (
                float(parts[3].replace("deg", "")) % 360.0
                if len(parts) > 3
                else (twd_deg % 360.0)
            )
        except (IndexError, ValueError):
            return None, {"course_id": cid}
    elif cid.startswith("bcn-") or cid == "default":
        leg_count = 4
        leg_length_m = 1500.0
        upwind_bearing_deg = twd_deg % 360.0
    else:
        return None, {"course_id": cid}

    legs = []
    for idx in range(leg_count):
        leg_num = idx + 1
        is_upwind = (leg_num % 2) == 1
        legs.append({
            "leg_num": leg_num,
            "leg_type": 1 if is_upwind else 0,
            "bearing_deg": upwind_bearing_deg if is_upwind else (upwind_bearing_deg + 180.0) % 360.0,
            "length_m": leg_length_m,
        })
    meta = {
        "course_id": cid,
        "leg_count": leg_count,
        "leg_length_m": leg_length_m,
        "upwind_bearing_deg": round(upwind_bearing_deg, 2),
    }
    return legs, meta


def _compile_team_leg_candidates(
    installed_model: InstalledModelBundle,
    team_id: str,
    leg_cfg: Mapping[str, Any],
    tws_mps: float,
    twd_deg: float,
    env_params: Mapping[str, Any] | None = None,
) -> tuple[list[list[tuple[str, float, float, float]]], np.ndarray] | None:
    """Pre-evaluates all matching route templates for (team_id, leg_type) on the target leg.

    Returns (compiled_templates, sampling_probabilities), or None if no templates exist.
    Each compiled template is a list of tuples:
      - ("straight", distance_m, mu_log_sog, sigma_log_sog)
      - ("maneuver", 0.0, man_log_mu, man_sigma)
    """
    leg_type = int(leg_cfg["leg_type"])
    bearing_deg = float(leg_cfg["bearing_deg"])
    length_m = float(leg_cfg["length_m"])

    weighted_templates, _tier = installed_model.template_library.query_nearest_templates(
        team_id, leg_type, tws_mps, length_m
    )
    if not weighted_templates:
        return None

    weights = []
    compiled: list[list[tuple[str, float, float, float]]] = []
    for tpl, w in weighted_templates:
        weights.append(float(w))

        trans_segs = transform_template_to_course(tpl, bearing_deg, length_m)
        seg_specs: list[tuple[str, float, float, float]] = []
        prev_pred_sog = 18.0

        for s in trans_segs:
            if s.segment_type == "straight":
                twa_deg = (s.target_heading_deg - twd_deg + 180.0) % 360.0 - 180.0
                feat = {
                    "team_id": team_id,
                    "tws_mps": tws_mps,
                    "twa_sin": math.sin(math.radians(twa_deg)),
                    "twa_cos": math.cos(math.radians(twa_deg)),
                    "tack_side": 1 if twa_deg >= 0 else -1,
                    "leg_type": leg_type,
                    "heading_cog_offset_deg": (
                        s.target_cog_deg - s.target_heading_deg + 180.0
                    )
                    % 360.0
                    - 180.0,
                    "course_wind_angle_deg": abs(twa_deg),
                    "practice_domain": 0,
                }
                if env_params:
                    for k in (
                        "current_speed_mps",
                        "current_dir_towards_deg",
                        "wave_height_m",
                        "wave_period_s",
                        "wave_dir_from_deg",
                        "air_temperature_c",
                        "water_temperature_c",
                    ):
                        if k in env_params and env_params[k] is not None:
                            feat[k] = float(env_params[k])
                mu_log, sigma_log = installed_model.predict_motion_distribution(feat)
                prev_pred_sog = math.exp(mu_log + 0.5 * (sigma_log ** 2))
                seg_specs.append(("straight", float(s.distance_m), mu_log, sigma_log))
            elif s.segment_type == "maneuver":
                man_feat = {
                    "turn_type": s.turn_type or ("tack" if leg_type == 1 else "gybe"),
                    "rotation_deg": (
                        float(s.turn_rotation_deg)
                        if s.turn_rotation_deg is not None
                        else (80.0 if leg_type == 1 else 70.0)
                    ),
                    "tws_mps": tws_mps,
                    "entry_speed_predicted_mps": prev_pred_sog,
                    "team_id": team_id,
                    "leg_type": leg_type,
                }
                validate_feature_separation(man_feat, task_type="event")
                man_log_mu = installed_model.maneuver_model._predict_log_mu(man_feat)
                man_sigma = installed_model.maneuver_model.sigma
                seg_specs.append(("maneuver", 0.0, float(man_log_mu), float(man_sigma)))

        compiled.append(seg_specs)

    probs = np.asarray(weights, dtype=float)
    probs = probs / np.sum(probs)
    return compiled, probs


def _simulate_boat_legs(
    compiled_legs: list[tuple[list[list[tuple[str, float, float, float]]], np.ndarray]],
    tpl_choices: np.ndarray,
    man_noises: np.ndarray,
    res_matrix: np.ndarray,
    starts: np.ndarray,
    step_s: float = 5.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulates straight and maneuver durations across all trials for one boat.

    Returns (total_times_s, straight_times_s, maneuver_times_s).
    """
    trial_count = len(starts)
    max_steps = res_matrix.shape[1]

    elapsed = starts.copy()
    straight_s = np.zeros(trial_count, dtype=float)
    maneuver_s = np.zeros(trial_count, dtype=float)

    for leg_idx, (compiled_pool, _probs) in enumerate(compiled_legs):
        chosen_k = tpl_choices[:, leg_idx]
        for k, seg_specs in enumerate(compiled_pool):
            trials_k = np.where(chosen_k == k)[0]
            if len(trials_k) == 0:
                continue
            man_slot = 0
            for seg_type, dist_m, mu_log, sigma_log in seg_specs:
                if seg_type == "straight":
                    if dist_m <= 0.0:
                        continue
                    t_cur = elapsed[trials_k]
                    step_idx = np.clip((t_cur // step_s).astype(int), 0, max_steps - 1)
                    z = res_matrix[trials_k, step_idx]
                    v = np.exp(mu_log + sigma_log * z)
                    # Censor extremely slow speeds at time limit instead of applying a 2 m/s floor
                    dt = np.minimum(dist_m / np.maximum(v, 0.25), 3600.0)
                    straight_s[trials_k] += dt
                    elapsed[trials_k] += dt
                elif seg_type == "maneuver":
                    z_m = man_noises[trials_k, leg_idx, man_slot % man_noises.shape[2]]
                    man_slot += 1
                    dt_m = np.maximum(3.0, np.exp(mu_log + sigma_log * z_m))
                    maneuver_s[trials_k] += dt_m
                    elapsed[trials_k] += dt_m

    return elapsed, straight_s, maneuver_s


def _build_scenario_id(params: Mapping[str, Any]) -> str:
    tws_raw = float(params["tws_mps"])
    tws_canon = 0.0 if tws_raw == 0.0 else tws_raw
    twd_raw = float(params["twd_deg"]) % 360.0
    twd_canon = 0.0 if (twd_raw == 0.0 or twd_raw == 360.0) else twd_raw
    payload = json.dumps(
        {
            "model_id": params["model_id"],
            "team_a": params["team_a"],
            "team_b": params["team_b"],
            "course_id": params["course_id"],
            "tws_mps": tws_canon,
            "twd_deg": twd_canon,
            "purpose": params["purpose"],
            "trial_count": int(params["trial_count"]),
            "seed": int(params["seed"]),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"scen_{digest}"


def predict_scenario(
    installed_model: InstalledModelBundle,
    request: Mapping[str, Any],
    *,
    return_trials: bool = False,
) -> Any:
    """Single numerical entry point for AC75 scenario simulation.

    Strictly validates inputs against SCENARIO_INPUT_ALLOWLIST.
    When return_trials=True, returns (ScenarioV2Result, SimulationTrialResult).
    """
    validate_feature_separation(request, task_type="scenario")

    team_a = str(request["team_a"])
    team_b = str(request["team_b"])
    course_id = str(request.get("course_id", "barcelona_lvc_4leg"))
    env = request.get("environment", {})
    tws_mps = float(
        env.get("tws_mps")
        if env.get("tws_mps") is not None
        else float(env.get("tws_kt", 12.0)) * (1852.0 / 3600.0)
    )
    twd_deg = float(
        env.get("twd_deg")
        if env.get("twd_deg") is not None
        else env.get("wind_from_deg", 180.0)
    )

    purpose = str(request.get("purpose", "standard"))
    trial_count = int(request.get("trial_count") or PURPOSE_TRIALS.get(purpose, 10000))
    seed = int(request.get("seed", 2027))

    scenario_id = _build_scenario_id(
        {
            "model_id": installed_model.model_id,
            "team_a": team_a,
            "team_b": team_b,
            "course_id": course_id,
            "tws_mps": tws_mps,
            "twd_deg": twd_deg,
            "purpose": purpose,
            "trial_count": trial_count,
            "seed": seed,
        }
    )

    legs_config, course_meta = _resolve_course_legs(course_id, twd_deg)
    if legs_config is None:
        unavail = ScenarioV2Result(
            schema_version="kinematic-race-sim-2",
            scenario_id=scenario_id,
            model_id=installed_model.model_id,
            status="unavailable",
            probability_scope="completion_assumed_on_water",
            applied_inputs={
                "team_a": team_a,
                "team_b": team_b,
                "course": course_meta,
                "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
                "purpose": purpose,
                "trial_count": trial_count,
                "seed": seed,
            },
            probabilities=None,
            timing=None,
            reason_codes=["unsupported_course_id"],
            trial_counts={"scheduled": trial_count, "completed": 0, "unresolved": trial_count},
        )
        if return_trials:
            from pipeline.kinematic_ml.scoring.trials import SimulationTrialResult
            empty = np.zeros(0, dtype=float)
            return unavail, SimulationTrialResult(
                scenario_id=scenario_id,
                model_id=installed_model.model_id,
                team_a=team_a,
                team_b=team_b,
                trial_count=trial_count,
                deltas=empty,
                times_a=empty,
                times_b=empty,
                wins_a=empty,
                both_finished=np.zeros(0, dtype=bool),
            )
        return unavail

    # Canonicalize competitor slot order so swapping (team_a, team_b) with the same seed
    # produces exact negation of margins and exact swap of win probabilities.
    swapped = team_a > team_b
    team_0, team_1 = (team_b, team_a) if swapped else (team_a, team_b)

    env_params = request.get("environment") if isinstance(request.get("environment"), Mapping) else None
    compiled_legs_0 = []
    compiled_legs_1 = []
    for leg in legs_config:
        comp_0 = _compile_team_leg_candidates(
            installed_model, team_0, leg, tws_mps, twd_deg, env_params
        )
        comp_1 = _compile_team_leg_candidates(
            installed_model, team_1, leg, tws_mps, twd_deg, env_params
        )
        if comp_0 is None or comp_1 is None:
            unavail = ScenarioV2Result(
                schema_version="kinematic-race-sim-2",
                scenario_id=scenario_id,
                model_id=installed_model.model_id,
                status="unavailable",
                probability_scope="completion_assumed_on_water",
                applied_inputs={
                    "team_a": team_a,
                    "team_b": team_b,
                    "course": course_meta,
                    "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
                    "purpose": purpose,
                    "trial_count": trial_count,
                    "seed": seed,
                },
                probabilities=None,
                timing=None,
                reason_codes=["missing_route_template_support"],
                trial_counts={"scheduled": trial_count, "completed": 0, "unresolved": trial_count},
            )
            if return_trials:
                from pipeline.kinematic_ml.scoring.trials import SimulationTrialResult
                empty = np.zeros(0, dtype=float)
                return unavail, SimulationTrialResult(
                    scenario_id=scenario_id,
                    model_id=installed_model.model_id,
                    team_a=team_a,
                    team_b=team_b,
                    trial_count=trial_count,
                    deltas=empty,
                    times_a=empty,
                    times_b=empty,
                    wins_a=empty,
                    both_finished=np.zeros(0, dtype=bool),
                )
            return unavail
        compiled_legs_0.append(comp_0)
        compiled_legs_1.append(comp_1)

    rng = np.random.default_rng(seed)
    n_legs = len(legs_config)
    step_s = 5.0
    steps_per_race = 360  # 1800s (30 min) within-race horizon at 5s intervals

    # 1. Sample start times for slot 0 and slot 1
    starts_0 = np.array(
        [installed_model.start_model.sample_start_time_s(rng, tws_mps) for _ in range(trial_count)],
        dtype=float,
    )
    starts_1 = np.array(
        [installed_model.start_model.sample_start_time_s(rng, tws_mps) for _ in range(trial_count)],
        dtype=float,
    )

    # 2. Sample route template index per trial and leg for slot 0 and slot 1
    tpl_choices_0 = np.zeros((trial_count, n_legs), dtype=int)
    tpl_choices_1 = np.zeros((trial_count, n_legs), dtype=int)
    for leg_idx in range(n_legs):
        pool_0, probs_0 = compiled_legs_0[leg_idx]
        pool_1, probs_1 = compiled_legs_1[leg_idx]
        tpl_choices_0[:, leg_idx] = rng.choice(len(pool_0), size=trial_count, p=probs_0)
        tpl_choices_1[:, leg_idx] = rng.choice(len(pool_1), size=trial_count, p=probs_1)

    # 3. Sample maneuver lognormal standard normal draws per trial, leg, and maneuver slot
    max_man_per_leg = 8
    man_noises_0 = rng.standard_normal((trial_count, n_legs, max_man_per_leg))
    man_noises_1 = rng.standard_normal((trial_count, n_legs, max_man_per_leg))

    # 4. Sample contemporaneous paired residual trajectories across within-race time steps
    res_flat_0, res_flat_1 = installed_model.residual_sampler.sample_residuals(
        duration_s=float(trial_count * steps_per_race * step_s),
        step_s=step_s,
        rng=rng,
    )
    res_mat_0 = res_flat_0[: trial_count * steps_per_race].reshape((trial_count, steps_per_race))
    res_mat_1 = res_flat_1[: trial_count * steps_per_race].reshape((trial_count, steps_per_race))

    times_0, str_0, man_0 = _simulate_boat_legs(
        compiled_legs_0, tpl_choices_0, man_noises_0, res_mat_0, starts_0, step_s=step_s
    )
    times_1, str_1, man_1 = _simulate_boat_legs(
        compiled_legs_1, tpl_choices_1, man_noises_1, res_mat_1, starts_1, step_s=step_s
    )

    if swapped:
        times_a, times_b = times_1, times_0
        str_a, str_b = str_1, str_0
        man_a, man_b = man_1, man_0
        starts_a, starts_b = starts_1, starts_0
    else:
        times_a, times_b = times_0, times_1
        str_a, str_b = str_0, str_1
        man_a, man_b = man_0, man_1
        starts_a, starts_b = starts_0, starts_1

    # Deltas: delta_T = time_b - time_a (positive if A finishes earlier / wins)
    deltas = times_b - times_a

    # Under completion_assumed_on_water, split exact numerical ties equally (0.5 / 0.5)
    ties = np.isclose(times_a, times_b, atol=1e-6)
    wins_a = (times_a < times_b) & (~ties)

    raw_prob_win_a = float(np.mean(wins_a) + 0.5 * np.mean(ties))
    prob_win_a = round(raw_prob_win_a, 4)
    prob_win_b = round(1.0 - prob_win_a, 4)

    prob_mc_error = float(
        math.sqrt(max(0.0, raw_prob_win_a * (1.0 - raw_prob_win_a)) / max(1, trial_count))
    )
    gamma = float(installed_model.margin_interval_scale)
    mean_time_a = float(np.mean(times_a))
    mean_time_b = float(np.mean(times_b))
    mean_delta = float(np.mean(deltas))
    margin_std_s = float(np.std(deltas)) * gamma
    margin_mc_se_s = float(margin_std_s / math.sqrt(max(1, trial_count)))

    raw_percentiles = [
        float(v)
        for v in np.percentile(deltas, [2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 97.5])
    ]
    if gamma == 1.0:
        p025, p05, p10, p25, p50, p75, p90, p95, p975 = raw_percentiles
    else:
        p025, p05, p10, p25, p50, p75, p90, p95, p975 = [
            mean_delta + gamma * (v - mean_delta) for v in raw_percentiles
        ]

    mean_start_delta = round(float(np.mean(starts_b - starts_a)), 2)
    mean_maneuver_delta = round(float(np.mean(man_b - man_a)), 2)
    rounded_mean_delta = round(mean_delta, 2)
    # Keep straight_delta_s consistent with rounded components so sum == total_mean_delta_s
    mean_straight_delta = round(
        rounded_mean_delta - mean_maneuver_delta - mean_start_delta, 2
    )

    timing_detail = ScenarioTimingDetail(
        mean_time_a_s=round(mean_time_a, 2),
        mean_time_b_s=round(mean_time_b, 2),
        mean_delta_t_s=rounded_mean_delta,
        central_80_margin_interval_s=(round(p10, 2), round(p90, 2)),
    )

    prob_detail = ScenarioProbabilityDetail(
        win_a=prob_win_a,
        win_b=prob_win_b,
        no_winner=None,
        mc_error=round(prob_mc_error, 4),
    )

    time_accounting = {
        "straight_delta_s": mean_straight_delta,
        "maneuver_delta_s": mean_maneuver_delta,
        "start_delta_s": mean_start_delta,
        "total_mean_delta_s": rounded_mean_delta,
        "margin_mc_se_s": round(margin_mc_se_s, 4),
        "margin_std_s": round(margin_std_s, 3),
        "motion_residual_scale": installed_model.motion_residual_scale,
        "margin_interval_scale": installed_model.margin_interval_scale,
        "quantiles_delta_t_s": {
            "p025": round(p025, 2),
            "p05": round(p05, 2),
            "p10": round(p10, 2),
            "p25": round(p25, 2),
            "p50": round(p50, 2),
            "p75": round(p75, 2),
            "p90": round(p90, 2),
            "p95": round(p95, 2),
            "p975": round(p975, 2),
        },
    }

    applied_inputs = {
        "team_a": team_a,
        "team_b": team_b,
        "course_id": course_id,
        "course": course_meta,
        "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
        "purpose": purpose,
        "trial_count": trial_count,
        "seed": seed,
        "seconds_accounting": time_accounting,
        "variance_attribution": asdict(installed_model.variance_ledger),
    }

    res = ScenarioV2Result(
        schema_version="kinematic-race-sim-2",
        scenario_id=scenario_id,
        model_id=installed_model.model_id,
        status="available",
        probability_scope="completion_assumed_on_water",
        applied_inputs=applied_inputs,
        timing=timing_detail,
        probabilities=prob_detail,
        time_accounting=time_accounting,
        trial_counts={"scheduled": trial_count, "completed": trial_count, "unresolved": 0},
    )
    if return_trials:
        from pipeline.kinematic_ml.scoring.trials import SimulationTrialResult
        trial_res = SimulationTrialResult(
            scenario_id=scenario_id,
            model_id=installed_model.model_id,
            team_a=team_a,
            team_b=team_b,
            trial_count=trial_count,
            deltas=deltas,
            times_a=times_a,
            times_b=times_b,
            wins_a=wins_a,
            both_finished=np.ones(trial_count, dtype=bool),
            straights_a=str_a,
            straights_b=str_b,
            maneuvers_a=man_a,
            maneuvers_b=man_b,
            starts_a=starts_a,
            starts_b=starts_b,
        )
        return res, trial_res
    return res
