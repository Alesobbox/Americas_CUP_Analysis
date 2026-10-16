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

    def validate(self) -> None:
        if not 0 <= self.rho <= 1 or self.sigma_multiplier < 0:
            raise ValueError("rho must lie in [0,1] and sigma_multiplier must be nonnegative")
        if self.match_concentration <= 0 or self.hazard_multiplier <= 0:
            raise ValueError("match concentration and hazard multiplier must be positive")
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("scenario parameters must be finite")

    @property
    def scenario_id(self) -> str:
        return (f"rho{self.rho:g}_sigma{self.sigma_multiplier:g}"
                f"_c{self.match_concentration:g}_k{self.hazard_multiplier:g}")


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
                 conditional_on_completed_scored_races: bool = True) -> dict:
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
    population = rng.normal(0, pooled_scale, (trials, 7))
    base = np.where(missing[None, :], population, means[None, :])
    # One draw per team per whole tournament, never independently per match.
    theta = scenario.rho * base + rng.normal(0, scenario.sigma_multiplier * pooled_scale, (trials, 7))
    slopes = np.array([rules.weather_sensitivity.get(team, 0.0) for team in TEAM_IDS])
    day_factors: dict[int, np.ndarray] = {}
    unresolved = np.zeros(trials, dtype=bool)
    reasons: set[str] = set()
    if rules.withdrawn:
        unresolved[:] = True
        reasons.add("Withdrawal scoring/advancement instructions are not supplied.")
    rr_wins = np.zeros((trials, 7))
    rr_played = np.zeros((trials, 7), dtype=np.int16)
    max_series_races = 0

    def day_theta(day: int) -> np.ndarray:
        if day not in day_factors:
            day_factors[day] = rng.normal(size=trials)
        return theta + day_factors[day][:, None] * slopes[None, :]

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
            unresolved |= ties
            if np.any(ties):
                reasons.add(f"{stage}: official tie resolution is unresolved; outer bounds retain the entire tied path.")
            secondary = np.broadcast_to(ids, points.shape)
        elif rules.tie_policy == "fixture_lots":
            secondary = rng.random(points.shape)
        else:
            priority = {TEAM_IDS.index(team): rank for rank, team in enumerate(rules.tie_priority)}
            secondary = np.broadcast_to(np.array([priority[int(i)] for i in ids]), points.shape)
        return np.broadcast_to(ids, points.shape)[rows[:, None], np.lexsort((secondary, -points), axis=1)]

    def draw_match(a: np.ndarray, b: np.ndarray, day: int) -> tuple[np.ndarray, np.ndarray]:
        nonlocal unresolved
        abilities = day_theta(day)
        # Joint uniform-reference mixture applied to the actual match draw.
        p = (1 - 0.0001) * _logistic(scenario.match_concentration *
                                    (abilities[rows, a] - abilities[rows, b])) + 0.0001 * 0.5
        win_a = rng.random(trials) < p
        if q:
            finish_a, finish_b = rng.random(trials) >= q, rng.random(trials) >= q
            unresolved |= ~finish_a | ~finish_b
            reasons.add("Sampled nonfinish requires official timing/status scoring unavailable to the rank-only kernel.")
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
        unresolved |= ~matched
        if np.any(~matched):
            reasons.add(f"{key}: observed participants require additional fixed earlier advancement results.")
        if not known.resolved:
            unresolved[:] = True
            reasons.add(f"{key}: observed score is unresolved.")
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
                unresolved |= any_failure
                reasons.add("Fleet nonfinish needs official status/timing points beyond rank-only observations.")
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
                        unresolved[:] = True
                        reasons.add(f"{key}: penalized points need separate observed match win credits for opponent selection.")
                        policy_pa, policy_pb = np.zeros(trials), np.zeros(trials)
                    rr_wins[:, a_idx] += policy_pa
                    rr_wins[:, b_idx] += policy_pb
                    rr_played[:, a_idx] += 1
                    rr_played[:, b_idx] += 1
                rr_race += 1
    seeds = standing(challenger_points[:, 1:], challenger_ids, "round_robin_challengers")

    def series(a: np.ndarray, b: np.ndarray, target: int, stage: str,
               initial_a: float = 0, initial_b: float = 0, day: int = 100) -> np.ndarray:
        nonlocal unresolved, max_series_races
        points_a, points_b = np.full(trials, initial_a, dtype=float), np.full(trials, initial_b, dtype=float)
        race_number = 0
        while np.any((points_a < target) & (points_b < target)):
            active = (points_a < target) & (points_b < target)
            race_number += 1
            if race_number > rules.series_race_safety_limit:
                unresolved |= active
                reasons.add(f"{stage}: continuation safety budget exhausted; no scheduled-race cap was substituted.")
                break
            pa, pb = apply_known(f"{stage}:{race_number}", a, b,
                                 *draw_match(a, b, day + (race_number - 1) // 3))
            points_a += np.where(active, pa, 0)
            points_b += np.where(active, pb, 0)
        max_series_races = max(max_series_races, race_number)
        unresolved |= (points_a >= target) & (points_b >= target)
        if np.any((points_a >= target) & (points_b >= target)):
            reasons.add(f"{stage}: simultaneous threshold requires official resolution.")
        return np.where(points_a >= target, a, b)

    repechage_first = series(seeds[:, 4], seeds[:, 5], 3, "repechage_1", initial_a=1, day=100)
    repechage_winner = series(seeds[:, 3], repechage_first, 3, "repechage_2", initial_a=1, day=110)
    eligible = np.column_stack((seeds[:, 1], seeds[:, 2], repechage_winner))
    selector = seeds[:, 0]
    fraction = np.divide(rr_wins, rr_played, out=np.full_like(rr_wins, 0.5), where=rr_played > 0)
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
        unresolved |= applies & ~legal
        if np.any(applies & ~legal):
            reasons.add("An official semifinal choice requires missing prior advancement results.")
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
    upper = np.minimum(1, (counts + unresolved_count) / trials)
    estimate = counts / trials if unresolved_count == 0 else None
    numerical_half_width = 1.96 * np.sqrt(0.25 / trials)
    payload = {
        "status": "conditional_scenario" if unresolved_count == 0 else "rule_bounds",
        "target": "2027 America's Cup AC75 trophy", "units": "probability",
        "scenario_id": scenario.scenario_id, "scenario": asdict(scenario),
        "trials": trials, "seed": seed, "resolved_trials": resolved_count,
        "unresolved_trials": unresolved_count, "probabilities": {
            team: float(estimate[i]) if estimate is not None else None for i, team in enumerate(TEAM_IDS)},
        "rule_bounds": {team: {"lower": float(lower[i]), "upper": float(upper[i])}
                        for i, team in enumerate(TEAM_IDS)},
        "bounds_kind": "conservative_outer_bounds; unresolved trajectories retain [0,1]",
        "numerical_error": {"worst_case_95_half_width": numerical_half_width,
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
        "diagnostics": {"mean_round_robin_points": dict(zip(TEAM_IDS, np.mean(challenger_points, axis=0).tolist())),
                        "mean_overall_points": dict(zip(TEAM_IDS, np.mean(overall_points, axis=0).tolist())),
                        "challenger_selection_frequency": dict(zip(TEAM_IDS, (np.bincount(challenger, minlength=7) / trials).tolist())),
                        "advancement_frequency": {
                            stage: dict(zip(TEAM_IDS, (np.bincount(winners, minlength=7) / trials).tolist()))
                            for stage, winners in (("repechage_1", repechage_first), ("repechage_2", repechage_winner),
                                                   ("semifinal_1", sf1), ("semifinal_2", sf2),
                                                   ("challenger_final", challenger))}},
    }
    payload["input_hash"] = _canonical_hash({"mapped_strength": dict(mapped_strength), "rules": asdict(rules),
                                             "scenario": asdict(scenario), "seed": seed, "trials": trials,
                                             "pooled_scale": pooled_scale, "failure_probability": failure_probability,
                                             "conditional_on_completed_scored_races": conditional_on_completed_scored_races})
    return payload


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


def public_cup_artifact(*, source_manifest_hash: str, mapped_strength: Mapping[str, float] | None = None,
                        rules: CupRules | None = None) -> dict:
    """Cheap static UI artifact; importing/building it never runs simulations.

    The source archive contains AC40 observations only. Even a fully specified
    conditional tournament model cannot support an unconditional calibrated
    actual-Cup percentage without its class-transfer and completion assumptions.
    Scenario builders must be invoked explicitly and their scopes kept separate.
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
        "scenario_envelope_by_team": None, "rule_bounds": None, "scenarios": [],
        "assumption_label": "AC40-informed scenario analysis; AC75 calibration unavailable",
        "forecast_start": "2027-05-22", "match_start": "2027-07-10",
        "schedule_policy": "versioned schedule; the Match may continue beyond July 19 under official instructions",
    }
