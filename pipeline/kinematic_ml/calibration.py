"""Chronological calibration protocol and predictor-specific scaling artifacts (T15/P3).

Implements:
1. Strict chronological inner splitting inside outer training periods:
   - Earlier dates: fit base model
   - Penultimate available date: tune hyperparameters (e.g. regularization / alpha)
   - Fit + tune dates: refit with selected hyperparameters
   - Last training date: calibrate residual/scaling artifacts
   - Subsequent outer-test date: score out-of-fold (strictly held out until after calibration)
2. Predictor-specific calibration artifacts:
   - Each predictor (empirical, spline, neural) owns its own residual distribution and scaling multipliers.
   - Calibrates predictive interval scaling strictly on the training calibration date.
   - Zero inspection of outer-test coverage to artificially narrow intervals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class ChronologicalInnerSplit:
    """Chronological fold decomposition inside an outer training period."""
    outer_train_dates: tuple[str, ...]
    fit_dates: tuple[str, ...]
    tune_dates: tuple[str, ...]
    refit_dates: tuple[str, ...]
    calibrate_dates: tuple[str, ...]
    outer_test_dates: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_outer_dates(
        cls,
        outer_train_dates: Sequence[str],
        outer_test_dates: Sequence[str] | None = None,
    ) -> ChronologicalInnerSplit:
        """Construct chronological inner split strictly respecting temporal ordering."""
        sorted_train = tuple(sorted(set(outer_train_dates)))
        sorted_test = tuple(sorted(set(outer_test_dates))) if outer_test_dates else ()

        n = len(sorted_train)
        if n == 0:
            raise ValueError("Cannot build inner split with zero outer training dates")
        elif n == 1:
            # Single training date: fit, tune, refit, calibrate all share this date
            fit = sorted_train
            tune = sorted_train
            refit = sorted_train
            calib = sorted_train
        elif n == 2:
            # Two dates: fit/tune/refit on first date, calibrate on second date
            fit = (sorted_train[0],)
            tune = (sorted_train[0],)
            refit = (sorted_train[0],)
            calib = (sorted_train[1],)
        else:
            # Three or more dates:
            # - fit on earlier dates: sorted_train[:-2]
            # - tune on penultimate date: (sorted_train[-2],)
            # - refit on fit + tune: sorted_train[:-1]
            # - calibrate on last training date: (sorted_train[-1],)
            fit = tuple(sorted_train[:-2])
            tune = (sorted_train[-2],)
            refit = tuple(sorted_train[:-1])
            calib = (sorted_train[-1],)

        return cls(
            outer_train_dates=sorted_train,
            fit_dates=fit,
            tune_dates=tune,
            refit_dates=refit,
            calibrate_dates=calib,
            outer_test_dates=sorted_test,
        )

    def validate_isolation(self) -> None:
        """Enforce strict chronological monotonicity and zero test leakage."""
        if self.outer_test_dates:
            test_set = set(self.outer_test_dates)
            for d in self.outer_train_dates:
                if d in test_set:
                    raise ValueError(f"Outer test date {d} leaks into outer training dates")

        # Monotonicity check across inner splits when multiple dates exist
        if len(self.outer_train_dates) >= 3:
            max_fit = max(self.fit_dates)
            min_tune = min(self.tune_dates)
            min_calib = min(self.calibrate_dates)
            if max_fit >= min_tune:
                raise ValueError(f"Fit dates ({self.fit_dates}) must precede tune date ({self.tune_dates})")
            if min_tune >= min_calib:
                raise ValueError(f"Tune date ({self.tune_dates}) must precede calibrate date ({self.calibrate_dates})")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PredictorCalibrationArtifacts:
    """Predictor-specific residual distributions and interval scaling parameters.
    
    Attributes:
        predictor_family: Canonical family identifier ('empirical', 'spline', 'neural').
        model_id: Concrete model identifier.
        calibration_date: Date on which calibration was computed.
        motion_residual_scale: Multiplicative scale adjustment for motion prediction std.
        maneuver_residual_scale: Multiplicative scale adjustment for maneuver duration std.
        margin_interval_scale: Scaling factor gamma applied to race-margin quantiles.
        calibration_sample_count: Number of evaluation samples on calibration date.
        calibration_metrics: Verification metrics measured strictly on calibration date.
        verified_no_test_leakage: Affirmation that outer-test date was never touched.
    """
    predictor_family: str
    model_id: str
    calibration_date: str
    motion_residual_scale: float = 1.0
    maneuver_residual_scale: float = 1.0
    margin_interval_scale: float = 1.0
    calibration_sample_count: int = 0
    calibration_metrics: dict[str, float] = field(default_factory=dict)
    verified_no_test_leakage: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calibrate_motion_residual_scale(
    y_sog: Sequence[float] | np.ndarray,
    mu_log: Sequence[float] | np.ndarray,
    sigma_log: Sequence[float] | np.ndarray,
    *,
    censor_mps: float = 2.0,
) -> float:
    """Compute empirical normalized log-speed residual standard error on calibration samples.
    
    Residual: z_i = (log(max(y_i, censor_mps)) - mu_log_i) / sigma_log_i
    Returns empirical standard deviation of z, clipped to [0.5, 2.0].
    """
    y_arr = np.asarray(y_sog, dtype=float)
    mu_arr = np.asarray(mu_log, dtype=float)
    sig_arr = np.clip(np.asarray(sigma_log, dtype=float), 0.05, 2.0)

    if len(y_arr) < 5:
        return 1.0

    valid = y_arr > censor_mps
    if np.sum(valid) < 5:
        return 1.0

    z = (np.log(y_arr[valid]) - mu_arr[valid]) / sig_arr[valid]
    std_z = float(np.std(z, ddof=1))
    return float(np.clip(std_z, 0.5, 2.0))


def calibrate_margin_interval_scale(
    trial_margins_by_race: Sequence[Sequence[float] | np.ndarray],
    observed_margins: Sequence[float] | np.ndarray,
    *,
    target_nominal_coverage: float = 0.80,
) -> float:
    """Calibrate predictive interval scaling factor gamma on calibration date races.
    
    Adjusts interval width: [mean + gamma * (p10 - mean), mean + gamma * (p90 - mean)]
    such that empirical coverage on the calibration date matches target_nominal_coverage.
    Never inspects outer-test data.
    """
    obs_arr = np.asarray(observed_margins, dtype=float)
    n_races = len(obs_arr)
    if n_races < 3 or len(trial_margins_by_race) != n_races:
        return 1.0

    # Grid search for gamma in [0.5, 2.5]
    best_gamma = 1.0
    best_diff = 1.0

    alpha = 1.0 - target_nominal_coverage
    p_low = 100.0 * (alpha / 2.0)
    p_high = 100.0 * (1.0 - alpha / 2.0)

    for gamma in np.linspace(0.5, 2.5, 41):
        covered = 0
        for i in range(n_races):
            trials = np.asarray(trial_margins_by_race[i], dtype=float)
            mean_m = float(np.mean(trials))
            q_low = float(np.percentile(trials, p_low))
            q_high = float(np.percentile(trials, p_high))
            scaled_low = mean_m + float(gamma) * (q_low - mean_m)
            scaled_high = mean_m + float(gamma) * (q_high - mean_m)
            if scaled_low <= obs_arr[i] <= scaled_high:
                covered += 1
        emp_cov = covered / float(n_races)
        diff = abs(emp_cov - target_nominal_coverage)
        if diff < best_diff:
            best_diff = diff
            best_gamma = float(gamma)

    return best_gamma


def build_predictor_calibration(
    predictor_family: str,
    model_id: str,
    inner_split: ChronologicalInnerSplit,
    calibration_telemetry_windows: Sequence[Mapping[str, Any]],
    predict_dist_fn: Any,
    *,
    calibration_races: Sequence[Mapping[str, Any]] | None = None,
    predict_race_fn: Any = None,
) -> PredictorCalibrationArtifacts:
    """Execute calibration protocol strictly on the last training date (calibration date).
    
    1. Validates that no outer-test dates are in the calibration window.
    2. Measures empirical residual spread of predict_dist_fn on calibration date steady windows.
    3. If calibration races are provided, tunes margin interval scale strictly on calibration date.
    4. Persists verified calibration artifacts bound to the specific predictor.
    """
    inner_split.validate_isolation()
    calib_date = inner_split.calibrate_dates[0] if inner_split.calibrate_dates else "unknown"

    # Filter steady windows to calibration date only
    calib_sw = [
        w for w in calibration_telemetry_windows
        if str(w.get("date_str") or "") in inner_split.calibrate_dates
        or str(w.get("family_id") or "") in inner_split.calibrate_dates
    ]

    motion_scale = 1.0
    calib_metrics: dict[str, float] = {}

    if calib_sw and len(calib_sw) >= 5:
        y_sogs = [float(w.get("sog_mps", 0.0)) for w in calib_sw]
        mus = []
        sigs = []
        for w in calib_sw:
            mu_l, log_s = predict_dist_fn(w)
            mus.append(float(mu_l))
            sigs.append(float(max(0.05, math.exp(log_s))))
        motion_scale = calibrate_motion_residual_scale(y_sogs, mus, sigs)
        calib_metrics["calib_sog_count"] = float(len(calib_sw))
        calib_metrics["motion_residual_scale"] = round(motion_scale, 4)

    margin_scale = 1.0
    if calibration_races and predict_race_fn is not None:
        calib_race_subset = [
            r for r in calibration_races
            if str(r.get("date_str") or r.get("date") or "") in inner_split.calibrate_dates
        ]
        if calib_race_subset:
            trial_lists = []
            obs_deltas = []
            for r in calib_race_subset:
                obs_d = r.get("observed_delta_t_s") or r.get("race_margin_s")
                if obs_d is not None and math.isfinite(float(obs_d)):
                    trials = predict_race_fn(r)
                    if trials is not None and len(trials) > 0:
                        trial_lists.append(trials)
                        obs_deltas.append(float(obs_d))
            if trial_lists and len(trial_lists) >= 3:
                margin_scale = calibrate_margin_interval_scale(trial_lists, obs_deltas)
                calib_metrics["margin_interval_scale"] = round(margin_scale, 4)

    return PredictorCalibrationArtifacts(
        predictor_family=predictor_family,
        model_id=model_id,
        calibration_date=calib_date,
        motion_residual_scale=round(motion_scale, 4),
        maneuver_residual_scale=1.0,
        margin_interval_scale=round(margin_scale, 4),
        calibration_sample_count=len(calib_sw),
        calibration_metrics=calib_metrics,
        verified_no_test_leakage=True,
    )
