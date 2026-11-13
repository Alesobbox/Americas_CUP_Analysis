"""AC38 tournament mechanics and explicitly conditional AC40 -> AC75 scenarios.

The official-publication entry point fails closed until the governing documents
and unresolved scoring clauses are pinned.  ``simulate_cup`` is an executable
rank-only scenario engine, not a calibrated AC75 forecast.  It never distributes
probability among unresolved official tie resolutions.  Its bounds are
conservative outer bounds, rather than a claim of sharp partial identification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


TEAM_IDS = ("ETNZ", "GB1", "LUNA_ROSSA", "ALINGHI", "LA_ROCHE_POSAY", "ARC_USA", "AUSTRALIA")
TEAM_NAMES = {
    "ETNZ": "Emirates Team New Zealand", "GB1": "GB1",
    "LUNA_ROSSA": "Luna Rossa", "ALINGHI": "Tudor Team Alinghi",
    "LA_ROCHE_POSAY": "La Roche-Posay Racing Team", "ARC_USA": "ARC Team USA",
    "AUSTRALIA": "Team Australia",
}
RULE_SOURCES = (
    {"version": "Protocol AC38.10", "url": "https://drive.google.com/file/d/1MZZN-TJlXUkaqTNxCje8RupzAjBP4vvL/view",
     "sha256": "084762ecd4ffb7d66921bd0d5d83e5ef9f5927cc8ce74edaa34648c3711118ee"},
    {"version": "LVC/Match Conditions v0", "url": "https://drive.google.com/file/d/1biI3_zCSaLrRiM4nwkhKpaBnMraS5KiP/view",
     "sha256": "4d3580f58b4dedb348d8f332bb01336b66f722560334fc800751b7bb2a397949"},
    {"version": "RRSAC v5.02", "url": "https://drive.google.com/file/d/1I21drErgKm4OuYCcGb3D9uv7_UYG4jwj/view",
     "sha256": "89d08f344abb1d5bb0f123f018bb876c4abdc749075b382cf98fe610c312f1f1"},
)
UNRESOLVED_OFFICIAL_CLAUSES = (
    "Six-challenger qualification/seeding tie procedure requires authoritative clarification.",
    "Timing-dependent shared/zero-score results require the applicable race state and instructions.",
    "Incomplete-series, withdrawal and continuation instructions must be pinned before publication.",
)


@dataclass(frozen=True)
class CupScenario:
    rho: float = 0.5
    sigma_multiplier: float = 1.0
    match_concentration: float = 1.0
    hazard_multiplier: float = 1.0
    daily_drift_sd: float = 0.0

    def validate(self) -> None:
        if not 0 <= self.rho <= 1 or self.sigma_multiplier < 0:
            raise ValueError("rho must lie in [0,1] and sigma_multiplier must be nonnegative")
        if self.match_concentration <= 0 or self.hazard_multiplier <= 0:
            raise ValueError("match concentration and hazard multiplier must be positive")
        if not 0 <= self.daily_drift_sd <= 0.5:
            raise ValueError("daily_drift_sd must lie in [0, 0.5]")
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("scenario parameters must be finite")

    @property
    def scenario_id(self) -> str:
        base_id = (f"rho{self.rho:g}_sigma{self.sigma_multiplier:g}"
                   f"_c{self.match_concentration:g}_k{self.hazard_multiplier:g}")
        if self.daily_drift_sd > 0:
            base_id += f"_drift{self.daily_drift_sd:g}"
        return base_id


@dataclass(frozen=True)
class MatchScore:
    """A fixed observed score, including a shared/zero result or point penalty.

    Scores are explicit inputs; the ranking kernel cannot infer official scores
    from a winner when timing, penalties or committee decisions are required.
    """
    team_a: str
    team_b: str
    points_a: float
    points_b: float
    resolved: bool = True
    win_credit_a: float | None = None
    win_credit_b: float | None = None

    def __post_init__(self) -> None:
        if self.team_a == self.team_b or self.team_a not in TEAM_IDS or self.team_b not in TEAM_IDS:
            raise ValueError("match score requires two distinct registered teams")
        if not math.isfinite(self.points_a) or not math.isfinite(self.points_b):
            raise ValueError("match points must be finite")
        credits = (self.win_credit_a, self.win_credit_b)
        if (credits[0] is None) != (credits[1] is None):
            raise ValueError("both observable match win credits must be supplied together")
        if any(value is not None and (not math.isfinite(value) or not 0 <= value <= 1) for value in credits):
            raise ValueError("observable match win credits must lie in [0,1]")


@dataclass(frozen=True)
class CupRules:
    """Versioned mechanics, with all assumptions visible.

    ``unresolved`` is the production tie policy. ``fixture_lots`` defines a
    *synthetic, complete* tie rule solely for exchangeability tests/benchmarks;
    it is never an interpretation of the unresolved official rule. ``priority``
    requires an explicit externally supplied complete team order and citation.
    Neither complete policy is enabled by the official-publication helper.
    """
    round_robins: int = 3
    fleet_races: int = 6
    # RRSAC 105.2: ten points for first, descending to four for seventh.
    fleet_points: tuple[float, ...] = (10, 9, 8, 7, 6, 5, 4)
    challenger_carry: tuple[float, ...] = (2.5, 2, 1.5, 1, 0.5, 0)
    # Conditions 5.2(b), distinct from Challenger-only 5.2(a).
    overall_carry: tuple[float, ...] | None = (3, 2.5, 2, 1.5, 1, 0.5, 0)
    tie_policy: str = "unresolved"
    tie_priority: tuple[str, ...] = ()
    tie_rule_reference: str | None = None
    document_hashes: Mapping[str, str] = field(default_factory=lambda: {
        source["version"]: source["sha256"] for source in RULE_SOURCES})
    document_effective_dates: Mapping[str, str] = field(default_factory=dict)
    resolved_clauses: tuple[str, ...] = ()
    official_selections: Mapping[str, str] = field(default_factory=dict)
    known_fleet_orders: tuple[tuple[str, ...], ...] = ()
    # IDs: rr:<round 1-based>:<TEAM_IDS first>:<TEAM_IDS second>, or
    # <repechage_1|repechage_2|semifinal_1|semifinal_2|challenger_final|cup_match>:<race 1-based>.
    known_match_scores: Mapping[str, MatchScore] = field(default_factory=dict)
    withdrawn: tuple[str, ...] = ()
    series_race_safety_limit: int = 4096
    # Explicit scenario slopes, not fitted AC75 weather effects. Nearby races
    # share a simulated day factor; zeros imply no asserted weather advantage.
    weather_sensitivity: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.round_robins not in (1, 2, 3) or self.fleet_races != 6:
            raise ValueError("configure 1-3 complete round robins and six fleet races")
        if len(self.fleet_points) != 7 or len(self.challenger_carry) != 6:
            raise ValueError("fleet and Challenger carry schedules must cover every entrant")
        if self.overall_carry is not None and len(self.overall_carry) != 7:
            raise ValueError("overall carry schedule must cover seven entrants")
        if self.tie_policy not in ("unresolved", "fixture_lots", "priority"):
            raise ValueError("unknown tie policy")
        if self.tie_policy == "priority" and (set(self.tie_priority) != set(TEAM_IDS)
                                                or len(self.tie_priority) != 7
                                                or not self.tie_rule_reference):
            raise ValueError("priority ties require a complete external order and rule reference")
        if self.series_race_safety_limit < 14:
            raise ValueError("a series cannot be capped at the usual 13 scheduled races")
        if len(self.known_fleet_orders) > self.fleet_races:
            raise ValueError("too many known fleet results")
        for order in self.known_fleet_orders:
            if len(order) != 7 or set(order) != set(TEAM_IDS):
                raise ValueError("known complete fleet order must include all seven teams once")
        if self.withdrawn and not set(self.withdrawn) <= set(TEAM_IDS):
            raise ValueError("withdrawal references an unknown team")
        for selection_a, selection_b in self.official_selections.items():
            if selection_a not in TEAM_IDS[1:] or selection_b not in TEAM_IDS[1:] or selection_a == selection_b:
                raise ValueError("official semifinal selections require distinct Challengers")
        values = [*self.fleet_points, *self.challenger_carry, *(self.overall_carry or ()),
                  *self.weather_sensitivity.values()]
        if any(not math.isfinite(v) for v in values):
            raise ValueError("rules contain nonfinite scores or weather sensitivities")


def standard_scenarios() -> tuple[CupScenario, ...]:
    """Exactly the standard nine scenarios; k/c sensitivities are separate."""
    return tuple(CupScenario(rho, sigma) for rho in (0, 0.5, 1) for sigma in (0.5, 1, 2))


def hazard_probability(probability: float, multiplier: float) -> float:
    if not 0 <= probability <= 1 or not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("invalid full-race hazard input")
    return 1.0 if probability == 1 else -math.expm1(multiplier * math.log1p(-probability))


def exposure_hazard_probability(hourly_failure_rate: float, hazard_multiplier: float = 1.0, duration_hours: float = 0.35) -> float:
    """Computes failure probability from continuous hourly exposure rate."""
    if not math.isfinite(hourly_failure_rate) or hourly_failure_rate < 0:
        raise ValueError("hourly_failure_rate must be finite and non-negative")
    if not math.isfinite(hazard_multiplier) or hazard_multiplier < 0:
        raise ValueError("hazard_multiplier must be finite and non-negative")
    if not math.isfinite(duration_hours) or duration_hours < 0:
        raise ValueError("duration_hours must be finite and non-negative")
    return -math.expm1(-hourly_failure_rate * hazard_multiplier * duration_hours)



def choose_semifinal_opponent(eligible: Sequence[str], wins: Mapping[str, float],
                              played: Mapping[str, int], prior_match_strength: Mapping[str, float]) -> str:
    """Observable-only policy; no sampled latent ability enters this interface."""
    if not eligible:
        raise ValueError("no eligible opponent")
    return min(eligible, key=lambda team: (wins.get(team, 0) / played[team] if played.get(team, 0) else 0.5,
                                          prior_match_strength.get(team, 0.5), team))


def _logistic(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(value, -700, 700)))


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def simulate_cup(mapped_strength: Mapping[str, float], *, scenario: CupScenario | None = None,
                 rules: CupRules | None = None, trials: int = 100_000, seed: int = 2027,
                 pooled_scale: float = 0.5, failure_probability: float = 0.0,
                 conditional_on_completed_scored_races: bool = True,
                 feasible_slot_rule_bounds: bool = False,
                 direct_ac75_distribution: Mapping[str, object] | None = None,
                 posterior_world_draws: np.ndarray | None = None,
                 forecast_prior_mean: Mapping[str, float] | None = None,
                 forecast_prior_var: Mapping[str, float] | None = None,
                 return_trial_outcomes: bool = False) -> dict:
    """Vectorized complete-tournament continuations with persistent team effects.

    A zero reliability input means an explicit no-failure scenario, not a learned
    estimate. If a sampled failure needs missing official timing, that trajectory
    is unresolved. A provisional internal stable tie order only lets simulation
    continue; its winner is discarded from exact estimates and bounds use [0,1]
    on every unresolved trajectory. Therefore no invented tie weights enter the
    reported estimates. These outer bounds may be deliberately uninformative.
    """
    scenario, rules = scenario or CupScenario(), rules or CupRules()
    scenario.validate()
    rules.validate()
    if trials < 1 or not isinstance(trials, int) or pooled_scale <= 0 or not math.isfinite(pooled_scale):
        raise ValueError("positive integer trials and positive finite pooled scale required")
    if any(team not in TEAM_IDS or not math.isfinite(value) for team, value in mapped_strength.items()):
        raise ValueError("mapped strengths require registered teams and finite values")
    if conditional_on_completed_scored_races and failure_probability != 0:
        raise ValueError("completed-scored-race conditioning cannot simultaneously sample failures")
    q = hazard_probability(failure_probability, scenario.hazard_multiplier)
    rng = np.random.default_rng(seed)
    rows = np.arange(trials)
    means = np.array([mapped_strength.get(team, 0.0) for team in TEAM_IDS])
    missing = np.array([team not in mapped_strength for team in TEAM_IDS])
    if posterior_world_draws is not None:
        theta = np.asarray(posterior_world_draws, dtype=float)
        if theta.shape != (trials, 7) or not np.all(np.isfinite(theta)):
            raise ValueError(f"posterior_world_draws must be finite with shape ({trials}, 7), got {theta.shape}")
        capability_source = "ac38_joint_posterior_draws"
    elif direct_ac75_distribution is not None:
        expected_order = list(TEAM_IDS)
        if list(direct_ac75_distribution.get("team_order", [])) != expected_order:
            raise ValueError(f"direct_ac75_distribution['team_order'] must match TEAM_IDS exactly: {expected_order}")
        cov_mat = np.asarray(direct_ac75_distribution["covariance"], dtype=float)
        if cov_mat.shape != (7, 7):
            raise ValueError(f"direct_ac75_distribution['covariance'] must be a 7x7 matrix, got {cov_mat.shape}")
        if not np.allclose(cov_mat, cov_mat.T, atol=1e-8):
            raise ValueError("direct_ac75_distribution['covariance'] must be symmetric")
        eigvals = np.linalg.eigvalsh(cov_mat)
        if np.any(eigvals < -1e-8):
            raise ValueError("direct_ac75_distribution['covariance'] must be positive semi-definite")
        cov_clean = 0.5 * (cov_mat + cov_mat.T)
        min_eig = np.min(np.linalg.eigvalsh(cov_clean))
        if min_eig < 1e-9:
            cov_clean += np.eye(7) * (abs(min_eig) + 1e-9)
        mu_vec = np.array([float(direct_ac75_distribution["mean"].get(t, 0.0)) for t in TEAM_IDS], dtype=float)
        theta = rng.multivariate_normal(mu_vec, cov_clean, size=trials)
        capability_source = "direct_ac75_posterior"
    else:
        population = rng.normal(0, pooled_scale, (trials, 7))
        base = np.where(missing[None, :], population, means[None, :])
        # One draw per team per whole tournament, never independently per match.
        theta = scenario.rho * base + rng.normal(0, scenario.sigma_multiplier * pooled_scale, (trials, 7))
        capability_source = "ac40_transfer_prior"

    slopes = np.array([rules.weather_sensitivity.get(team, 0.0) for team in TEAM_IDS])
    day_factors: dict[int, np.ndarray] = {}
    day_drifts: dict[int, np.ndarray] = {}
    sorted_days_seen: list[int] = []
    unresolved = np.zeros(trials, dtype=bool)
    reasons: set[str] = set()
    reason_masks: dict[str, np.ndarray] = {}
    first_unresolved_stage = np.full(trials, "", dtype=object)

    def mark_unresolved(mask, stage, reason):
        selected_mask = np.broadcast_to(np.asarray(mask, dtype=bool), (trials,))
        if not np.any(selected_mask):
            return
        first_unresolved_stage[selected_mask & ~unresolved] = stage
        unresolved[:] |= selected_mask
        reasons.add(reason)
        if reason not in reason_masks:
            reason_masks[reason] = np.zeros(trials, dtype=bool)
        reason_masks[reason] |= selected_mask

    if rules.withdrawn:
        mark_unresolved(True, "withdrawal", "Withdrawal scoring/advancement instructions are not supplied.")
    rr_wins = np.zeros((trials, 7))
    rr_played = np.zeros((trials, 7), dtype=np.int16)
    max_series_races = 0

    def day_theta(day: int) -> np.ndarray:
        if day not in day_factors:
            day_factors[day] = rng.normal(size=trials)
            if scenario.daily_drift_sd > 0:
                if not sorted_days_seen:
                    day_drifts[day] = np.zeros((trials, 7), dtype=float)
                    sorted_days_seen.append(day)
                else:
                    prev_day = sorted_days_seen[-1]
                    delta_t = max(1, abs(day - prev_day))
                    drift_step = rng.normal(0, math.sqrt(delta_t) * scenario.daily_drift_sd, (trials, 7))
                    day_drifts[day] = day_drifts[prev_day] + drift_step
                    sorted_days_seen.append(day)
            else:
                day_drifts[day] = np.zeros((trials, 7), dtype=float)
        return theta + day_drifts[day] + day_factors[day][:, None] * slopes[None, :]

    def standing(points: np.ndarray, ids: np.ndarray, stage: str,
                 fleet_history: list[np.ndarray] | None = None) -> np.ndarray:
        nonlocal unresolved
        sorted_values = np.sort(points, axis=1)
        ties = np.any(np.diff(sorted_values, axis=1) == 0, axis=1)
        if fleet_history:
            # RRSAC 107: latest common scheduled finishing places, then earlier
            # races. Complete rank-only races have a distinct latest placing.
            order = np.lexsort((*[ranks[:, ids] for ranks in fleet_history], -points), axis=1)
            return np.broadcast_to(ids, points.shape)[rows[:, None], order]
        if rules.tie_policy == "unresolved":
            mark_unresolved(ties, stage, f"{stage}: official tie resolution is unresolved; outer bounds retain the entire tied path.")
            secondary = np.broadcast_to(ids, points.shape)
        elif rules.tie_policy == "fixture_lots":
            secondary = rng.random(points.shape)
        else:
            priority = {TEAM_IDS.index(team): rank for rank, team in enumerate(rules.tie_priority)}
            secondary = np.broadcast_to(np.array([priority[int(i)] for i in ids]), points.shape)
        return np.broadcast_to(ids, points.shape)[rows[:, None], np.lexsort((secondary, -points), axis=1)]

    def draw_match(a: np.ndarray, b: np.ndarray, day: int, stage="round_robin") -> tuple[np.ndarray, np.ndarray]:
        nonlocal unresolved
        abilities = day_theta(day)
        # Joint uniform-reference mixture applied to the actual match draw.
        p = (1 - 0.0001) * _logistic(scenario.match_concentration *
                                    (abilities[rows, a] - abilities[rows, b])) + 0.0001 * 0.5
        win_a = rng.random(trials) < p
        if q:
            finish_a, finish_b = rng.random(trials) >= q, rng.random(trials) >= q
            mark_unresolved(~finish_a | ~finish_b, stage,
                            "Sampled nonfinish requires official timing/status scoring unavailable to the rank-only kernel.")
            return ((finish_a & (win_a | ~finish_b)).astype(float),
                    (finish_b & (~win_a | ~finish_a)).astype(float))
        return win_a.astype(float), (~win_a).astype(float)

    def apply_known(key: str, a: np.ndarray, b: np.ndarray, pa: np.ndarray,
                    pb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        nonlocal unresolved
        known = rules.known_match_scores.get(key)
        if known is None:
            return pa, pb
        ia, ib = TEAM_IDS.index(known.team_a), TEAM_IDS.index(known.team_b)
        forward, reverse = (a == ia) & (b == ib), (a == ib) & (b == ia)
        matched = forward | reverse
        mark_unresolved(~matched, key.split(":")[0], f"{key}: observed participants require additional fixed earlier advancement results.")
        if not known.resolved:
            mark_unresolved(True, key.split(":")[0], f"{key}: observed score is unresolved.")
        return (np.where(forward, known.points_a, np.where(reverse, known.points_b, pa)),
                np.where(forward, known.points_b, np.where(reverse, known.points_a, pb)))

    fleet_points = np.zeros((trials, 7))
    fleet_history = []
    for race in range(rules.fleet_races):
        if race < len(rules.known_fleet_orders):
            order = np.broadcast_to([TEAM_IDS.index(team) for team in rules.known_fleet_orders[race]], (trials, 7))
        else:
            ability = day_theta(race // 3)
            uniform_reference = rng.random(trials) < 0.0001
            utilities = np.where(uniform_reference[:, None], 0, ability) + rng.gumbel(size=(trials, 7))
            order = np.argsort(-utilities, axis=1)
            if q:
                any_failure = np.any(rng.random((trials, 7)) < q, axis=1)
                mark_unresolved(any_failure, "fleet", "Fleet nonfinish needs official status/timing points beyond rank-only observations.")
        fleet_points[rows[:, None], order] += np.array(rules.fleet_points)[None, :]
        ranks = np.empty((trials, 7), dtype=np.int8)
        ranks[rows[:, None], order] = np.arange(7)[None, :]
        fleet_history.append(ranks)
    challenger_ids = np.arange(1, 7)
    fleet_challenger_order = standing(fleet_points[:, 1:], challenger_ids, "fleet_challengers", fleet_history)
    overall_fleet_order = standing(fleet_points, np.arange(7), "fleet_overall", fleet_history)
    challenger_points = np.zeros((trials, 7))
    challenger_points[rows[:, None], fleet_challenger_order] = np.array(rules.challenger_carry)[None, :]
    overall_points = np.zeros((trials, 7))
    if rules.overall_carry is not None:
        overall_points[rows[:, None], overall_fleet_order] = np.array(rules.overall_carry)[None, :]
    rr_race = 0
    for round_number in range(1, rules.round_robins + 1):
        for a_idx in range(7):
            for b_idx in range(a_idx + 1, 7):
                a, b = np.full(trials, a_idx), np.full(trials, b_idx)
                key = f"rr:{round_number}:{TEAM_IDS[a_idx]}:{TEAM_IDS[b_idx]}"
                pa, pb = apply_known(key, a, b, *draw_match(a, b, 10 + rr_race // 7))
                overall_points[:, a_idx] += pa
                overall_points[:, b_idx] += pb
                if a_idx != 0:  # Defender results never enter Challenger standings/policy.
                    challenger_points[:, a_idx] += pa
                    challenger_points[:, b_idx] += pb
                    policy_pa, policy_pb = pa, pb
                    known = rules.known_match_scores.get(key)
                    if known is not None and known.win_credit_a is not None:
                        forward = known.team_a == TEAM_IDS[a_idx]
                        policy_pa = np.full(trials, known.win_credit_a if forward else known.win_credit_b)
                        policy_pb = np.full(trials, known.win_credit_b if forward else known.win_credit_a)
                    elif known is not None and not (0 <= known.points_a <= 1 and 0 <= known.points_b <= 1):
                        mark_unresolved(True, "round_robin", f"{key}: penalized points need separate observed match win credits for opponent selection.")
                        policy_pa, policy_pb = np.zeros(trials), np.zeros(trials)
                    rr_wins[:, a_idx] += policy_pa
                    rr_wins[:, b_idx] += policy_pb
                    rr_played[:, a_idx] += 1
                    rr_played[:, b_idx] += 1
                rr_race += 1
    seeds = standing(challenger_points[:, 1:], challenger_ids, "round_robin_challengers")
    top3 = seeds[:, :3]
    fourth = seeds[:, 3]
    rep_entrants = seeds[:, 3:6]

    def series(a: np.ndarray, b: np.ndarray, target: int, stage: str,
               initial_a: float = 0, initial_b: float = 0, day: int = 100) -> np.ndarray:
        nonlocal unresolved, max_series_races
        points_a, points_b = np.full(trials, initial_a, dtype=float), np.full(trials, initial_b, dtype=float)
        race_number = 0
        while np.any((points_a < target) & (points_b < target)):
            active = (points_a < target) & (points_b < target)
            race_number += 1
            if race_number > rules.series_race_safety_limit:
                mark_unresolved(active, stage, f"{stage}: continuation safety budget exhausted; no scheduled-race cap was substituted.")
                break
            pa, pb = apply_known(f"{stage}:{race_number}", a, b,
                                 *draw_match(a, b, day + (race_number - 1) // 3, stage))
            points_a += np.where(active, pa, 0)
            points_b += np.where(active, pb, 0)
        max_series_races = max(max_series_races, race_number)
        mark_unresolved((points_a >= target) & (points_b >= target), stage,
                        f"{stage}: simultaneous threshold requires official resolution.")
        return np.where(points_a >= target, a, b)

    repechage_first = series(seeds[:, 4], seeds[:, 5], 3, "repechage_1", initial_a=1, day=100)
    repechage_winner = series(seeds[:, 3], repechage_first, 3, "repechage_2", initial_a=1, day=110)
    eligible = np.column_stack((seeds[:, 1], seeds[:, 2], repechage_winner))
    selector = seeds[:, 0]
    fraction = np.divide(rr_wins, rr_played, out=np.full_like(rr_wins, 0.5), where=rr_played > 0)
    if posterior_world_draws is not None:
        prior_mean = (
            np.array([float(forecast_prior_mean.get(t, 0.0)) for t in TEAM_IDS], dtype=float)
            if forecast_prior_mean is not None
            else np.mean(theta, axis=0)
        )
        prior_variance = (
            np.array([max(0.0, float(forecast_prior_var.get(t, 0.0))) for t in TEAM_IDS], dtype=float)
            if forecast_prior_var is not None
            else np.var(theta, axis=0)
        )
    else:
        prior_variance = (scenario.sigma_multiplier * pooled_scale) ** 2 + missing * (scenario.rho * pooled_scale) ** 2
        prior_mean = scenario.rho * means
    prior_logits = (scenario.match_concentration * (prior_mean[eligible] - prior_mean[selector][:, None]) /
                    np.sqrt(1 + math.pi * scenario.match_concentration**2 *
                            (prior_variance[eligible] + prior_variance[selector][:, None]) / 8))
    # Stable team-name order is policy tie handling, not an official scoring tie.
    alphabetical = np.array([sorted(TEAM_IDS).index(team) for team in TEAM_IDS])
    eligible_order = np.lexsort((alphabetical[eligible], _logistic(prior_logits),
                                fraction[rows[:, None], eligible]), axis=1)
    selected = eligible[rows, eligible_order[:, 0]]
    for selecting_team, selected_team in rules.official_selections.items():
        applies = selector == TEAM_IDS.index(selecting_team)
        actual = TEAM_IDS.index(selected_team)
        legal = np.any(eligible == actual, axis=1)
        mark_unresolved(applies & ~legal, "semifinal_selection",
                        "An official semifinal choice requires missing prior advancement results.")
        selected = np.where(applies & legal, actual, selected)
    others = np.sort(np.where(eligible != selected[:, None], eligible, 99), axis=1)[:, :2]
    sf1 = series(selector, selected, 5, "semifinal_1", day=120)
    sf2 = series(others[:, 0], others[:, 1], 5, "semifinal_2", day=120)
    challenger = series(sf1, sf2, 7, "challenger_final", day=140)
    champion = series(np.zeros(trials, dtype=int), challenger, 7, "cup_match", day=160)
    resolved_count = int(np.sum(~unresolved))
    unresolved_count = trials - resolved_count
    counts = np.bincount(champion[~unresolved], minlength=7)
    lower = counts / trials
    if feasible_slot_rule_bounds and unresolved_count > 0:
        feasible_champions = np.zeros((trials, 7), dtype=bool)
        feasible_champions[~unresolved, champion[~unresolved]] = True
        feasible_champions[unresolved, 0] = True

        m_cup = unresolved & (first_unresolved_stage == "cup_match")
        if np.any(m_cup):
            feasible_champions[m_cup, challenger[m_cup]] = True

        m_cf = unresolved & (first_unresolved_stage == "challenger_final")
        if np.any(m_cf):
            feasible_champions[m_cf, sf1[m_cf]] = True
            feasible_champions[m_cf, sf2[m_cf]] = True

        m_sf1 = unresolved & np.isin(first_unresolved_stage, ["semifinal_1", "semifinal_selection"])
        if np.any(m_sf1):
            feasible_champions[m_sf1, selector[m_sf1]] = True
            for col in range(eligible.shape[1]):
                feasible_champions[m_sf1, eligible[m_sf1, col]] = True

        m_sf2 = unresolved & (first_unresolved_stage == "semifinal_2")
        if np.any(m_sf2):
            feasible_champions[m_sf2, sf1[m_sf2]] = True
            feasible_champions[m_sf2, others[m_sf2, 0]] = True
            feasible_champions[m_sf2, others[m_sf2, 1]] = True

        m_rep2 = unresolved & (first_unresolved_stage == "repechage_2")
        if np.any(m_rep2):
            for col in range(top3.shape[1]):
                feasible_champions[m_rep2, top3[m_rep2, col]] = True
            feasible_champions[m_rep2, fourth[m_rep2]] = True
            feasible_champions[m_rep2, repechage_first[m_rep2]] = True

        m_rep1 = unresolved & np.isin(first_unresolved_stage, ["repechage_1", "repechage"])
        if np.any(m_rep1):
            feasible_champions[m_rep1, :] = True

        m_rr = unresolved & (first_unresolved_stage == "round_robin_challengers")
        if np.any(m_rr):
            # All 6 Challengers enter Semifinals (seeds 1-3) or Repechage (seeds 4-6).
            # No Challenger is eliminated at round_robin_challengers; all remain alive.
            feasible_champions[m_rr, :] = True

        m_earlier = unresolved & ~np.isin(first_unresolved_stage, [
            "cup_match", "challenger_final", "semifinal_1", "semifinal_2",
            "semifinal_selection", "repechage_2", "repechage_1", "repechage",
            "round_robin_challengers"
        ])
        if np.any(m_earlier):
            feasible_champions[m_earlier, :] = True

        upper = np.sum(feasible_champions, axis=0) / trials
    else:
        upper = np.minimum(1, (counts + unresolved_count) / trials)
    estimate = counts / trials if unresolved_count == 0 else None
    numerical_half_width = 1.96 * np.sqrt(0.25 / trials)
    overall_fleet_ranks = np.empty((trials, 7), dtype=np.int8)
    overall_fleet_ranks[rows[:, None], overall_fleet_order] = np.arange(1, 8, dtype=np.int8)[None, :]
    mean_fleet_pos = np.mean(overall_fleet_ranks, axis=0)
    fleet_pos_dist = {
        team: [float(np.mean(overall_fleet_ranks[:, i] == pos)) for pos in range(1, 8)]
        for i, team in enumerate(TEAM_IDS)
    }
    top3_counts = np.bincount(top3.ravel(), minlength=7)
    sf_contenders = np.column_stack((selector, selected, others))
    sf_counts = np.bincount(sf_contenders.ravel(), minlength=7)
    actual_mc_se = {
        team: {
            "lower": float(math.sqrt(max(lower[i] * (1.0 - lower[i]), 0.0) / trials)),
            "upper": float(math.sqrt(max(upper[i] * (1.0 - upper[i]), 0.0) / trials)),
        }
        for i, team in enumerate(TEAM_IDS)
    }
    payload = {
        "status": "conditional_scenario" if unresolved_count == 0 else "rule_bounds",
        "target": "2027 America's Cup AC75 trophy", "units": "probability",
        "scenario_id": scenario.scenario_id, "scenario": asdict(scenario),
        "trials": trials, "seed": seed, "resolved_trials": resolved_count,
        "unresolved_trials": unresolved_count, "probabilities": {
            team: float(estimate[i]) if estimate is not None else None for i, team in enumerate(TEAM_IDS)},
        "rule_bounds": {team: {"lower": float(lower[i]), "upper": float(upper[i])}
                        for i, team in enumerate(TEAM_IDS)},
        "bounds_kind": ("feasible_slot_rule_bounds; unresolved mass restricted to feasible slot contenders"
                        if feasible_slot_rule_bounds else "conservative_outer_bounds; unresolved trajectories retain [0,1]"),
        "numerical_error": {"worst_case_95_half_width": numerical_half_width,
                            "actual_mc_se_by_team": actual_mc_se,
                            "scope": "Monte Carlo integration only; excludes model/rule uncertainty"},
        "rules": {"tie_policy": rules.tie_policy, "tie_rule_reference": rules.tie_rule_reference,
                  "round_robins": rules.round_robins, "fleet_races": rules.fleet_races,
                  "overall_carry_verified": rules.overall_carry is not None,
                  "max_observed_series_races": max_series_races,
                  "known_results_fixed": list(rules.known_match_scores),
                  "known_fleet_results_fixed": len(rules.known_fleet_orders)},
        "assumptions": ["AC40-informed transfer stress test; not a calibrated AC75 forecast.",
                        "Team capability is drawn once and persists across the entire tournament.",
                        "Australia and every unmapped entrant receive a population prior.",
                        "Rank-only races, conditional on completed scored races without unrepresented timing stoppages."
                        if conditional_on_completed_scored_races else
                        "Sampled nonfinish branches are unresolved wherever official timing/status scoring is missing.",
                        "Configured weather slopes are scenario assumptions; no AC75 weather response is fitted."],
        "unresolved_reasons": sorted(reasons),
        "resolved_fraction": resolved_count / trials,
        "unresolved_fraction": unresolved_count / trials,
        "resolved_win_counts": dict(zip(TEAM_IDS, map(int, counts))),
        "first_unresolved_stage_counts": {stage: int(np.sum(first_unresolved_stage == stage))
                                           for stage in sorted(set(first_unresolved_stage) - {""})},
        "overlapping_reason_counts": {reason: int(np.sum(mask)) for reason, mask in sorted(reason_masks.items())},
        "reason_count_policy": "First-stage counts are mutually exclusive; reason counts may overlap and must not be added.",
        "diagnostics": {"capability_source": capability_source,
                        "missing_strength_teams": [team for i, team in enumerate(TEAM_IDS) if missing[i]],
                        "persistent_ability_variance_by_team": dict(zip(TEAM_IDS, ((scenario.sigma_multiplier * pooled_scale) ** 2 + missing * (scenario.rho * pooled_scale) ** 2).tolist())),
                        "mean_round_robin_points": dict(zip(TEAM_IDS, np.mean(challenger_points, axis=0).tolist())),
                        "mean_overall_points": dict(zip(TEAM_IDS, np.mean(overall_points, axis=0).tolist())),
                        "mean_fleet_position": dict(zip(TEAM_IDS, mean_fleet_pos.tolist())),
                        "fleet_position_distribution": fleet_pos_dist,
                        "top3_challenger_frequency": dict(zip(TEAM_IDS, (top3_counts / trials).tolist())),
                        "semifinal_frequency": dict(zip(TEAM_IDS, (sf_counts / trials).tolist())),
                        "challenger_selection_frequency": dict(zip(TEAM_IDS, (np.bincount(challenger, minlength=7) / trials).tolist())),
                        "advancement_frequency": {
                            stage: dict(zip(TEAM_IDS, (np.bincount(winners, minlength=7) / trials).tolist()))
                            for stage, winners in (("repechage_1", repechage_first), ("repechage_2", repechage_winner),
                                                   ("semifinal_1", sf1), ("semifinal_2", sf2),
                                                   ("challenger_final", challenger))}},
    }
    draws_digest = (
        hashlib.sha256(np.ascontiguousarray(theta, dtype=np.float64).tobytes()).hexdigest()
        if posterior_world_draws is not None
        else None
    )
    if draws_digest is not None:
        payload["posterior_draws_sha256"] = draws_digest
    payload["input_hash"] = _canonical_hash({"mapped_strength": dict(mapped_strength), "rules": asdict(rules),
                                             "scenario": asdict(scenario), "seed": seed, "trials": trials,
                                             "pooled_scale": pooled_scale, "failure_probability": failure_probability,
                                             "conditional_on_completed_scored_races": conditional_on_completed_scored_races,
                                             **({"posterior_draws_sha256": draws_digest} if draws_digest else {})})
    if return_trial_outcomes:
        payload["_trial_outcomes"] = {
            "champion": champion,
            "unresolved": unresolved,
            "feasible_champions": feasible_champions if (feasible_slot_rule_bounds and unresolved_count > 0) else None,
        }
    return payload


def update_cup_from_2027_results(prior_mean: Mapping[str, float],
                                 prior_cov: np.ndarray,
                                 completed_ac75_orders: Sequence[Sequence[str]],
                                 *,
                                 kappa: float = 1.8) -> dict:
    """Laplace approximation updating of AC75 team capabilities given 2027 race finish orders."""
    team_list = list(TEAM_IDS)
    t_map = {t: idx for idx, t in enumerate(team_list)}
    mu_0 = np.array([prior_mean.get(t, 0.0) for t in team_list], dtype=float)
    Sigma_0 = np.asarray(prior_cov, dtype=float)
    if Sigma_0.shape != (7, 7):
        raise ValueError(f"prior_cov must be 7x7, got {Sigma_0.shape}")
    
    inv_Sigma_0 = np.linalg.pinv(Sigma_0)
    theta = mu_0.copy()
    
    for _ in range(25):
        diff = theta - mu_0
        grad = inv_Sigma_0 @ diff
        H = inv_Sigma_0.copy()
        
        for order in completed_ac75_orders:
            valid_order = [t_map[t] for t in order if t in t_map]
            if len(valid_order) < 2:
                continue
            for k in range(len(valid_order) - 1):
                subset = valid_order[k:]
                winner = valid_order[k]
                u = theta[subset] * kappa
                u_max = np.max(u)
                exp_u = np.exp(u - u_max)
                sum_exp = np.sum(exp_u)
                p = exp_u / sum_exp
                
                grad[winner] -= kappa
                for idx_s, s in enumerate(subset):
                    grad[s] += kappa * p[idx_s]
                    
                W = np.diag(p) - np.outer(p, p)
                for r_i, s_i in enumerate(subset):
                    for c_j, s_j in enumerate(subset):
                        H[s_i, s_j] += (kappa ** 2) * W[r_i, c_j]
                        
        step = np.linalg.solve(H + 1e-6 * np.eye(7), grad)
        theta -= step
        if float(np.max(np.abs(step))) < 1e-6:
            break
            
    post_cov = np.linalg.pinv(H)
    post_cov = 0.5 * (post_cov + post_cov.T)
    
    return {
        "mean": {t: float(theta[i]) for i, t in enumerate(team_list)},
        "covariance": post_cov.tolist(),
        "team_order": team_list
    }



def official_rules_gaps(rules: CupRules | None = None) -> list[str]:
    """Publication checks; real digests/dates cannot be replaced by URL strings."""
    rules = rules or CupRules()
    gaps = []
    for source in RULE_SOURCES:
        version = source["version"]
        digest = rules.document_hashes.get(version, "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            gaps.append(f"Missing verified document SHA-256: {version}")
        if not rules.document_effective_dates.get(version):
            gaps.append(f"Missing verified effective date: {version}")
    gaps.extend(clause for clause in UNRESOLVED_OFFICIAL_CLAUSES if clause not in rules.resolved_clauses)
    if rules.tie_policy == "fixture_lots":
        gaps.append("Synthetic fixture lottery rules cannot be published as official AC38 rules.")
    if rules.overall_carry is None:
        gaps.append("Overall-series carry-over points are not verified.")
    return gaps


def build_cup_forecast(mapped_strength: Mapping[str, float] | None = None, *, rules: CupRules | None = None,
                       scenarios: Sequence[CupScenario] | None = None, trials: int = 100_000,
                       seed: int = 2027, pooled_scale: float = 0.5) -> dict:
    """Production export. Never emits invented Cup percentages for missing rules."""
    rules = rules or CupRules()
    rules.validate()
    gaps = official_rules_gaps(rules)
    result = {"schema_version": "1.0", "method_version": "cup-ac38-conditional-1",
              "target": "2027 America's Cup AC75 trophy", "class": "AC75", "scope": "cup",
              "team_ids": list(TEAM_IDS), "team_names": TEAM_NAMES,
              "rule_sources": [dict(source, sha256=rules.document_hashes.get(source["version"]),
                                    effective_date=rules.document_effective_dates.get(source["version"]))
                               for source in RULE_SOURCES],
              "assumption_label": "AC40-informed scenario envelope, not calibrated AC75 probabilities",
              "forecast_start": "2027-05-22", "match_start": "2027-07-10",
              "schedule_policy": "versioned; continue beyond July 19 if required by official instructions",
              "probabilities": {team: None for team in TEAM_IDS}}
    if gaps:
        return dict(result, status="unavailable", reason_codes=["official_rules_not_fully_verified"],
                    unresolved_reasons=gaps, scenarios=[], scenario_envelope=None)
    if not mapped_strength:
        return dict(result, status="unavailable", reason_codes=["audited_competitive_strength_missing"],
                    unresolved_reasons=["No audited competitive AC40 ranking-layer strengths were supplied."],
                    scenarios=[], scenario_envelope=None)
    built = [simulate_cup(mapped_strength, scenario=scenario, rules=rules, trials=trials, seed=seed,
                          pooled_scale=pooled_scale) for scenario in (scenarios or standard_scenarios())]
    # An envelope covers only the scenarios actually built. Rule bounds remain
    # separate; they are never represented as a model-confidence interval.
    envelope = {team: {"minimum": min(item["probabilities"][team] for item in built),
                       "maximum": max(item["probabilities"][team] for item in built)}
                for team in TEAM_IDS} if all(item["status"] == "conditional_scenario" for item in built) else None
    return dict(result, status="conditional_scenario_envelope" if envelope else "rule_bounds",
                reason_codes=[], unresolved_reasons=[], scenarios=built, scenario_envelope=envelope,
                evaluated_scenario_ids=[item["scenario_id"] for item in built])


ROSTER_POLICIES = ("equal", "principal_only", "assumed_10_02")


def build_roster_mapping_matrix(entry_keys: list[str], policy: str = "equal",
                                entry_id_mode: str = "pooled_entry",
                                roster_path: Path | None = None) -> np.ndarray:
    """Build 7 x K linear combination matrix A mapping entry effects to syndicates."""
    if policy not in ROSTER_POLICIES:
        raise ValueError(f"Unknown roster policy '{policy}'; choose from {ROSTER_POLICIES}")
    mapping_weights = {
        "ETNZ": {"equal": {"NZL B": 0.5, "NZL G": 0.5, "NZL": 1.0},
                 "principal_only": {"NZL B": 1.0, "NZL G": 0.0, "NZL": 1.0},
                 "assumed_10_02": {"NZL B": 10.0 / 12.0, "NZL G": 2.0 / 12.0, "NZL": 1.0}},
        "GB1": {"equal": {"GBR B": 0.5, "GBR G": 0.5, "GBR": 1.0},
                "principal_only": {"GBR B": 1.0, "GBR G": 0.0, "GBR": 1.0},
                "assumed_10_02": {"GBR B": 10.0 / 12.0, "GBR G": 2.0 / 12.0, "GBR": 1.0}},
        "LUNA_ROSSA": {"equal": {"ITA B": 0.5, "ITA G": 0.5, "ITA": 1.0},
                       "principal_only": {"ITA B": 1.0, "ITA G": 0.0, "ITA": 1.0},
                       "assumed_10_02": {"ITA B": 10.0 / 12.0, "ITA G": 2.0 / 12.0, "ITA": 1.0}},
        "ALINGHI": {"equal": {"SUI": 1.0}, "principal_only": {"SUI": 1.0}, "assumed_10_02": {"SUI": 1.0}},
        "LA_ROCHE_POSAY": {"equal": {"FRA": 1.0}, "principal_only": {"FRA": 1.0}, "assumed_10_02": {"FRA": 1.0}},
        "ARC_USA": {"equal": {"USA": 1.0}, "principal_only": {"USA": 1.0}, "assumed_10_02": {"USA": 1.0}},
        "AUSTRALIA": {"equal": {"AUS": 1.0, "AUSTRALIA": 1.0},
                      "principal_only": {"AUS": 1.0, "AUSTRALIA": 1.0},
                      "assumed_10_02": {"AUS": 1.0, "AUSTRALIA": 1.0}},
    }
    event_entry_comp_races = {}
    if entry_id_mode == "event_entry" or any("::" in k for k in entry_keys):
        r_path = roster_path or (Path(__file__).resolve().parent.parent.parent / "docs" / "ac38_roster.json")
        if r_path.exists():
            try:
                r_doc = json.loads(r_path.read_text(encoding="utf-8"))
                for ee in r_doc.get("event_entries", []):
                    event_entry_comp_races[ee["event_entry_id"]] = max(ee.get("n_competitive_races", 1), 1)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Failed to load competitive race weights from {r_path}: {exc}") from exc

    k = len(entry_keys)
    A = np.zeros((7, k), dtype=float)
    key_idx = {k: i for i, k in enumerate(entry_keys)}
    for row_idx, team in enumerate(TEAM_IDS):
        weights = mapping_weights.get(team, {}).get(policy, {})
        present = {}
        for ek in entry_keys:
            base_k = ek.split("::")[-1]
            if base_k in weights:
                base_w = weights[base_k]
                comp_mult = event_entry_comp_races.get(ek, 1) if ("::" in ek or entry_id_mode == "event_entry") else 1
                present[ek] = base_w * comp_mult
        if present:
            tot = sum(present.values())
            if tot > 0:
                for ek, w in present.items():
                    A[row_idx, key_idx[ek]] = w / tot
    return A


def map_ac40_to_cup(ac40_effects: Mapping[str, float], policy: str = "equal",
                    entry_id_mode: str = "pooled_entry") -> dict[str, float]:
    """Map AC40 entry abilities to the 7 registered 2027 America's Cup teams.

    Uses linear combination weights according to the specified roster policy:
    - 'equal': 50/50 mean between senior (B) and youth/women (G) pairs.
    - 'principal_only': 100% weight to primary senior (B) team.
    - 'assumed_10_02': 10/12 senior, 2/12 youth/women.
    Unobserved teams are omitted so the simulator draws their population prior.
    """
    valid_groups = [
        ["NZL", "NZL B", "NZL G"],
        ["GBR", "GBR B", "GBR G"],
        ["ITA", "ITA B", "ITA G"],
        ["SUI"], ["FRA"], ["USA"], ["AUS", "AUSTRALIA"]
    ]
    keys = [k for k in ac40_effects if any(k.split("::")[-1] in grp for grp in valid_groups)]
    if not keys:
        return {}
    A = build_roster_mapping_matrix(keys, policy=policy, entry_id_mode=entry_id_mode)
    theta_entry = np.array([float(ac40_effects[k]) for k in keys])
    theta_syndicate = A @ theta_entry
    result = {}
    for i, team in enumerate(TEAM_IDS):
        if np.any(A[i, :] > 0):
            result[team] = float(theta_syndicate[i])
    return result


def map_ac40_to_cup_with_covariance(ac40_effects: Mapping[str, float],
                                    covariance: np.ndarray,
                                    entry_keys: list[str],
                                    policy: str = "equal",
                                    entry_id_mode: str = "pooled_entry") -> tuple[dict[str, float], dict[str, float], np.ndarray]:
    """Propagate Laplace posterior covariance from entry effects to syndicates:
    theta_syndicate = A @ theta_entry
    Sigma_syndicate = A @ Sigma_entry @ A^T
    """
    A = build_roster_mapping_matrix(entry_keys, policy=policy, entry_id_mode=entry_id_mode)
    theta_entry = np.array([float(ac40_effects[k]) for k in entry_keys])
    theta_syndicate = A @ theta_entry
    cov_syndicate = A @ covariance @ A.T
    mean_result = {}
    sd_result = {}
    for i, team in enumerate(TEAM_IDS):
        if np.any(A[i, :] > 0):
            mean_result[team] = float(theta_syndicate[i])
            sd_result[team] = float(np.sqrt(max(0.0, cov_syndicate[i, i])))
    return mean_result, sd_result, cov_syndicate


def cup_mapping_provenance(ac40_effects: Mapping[str, float], policy: str = "equal") -> dict:
    groups = {"ETNZ": ("NZL", "NZL B", "NZL G"), "GB1": ("GBR", "GBR B", "GBR G"),
              "LUNA_ROSSA": ("ITA", "ITA B", "ITA G"), "ALINGHI": ("SUI",),
              "LA_ROCHE_POSAY": ("FRA",), "ARC_USA": ("USA",), "AUSTRALIA": ("AUS", "AUSTRALIA")}
    mapped = map_ac40_to_cup(ac40_effects, policy=policy)
    return {"policy": f"Combination policy '{policy}' of observed AC40 entry effects within each team; unobserved teams retain a population prior.",
            "teams": [{"team_id": team, "observed": team in mapped,
                       "source_entries": [{"entry_id": entry, "effect": float(ac40_effects[entry])}
                                          for entry in groups[team] if entry in ac40_effects],
                       "mapped_strength": mapped.get(team)} for team in TEAM_IDS]}


def public_cup_artifact(*, source_manifest_hash: str, mapped_strength: Mapping[str, float] | None = None,
                        rules: CupRules | None = None, trials: int = 5_000, seed: int = 2027,
                        model_lineage: Mapping | None = None, mapping_provenance: Mapping | None = None,
                        feasible_slot_rule_bounds: bool = False,
                        direct_ac75_distribution: Mapping[str, object] | None = None,
                        posterior_draws_by_scenario: Mapping[str, np.ndarray] | None = None) -> dict:
    """Production Cup UI artifact with AC40 transfer scenario envelope and rule bounds.

    The source archive contains AC40 observations only. When mapped AC40 strengths
    are supplied, 9 standard correlation and variance scenarios are evaluated
    under conservative tournament rules to produce transfer envelopes.
    """
    rules = rules or CupRules()
    gaps = official_rules_gaps(rules)
    gaps.extend((
        "The archive contains no AC75 outcomes validating the AC40-to-AC75 transfer assumptions.",
        "AC75 completion reliability and committee timing/raceability conditions are not established by this AC40 archive.",
    ))
    if not mapped_strength:
        gaps.append("Audited competitive AC40 ranking-layer strengths are not yet supplied to the Cup adapter.")
        return {
            "header": {"schema_version": "cup-1", "method_version": "cup-ac38-conditional-1",
                       "boat_class": "AC75", "scope": "cup", "source_manifest_hash": source_manifest_hash,
                       "target": "2027 America's Cup AC75 trophy", "units": "probability",
                       "rule_sources": [dict(source, effective_date=rules.document_effective_dates.get(source["version"]))
                                        for source in RULE_SOURCES]},
            "status": "unavailable", "reason_code": "official_rules_and_ac75_evidence_unresolved",
            "reason": " ".join(gaps), "reason_codes": ["official_tie_and_continuation_clauses_unresolved",
                                                        "ac40_ac75_transfer_unvalidated",
                                                        "ac75_timing_and_completion_evidence_missing"],
            "unresolved_reasons": gaps,
            "teams": [{"id": team, "name": TEAM_NAMES[team]} for team in TEAM_IDS],
            "probabilities": {team: None for team in TEAM_IDS},
            "win_prob_by_team": {team: None for team in TEAM_IDS},
            "scenario_envelope_by_team": None, "rule_bounds_by_team": None, "scenarios": [],
            "assumption_label": "AC40-informed scenario analysis; AC75 calibration unavailable",
            "forecast_start": "2027-05-22", "match_start": "2027-07-10",
            "schedule_policy": "versioned schedule; the Match may continue beyond July 19 under official instructions",
        }

    scenarios = standard_scenarios()
    built = [
        simulate_cup(
            mapped_strength,
            scenario=s,
            rules=rules,
            trials=trials,
            seed=seed,
            feasible_slot_rule_bounds=feasible_slot_rule_bounds,
            direct_ac75_distribution=direct_ac75_distribution,
            posterior_world_draws=(posterior_draws_by_scenario or {}).get(s.scenario_id),
        )
        for s in scenarios
    ]
    envelope = {
        team: {
            "lower": round(min(item["rule_bounds"][team]["lower"] for item in built), 4),
            "upper": round(max(item["rule_bounds"][team]["upper"] for item in built), 4),
        }
        for team in TEAM_IDS
    }
    # Baseline scenario is rho=0.5, sigma=1.0 (index 4 in standard_scenarios)
    baseline = built[4] if len(built) > 4 else built[0]
    rule_bounds = {
        team: {
            "lower": round(baseline["rule_bounds"][team]["lower"], 4),
            "upper": round(baseline["rule_bounds"][team]["upper"], 4),
        }
        for team in TEAM_IDS
    }
    analysis = {
        "schema_version": "cup-scenarios-1", "baseline_scenario_id": baseline["scenario_id"],
        "model_lineage": dict(model_lineage or {}),
        "mapping_provenance": dict(mapping_provenance or {
            "policy": "Explicit supplied team strengths; absent keys receive the population prior.",
            "teams": [{"team_id": team, "observed": team in mapped_strength, "source_entries": [],
                       "mapped_strength": mapped_strength.get(team)} for team in TEAM_IDS]}),
        "build_budget": {"trials_per_scenario": trials, "scenario_count": len(built), "seed": seed,
                         "profile": "explicit-cup-scenario-budget", "common_random_numbers": True,
                         "randomization_policy": "Shared seed and common initial Gaussian draws; later draw alignment can differ when simulated series lengths differ."},
        "simulation_inputs": {"mapped_strength": dict(mapped_strength), "rules": asdict(rules),
                              "pooled_scale": .5, "failure_probability": 0.0,
                              "conditional_on_completed_scored_races": True},
        "conditioning": {
            "reliability": "Conditional on completed, scored races; failures and timing stoppages are not sampled.",
            "weather": "All team weather-response slopes are zero unless explicitly supplied in the rules; no AC75 weather response is fitted.",
            "transfer": "Rho is an assumed loading on AC40 effects, not a fitted cross-class correlation. No AC75 calibration is established.",
            "ability": "Team capability is drawn once and persists throughout the tournament; missing AC40 strengths receive a population prior.",
            "scenario_weights": "Finite sensitivity grid with no probability weights; its envelope is not a confidence interval.",
        },
        "records": [{key: item[key] for key in (
            "scenario_id", "scenario", "trials", "seed", "input_hash", "status", "resolved_trials",
            "unresolved_trials", "resolved_fraction", "unresolved_fraction", "resolved_win_counts",
            "first_unresolved_stage_counts", "overlapping_reason_counts", "reason_count_policy",
            "rule_bounds", "probabilities", "numerical_error", "unresolved_reasons", "assumptions")}
            | {"model_ref": (model_lineage or {}).get("model_ref"),
               "source_manifest_hash": source_manifest_hash,
               **({"posterior_draws_sha256": item["posterior_draws_sha256"]} if item.get("posterior_draws_sha256") else {})} for item in built],
        "extrema_by_team": {team: {
            "lower_scenario_ids": [item["scenario_id"] for item in built if item["rule_bounds"][team]["lower"] == min(b["rule_bounds"][team]["lower"] for b in built)],
            "upper_scenario_ids": [item["scenario_id"] for item in built if item["rule_bounds"][team]["upper"] == max(b["rule_bounds"][team]["upper"] for b in built)],
        } for team in TEAM_IDS},
        "refinement_policy": {"method": "conservative_outer_bounds", "status": "retained",
            "reason": "The authoritative six-Challenger tie completion set is not pinned. No invented lottery or feasible-champion restriction is applied; unresolved paths retain [0,1]."},
    }

    return {
        "header": {"schema_version": "cup-1", "method_version": "cup-ac38-conditional-1",
                   "boat_class": "AC75", "scope": "cup", "source_manifest_hash": source_manifest_hash,
                   "target": "2027 America's Cup AC75 trophy", "units": "probability",
                   "method_and_assumption_refs": [
                       "AC40-to-AC75 strength transfer envelope",
                       "9 standard transfer-loading/residual-variance scenarios",
                       "Unresolved official tie policy: outer rule bounds retain tied paths",
                   ],
                   "rule_sources": [dict(source, effective_date=rules.document_effective_dates.get(source["version"]))
                                    for source in RULE_SOURCES]},
        "status": "estimated",
        "reason_code": "conditional_scenario_envelope",
        "reason": "AC40-informed scenario analysis; AC75 calibration unavailable",
        "reason_codes": ["ac40_informed_transfer_envelope", "rule_bounds_unresolved_ties"],
        "unresolved_reasons": gaps,
        "teams": [{"id": team, "name": TEAM_NAMES[team]} for team in TEAM_IDS],
        "probabilities": {team: None for team in TEAM_IDS},
        "win_prob_by_team": {team: None for team in TEAM_IDS},
        "scenario_envelope_by_team": envelope,
        "scenario_analysis": analysis,
        "rule_bounds_by_team": rule_bounds,
        "evaluated_scenarios": [s.scenario_id for s in scenarios],
        "scenarios": [item["scenario_id"] for item in built],
        "assumption_label": "AC40-informed scenario analysis; AC75 calibration unavailable",
        "forecast_start": "2027-05-22", "match_start": "2027-07-10",
        "schedule_policy": "versioned schedule; the Match may continue beyond July 19 under official instructions",
    }
