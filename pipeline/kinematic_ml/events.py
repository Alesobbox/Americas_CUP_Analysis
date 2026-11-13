"""Maneuver event timing, start behavior, and duration models for AC75 (T12).

Contract (G3.3, EVENT_PREDICTOR_ALLOWLIST):
- Lognormal maneuver-plus-recovery duration model with regularized team effects.
- Right-censored likelihood for unrecovered turns (censoring = True).
- Inputs strictly match EVENT_PREDICTOR_ALLOWLIST:
  'entry_speed_predicted_mps', 'tws_mps', 'rotation_deg', 'team_id', 'leg_type', 'turn_type'
- Start behavior model: gun-to-steady duration distribution.
- Accounting: maneuver duration replaces straight integration; no double-counting.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr

from pipeline.kinematic_ml.contracts import (
     validate_feature_separation,
)

CANONICAL_TEAMS = [
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
]


class ManeuverDurationModel:
    """Lognormal duration regressor with right-censored survival likelihood."""

    def __init__(self) -> None:
        self.intercept_tack: float = math.log(12.0)
        self.intercept_gybe: float = math.log(14.0)
        self.coef_rotation: float = 0.005
        self.coef_tws: float = -0.02
        self.coef_entry_v: float = -0.015
        self.sigma: float = 0.25
        self.team_offsets: dict[str, float] = {t: 0.0 for t in CANONICAL_TEAMS}
        self.fitted_turn_count: int = 0
        self.censored_turn_count: int = 0

    @staticmethod
    def _extract_maneuver_inputs(t: Mapping[str, Any]) -> tuple[float, float, float] | None:
        rot_raw = t.get("rotation_deg")
        tws_raw = t.get("tws_mps")
        ev_raw = t.get("entry_speed_predicted_mps")
        if ev_raw is None:
            ev_raw = t.get("entry_speed_mps")
        if rot_raw is None or tws_raw is None or ev_raw is None:
            return None
        rot = float(rot_raw)
        tws = float(tws_raw)
        ev = float(ev_raw)
        if not (math.isfinite(rot) and math.isfinite(tws) and math.isfinite(ev)):
            return None
        return rot, tws, ev

    def fit(self, turns: Sequence[Mapping[str, Any]]) -> None:
        """Fits lognormal duration model parameters via right-censored maximum likelihood."""
        valid_turns: list[tuple[Mapping[str, Any], float, float, float, float]] = []
        for t in turns:
            dur = float(t.get("total_event_s") or t.get("duration_s") or 0.0)
            if dur <= 1.0:
                continue
            parsed = self._extract_maneuver_inputs(t)
            if parsed is None:
                continue
            rot, tws, ev = parsed
            valid_turns.append((t, dur, rot, tws, ev))

        if not valid_turns:
            return

        n = len(valid_turns)
        self.fitted_turn_count = n
        y_log = np.zeros(n, dtype=float)
        is_gybe = np.zeros(n, dtype=float)
        rot_c = np.zeros(n, dtype=float)
        tws_c = np.zeros(n, dtype=float)
        entry_c = np.zeros(n, dtype=float)
        is_censored = np.zeros(n, dtype=bool)
        team_idx = np.full(n, -1, dtype=int)
        weights = np.ones(n, dtype=float)

        # Compute race-equal weights if family_id is present
        fam_counts: dict[str, int] = {}
        for t, _dur, _rot, _tws, _ev in valid_turns:
            fid = str(t.get("family_id", ""))
            if fid:
                fam_counts[fid] = fam_counts.get(fid, 0) + 1

        team_to_i = {t: idx for idx, t in enumerate(CANONICAL_TEAMS)}
        for i, (t, dur, rot, tws, ev) in enumerate(valid_turns):
            y_log[i] = math.log(max(dur, 1.01))
            ttype = str(t.get("turn_type", "tack")).lower()
            is_gybe[i] = 1.0 if ttype == "gybe" else 0.0
            rot_c[i] = rot - 75.0
            tws_c[i] = tws - 10.0
            entry_c[i] = ev - 20.0
            is_censored[i] = bool(t.get("censoring", False))
            tid = str(t.get("team_id", ""))
            if tid in team_to_i:
                team_idx[i] = team_to_i[tid]
            fid = str(t.get("family_id", ""))
            if fid and fam_counts.get(fid, 0) > 0:
                weights[i] = 1.0 / float(fam_counts[fid])

        weights = weights / np.mean(weights)
        self.censored_turn_count = int(np.sum(is_censored))

        is_tack = 1.0 - is_gybe
        has_tack = bool(np.sum(is_tack) > 0)
        has_gybe = bool(np.sum(is_gybe) > 0)
        n_teams = len(CANONICAL_TEAMS)

        # One-hot team matrix (n, 6)
        T_mat = np.zeros((n, n_teams), dtype=float)
        for i, tidx in enumerate(team_idx):
            if tidx >= 0:
                T_mat[i, tidx] = 1.0

        init_tack = float(np.mean(y_log[is_tack > 0.5])) if has_tack else math.log(12.0)
        init_gybe = float(np.mean(y_log[is_gybe > 0.5])) if has_gybe else math.log(14.0)
        theta0 = np.array(
            [
                init_tack,
                init_gybe,
                self.coef_rotation,
                self.coef_tws,
                self.coef_entry_v,
                math.log(0.25),
                *([0.0] * n_teams),
            ],
            dtype=float,
        )

        bounds = [
            (math.log(2.0), math.log(120.0)),  # intercept_tack
            (math.log(2.0), math.log(120.0)),  # intercept_gybe
            (-0.05, 0.05),                     # coef_rotation
            (-0.20, 0.20),                     # coef_tws
            (-0.20, 0.20),                     # coef_entry_v
            (math.log(0.05), math.log(1.5)),   # log_sigma
            *([(-1.0, 1.0)] * n_teams),        # team_offsets
        ]

        def objective(theta: np.ndarray) -> float:
            b_tack, b_gybe, c_rot, c_tws, c_ev, log_sig = theta[:6]
            t_off = theta[6:]
            sig = math.exp(log_sig)

            mu = (
                b_tack * is_tack
                + b_gybe * is_gybe
                + c_rot * rot_c
                + c_tws * tws_c
                + c_ev * entry_c
                + (T_mat @ t_off)
            )

            nll = np.zeros(n, dtype=float)
            uncens = ~is_censored
            if np.any(uncens):
                z_u = (y_log[uncens] - mu[uncens]) / sig
                nll[uncens] = log_sig + 0.5 * (z_u ** 2) + 0.5 * math.log(2.0 * math.pi)

            if np.any(is_censored):
                # Right-censored survival: P(Y > y_c) = Phi((mu - y_c) / sig)
                z_c = (mu[is_censored] - y_log[is_censored]) / sig
                nll[is_censored] = -log_ndtr(z_c)

            weighted_nll = float(np.sum(weights * nll) / np.sum(weights))

            # Weakly informative regularization for identifiability and shrinkage
            pen_slopes = (
                0.5 * ((c_rot - 0.005) / 0.02) ** 2
                + 0.5 * ((c_tws - (-0.02)) / 0.05) ** 2
                + 0.5 * ((c_ev - (-0.015)) / 0.05) ** 2
            ) / max(n, 1)
            pen_teams = 10.0 * float(np.sum(t_off ** 2)) / max(n, 1)
            pen_missing = 0.0
            if not has_tack:
                pen_missing += 0.5 * (b_tack - math.log(12.0)) ** 2
            if not has_gybe:
                pen_missing += 0.5 * (b_gybe - math.log(14.0)) ** 2

            return weighted_nll + pen_slopes + pen_teams + pen_missing

        res = minimize(objective, theta0, method="L-BFGS-B", bounds=bounds)
        opt = res.x if res.success or np.all(np.isfinite(res.x)) else theta0

        self.intercept_tack = float(opt[0])
        self.intercept_gybe = float(opt[1])
        self.coef_rotation = float(opt[2])
        self.coef_tws = float(opt[3])
        self.coef_entry_v = float(opt[4])
        self.sigma = float(math.exp(opt[5]))
        for idx, team in enumerate(CANONICAL_TEAMS):
            self.team_offsets[team] = float(opt[6 + idx])

    def _predict_log_mu(self, features: Mapping[str, Any]) -> float:
        ttype = str(features.get("turn_type", "tack")).lower()
        base = self.intercept_gybe if ttype == "gybe" else self.intercept_tack

        parsed = self._extract_maneuver_inputs(features)
        if parsed is None:
            raise ValueError(
                "Maneuver duration prediction requires finite causal rotation_deg, tws_mps, and entry_speed_predicted_mps"
            )
        rot, tws, entry_v = parsed
        tid = str(features.get("team_id", ""))

        return (
            base
            + self.coef_rotation * (rot - 75.0)
            + self.coef_tws * (tws - 10.0)
            + self.coef_entry_v * (entry_v - 20.0)
            + self.team_offsets.get(tid, 0.0)
        )

    def predict_duration_s(
        self,
        features: Mapping[str, Any],
        *,
        rng: np.random.Generator | None = None,
    ) -> float:
        """Predicts maneuver-plus-recovery duration in seconds.

        Enforces EVENT_PREDICTOR_ALLOWLIST.
        """
        validate_feature_separation(features, task_type="event")
        log_mu = self._predict_log_mu(features)

        if rng is not None:
            sample_log = float(rng.normal(log_mu, self.sigma))
            return float(max(3.0, math.exp(sample_log)))
        return float(max(3.0, math.exp(log_mu + 0.5 * (self.sigma ** 2))))

    def score_censored_nll(self, turns: Sequence[Mapping[str, Any]]) -> float:
        """Computes mean right-censored negative log-likelihood on evaluation turns."""
        losses = []
        for t in turns:
            dur = float(t.get("total_event_s") or t.get("duration_s") or 0.0)
            if dur <= 1.0:
                continue
            parsed = self._extract_maneuver_inputs(t)
            if parsed is None:
                continue
            rot, tws, entry_v = parsed
            y = math.log(dur)
            feat = {
                "turn_type": str(t.get("turn_type", "tack")).lower(),
                "rotation_deg": rot,
                "tws_mps": tws,
                "entry_speed_predicted_mps": entry_v,
                "team_id": str(t.get("team_id", "")),
                "leg_type": int(t.get("leg_type", 1)),
            }
            mu = self._predict_log_mu(feat)
            if bool(t.get("censoring", False)):
                z_c = (mu - y) / self.sigma
                losses.append(float(-log_ndtr(z_c)))
            else:
                z_u = (y - mu) / self.sigma
                losses.append(math.log(self.sigma) + 0.5 * (z_u ** 2) + 0.5 * math.log(2.0 * math.pi))
        return float(np.mean(losses)) if losses else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "intercept_tack": round(self.intercept_tack, 6),
            "intercept_gybe": round(self.intercept_gybe, 6),
            "coef_rotation": round(self.coef_rotation, 6),
            "coef_tws": round(self.coef_tws, 6),
            "coef_entry_v": round(self.coef_entry_v, 6),
            "sigma": round(self.sigma, 6),
            "team_offsets": {k: round(v, 6) for k, v in self.team_offsets.items()},
            "fitted_turn_count": self.fitted_turn_count,
            "censored_turn_count": self.censored_turn_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ManeuverDurationModel:
        m = cls()
        m.intercept_tack = float(data.get("intercept_tack", m.intercept_tack))
        m.intercept_gybe = float(data.get("intercept_gybe", m.intercept_gybe))
        m.coef_rotation = float(data.get("coef_rotation", m.coef_rotation))
        m.coef_tws = float(data.get("coef_tws", m.coef_tws))
        m.coef_entry_v = float(data.get("coef_entry_v", m.coef_entry_v))
        m.sigma = float(data.get("sigma", m.sigma))
        raw_offsets = data.get("team_offsets", {})
        if isinstance(raw_offsets, Mapping):
            for k in CANONICAL_TEAMS:
                if k in raw_offsets:
                    m.team_offsets[k] = float(raw_offsets[k])
        m.fitted_turn_count = int(data.get("fitted_turn_count", 0))
        m.censored_turn_count = int(data.get("censored_turn_count", 0))
        return m


class StartBehaviorModel:
    """Models acceleration and timing from the starting gun to steady foiling speed."""

    def __init__(
        self,
        mean_start_dur_s: float = 18.0,
        stdev_s: float = 3.0,
        wind_slope: float = -1.2,
    ) -> None:
        self.mean_start_dur_s = float(mean_start_dur_s)
        self.stdev_s = float(stdev_s)
        self.wind_slope = float(wind_slope)
        self.fitted_count: int = 0

    def fit(self, intervals: Sequence[Mapping[str, Any]]) -> None:
        """Fits start gun-to-steady duration distribution from extracted start intervals."""
        durs: list[float] = []
        tws_durs: list[float] = []
        tws_vals: list[float] = []
        for row in intervals:
            d = row.get("gun_to_steady_s")
            if d is None:
                d = row.get("start_duration_s")
            if d is not None and 2.0 <= float(d) <= 90.0:
                d_val = float(d)
                durs.append(d_val)
                tws = row.get("tws_mps")
                if tws is not None and math.isfinite(float(tws)):
                    tws_durs.append(d_val)
                    tws_vals.append(float(tws))

        if not durs:
            return

        self.fitted_count = len(durs)
        arr_d = np.asarray(durs, dtype=float)
        self.mean_start_dur_s = float(np.clip(np.mean(arr_d), 5.0, 45.0))
        if len(arr_d) >= 3:
            self.stdev_s = float(np.clip(np.std(arr_d), 1.0, 12.0))
        if len(tws_vals) >= 5 and np.std(tws_vals) > 0.5:
            arr_w = np.asarray(tws_vals, dtype=float) - 8.0
            arr_tws_d = np.asarray(tws_durs, dtype=float)
            cov = float(np.mean((arr_w - np.mean(arr_w)) * (arr_tws_d - np.mean(arr_tws_d))))
            var_w = float(np.var(arr_w))
            if var_w > 1e-4:
                self.wind_slope = float(np.clip(cov / var_w, -4.0, 0.0))

    def sample_start_time_s(self, rng: np.random.Generator, tws_mps: float = 10.0) -> float:
        """Samples gun-to-steady foiling duration."""
        wind_adjustment = max(0.0, (8.0 - tws_mps) * abs(self.wind_slope))
        mu = self.mean_start_dur_s + wind_adjustment
        dur = float(rng.normal(mu, self.stdev_s))
        return float(max(5.0, dur))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_start_dur_s": round(self.mean_start_dur_s, 4),
            "stdev_s": round(self.stdev_s, 4),
            "wind_slope": round(self.wind_slope, 4),
            "fitted_count": self.fitted_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StartBehaviorModel:
        m = cls(
            mean_start_dur_s=float(data.get("mean_start_dur_s", 18.0)),
            stdev_s=float(data.get("stdev_s", 3.0)),
            wind_slope=float(data.get("wind_slope", -1.2)),
        )
        m.fitted_count = int(data.get("fitted_count", 0))
        return m
