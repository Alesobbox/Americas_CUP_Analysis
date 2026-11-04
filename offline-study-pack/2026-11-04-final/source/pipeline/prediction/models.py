"""Small, pooled forecasting models. No retrospective replay features are used here.

Input contracts deliberately require explicit audit flags for reliability.  A
recorded DNF or a truncated telemetry file is not an audited random failure.
The ranking and travel-time models are alternatives: their ability effects are
never added together in the simulator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def _competitive(row: Mapping[str, Any]) -> bool:
    return not bool(row.get("practice", False)) and row.get("competitive", True) is not False


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _digamma_positive(value: float) -> float:
    """Stable positive-argument digamma; avoids a mandatory scipy import."""
    correction = 0.
    while value < 8.:
        correction -= 1. / value
        value += 1.
    inverse = 1. / value
    return (correction + math.log(value) - .5 * inverse - inverse**2/12
            + inverse**4/120 - inverse**6/252)


def _trigamma_positive(value: float) -> float:
    correction = 0.
    while value < 8.:
        correction += 1. / value**2
        value += 1.
    inverse = 1. / value
    return correction + inverse + .5*inverse**2 + inverse**3/6 - inverse**5/30 + inverse**7/42


@dataclass
class StrengthModel:
    """Ridge-MAP Plackett--Luce reference, fitted only to valid finisher orders.

    Each row has ``order`` (best first). An optional ``wind_knots`` supports a
    strongly pooled entry-specific response; a common wind intercept would
    cancel. Nonfinishers must not be appended to ``order`` as weak finishers.
    """

    effects: dict[str, float] = field(default_factory=dict)
    wind_effects: dict[str, float] = field(default_factory=dict)
    wind_center: float = 0.0
    wind_scale: float = 1.0
    n_races: int = 0
    strength_sd: float = 1.2
    condition_sd: float = 0.25
    discrimination_scale: float = 1.0
    method: str = "ridge-plackett-luce-1"
    covariance: list[list[float]] = field(default_factory=list)
    boat_order: list[str] = field(default_factory=list)

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]], *, condition_effects: bool = False,
            strength_sd: float = 1.2, condition_sd: float = 0.25,
            practice_weight: float = 0.0,
            discrimination_scale: float = 1.8) -> "StrengthModel":
        valid_rows = []
        weights = []
        for r in rows:
            if len(r.get("order", [])) < 2 or r.get("order_valid", True) is False or r.get("competitive", True) is False:
                continue
            is_practice = bool(r.get("practice", False))
            w = practice_weight if is_practice else 1.0
            if w > 0:
                valid_rows.append(dict(r))
                weights.append(float(w))
        for row in valid_rows:
            if len(set(row["order"])) != len(row["order"]):
                raise ValueError("An order cannot contain duplicate entries")
        boats = sorted({str(b) for r in valid_rows for b in r["order"]})
        if not boats:
            return cls(strength_sd=strength_sd, condition_sd=condition_sd,
                       discrimination_scale=discrimination_scale)
        winds = [float(r["wind_knots"]) for r in valid_rows if _positive(r.get("wind_knots"))]
        center = float(np.mean(winds)) if winds else 0.0
        scale = max(float(np.std(winds)), 1.0) if winds else 1.0
        n = len(boats)
        dimensions = n * (2 if condition_effects else 1)
        lookup = {b: i for i, b in enumerate(boats)}
        precision = np.full(dimensions, 1.0 / strength_sd ** 2)
        if condition_effects:
            precision[n:] = 1.0 / condition_sd ** 2
        designs = []
        for row in valid_rows:
            order = [lookup[str(b)] for b in row["order"]]
            wind = ((float(row["wind_knots"]) - center) / scale
                    if _positive(row.get("wind_knots")) else 0.0)
            design = np.zeros((len(order), dimensions))
            design[np.arange(len(order)), order] = 1.0
            if condition_effects:
                design[np.arange(len(order)), np.array(order) + n] = wind
            designs.append(design)

        def objective(beta: np.ndarray, derivatives: bool = True):
            value = 0.5 * float(np.dot(precision * beta, beta))
            gradient = precision * beta
            hessian = np.diag(precision)
            for w, design in zip(weights, designs):
                for k in range(len(design) - 1):
                    x = design[k:]
                    logits = x @ beta
                    peak = float(np.max(logits))
                    weights_k = np.exp(logits - peak)
                    weights_k /= weights_k.sum()
                    value += w * (peak + math.log(float(np.exp(logits - peak).sum())) - logits[0])
                    if derivatives:
                        mean = weights_k @ x
                        gradient += w * (mean - x[0])
                        centered = x - mean
                        hessian += w * ((centered.T * weights_k) @ centered)
            return value, gradient, hessian

        beta = np.zeros(dimensions)
        for _ in range(50):
            value, gradient, hessian = objective(beta)
            step = np.linalg.solve(hessian, gradient)
            if float(np.linalg.norm(step)) < 1e-9:
                break
            fraction = 1.0
            while fraction > 1e-7:
                trial = beta - fraction * step
                if objective(trial, False)[0] <= value:
                    beta = trial
                    break
                fraction *= 0.5
            else:
                break
        beta[:n] -= beta[:n].mean()
        if condition_effects:
            beta[n:] -= beta[n:].mean()
        # Laplace approximation: Gaussian posterior with the MAP Hessian. The
        # ridge prior makes the Hessian positive definite.
        covariance = np.linalg.inv(objective(beta)[2])
        covariance = (covariance + covariance.T) / 2
        return cls(dict(zip(boats, map(float, beta[:n]))),
                   dict(zip(boats, map(float, beta[n:]))) if condition_effects else {},
                   center, scale, len(valid_rows), strength_sd, condition_sd,
                   discrimination_scale=discrimination_scale,
                   covariance=covariance.tolist(), boat_order=boats)

    def sample_log_worth(self, boat_ids: Sequence[str], rng: np.random.Generator, n: int,
                         wind_knots: float | None = None,
                         state_features: Mapping[str, float] | None = None,
                         *, state_coefficient: float = 0.25) -> np.ndarray:
        """Posterior draws of log-worth, shape (n, len(boat_ids)).

        Fitted entries use the Laplace posterior (correlated). Unseen entries
        draw independently from the ridge prior, so a new boat is uncertain
        rather than average-with-certainty.
        """
        wind = (wind_knots - self.wind_center) / self.wind_scale if wind_knots is not None else 0.0
        mean = self.log_worth(boat_ids, wind_knots, state_features, state_coefficient=state_coefficient)
        draws = np.repeat(mean[None, :], n, axis=0)
        known_indices = {b: i for i, b in enumerate(self.boat_order)}
        specified = set(self.boat_order) | set(self.effects.keys())
        m = len(self.boat_order)
        conditional = bool(self.wind_effects)
        if self.covariance and m:
            cov = np.asarray(self.covariance, dtype=float)
            # Linear map from parameters to the requested fitted entries.
            columns = [j for j, b in enumerate(boat_ids) if b in known_indices]
            if columns:
                design = np.zeros((len(columns), cov.shape[0]))
                for row, j in enumerate(columns):
                    design[row, known_indices[boat_ids[j]]] = 1.0
                    if conditional:
                        design[row, m + known_indices[boat_ids[j]]] = wind
                local = design @ cov @ design.T
                sampled_shifts = rng.multivariate_normal(np.zeros(len(columns)), local, size=n,
                                                         method="cholesky")
                if len(columns) > 1:
                    sampled_shifts -= sampled_shifts.mean(axis=1, keepdims=True)
                draws[:, columns] += sampled_shifts
        unseen = [j for j, b in enumerate(boat_ids) if b not in specified]
        if unseen:
            sd = math.sqrt(self.strength_sd**2 + (wind * self.condition_sd)**2 if conditional else self.strength_sd**2)
            draws[:, unseen] += rng.normal(0.0, sd, size=(n, len(unseen)))
        return draws

    def log_worth(self, boat_ids: Sequence[str], wind_knots: float | None = None,
                  state_features: Mapping[str, float] | None = None,
                  *, state_coefficient: float = 0.25) -> np.ndarray:
        wind = (wind_knots - self.wind_center) / self.wind_scale if wind_knots is not None else 0.0
        # A conservative fixed benchmark extension, not an estimated physical law.
        return np.array([self.effects.get(b, 0.0) + wind * self.wind_effects.get(b, 0.0)
                         + state_coefficient * (state_features or {}).get(b, 0.0)
                         for b in boat_ids], dtype=float)

    def predict_win_probabilities(self, boat_ids: Sequence[str], wind_knots: float | None = None,
                                  state_features: Mapping[str, float] | None = None) -> dict[str, float]:
        if not boat_ids:
            return {}
        logits = self.log_worth(boat_ids, wind_knots, state_features)
        scaled = logits * self.discrimination_scale
        worth = np.exp(scaled - scaled.max())
        return dict(zip(boat_ids, map(float, worth / worth.sum())))

    def sample_orders(self, boat_ids: Sequence[str], n: int, seed: int = 42,
                      wind_knots: float | None = None) -> np.ndarray:
        """Rows contain field indices, in finishing order (Gumbel top-k)."""
        rng = np.random.default_rng(seed)
        scores = self.log_worth(boat_ids, wind_knots) * self.discrimination_scale + rng.gumbel(size=(n, len(boat_ids)))
        return np.argsort(-scores, axis=1, kind="stable")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StrengthModel":
        return cls(**dict(payload))


@dataclass
class UniformOrderModel:
    """Field-aware exchangeable complete-order reference."""

    method: str = "uniform-order-1"

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]] = ()) -> "UniformOrderModel":
        return cls()

    def predict_win_probabilities(self, boat_ids: Sequence[str], **_: Any) -> dict[str, float]:
        return {b: 1.0 / len(boat_ids) for b in boat_ids}

    def expected_positions(self, boat_ids: Sequence[str]) -> dict[str, float]:
        return {b: (len(boat_ids) + 1) / 2 for b in boat_ids}

    def sample_orders(self, boat_ids: Sequence[str], n: int, seed: int = 42, **_: Any) -> np.ndarray:
        return np.argsort(np.random.default_rng(seed).random((n, len(boat_ids))), axis=1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EmpiricalOrderModel:
    """Race-equal historical-order bootstrap with uniform unseen-entry insertion.

    A subset of a recorded order retains that order. New field members are
    inserted uniformly among all compatible full orders; missing observations
    are therefore not treated as losses. This reference is conditional on the
    sampled set completing; completion is the separate shared component.
    """

    orders: list[list[str]] = field(default_factory=list)
    method: str = "pooled-empirical-order-1"

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]]) -> "EmpiricalOrderModel":
        return cls([list(map(str, row["order"])) for row in rows
                    if _competitive(row) and row.get("order_valid", True) is not False
                    and len(row.get("order", [])) >= 2])

    def predict_win_probabilities(self, boat_ids: Sequence[str], **_: Any) -> dict[str, float]:
        if not self.orders:
            return UniformOrderModel().predict_win_probabilities(boat_ids)
        field_set = set(boat_ids)
        probability = dict.fromkeys(boat_ids, 0.0)
        for order in self.orders:
            known = [b for b in order if b in field_set]
            if not known:
                for b in boat_ids:
                    probability[b] += 1.0 / len(boat_ids)
            else:
                probability[known[0]] += len(known) / len(boat_ids)
                for b in field_set - set(known):
                    probability[b] += 1.0 / len(boat_ids)
        return {b: float(p / len(self.orders)) for b, p in probability.items()}

    def expected_positions(self, boat_ids: Sequence[str]) -> dict[str, float]:
        if not self.orders:
            return UniformOrderModel().expected_positions(boat_ids)
        result = dict.fromkeys(boat_ids, 0.0)
        field_set = set(boat_ids)
        for order in self.orders:
            known = [b for b in order if b in field_set]
            for rank, b in enumerate(known, 1):
                result[b] += rank * (len(boat_ids) + 1) / (len(known) + 1)
            for b in field_set - set(known):
                result[b] += (len(boat_ids) + 1) / 2
        return {b: float(p / len(self.orders)) for b, p in result.items()}

    def sample_orders(self, boat_ids: Sequence[str], n: int, seed: int = 42, **_: Any) -> np.ndarray:
        rng = np.random.default_rng(seed)
        priorities = rng.random((n, len(boat_ids)))
        if self.orders:
            selected = rng.integers(0, len(self.orders), n)
            lookup = {b: j for j, b in enumerate(boat_ids)}
            for order_index in np.unique(selected):
                indices = [lookup[b] for b in self.orders[order_index] if b in lookup]
                rows = np.flatnonzero(selected == order_index)
                if indices:
                    priorities[np.ix_(rows, indices)] = np.sort(priorities[np.ix_(rows, indices)], axis=1)
        return np.argsort(priorities, axis=1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConditionalLogitModel:
    """Small jointly regularized PL state benchmark, with past-only scaling.

    Rows use ``order`` and ``state_features[boat][name]``. Each race's total
    checkpoint weight must be one (``weight``); callers cannot manufacture
    independent races by repeating ten-second observations. Missing feature
    values use the training mean. The diffusion feature is derived exclusively
    from current progress, never eventual race duration.
    """

    effects: dict[str, float] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=lambda: ["diffusion_lead", "relative_vmg", "crosswind_fraction"])
    feature_means: list[float] = field(default_factory=list)
    feature_scales: list[float] = field(default_factory=list)
    state_coefficients: list[float] = field(default_factory=list)
    n_rows: int = 0
    method: str = "conditional-ridge-plackett-luce-1"

    @staticmethod
    def _features(values: Mapping[str, Any]) -> dict[str, Any]:
        output = dict(values)
        if "diffusion_lead" not in output and "lead_fraction" in output:
            output["diffusion_lead"] = float(output["lead_fraction"]) / math.sqrt(
                max(float(output.get("remaining_fraction", 1.0)), 0.01))
        return output

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]], *, raw_lead_ablation: bool = False) -> "ConditionalLogitModel":
        rows = [dict(r) for r in rows if _competitive(r) and len(r.get("order", [])) >= 2
                and r.get("order_valid", True) is not False]
        names = ["lead_fraction" if raw_lead_ablation else "diffusion_lead", "relative_vmg", "crosswind_fraction"]
        if not rows:
            return cls(feature_names=names, feature_means=[0.] * 3,
                       feature_scales=[1.] * 3, state_coefficients=[0.] * 3)
        boats = sorted({str(b) for row in rows for b in row["order"]})
        lookup = {b: j for j, b in enumerate(boats)}
        observed = []
        for row in rows:
            for b in row["order"]:
                features = cls._features(row.get("state_features", {}).get(b, {}))
                observed.append([features.get(name, np.nan) for name in names])
        observed = np.asarray(observed, dtype=float)
        means = np.array([np.nanmean(observed[:, k]) if np.any(np.isfinite(observed[:, k])) else 0.
                          for k in range(3)])
        scales = np.array([max(float(np.nanstd(observed[:, k])), 1e-6)
                           if np.any(np.isfinite(observed[:, k])) else 1. for k in range(3)])
        precision = np.r_[np.full(len(boats), 4.), np.full(3, 16.)]
        designs = []
        # Default row weights normalize repeated checkpoints within race.
        race_counts: dict[str, int] = {}
        for index, row in enumerate(rows):
            race_key = str(row.get("race_id", f"row:{index}"))
            race_counts[race_key] = race_counts.get(race_key, 0) + 1
        for index, row in enumerate(rows):
            design = np.zeros((len(row["order"]), len(boats) + 3))
            for j, boat in enumerate(row["order"]):
                design[j, lookup[str(boat)]] = 1.
                features = cls._features(row.get("state_features", {}).get(boat, {}))
                values = np.array([features.get(name, means[k]) for k, name in enumerate(names)], dtype=float)
                values[~np.isfinite(values)] = means[~np.isfinite(values)]
                design[j, len(boats):] = (values - means) / scales
            weight = float(row.get("weight", 1. / race_counts[str(row.get("race_id", f"row:{index}"))]))
            if not 0 < weight <= 1:
                raise ValueError("Checkpoint weight must lie in (0,1]")
            designs.append((design, weight))
        beta = np.zeros(len(precision))
        for _ in range(40):
            grad = precision * beta
            hess = np.diag(precision)
            for design, weight in designs:
                for k in range(len(design) - 1):
                    x = design[k:]
                    score = x @ beta
                    p = np.exp(score - np.max(score))
                    p /= p.sum()
                    mean = p @ x
                    grad += weight * (mean - x[0])
                    centered = x - mean
                    hess += weight * (centered.T * p) @ centered
            step = np.linalg.solve(hess, grad)
            # The strongly regularized, standardized model has a bounded step;
            # damping protects sparse near-separable examples.
            step /= max(1., float(np.linalg.norm(step)))
            beta -= step
            if np.linalg.norm(step) < 1e-8:
                break
        return cls(dict(zip(boats, map(float, beta[:len(boats)]))), names,
                   list(map(float, means)), list(map(float, scales)),
                   list(map(float, beta[len(boats):])), len(rows))

    def predict_win_probabilities(self, boat_ids: Sequence[str],
                                  state_features: Mapping[str, Mapping[str, Any]] | None = None, **_: Any) -> dict[str, float]:
        if not boat_ids:
            return {}
        means = np.array(self.feature_means or [0.] * 3)
        scales = np.array(self.feature_scales or [1.] * 3)
        beta = np.array(self.state_coefficients or [0.] * 3)
        scores = []
        for boat in boat_ids:
            features = self._features((state_features or {}).get(boat, {}))
            values = np.array([features.get(name, means[k]) for k, name in enumerate(self.feature_names)])
            values = np.where(np.isfinite(values), values, means)
            scores.append(self.effects.get(boat, 0.) + float(((values - means) / scales) @ beta))
        p = np.exp(np.asarray(scores) - max(scores))
        return dict(zip(boat_ids, map(float, p / p.sum())))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompletionModel:
    """Pooled DNS and in-race non-completion posteriors over scheduled entries.

    Two ascertainment tiers are accepted and counted separately:

    * ``audited=True`` independent reviews. Started records require
      ``completed=True`` or ``failure_type='exogenous'``; unknown/time-rule
      outcomes block availability (no approved censoring treatment).
    * ``ascertainment='source'`` reconstructions from the same feed. For the
      first-valid-on-water-finisher target every started non-completion
      (retired, disqualified or unresolved) removes the boat from the on-water
      finish, so all of them count as non-completion events. Their cause is not
      claimed; ``evidence_tier`` reports that the rate is source-reconstructed.

    Practice contributes no counts. A race with an audited record uses it in
    preference to the source reconstruction (caller responsibility).
    """

    dns_events: int = 0
    scheduled_audited: int = 0
    failure_events: int = 0
    starters_ascertained: int = 0
    prior_alpha: float = 0.0
    prior_beta: float = 0.0
    excluded_records: int = 0
    unresolved_audited_starters: int = 0
    source_records: int = 0
    source_failure_types: dict[str, int] = field(default_factory=dict)
    method: str = "pooled-beta-completion-2"

    @property
    def evidence_tier(self) -> str | None:
        if not self.scheduled_audited:
            return "bayesian_prior" if (self.prior_alpha > 0 and self.prior_beta > 0) else None
        if self.source_records == 0:
            return "independent_audit"
        return "source_reconstructed" if self.source_records == self.scheduled_audited else "mixed_audit_and_source"

    @property
    def available(self) -> bool:
        if self.unresolved_audited_starters > 0:
            return False
        if self.scheduled_audited > 0 and self.starters_ascertained > 0:
            return True
        if self.scheduled_audited == 0:
            return self.prior_alpha > 0 and self.prior_beta > 0
        return False

    @property
    def reason(self) -> str | None:
        if self.unresolved_audited_starters:
            return "Audited starters include unresolved/time-rule failure ascertainment; no approved exposure-censoring treatment"
        if self.scheduled_audited > 0 and self.starters_ascertained == 0:
            return "No earlier competitive starter completion denominator"
        if not self.available:
            return "No earlier competitive scheduled-entry completion denominator"
        return None

    @classmethod
    def fit(cls, records: Iterable[Mapping[str, Any]], *, prior: str = "jeffreys") -> "CompletionModel":
        if prior not in {"jeffreys", "beta-1-19"}:
            raise ValueError("Unknown completion prior")
        model = cls(prior_alpha=0.5 if prior == "jeffreys" else 1.0,
                    prior_beta=0.5 if prior == "jeffreys" else 19.0)
        for record in records:
            source = record.get("ascertainment") == "source" and record.get("audited") is not True
            if (not _competitive(record) or not isinstance(record.get("started"), bool)
                    or not (source or record.get("audited") is True)):
                model.excluded_records += 1
                continue
            model.scheduled_audited += 1
            if source:
                model.source_records += 1
            if not record["started"]:
                model.dns_events += 1
            elif record.get("completed") is True:
                model.starters_ascertained += 1
            elif source:
                cause = str(record.get("failure_type") or "unresolved")
                model.source_failure_types[cause] = model.source_failure_types.get(cause, 0) + 1
                model.starters_ascertained += 1
                model.failure_events += 1
            elif record.get("failure_type") == "exogenous":
                model.starters_ascertained += 1
                model.failure_events += 1
            else:
                model.excluded_records += 1
                model.unresolved_audited_starters += 1
        return model

    @property
    def dns_mean(self) -> float | None:
        if not self.available:
            return None
        return (self.dns_events + self.prior_alpha) / (self.scheduled_audited + self.prior_alpha + self.prior_beta)

    @property
    def failure_mean(self) -> float | None:
        if not self.available:
            return None
        return (self.failure_events + self.prior_alpha) / (self.starters_ascertained + self.prior_alpha + self.prior_beta)

    def sample(self, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
        if not self.available:
            raise ValueError(self.reason)
        dns = rng.beta(self.dns_events + self.prior_alpha,
                       self.scheduled_audited - self.dns_events + self.prior_beta, n)
        failure = rng.beta(self.failure_events + self.prior_alpha,
                           self.starters_ascertained - self.failure_events + self.prior_beta, n)
        return dns, failure

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "available": self.available, "reason": self.reason,
                "evidence_tier": self.evidence_tier,
                "dns_mean": self.dns_mean, "failure_mean": self.failure_mean}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionModel":
        keys = cls.__dataclass_fields__
        return cls(**{k: v for k, v in payload.items() if k in keys})


@dataclass
class LegTimeModel:
    """Joint pooled lognormal reference fitted to observed valid gate transitions.

    Full travel times already contain manoeuvre/performance loss. The severe-loss
    mixture remains disabled unless independently reviewed labels and held-out
    promotion evidence are supplied. No additional delay is silently appended.
    All dynamics coefficients, crew effects and residual factors use the same fit.
    """

    coefficients: list[float] = field(default_factory=lambda: [math.log(120.0), 1.0, 0.0])
    crew_effects: dict[str, float] = field(default_factory=dict)
    kind_effects: dict[str, float] = field(default_factory=dict)
    distance_reference_m: float = 1000.0
    wind_reference_knots: float = 12.0
    residual_sigma: float = 0.0
    crew_form_sigma: float = 0.0
    race_sigma: float = 0.0
    weather_sigma: float = 0.0
    innovation_sigma: float = 0.0
    innovation_rho: float = 0.0
    n_rows: int = 0
    n_races: int = 0
    mixture_enabled: bool = False
    mixture_reason: str = "Reviewed loss labels and held-out promotion evidence are absent; fitted lognormal reference retained"
    dependence_evidence: str = "earlier in-sample synchronized residual moments; provisional; innovation AR coefficient fully pooled to zero without certified out-of-fold lag evidence"
    method: str = "pooled-correlated-lognormal-1"

    @property
    def available(self) -> bool:
        return self.n_rows >= 2

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]]) -> "LegTimeModel":
        valid = [dict(r) for r in rows if _competitive(r) and r.get("valid", True) is not False
                 and _positive(r.get("duration_s")) and _positive(r.get("distance_m"))
                 and r.get("target_censored", False) is not True]
        # Final retirement does not exclude a previously observed valid leg.
        if len(valid) < 2:
            return cls(n_rows=len(valid))
        crews = sorted({str(r["boat_id"]) for r in valid})
        kinds = sorted({str(r.get("leg_kind", "unknown")) for r in valid})
        reference = float(np.exp(np.mean(np.log([r["distance_m"] for r in valid]))))
        winds = [r["wind_knots"] for r in valid if _positive(r.get("wind_knots"))]
        wind_ref = float(np.exp(np.mean(np.log(winds)))) if winds else 12.0
        x = np.zeros((len(valid), 3 + len(crews) + len(kinds)))
        y = np.log([r["duration_s"] for r in valid])
        for i, row in enumerate(valid):
            x[i, :3] = [1.0, math.log(row["distance_m"] / reference),
                        math.log(row["wind_knots"] / wind_ref) if _positive(row.get("wind_knots")) else 0.0]
            x[i, 3 + crews.index(str(row["boat_id"]))] = 1.0
            x[i, 3 + len(crews) + kinds.index(str(row.get("leg_kind", "unknown")))] = 1.0
        # Distance elasticity centered at 1; other non-intercept coefficients
        # pooled to zero. Crew log-time effects fitted once, never PL plus time.
        precision = np.full(x.shape[1], 4.0)
        precision[0] = 1e-8
        precision[2] = 16.0
        prior = np.zeros(x.shape[1])
        prior[1] = 1.0
        beta = np.linalg.solve(x.T @ x + np.diag(precision), x.T @ y + precision * prior)
        residual = y - x @ beta
        total = float(np.mean(residual ** 2))
        race_groups: dict[str, list[int]] = {}
        phase_groups: dict[tuple[str, str], list[int]] = {}
        crew_groups: dict[tuple[str, str], list[int]] = {}
        for i, row in enumerate(valid):
            race = str(row.get("race_id", "unknown"))
            race_groups.setdefault(race, []).append(i)
            phase_groups.setdefault((race, str(row.get("leg_index", row.get("leg_kind", "unknown")))), []).append(i)
            crew_groups.setdefault((race, str(row["boat_id"])), []).append(i)

        def covariance(groups: Mapping[Any, list[int]], different_boats: bool = False) -> tuple[float, int]:
            products = []
            for indices in groups.values():
                for a, i in enumerate(indices):
                    for j in indices[a + 1:]:
                        if different_boats and valid[i]["boat_id"] == valid[j]["boat_id"]:
                            continue
                        products.append(float(residual[i] * residual[j]))
            if not products:
                return 0.0, 0
            # Small-factor shrinkage protects tiny synchronized samples.
            return max(0.0, float(np.mean(products))) * len(products) / (len(products) + 20), len(products)

        race_var, _ = covariance(race_groups, True)
        phase_var, _ = covariance(phase_groups, True)
        own_var, _ = covariance(crew_groups)
        race_var = min(race_var, total * 0.35)
        weather_var = min(max(phase_var - race_var, 0.0), total * 0.35)
        own_var = min(max(own_var - race_var - weather_var, 0.0), total * 0.35)
        innovation_var = max(total - race_var - weather_var - own_var, 0.0)
        return cls(list(map(float, beta[:3])), dict(zip(crews, map(float, beta[3:3 + len(crews)]))),
                   dict(zip(kinds, map(float, beta[3 + len(crews):]))), reference, wind_ref,
                   math.sqrt(total), math.sqrt(own_var), math.sqrt(race_var), math.sqrt(weather_var),
                   math.sqrt(innovation_var), 0.0, len(valid), len(race_groups))

    def median_seconds(self, boat_id: str, leg: Mapping[str, Any], wind_knots: float | None = None) -> float:
        distance = float(leg.get("distance_m", self.distance_reference_m))
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError("Leg distance must be positive metres")
        wind = wind_knots if wind_knots is not None else leg.get("wind_knots", self.wind_reference_knots)
        if not _positive(wind):
            raise ValueError("Wind must be positive knots")
        b = self.coefficients
        logtime = (b[0] + b[1] * math.log(distance / self.distance_reference_m)
                   + b[2] * math.log(float(wind) / self.wind_reference_knots)
                   + self.crew_effects.get(boat_id, 0.0)
                   + self.kind_effects.get(str(leg.get("leg_kind", "unknown")), 0.0))
        return math.exp(float(logtime))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "available": self.available}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LegTimeModel":
        return cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})


@dataclass
class PositiveDelayMixture:
    """Gated research candidate fitted jointly by convolution EM.

    ``T = LogNormal(X beta, sigma) + Z * Gamma(shape, scale_seconds)``.
    The EM refits the clean context/crew regression; it never appends a delay to
    the unchanged loss-inclusive reference. Reviewed ``loss_episode`` booleans
    anchor Z only when ``loss_reviewed=True``. These are performance-loss labels,
    not foil-state measurements. Fit availability is separate from promotion.

    The minimum counts and stability thresholds below are preregistered
    engineering safeguards, not a statistical identifiability theorem. A caller
    must supply independently stored frozen held-out promotion evidence before
    ``promoted`` can become true. Current source data do not provide this.
    """

    available: bool = False
    promoted: bool = False
    reason: str = "No reviewed competitive clean/loss labels"
    clean_model_payload: dict[str, Any] = field(default_factory=dict)
    episode_probability: float = 0.0
    delay_shape: float = 2.0
    delay_scale_seconds: float = 0.0
    clean_sigma: float = 0.0
    n_rows: int = 0
    reviewed_clean: int = 0
    reviewed_loss: int = 0
    n_dates: int = 0
    stable: bool = False
    training_mean_log_likelihood: float | None = None
    stability_diagnostics: dict[str, float] = field(default_factory=dict)
    method: str = "joint-lognormal-gamma-convolution-em-1"

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, Any]], *, baseline: LegTimeModel | None = None,
            promotion_evidence: Mapping[str, Any] | None = None) -> "PositiveDelayMixture":
        valid = [dict(r) for r in rows if _competitive(r) and r.get("valid", True) is not False
                 and _positive(r.get("duration_s")) and _positive(r.get("distance_m"))
                 and not r.get("target_censored", False)]
        clean = sum(r.get("loss_reviewed") is True and r.get("loss_episode") is False for r in valid)
        loss = sum(r.get("loss_reviewed") is True and r.get("loss_episode") is True for r in valid)
        dates = sorted({str(r["date"]) for r in valid if r.get("date")})
        result = cls(n_rows=len(valid), reviewed_clean=clean, reviewed_loss=loss, n_dates=len(dates))
        if clean < 50 or loss < 20 or len(dates) < 3:
            result.reason = "Joint mixture requires at least 50 reviewed clean, 20 reviewed loss legs and three competitive dates"
            return result
        baseline = baseline or LegTimeModel.fit(valid)
        crews = sorted({str(r["boat_id"]) for r in valid})
        kinds = sorted({str(r.get("leg_kind", "unknown")) for r in valid})
        x = np.zeros((len(valid), 3 + len(crews) + len(kinds)))
        for i, row in enumerate(valid):
            x[i, :3] = [1., math.log(row["distance_m"] / baseline.distance_reference_m),
                        math.log(row["wind_knots"] / baseline.wind_reference_knots)
                        if _positive(row.get("wind_knots")) else 0.]
            x[i, 3 + crews.index(str(row["boat_id"]))] = 1.
            x[i, 3 + len(crews) + kinds.index(str(row.get("leg_kind", "unknown")))] = 1.
        target = np.array([r["duration_s"] for r in valid], dtype=float)
        labels = np.array([int(r["loss_episode"]) if r.get("loss_reviewed") is True
                           and isinstance(r.get("loss_episode"), bool) else -1 for r in valid])
        initial = np.r_[baseline.coefficients,
                        [baseline.crew_effects.get(b, 0.) for b in crews],
                        [baseline.kind_effects.get(k, 0.) for k in kinds]]
        precision = np.r_[1e-8, 4., 16., np.full(len(crews) + len(kinds), 4.)]
        prior = np.zeros(len(precision))
        prior[1] = 1.

        def fit_one(indices: np.ndarray, offset: float = 0.) -> dict[str, Any]:
            design = x[indices]
            times = target[indices]
            observed = labels[indices]
            beta = initial.copy()
            beta[0] += offset
            sigma = max(float(np.std(np.log(times) - design @ beta)) * .7, .03)
            pi = min(.8, max(.05, float(np.mean(observed == 1))))
            shape = 2.
            scale = max(float(np.median(times)) * .15, .1)
            # Midpoint quadrature over 0<delay<T. Units remain seconds and the
            # integration Jacobian is T/64, not a dimensionless log-time jump.
            delay = times[:, None] * ((np.arange(64) + .5) / 64)[None, :]
            log_clean = np.log(times[:, None] - delay)
            log_times = np.log(times)
            expected_log_clean = log_times.copy()
            log_likelihood = -math.inf
            for _ in range(100):
                mu = design @ beta
                density_clean = (-np.log(times * sigma * math.sqrt(2 * math.pi))
                                 - .5 * ((log_times - mu) / sigma) ** 2)
                log_joint = (-np.log((times[:, None] - delay) * sigma * math.sqrt(2 * math.pi))
                             - .5 * ((log_clean - mu[:, None]) / sigma) ** 2
                             + (shape - 1) * np.log(delay) - delay / scale
                             - math.lgamma(shape) - shape * math.log(scale)
                             + np.log(times[:, None] / 64))
                peak = log_joint.max(axis=1)
                quadrature = np.exp(log_joint - peak[:, None])
                total = quadrature.sum(axis=1)
                quadrature /= total[:, None]
                density_loss = peak + np.log(total)
                a = math.log1p(-pi) + density_clean
                b = math.log(pi) + density_loss
                maximum = np.maximum(a, b)
                denominator = maximum + np.log(np.exp(a-maximum) + np.exp(b-maximum))
                z = np.exp(b-denominator)
                z[observed == 0] = 0.
                z[observed == 1] = 1.
                assigned_log_likelihood = denominator.copy()
                assigned_log_likelihood[observed == 0] = a[observed == 0]
                assigned_log_likelihood[observed == 1] = b[observed == 1]
                current_ll = float(np.mean(assigned_log_likelihood))
                posterior_log = (quadrature * log_clean).sum(axis=1)
                posterior_log2 = (quadrature * log_clean ** 2).sum(axis=1)
                expected_log_clean = (1-z) * log_times + z * posterior_log
                expected_log2 = (1-z) * log_times ** 2 + z * posterior_log2
                beta = np.linalg.solve(design.T @ design + np.diag(precision),
                                       design.T @ expected_log_clean + precision * prior)
                fitted = design @ beta
                sigma = math.sqrt(max(float(np.mean(expected_log2 - 2*fitted*expected_log_clean + fitted**2)), 1e-5))
                pi = float((z.sum() + .5) / (len(z) + 1.))
                delay_mean = float(np.sum(z * (quadrature * delay).sum(axis=1)) / max(z.sum(), 1e-8))
                mean_log_delay = float(np.sum(z * (quadrature * np.log(delay)).sum(axis=1)) / max(z.sum(), 1e-8))
                gamma_target = math.log(max(delay_mean, 1e-8)) - mean_log_delay
                for _ in range(12):
                    gradient = math.log(shape) - _digamma_positive(shape) - gamma_target
                    derivative = 1./shape - _trigamma_positive(shape)
                    updated = float(np.clip(shape-gradient/derivative, .5, 20.))
                    if abs(updated-shape) < 1e-7:
                        break
                    shape = updated
                scale = max(delay_mean/shape, .001)
                if abs(current_ll-log_likelihood) < 1e-6:
                    log_likelihood = current_ll
                    break
                log_likelihood = current_ll
            return {"beta": beta, "sigma": sigma, "pi": pi, "shape": shape,
                    "scale": scale, "log_likelihood": log_likelihood}

        all_indices = np.arange(len(valid))
        fits = [fit_one(all_indices, offset) for offset in [0., -.10, -.25]]
        best = max(fits, key=lambda fitted: fitted["log_likelihood"])
        deletion_fits = [fit_one(np.array([i for i, r in enumerate(valid) if str(r.get("date")) != date]))
                         for date in dates]
        comparisons = fits + deletion_fits
        pi_range = max(f["pi"] for f in comparisons) - min(f["pi"] for f in comparisons)
        mean_delays = [f["shape"] * f["scale"] for f in comparisons]
        ratio = max(mean_delays) / max(min(mean_delays), 1e-8)
        sigma_ratio = max(f["sigma"] for f in comparisons) / max(min(f["sigma"] for f in comparisons), 1e-8)
        result.stability_diagnostics = {"pi_range": float(pi_range), "mean_delay_ratio": float(ratio),
                                        "clean_sigma_ratio": float(sigma_ratio)}
        result.stable = pi_range <= .15 and ratio <= 2. and sigma_ratio <= 2.
        beta = best["beta"]
        payload = baseline.to_dict()
        payload.update(coefficients=list(map(float, beta[:3])),
                       crew_effects=dict(zip(crews, map(float, beta[3:3+len(crews)]))),
                       kind_effects=dict(zip(kinds, map(float, beta[3+len(crews):]))))
        # Keep the residual variance decomposition coherent when replacing the
        # total inclusive distribution by the jointly fitted clean component.
        shrink = best["sigma"] / max(baseline.residual_sigma, 1e-8)
        for name in ["crew_form_sigma", "race_sigma", "weather_sigma", "innovation_sigma"]:
            payload[name] *= shrink
        payload["residual_sigma"] = best["sigma"]
        payload["mixture_enabled"] = False  # promotion is never implied by fit
        result.clean_model_payload = payload
        result.available = True
        result.episode_probability = best["pi"]
        result.delay_shape = best["shape"]
        result.delay_scale_seconds = best["scale"]
        result.clean_sigma = best["sigma"]
        result.training_mean_log_likelihood = best["log_likelihood"]
        evidence = promotion_evidence or {}
        needed = ["frozen_before_audit", "identification_reviewed", "tail_score_improved",
                  "primary_improved_race_equal", "primary_improved_day_equal",
                  "guardrails_pass", "locked_audit_direction"]
        result.promoted = result.stable and all(evidence.get(key) is True for key in needed)
        result.reason = ("Joint candidate passed stability and externally recorded frozen promotion gates"
                         if result.promoted else "Joint candidate fit only; stability or independent frozen held-out promotion evidence is incomplete")
        return result

    def sample_leg_seconds(self, median_seconds: float | np.ndarray, n: int,
                           rng: np.random.Generator) -> np.ndarray:
        """Research draw using a jointly fitted *clean* conditional median."""
        if not self.available:
            raise ValueError(self.reason)
        median = np.asarray(median_seconds, dtype=float)
        if np.any(median <= 0):
            raise ValueError("Clean median duration must be positive seconds")
        clean = median * np.exp(rng.normal(0., self.clean_sigma, n))
        episode = rng.random(n) < self.episode_probability
        return clean + episode * rng.gamma(self.delay_shape, self.delay_scale_seconds, n)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
