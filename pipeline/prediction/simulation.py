"""Vectorized joint gate-time Monte Carlo and coherent marginal summaries.

No XY path is forecast. Shared environment is evaluated at each boat's own
simulated calendar time; ordinary manoeuvre losses are already in fitted leg
times. Unknown legal phase or an unaudited completion denominator fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .models import CompletionModel, LegTimeModel, StrengthModel


TAIL_WEIGHT = 0.0001
TERMINAL_NONFINISH = {"dns", "dnf", "ret", "retired", "disqualified", "exogenous_failure"}


def hazard_integral(u: float | np.ndarray, legs: int, shape: str = "constant") -> np.ndarray:
    """Normalized H(u), so H(0)=0 and H(1)=1 for either declared shape."""
    if legs < 1 or shape not in {"constant", "transition"}:
        raise ValueError("Expected a positive leg count and constant/transition hazard")
    values = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    if shape == "constant":
        return values
    edges, cumulative = _hazard_grid(legs)
    return np.interp(values, edges, cumulative)


def _hazard_grid(legs: int) -> tuple[np.ndarray, np.ndarray]:
    edges = np.array(sorted({0.0, 1.0, 1.0 / legs,
                             *[(k + 0.95) / legs for k in range(legs)],
                             *[(k + 1) / legs for k in range(legs)]}))
    midpoint = (edges[:-1] + edges[1:]) / 2
    first_leg = midpoint < 1.0 / legs
    pre_gate = (midpoint * legs) % 1.0 >= 0.95
    # Union, not a double multiplier in overlapping first-leg/pre-gate zones.
    weights = np.where(first_leg | pre_gate, 2.0, 1.0)
    cumulative = np.r_[0.0, np.cumsum(np.diff(edges) * weights)]
    return edges, cumulative / cumulative[-1]


def conditional_failure_probability(q: float | np.ndarray, progress: float | np.ndarray,
                                    legs: int, shape: str = "constant") -> np.ndarray:
    q = np.asarray(q, dtype=float)
    if np.any((q < 0) | (q > 1)):
        raise ValueError("Failure probability must lie in [0,1]")
    return -np.expm1(np.log1p(-q) * (1.0 - hazard_integral(progress, legs, shape)))


def _uniform_marginals(p: np.ndarray, fixed_order: Sequence[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact uniform-order marginals conditional on each draw's completion risk.

    The polynomial is Poisson-binomial, hence sums all finisher subsets without
    adding numerical reference-order sampling noise. Rows of p may have shared
    Beta latent risks; independence is only conditional on that risk draw.
    """
    n, boats = p.shape
    means = np.zeros((n, boats))
    ranks = np.full((n, boats), float(boats))
    locked = set(fixed_order)
    if fixed_order:
        means[:, fixed_order[0]] = 1.0
        no_finisher = np.zeros(n)
        for place, index in enumerate(fixed_order, 1):
            ranks[:, index] = place
        free = [j for j in range(boats) if j not in locked]
        total = p[:, free].sum(axis=1)
        for index in free:
            ranks[:, index] = boats * (1 - p[:, index]) + p[:, index] * (
                len(fixed_order) + 1 + 0.5 * (total - p[:, index]))
    else:
        no_finisher = np.prod(1.0 - p, axis=1)
        total = p.sum(axis=1)
        for index in range(boats):
            count_distribution = np.ones((n, 1))
            for other in range(boats):
                if other == index:
                    continue
                previous = count_distribution
                count_distribution = np.zeros((n, previous.shape[1] + 1))
                count_distribution[:, :-1] += previous * (1 - p[:, other, None])
                count_distribution[:, 1:] += previous * p[:, other, None]
            means[:, index] = p[:, index] * (count_distribution / np.arange(1, boats + 1)).sum(axis=1)
            ranks[:, index] = boats * (1 - p[:, index]) + p[:, index] * (
                1 + 0.5 * (total - p[:, index]))
    return means.mean(axis=0), no_finisher.mean(), ranks.mean(axis=0)


@dataclass
class RaceSimulation:
    available: bool
    status: str
    reason: str | None
    boat_ids: list[str]
    win_probabilities: dict[str, float | None]
    no_finisher_probability: float | None
    expected_positions: dict[str, float | None]
    n_simulations: int
    seed: int
    numerical_error_95: float | None = None
    conditional_complete: bool = False
    assumptions: list[str] = field(default_factory=list)
    # Local diagnostics/samples, intentionally excluded from browser summaries.
    ranks: np.ndarray | None = field(default=None, repr=False)
    finish_times_s: np.ndarray | None = field(default=None, repr=False)
    gate_times_s: np.ndarray | None = field(default=None, repr=False)
    failure_course_fractions: np.ndarray | None = field(default=None, repr=False)
    winners: np.ndarray | None = field(default=None, repr=False)

    @property
    def win_prob_by_boat(self) -> dict[str, float | None]:
        return self.win_probabilities

    @property
    def expected_position_by_boat(self) -> dict[str, float | None]:
        return self.expected_positions

    @property
    def no_finisher_prob(self) -> float | None:
        return self.no_finisher_probability

    def to_dict(self) -> dict[str, Any]:
        return {"available": self.available, "status": self.status, "reason": self.reason,
                "boat_ids": self.boat_ids, "win_prob_by_boat": self.win_probabilities,
                "no_finisher_prob": self.no_finisher_probability,
                "expected_position_by_boat": self.expected_positions, "nonfinish_score": "N",
                "n_simulations": self.n_simulations, "seed": self.seed,
                "numerical_error_95": self.numerical_error_95,
                "conditional_complete": self.conditional_complete, "assumptions": self.assumptions}


def _unavailable(boats: Sequence[str], reason: str, n: int, seed: int) -> RaceSimulation:
    return RaceSimulation(False, "unavailable", reason, list(boats), dict.fromkeys(boats),
                          None, dict.fromkeys(boats), n, seed)


def _ranks_and_winners(times: np.ndarray, tie_break: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n, boats = times.shape
    # Random tie-break only for unresolved equal simulated arrivals. Resolved
    # observed orders use distinct validated times or fail closed upstream.
    order = np.lexsort((tie_break, times), axis=1)
    ranks = np.empty((n, boats), dtype=np.int16)
    ranks[np.arange(n)[:, None], order] = np.arange(1, boats + 1)
    ranks[~np.isfinite(times)] = boats
    winners = order[:, 0].copy()
    winners[~np.isfinite(times).any(axis=1)] = -1
    return ranks, winners


def simulate_race(model: LegTimeModel, boat_ids: Sequence[str], legs: Sequence[Mapping[str, Any]],
                  completion: CompletionModel | None, *, state: Mapping[str, Mapping[str, Any]] | None = None,
                  n: int = 20_000, seed: int = 42, conditional_complete: bool = False,
                  wind_knots: float | None = None, hazard_shape: str = "constant",
                  hazard_multiplier: float = 1.0, tail_weight: float = TAIL_WEIGHT,
                  known_winner: str | None = None, global_finish_order_resolved: bool = False,
                  race_time_limit_s: float | None = None, first_gate_limit_s: float | None = None,
                  finishing_window_s: float | None = None, return_samples: bool = True) -> RaceSimulation:
    """Sample one coherent race continuation.

    Per-boat state: ``current_leg`` zero-based, ``remaining_fraction`` in [0,1],
    ``elapsed_s`` gun-to-cutoff time, ``started`` bool, ``pace_ratio`` relative
    observed speed (optional), ``terminal_status``/``finished_at_s``, ``quality``.
    ``pace_ratio`` is an observation of the persistent pace factor with a
    residual-derived observation variance; missing pace leaves the prior intact.
    State uncertainty may be passed as ``remaining_fraction_sd`` and is sampled
    once, rather than subsequently added again as residual variance.

    A zero-progress/no-new-information current leg is precisely the full-leg
    prior under the same seed. Conditional-complete is diagnostic only and must
    never be exported as an unconditional public probability.
    """
    boats = list(boat_ids)
    count = len(boats)
    if count == 0 or len(set(boats)) != count:
        raise ValueError("A nonempty field with unique boat IDs is required")
    if n < 1 or not legs or not 0 <= tail_weight <= 1 or hazard_multiplier <= 0:
        raise ValueError("Invalid simulation size, course or mixture/hazard configuration")
    length = len(legs)
    if state is not None and any(b not in state for b in boats):
        return _unavailable(boats, "A contender's causal state is missing; field retained", n, seed)
    states = [dict((state or {}).get(b, {})) for b in boats]
    if any(s.get("quality", "available") not in {"available", "estimated", "fresh"} for s in states):
        return _unavailable(boats, "Unresolved field state or legal gate phase", n, seed)
    statuses = [str(s.get("terminal_status", "")).lower() for s in states]
    fixed_order = sorted([j for j, s in enumerate(states) if statuses[j] == "finished"],
                         key=lambda j: states[j].get("finished_at_s", math.inf))
    if any(not math.isfinite(float(states[j].get("finished_at_s", math.inf))) for j in fixed_order):
        return _unavailable(boats, "Observed finish lacks a resolved event time", n, seed)
    if len({states[j]["finished_at_s"] for j in fixed_order}) != len(fixed_order):
        return _unavailable(boats, "Equal observed finish times require an audited on-water order", n, seed)
    if fixed_order and not (global_finish_order_resolved or known_winner is not None):
        return _unavailable(boats, "First received finish is not a globally resolved first finisher", n, seed)
    if known_winner is not None and (known_winner not in boats or
                                    fixed_order and boats[fixed_order[0]] != known_winner):
        raise ValueError("Known winner conflicts with the field or observed finish order")
    all_terminal = all(t in TERMINAL_NONFINISH or t == "finished" for t in statuses)
    if not all_terminal and not model.available:
        return _unavailable(boats, "Fewer than two eligible empirical gate-duration targets", n, seed)
    if not all_terminal and not conditional_complete and (completion is None or not completion.available):
        return _unavailable(boats, completion.reason if completion else "Completion audit is absent", n, seed)
    current = np.array([int(s.get("current_leg", 0)) for s in states])
    remaining = np.array([float(s.get("remaining_fraction", 1.0)) for s in states])
    elapsed = np.array([float(s.get("elapsed_s", 0.0)) for s in states])
    if np.any((current < 0) | (current >= length)) or np.any((remaining < 0) | (remaining > 1)) or np.any(~np.isfinite(remaining)):
        return _unavailable(boats, "Invalid current course phase/progress", n, seed)
    if np.any(~np.isfinite(elapsed)) or np.any(elapsed < 0):
        return _unavailable(boats, "Invalid causal elapsed time", n, seed)
    progress = (current + 1.0 - remaining) / length
    known_started = np.array([s.get("started", state is not None) is True for s in states])
    rng = np.random.default_rng(seed)
    # Allocate the same latent arrays in the same order under competing fitted
    # models. Common random numbers reduce paired-comparison simulation noise.
    dns_uniform = rng.random((n, count))
    failure_exposure = rng.exponential(size=(n, count))
    crew_normal = rng.normal(size=(n, count))
    race_normal = rng.normal(size=(n, 1))
    weather_a = rng.normal(size=(n, 8))
    weather_b = rng.normal(size=(n, 8))
    omega = np.array([0.23, 0.47, 0.83, 1.19, 1.79, 2.71, 4.17, 7.13]) / 300.0
    innovation = rng.normal(size=(n, count, length))
    if not -0.95 <= model.innovation_rho <= 0.95:
        raise ValueError("Innovation persistence must lie in [-0.95,0.95]")
    for k in range(1, length):
        innovation[:, :, k] = (model.innovation_rho * innovation[:, :, k - 1]
                               + math.sqrt(1 - model.innovation_rho ** 2) * innovation[:, :, k])
    position_normal = rng.normal(size=(n, count))
    tie_break = rng.random((n, count))
    reference_uniform = rng.random((n, count))
    reference_priority = rng.random((n, count))
    mixture_uniform = rng.random(n)
    if conditional_complete or all_terminal:
        dns = np.zeros(n)
        q = np.zeros(n)
    else:
        assert completion is not None
        dns, q = completion.sample(rng, n)
        # Known starts are new survival evidence for the pooled DNS parameter.
        if known_started.any():
            dns = rng.beta(completion.dns_events + completion.prior_alpha,
                           completion.scheduled_audited - completion.dns_events + completion.prior_beta
                           + int(known_started.sum()), n)
        # Bayesian reweighting on observed post-start survival, without treating
        # that partial exposure as another complete successful race.
        exposure = float(hazard_integral(progress[known_started], length, hazard_shape).sum())
        if exposure > 0:
            log_weight = np.log1p(-q) * exposure
            weights = np.exp(log_weight - np.max(log_weight))
            q = q[rng.choice(n, n, replace=True, p=weights / weights.sum())]
    lam = -np.log1p(-q) * hazard_multiplier
    h_current = hazard_integral(progress, length, hazard_shape)
    failure_h = h_current[None, :] + failure_exposure / np.maximum(lam[:, None], 1e-300)
    failure_fraction = failure_h.copy()
    if hazard_shape == "transition":
        grid, integral = _hazard_grid(length)
        failure_fraction = np.interp(np.minimum(failure_h, 1.0), integral, grid)
    elif hazard_shape != "constant":
        raise ValueError("Unknown hazard shape")
    failure_fraction[failure_h > 1.0] = math.inf
    starts = dns_uniform >= dns[:, None]
    starts[:, known_started] = True
    completion_probability = np.exp(-lam[:, None] * (1.0 - h_current[None, :]))
    completion_probability *= np.where(known_started[None, :], 1.0, 1.0 - dns[:, None])
    for j, status in enumerate(statuses):
        if status in TERMINAL_NONFINISH:
            starts[:, j] = False
            completion_probability[:, j] = 0.0
            failure_fraction[:, j] = progress[j]
        elif status == "finished":
            starts[:, j] = True
            completion_probability[:, j] = 1.0
            failure_fraction[:, j] = math.inf

    crew_form = crew_normal * model.crew_form_sigma
    for j, s in enumerate(states):
        ratio = s.get("pace_ratio")
        if isinstance(ratio, (float, int)) and ratio > 0 and math.isfinite(ratio):
            # Conditioning the same persistent latent, not appending another
            # ability effect or treating future realized VMG as known.
            prior_var = model.crew_form_sigma ** 2
            obs_var = max(model.innovation_sigma ** 2, 1e-6)
            gain = prior_var / (prior_var + obs_var)
            crew_form[:, j] = (-gain * math.log(ratio)
                               + crew_normal[:, j] * math.sqrt((1 - gain) * prior_var))
    shared_race = race_normal[:, 0] * model.race_sigma

    def weather_at(times: np.ndarray) -> np.ndarray:
        phase = times[:, None] * omega[None, :]
        return (weather_a * np.cos(phase) + weather_b * np.sin(phase)).sum(axis=1) * model.weather_sigma / math.sqrt(8)

    gate_times = np.full((n, count, length), np.nan)
    times = np.broadcast_to(elapsed[None, :], (n, count)).copy()
    # Gate events are causally evaluated per boat. With the preregistered zero
    # tactical-interaction coefficient this vectorized queue is equivalent to a
    # sorted event queue and never inspects another boat's future gate arrival.
    for leg_index, leg in enumerate(legs):
        for j, boat in enumerate(boats):
            if leg_index < current[j] or statuses[j] in TERMINAL_NONFINISH or statuses[j] == "finished":
                continue
            entry = times[:, j]
            median = model.median_seconds(boat, leg, wind_knots)
            # A deterministic median window is computed before evaluating the
            # shared environment along each boat's own calendar interval.
            weather_entry = weather_at(entry)
            median_window = median * np.exp(weather_entry)
            shared_weather = 0.5 * (weather_entry + weather_at(entry + median_window))
            log_residual = crew_form[:, j] + shared_race + shared_weather + model.innovation_sigma * innovation[:, j, leg_index]
            duration = median * np.exp(log_residual)
            if leg_index == current[j]:
                sd = max(0.0, float(states[j].get("remaining_fraction_sd", 0.0)))
                fraction = np.clip(remaining[j] + sd * position_normal[:, j], 0.0, 1.0)
                duration *= fraction
            times[:, j] = entry + duration
            gate_times[:, j, leg_index] = times[:, j]
    finish_times = times.copy()
    for j, status in enumerate(statuses):
        if status == "finished":
            finish_times[:, j] = float(states[j]["finished_at_s"])
        elif status in TERMINAL_NONFINISH:
            finish_times[:, j] = math.inf
    finish_times[~starts | (failure_fraction <= 1.0)] = math.inf
    if first_gate_limit_s is not None:
        first_gate = gate_times[:, :, 0].copy()
        first_gate[~starts | (failure_fraction <= 1.0 / length)] = math.inf
        first_gate[np.isnan(first_gate)] = math.inf
        # A live checkpoint after a verified first gate already satisfies this
        # race-wide limit; its original elapsed crossing belongs to caller rules.
        if not np.any(current > 0):
            finish_times[np.min(first_gate, axis=1) > first_gate_limit_s, :] = math.inf
    if race_time_limit_s is not None:
        finish_times[np.min(finish_times, axis=1) > race_time_limit_s, :] = math.inf
    if finishing_window_s is not None:
        first = np.min(finish_times, axis=1)
        finish_times[finish_times > first[:, None] + finishing_window_s] = math.inf
    candidate_ranks, candidate_winners = _ranks_and_winners(finish_times, tie_break)
    if known_winner is not None:
        winner_index = boats.index(known_winner)
        candidate_winners[:] = winner_index
        # An audited winner is a valid finisher even if no other finish time is
        # available yet. Put it before all still-active simulated arrivals.
        if winner_index not in fixed_order:
            fixed_order = [winner_index, *fixed_order]
            finish_times[:, winner_index] = min(float(elapsed.min()), 0.0)
            completion_probability[:, winner_index] = 1.0
            candidate_ranks, candidate_winners = _ranks_and_winners(finish_times, tie_break)

    timing_rules = any(v is not None for v in (first_gate_limit_s, race_time_limit_s, finishing_window_s))
    # When timerules matter, condition the uniform reference on each actual
    # legally eligible subset. Otherwise integrate all completion subsets exactly.
    reference_p = np.isfinite(finish_times).astype(float) if timing_rules else completion_probability
    ref_win, ref_none, ref_rank = _uniform_marginals(reference_p, fixed_order)
    candidate_win = np.bincount(candidate_winners[candidate_winners >= 0], minlength=count) / n
    candidate_none = float(np.mean(candidate_winners < 0))
    probabilities = (1 - tail_weight) * candidate_win + tail_weight * ref_win
    no_finisher = (1 - tail_weight) * candidate_none + tail_weight * ref_none
    expected = (1 - tail_weight) * candidate_ranks.mean(axis=0) + tail_weight * ref_rank
    # Samples use the very same joint mixture, for downstream tournament draws.
    reference_times = np.where(reference_uniform < reference_p, reference_priority, math.inf)
    for place, j in enumerate(fixed_order):
        reference_times[:, j] = -len(fixed_order) + place
    reference_ranks, reference_winners = _ranks_and_winners(reference_times, tie_break)
    use_reference = mixture_uniform < tail_weight
    sampled_ranks = np.where(use_reference[:, None], reference_ranks, candidate_ranks)
    sampled_winners = np.where(use_reference, reference_winners, candidate_winners)
    assumptions = ["Empirical gate-time model; no predicted XY paths",
                   "Identity calibration; no calibration claim",
                   f"Joint uniform-reference mixture weight {tail_weight:g}",
                   f"{hazard_shape} course-exposure hazard; multiplier {hazard_multiplier:g}",
                   model.dependence_evidence, model.mixture_reason]
    if conditional_complete:
        assumptions.append("Conditional on every nonterminal entry starting and completing; diagnostic only")
    if timing_rules:
        assumptions.append("Uniform reference conditions on simulated legally timerule-eligible subsets")
    estimated = any(s.get("quality") == "estimated" for s in states)
    return RaceSimulation(True, "estimated" if estimated else "available", None, boats,
                          dict(zip(boats, map(float, probabilities))), float(no_finisher),
                          dict(zip(boats, map(float, expected))), n, seed,
                          1.96 * math.sqrt(0.25 / n), conditional_complete, assumptions,
                          sampled_ranks if return_samples else None,
                          finish_times if return_samples else None,
                          gate_times if return_samples else None,
                          failure_fraction if return_samples else None,
                          sampled_winners if return_samples else None)


def simulate_order_reference(strength: StrengthModel, boat_ids: Sequence[str],
                             completion: CompletionModel | None, *,
                             state: Mapping[str, Mapping[str, Any]] | None = None,
                             n: int = 20_000, seed: int = 42, wind_knots: float | None = None,
                             conditional_complete: bool = False, total_legs: int | None = None,
                             hazard_shape: str = "constant", hazard_multiplier: float = 1.0,
                             known_winner: str | None = None,
                             global_finish_order_resolved: bool = False,
                             return_samples: bool = True) -> RaceSimulation:
    """Joint PL complete-order reference with the same audited completion model.

    Independent exponential clocks produce a genuine PL order conditional on
    the sampled finisher subset. These are ordering auxiliaries, not predicted
    finish times. No gate-time ability effect is added. Live progress is a
    declared small diffusion-lead extension; it is distinct from a measured
    travel-time conditioner and is not claimed calibrated.
    """
    boats = list(boat_ids)
    if total_legs is None:
        specified = {int(s["total_legs"]) for s in (state or {}).values() if "total_legs" in s}
        if len(specified) == 1:
            total_legs = specified.pop()
        elif any(int(s.get("current_leg", 0)) > 0 for s in (state or {}).values()):
            return _unavailable(boats, "Live course exposure requires the known total leg count", n, seed)
        else:
            total_legs = 1
    if total_legs < 1:
        raise ValueError("Total leg count must be positive")
    # This neutral duration engine is used only for its shared audited
    # completion/survival and terminal-constraint machinery. Its durations and
    # gate clocks are discarded, never used as physical forecasts or fitted
    # strength. tail_weight=1 gives exact uniform conditional-subset marginals.
    neutral = LegTimeModel(coefficients=[0., 1., 0.], n_rows=2, n_races=1)
    base = simulate_race(neutral, boats,
                         [{"distance_m": neutral.distance_reference_m}] * total_legs,
                         completion, state=state, n=n, seed=seed,
                         conditional_complete=conditional_complete, wind_knots=wind_knots,
                         hazard_shape=hazard_shape, hazard_multiplier=hazard_multiplier,
                         tail_weight=1.0, known_winner=known_winner,
                         global_finish_order_resolved=global_finish_order_resolved,
                         return_samples=True)
    if not base.available:
        return base
    rng = np.random.default_rng(np.random.SeedSequence([seed, 0x504C]))
    progress = np.array([(int((state or {}).get(b, {}).get("current_leg", 0)) + 1
                          - float((state or {}).get(b, {}).get("remaining_fraction", 1.))) / total_legs
                         for b in boats])
    lead = progress - progress.mean()
    state_features = dict(zip(boats, lead / np.sqrt(np.maximum(1 - progress, .01)))) if state else None
    if hasattr(strength, "log_worth"):
        logits = strength.log_worth(boats, wind_knots, state_features)
    else:
        # Also accepts the past-fitted conditional PL benchmark.
        nested = {b: {"lead_fraction": float(lead[j]), "remaining_fraction": float(1-progress[j])}
                  for j, b in enumerate(boats)}
        p = strength.predict_win_probabilities(boats, state_features=nested)
        logits = np.log([max(float(p[b]), 1e-300) for b in boats])
    worth = np.exp(np.clip(logits - np.max(logits), -700, 0))
    clocks = rng.exponential(size=(n, len(boats))) / worth[None, :]
    assert base.finish_times_s is not None and base.ranks is not None and base.winners is not None
    clocks[~np.isfinite(base.finish_times_s)] = math.inf
    locked = sorted([j for j, b in enumerate(boats)
                     if str((state or {}).get(b, {}).get("terminal_status", "")).lower() == "finished"],
                    key=lambda j: (state or {})[boats[j]].get("finished_at_s", math.inf))
    if known_winner is not None and boats.index(known_winner) not in locked:
        locked = [boats.index(known_winner), *locked]
    for place, j in enumerate(locked):
        clocks[:, j] = -len(locked) + place
    ranks, winners = _ranks_and_winners(clocks, rng.random(clocks.shape))
    win = np.bincount(winners[winners >= 0], minlength=len(boats)) / n
    no_finisher = float(np.mean(winners < 0))
    expected = ranks.mean(axis=0)
    probabilities = {b: float((1 - TAIL_WEIGHT) * win[j] + TAIL_WEIGHT * base.win_prob_by_boat[b])
                     for j, b in enumerate(boats)}
    positions = {b: float((1 - TAIL_WEIGHT) * expected[j] + TAIL_WEIGHT * base.expected_position_by_boat[b])
                 for j, b in enumerate(boats)}
    none = (1 - TAIL_WEIGHT) * no_finisher + TAIL_WEIGHT * base.no_finisher_prob
    mixture = rng.random(n) < TAIL_WEIGHT
    return RaceSimulation(True, base.status, None, boats, probabilities, float(none), positions,
                          n, seed, 1.96 * math.sqrt(.25/n), conditional_complete,
                          ["Pooled ridge PL complete-order reference; identity calibration",
                           "Nonfinish scored N; sampled complete orders share audited completion",
                           "Course-exposure survival conditioning; no predicted travel-time clock",
                           "Fixed conservative diffusion-lead live extension" if state else "Pre-race static strength",
                           f"Joint uniform-reference mixture weight {TAIL_WEIGHT:g}"],
                          np.where(mixture[:, None], base.ranks, ranks) if return_samples else None,
                          None, None,
                          base.failure_course_fractions if return_samples else None,
                          np.where(mixture, base.winners, winners) if return_samples else None)
