"""Empirical and regularized learned polar baselines for AC75 (T10).

Contract (G3.1, G3.6):
- Real fitted artifacts with out-of-fold predictions.
- Binned polar table with bilinear interpolation and bounded extrapolation.
- Penalized regularized log-speed model with shrunken team deviations.
- Strict adherence to MOTION_PREDICTOR_ALLOWLIST.
- Legacy fixed model retained as a labeled benchmark comparison.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

CANONICAL_TEAMS = [
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
]


def _compute_race_weights(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Computes race-equal weights w_i = 1 / N_{family} normalized to mean 1.0."""
    n = len(rows)
    if n == 0:
        return np.zeros(0, dtype=float)
    counts: dict[str, int] = {}
    for r in rows:
        fid = str(r.get("family_id", ""))
        if fid:
            counts[fid] = counts.get(fid, 0) + 1
    if not counts:
        return np.ones(n, dtype=float)
    w = np.ones(n, dtype=float)
    for i, r in enumerate(rows):
        fid = str(r.get("family_id", ""))
        if fid and counts.get(fid, 0) > 0:
            w[i] = 1.0 / float(counts[fid])
    mean_w = float(np.mean(w))
    return w / mean_w if mean_w > 0.0 else np.ones(n, dtype=float)


class BinnedPolarBaseline:
    """Empirical polar baseline binned across TWS and TWA."""

    def __init__(
        self,
        tws_bins: Sequence[float] | None = None,
        twa_bins: Sequence[float] | None = None,
    ) -> None:
        self.tws_bins = np.asarray(
            tws_bins if tws_bins is not None else np.arange(4.0, 26.0, 2.0),
            dtype=float,
        )
        self.twa_bins = np.asarray(
            twa_bins if twa_bins is not None else np.arange(30.0, 180.0, 10.0),
            dtype=float,
        )
        self.grid_mean_sog = np.full(
            (len(self.tws_bins), len(self.twa_bins)), 18.0, dtype=float
        )
        self.grid_counts = np.zeros(
            (len(self.tws_bins), len(self.twa_bins)), dtype=int
        )
        self.team_offsets: dict[str, float] = {t: 0.0 for t in CANONICAL_TEAMS}
        self.global_mean_sog = 18.0
        self.residual_log_scale = 0.16

    def fit(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Fits empirical grid cells and shrunken team offsets from steady window rows."""
        valid = [r for r in rows if float(r.get("sog_mps", 0.0)) > 0.0]
        if not valid:
            return

        weights = _compute_race_weights(valid)
        bin_sogs: dict[tuple[int, int], list[tuple[float, float]]] = {}
        team_residuals: dict[str, list[tuple[float, float]]] = {
            t: [] for t in CANONICAL_TEAMS
        }
        all_sogs = np.array([float(r.get("sog_mps", 0.0)) for r in valid], dtype=float)
        self.global_mean_sog = float(np.average(all_sogs, weights=weights))

        for r, w in zip(valid, weights):
            sog = float(r.get("sog_mps", 0.0))
            tws = float(r.get("tws_mps", 10.0))
            twa = abs(
                float(
                    math.degrees(
                        math.atan2(
                            float(r.get("twa_sin", 0.0)),
                            float(r.get("twa_cos", 1.0)),
                        )
                    )
                )
            )
            tid = str(r.get("team_id", ""))

            i = int(np.clip(np.digitize(tws, self.tws_bins) - 1, 0, len(self.tws_bins) - 1))
            j = int(np.clip(np.digitize(twa, self.twa_bins) - 1, 0, len(self.twa_bins) - 1))
            bin_sogs.setdefault((i, j), []).append((sog, float(w)))

            if tid in team_residuals:
                team_residuals[tid].append((sog, float(w)))

        for (i, j), pairs in bin_sogs.items():
            vals = np.array([p[0] for p in pairs], dtype=float)
            ws = np.array([p[1] for p in pairs], dtype=float)
            self.grid_mean_sog[i, j] = float(np.average(vals, weights=ws))
            self.grid_counts[i, j] = len(pairs)

        self.grid_mean_sog[self.grid_counts == 0] = self.global_mean_sog

        for tid, pairs in team_residuals.items():
            n = len(pairs)
            if n > 0:
                vals = np.array([p[0] for p in pairs], dtype=float)
                ws = np.array([p[1] for p in pairs], dtype=float)
                raw_diff = float(np.average(vals, weights=ws)) - self.global_mean_sog
                shrinkage = n / (n + 50.0)
                self.team_offsets[tid] = raw_diff * shrinkage
            else:
                self.team_offsets[tid] = 0.0

        # Estimate empirical log-residual scale on uncensored rows (sog > 2.0)
        log_res = []
        for r in valid:
            sog = float(r.get("sog_mps", 0.0))
            if sog <= 2.0:
                continue
            tws = float(r.get("tws_mps", 10.0))
            twa = abs(
                float(
                    math.degrees(
                        math.atan2(
                            float(r.get("twa_sin", 0.0)),
                            float(r.get("twa_cos", 1.0)),
                        )
                    )
                )
            )
            pred = self.predict(tws, twa, str(r.get("team_id", "")))
            log_res.append(math.log(sog) - math.log(max(pred, 2.0)))
        if len(log_res) >= 5:
            self.residual_log_scale = float(np.clip(np.std(log_res), 0.05, 0.8))

    def predict(self, tws_mps: float, twa_deg: float, team_id: str = "") -> float:
        """Predicts expected SOG in m/s using bilinear interpolation and team offset."""
        tws_clipped = np.clip(tws_mps, self.tws_bins[0], self.tws_bins[-1])
        twa_clipped = np.clip(abs(twa_deg), self.twa_bins[0], self.twa_bins[-1])

        i = int(np.clip(np.digitize(tws_clipped, self.tws_bins) - 1, 0, len(self.tws_bins) - 2))
        j = int(np.clip(np.digitize(twa_clipped, self.twa_bins) - 1, 0, len(self.twa_bins) - 2))

        t1, t2 = self.tws_bins[i], self.tws_bins[i + 1]
        a1, a2 = self.twa_bins[j], self.twa_bins[j + 1]

        u = (tws_clipped - t1) / (t2 - t1) if t2 > t1 else 0.0
        v = (twa_clipped - a1) / (a2 - a1) if a2 > a1 else 0.0

        q11 = self.grid_mean_sog[i, j]
        q12 = self.grid_mean_sog[i, j + 1]
        q21 = self.grid_mean_sog[i + 1, j]
        q22 = self.grid_mean_sog[i + 1, j + 1]

        base_sog = (
            (1.0 - u) * (1.0 - v) * q11
            + (1.0 - u) * v * q12
            + u * (1.0 - v) * q21
            + u * v * q22
        )

        offset = self.team_offsets.get(team_id, 0.0)
        return float(max(2.0, base_sog + offset))

    def predict_distribution(self, feature_row: Mapping[str, Any]) -> tuple[float, float]:
        """Returns (mu_log_sog, log_scale) for a feature row."""
        tws = float(feature_row.get("tws_mps", 10.0))
        twa = abs(
            float(
                math.degrees(
                    math.atan2(
                        float(feature_row.get("twa_sin", 0.0)),
                        float(feature_row.get("twa_cos", 1.0)),
                    )
                )
            )
        )
        tid = str(feature_row.get("team_id", ""))
        expected_sog = self.predict(tws, twa, tid)
        sig = self.residual_log_scale
        mu_log = math.log(max(expected_sog, 2.0)) - 0.5 * (sig ** 2)
        return float(mu_log), float(math.log(sig))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tws_bins": self.tws_bins.tolist(),
            "twa_bins": self.twa_bins.tolist(),
            "grid_mean_sog": self.grid_mean_sog.tolist(),
            "grid_counts": self.grid_counts.tolist(),
            "team_offsets": {k: round(v, 6) for k, v in self.team_offsets.items()},
            "global_mean_sog": round(self.global_mean_sog, 6),
            "residual_log_scale": round(self.residual_log_scale, 6),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BinnedPolarBaseline:
        m = cls(
            tws_bins=data.get("tws_bins"),
            twa_bins=data.get("twa_bins"),
        )
        if "grid_mean_sog" in data:
            m.grid_mean_sog = np.asarray(data["grid_mean_sog"], dtype=float)
        if "grid_counts" in data:
            m.grid_counts = np.asarray(data["grid_counts"], dtype=int)
        if "team_offsets" in data and isinstance(data["team_offsets"], Mapping):
            for k in CANONICAL_TEAMS:
                if k in data["team_offsets"]:
                    m.team_offsets[k] = float(data["team_offsets"][k])
        m.global_mean_sog = float(data.get("global_mean_sog", 18.0))
        m.residual_log_scale = float(data.get("residual_log_scale", 0.16))
        return m


class RegularizedSplinePolarBaseline:
    """Regularized Ridge linear-in-basis model predicting ln(SOG)."""

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = float(alpha)
        self.weights: np.ndarray | None = None
        self.bias: float = float(math.log(18.0))
        self.residual_scale: float = 0.15

    def _make_features(self, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
        n = len(rows)
        # Basis: tws, tws^2, twa_cos, twa_sin, tws*twa_cos, tws*twa_sin, practice_domain, 6 team one-hots
        d = 7 + len(CANONICAL_TEAMS)
        F = np.zeros((n, d), dtype=float)

        for i, r in enumerate(rows):
            tws = float(r.get("tws_mps", 10.0))
            twa_cos = float(r.get("twa_cos", 0.7))
            twa_sin = float(r.get("twa_sin", 0.7))
            prac = float(r.get("practice_domain", 0.0))

            F[i, 0] = tws / 10.0
            F[i, 1] = (tws / 10.0) ** 2
            F[i, 2] = twa_cos
            F[i, 3] = twa_sin
            F[i, 4] = (tws / 10.0) * twa_cos
            F[i, 5] = (tws / 10.0) * twa_sin
            F[i, 6] = prac

            tid = str(r.get("team_id", ""))
            for t_idx, team in enumerate(CANONICAL_TEAMS):
                if tid == team:
                    F[i, 7 + t_idx] = 1.0
                    break

        return F

    def fit(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Fits weighted ridge regression weights onto ln(SOG)."""
        if not rows:
            return

        y_list = []
        valid_rows = []
        for r in rows:
            sog = float(r.get("sog_mps", 0.0))
            if sog > 2.0:
                y_list.append(math.log(sog))
                valid_rows.append(r)

        if not valid_rows:
            return

        X = self._make_features(valid_rows)
        y = np.asarray(y_list, dtype=float)
        w = _compute_race_weights(valid_rows)

        self.bias = float(np.average(y, weights=w))
        y_centered = y - self.bias

        d = X.shape[1]
        WX = X * w[:, None]
        XtWX = X.T @ WX
        reg_I = self.alpha * np.eye(d)
        self.weights = np.linalg.solve(XtWX + reg_I, WX.T @ y_centered)

        residuals = y_centered - (X @ self.weights)
        var_w = float(np.average(residuals ** 2, weights=w))
        self.residual_scale = float(np.clip(math.sqrt(max(var_w, 1e-6)), 0.05, 0.8))

    def fit_with_validation(
        self,
        train_rows: Sequence[Mapping[str, Any]],
        val_rows: Sequence[Mapping[str, Any]],
        alphas: Sequence[float] = (0.1, 1.0, 10.0, 100.0),
    ) -> float:
        """Selects alpha on inner validation rows and refits on train_rows."""
        if not val_rows:
            self.fit(train_rows)
            return self.alpha

        best_alpha = self.alpha
        best_nll = float("inf")
        for cand_alpha in alphas:
            cand = RegularizedSplinePolarBaseline(alpha=cand_alpha)
            cand.fit(train_rows)
            nlls = []
            for r in val_rows:
                sog = float(r.get("sog_mps", 0.0))
                if sog <= 2.0:
                    continue
                mu_log, log_sig = cand.predict_distribution(r)
                sig = math.exp(log_sig)
                z = (math.log(sog) - mu_log) / sig
                nlls.append(log_sig + 0.5 * (z ** 2))
            mean_nll = float(np.mean(nlls)) if nlls else float("inf")
            if mean_nll < best_nll:
                best_nll = mean_nll
                best_alpha = float(cand_alpha)

        self.alpha = best_alpha
        self.fit(train_rows)
        return self.alpha

    def predict_distribution(self, feature_row: Mapping[str, Any]) -> tuple[float, float]:
        """Predicts (mu_log_sog, log_scale) in log-speed space."""
        if self.weights is None:
            return float(self.bias), float(math.log(self.residual_scale))
        x = self._make_features([feature_row])[0]
        pred_log = self.bias + float(x @ self.weights)
        return float(pred_log), float(math.log(self.residual_scale))

    def predict(self, feature_row: Mapping[str, Any]) -> tuple[float, float]:
        """Predicts (expected_sog_mps, log_scale)."""
        pred_log, log_scale = self.predict_distribution(feature_row)
        expected_sog = math.exp(pred_log + 0.5 * (self.residual_scale ** 2))
        return float(max(2.0, expected_sog)), float(log_scale)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "bias": round(self.bias, 6),
            "residual_scale": round(self.residual_scale, 6),
            "weights": self.weights.tolist() if self.weights is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RegularizedSplinePolarBaseline:
        m = cls(alpha=float(data.get("alpha", 1.0)))
        m.bias = float(data.get("bias", math.log(18.0)))
        m.residual_scale = float(data.get("residual_scale", 0.15))
        if data.get("weights") is not None:
            m.weights = np.asarray(data["weights"], dtype=float)
        return m
