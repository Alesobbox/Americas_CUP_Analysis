"""Deterministic rule fixtures; no downloaded data, weights or network calls."""

from dataclasses import replace
import unittest

from pipeline.prediction.cup import (
    TEAM_IDS, CupRules, CupScenario, MatchScore, build_cup_forecast,
    choose_semifinal_opponent, hazard_probability, official_rules_gaps,
    public_cup_artifact, simulate_cup, standard_scenarios,
)


def fixed_results(*, cup_zero_races=0, selected="LA_ROCHE_POSAY"):
    """Every qualifying result is fixed, so later known participants are valid."""
    scores = {}
    for round_number in range(1, 4):
        for index_a, team_a in enumerate(TEAM_IDS):
            for team_b in TEAM_IDS[index_a + 1:]:
                scores[f"rr:{round_number}:{team_a}:{team_b}"] = MatchScore(team_a, team_b, 1, 0)

    def wins(stage, team_a, team_b, count):
        for race in range(1, count + 1):
            scores[f"{stage}:{race}"] = MatchScore(team_a, team_b, 1, 0)

    wins("repechage_1", "ARC_USA", "AUSTRALIA", 2)
    wins("repechage_2", "LA_ROCHE_POSAY", "ARC_USA", 2)
    wins("semifinal_1", "GB1", selected, 5)
    other = "ALINGHI" if selected == "LA_ROCHE_POSAY" else "LA_ROCHE_POSAY"
    wins("semifinal_2", "LUNA_ROSSA", other, 5)
    wins("challenger_final", "GB1", "LUNA_ROSSA", 7)
    for race in range(1, cup_zero_races + 1):
        scores[f"cup_match:{race}"] = MatchScore("ETNZ", "GB1", 0, 0)
    for race in range(cup_zero_races + 1, cup_zero_races + 8):
        scores[f"cup_match:{race}"] = MatchScore("ETNZ", "GB1", 1, 0)
    return CupRules(known_fleet_orders=(TEAM_IDS,) * 6, known_match_scores=scores,
                    official_selections={"GB1": selected} if selected != "LA_ROCHE_POSAY" else {})


class CupTournamentTests(unittest.TestCase):
    def test_fixed_official_results_and_every_advancement_path(self):
        forecast = simulate_cup({}, rules=fixed_results(), trials=12, seed=9)
        self.assertEqual(forecast["status"], "conditional_scenario")
        self.assertEqual(forecast["probabilities"]["ETNZ"], 1)
        advancements = forecast["diagnostics"]["advancement_frequency"]
        self.assertEqual(advancements["repechage_1"]["ARC_USA"], 1)
        self.assertEqual(advancements["repechage_2"]["LA_ROCHE_POSAY"], 1)
        self.assertEqual(advancements["semifinal_1"]["GB1"], 1)
        self.assertEqual(advancements["semifinal_2"]["LUNA_ROSSA"], 1)
        self.assertEqual(advancements["challenger_final"]["GB1"], 1)
        # Fifteen Challenger-only RR points plus fleet carry: Defender results excluded.
        self.assertEqual(forecast["diagnostics"]["mean_round_robin_points"]["GB1"], 17.5)
        self.assertEqual(forecast["diagnostics"]["mean_round_robin_points"]["ETNZ"], 0)

    def test_zero_results_extend_cup_match_beyond_thirteen(self):
        forecast = simulate_cup({}, rules=fixed_results(cup_zero_races=14), trials=6)
        self.assertEqual(forecast["probabilities"]["ETNZ"], 1)
        self.assertEqual(forecast["rules"]["max_observed_series_races"], 21)

    def test_actual_semifinal_choice_overrides_default_policy(self):
        forecast = simulate_cup({}, rules=fixed_results(selected="ALINGHI"), trials=7)
        self.assertEqual(forecast["status"], "conditional_scenario")
        self.assertEqual(forecast["probabilities"]["ETNZ"], 1)

    def test_fleet_points_ties_use_last_finishing_places_under_rule_107(self):
        rules = replace(fixed_results(), known_fleet_orders=(TEAM_IDS, tuple(reversed(TEAM_IDS))) * 3)
        forecast = simulate_cup({}, rules=rules, trials=6)
        self.assertEqual(forecast["status"], "conditional_scenario")
        # Every fleet points total is tied; Australia won the latest race and
        # receives 2.5 carry, while GB1 is last Challenger and receives zero.
        points = forecast["diagnostics"]["mean_round_robin_points"]
        self.assertEqual(points["GB1"], 15)
        self.assertEqual(points["AUSTRALIA"], 2.5)
        self.assertEqual(forecast["diagnostics"]["mean_overall_points"]["ETNZ"], 18)

    def test_penalized_round_robin_points_keep_separate_observable_win_record(self):
        rules = fixed_results()
        scores = dict(rules.known_match_scores)
        key = "rr:1:GB1:LUNA_ROSSA"
        scores[key] = MatchScore("GB1", "LUNA_ROSSA", -1, 0, win_credit_a=1, win_credit_b=0)
        result = simulate_cup({}, rules=replace(rules, known_match_scores=scores), trials=5)
        self.assertEqual(result["status"], "conditional_scenario")
        self.assertEqual(result["diagnostics"]["mean_round_robin_points"]["GB1"], 15.5)
        scores[key] = MatchScore("GB1", "LUNA_ROSSA", -1, 0)
        unknown_record = simulate_cup({}, rules=replace(rules, known_match_scores=scores), trials=5)
        self.assertEqual(unknown_record["status"], "rule_bounds")
        self.assertTrue(any("win credits" in reason for reason in unknown_record["unresolved_reasons"]))

    def test_observable_opponent_policy_uses_record_then_prior_then_id(self):
        eligible = ("ALINGHI", "ARC_USA", "AUSTRALIA")
        self.assertEqual(choose_semifinal_opponent(eligible,
            {"ALINGHI": 8, "ARC_USA": 2, "AUSTRALIA": 3},
            {"ALINGHI": 10, "ARC_USA": 10, "AUSTRALIA": 10},
            {"ALINGHI": 0.1, "ARC_USA": 0.8, "AUSTRALIA": 0.01}), "ARC_USA")
        self.assertEqual(choose_semifinal_opponent(eligible, dict.fromkeys(eligible, 3),
            dict.fromkeys(eligible, 10), {"ALINGHI": 0.3, "ARC_USA": 0.2, "AUSTRALIA": 0.2}), "ARC_USA")

    def test_unresolved_official_ties_are_bounds_not_equal_weight_draws(self):
        result = simulate_cup(dict.fromkeys(TEAM_IDS, 0), scenario=CupScenario(1, 0),
                              trials=1000, seed=37)
        self.assertEqual(result["status"], "rule_bounds")
        self.assertTrue(all(value is None for value in result["probabilities"].values()))
        self.assertGreater(result["unresolved_trials"], 0)
        for bounds in result["rule_bounds"].values():
            self.assertGreaterEqual(bounds["lower"], 0)
            self.assertLessEqual(bounds["upper"], 1)
            self.assertGreaterEqual(bounds["upper"], bounds["lower"])

    def test_equal_known_abilities_under_complete_symmetric_fixture_rules(self):
        # The fixture lottery is a complete synthetic rule, not an assumption
        # resolving the missing official six-Challenger tie clause.
        result = simulate_cup(dict.fromkeys(TEAM_IDS, 0), scenario=CupScenario(1, 0),
                              rules=CupRules(tie_policy="fixture_lots"), trials=30_000, seed=19)
        self.assertEqual(result["status"], "conditional_scenario")
        self.assertAlmostEqual(result["probabilities"]["ETNZ"], 0.5, delta=0.012)
        for team in TEAM_IDS[1:]:
            self.assertAlmostEqual(result["probabilities"][team], 1 / 12, delta=0.008)
        self.assertAlmostEqual(sum(result["probabilities"].values()), 1)

    def test_dominant_defender_and_match_concentration_sensitivity(self):
        strengths = dict.fromkeys(TEAM_IDS, 0)
        strengths["ETNZ"] = 0.7
        args = dict(mapped_strength=strengths, rules=CupRules(tie_policy="fixture_lots"),
                    trials=6000, seed=3)
        soft = simulate_cup(scenario=CupScenario(1, 0, 1), **args)
        sharp = simulate_cup(scenario=CupScenario(1, 0, 3), **args)
        self.assertGreater(sharp["probabilities"]["ETNZ"], soft["probabilities"]["ETNZ"] + 0.08)

    def test_australia_is_never_omitted_for_missing_source_history(self):
        result = simulate_cup({"ETNZ": 0.1}, rules=CupRules(tie_policy="fixture_lots"),
                              trials=1000, seed=21)
        self.assertIn("AUSTRALIA", result["probabilities"])
        self.assertGreater(result["probabilities"]["AUSTRALIA"], 0)

    def test_unknown_timing_and_nonfinish_are_not_fabricated_scores(self):
        result = simulate_cup({}, rules=CupRules(tie_policy="fixture_lots"), trials=20,
                              failure_probability=1, conditional_on_completed_scored_races=False,
                              seed=8)
        self.assertEqual(result["unresolved_trials"], 20)
        for bounds in result["rule_bounds"].values():
            self.assertEqual(bounds, {"lower": 0, "upper": 1})
        self.assertTrue(any("safety budget" in reason for reason in result["unresolved_reasons"]))

    def test_publication_fails_closed_with_missing_rule_evidence(self):
        output = build_cup_forecast({"ETNZ": 0.2})
        self.assertEqual(output["status"], "unavailable")
        self.assertIsNone(output["scenario_envelope"])
        self.assertEqual(output["scenarios"], [])
        self.assertTrue(all(p is None for p in output["probabilities"].values()))
        self.assertTrue(any("effective date" in reason for reason in output["unresolved_reasons"]))
        self.assertTrue(all(len(source["sha256"]) == 64 for source in output["rule_sources"]))

    def test_public_static_contract_has_all_teams_and_pinned_sources(self):
        output = public_cup_artifact(source_manifest_hash="a" * 64)
        self.assertEqual(output["header"]["schema_version"], "cup-1")
        self.assertEqual(output["header"]["boat_class"], "AC75")
        self.assertEqual(output["header"]["source_manifest_hash"], "a" * 64)
        self.assertEqual({team["id"] for team in output["teams"]}, set(TEAM_IDS))
        self.assertTrue(all(len(source["sha256"]) == 64 for source in output["header"]["rule_sources"]))
        self.assertIsNone(output["scenario_envelope_by_team"])
        self.assertEqual(CupRules().fleet_points, (10, 9, 8, 7, 6, 5, 4))
        self.assertEqual(CupRules().overall_carry, (3, 2.5, 2, 1.5, 1, 0.5, 0))

    def test_standard_grid_and_hazard_are_exact_declared_assumptions(self):
        grid = standard_scenarios()
        self.assertEqual(len(grid), 9)
        self.assertEqual(len({item.scenario_id for item in grid}), 9)
        self.assertTrue(all(item.match_concentration == item.hazard_multiplier == 1 for item in grid))
        self.assertAlmostEqual(hazard_probability(0.2, 2), 0.36)
        self.assertAlmostEqual(hazard_probability(0.2, 0.5), 1 - 0.8**0.5)
        self.assertEqual(hazard_probability(1, 2), 1)
        with self.assertRaises(ValueError):
            hazard_probability(1.01, 1)

    def test_invalid_fixed_results_and_fixture_rules_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate_cup({}, rules=CupRules(known_fleet_orders=(("ETNZ",) * 7,)), trials=2)
        with self.assertRaises(ValueError):
            simulate_cup({}, rules=CupRules(tie_policy="priority"), trials=2)
        with self.assertRaises(ValueError):
            simulate_cup({}, rules=CupRules(series_race_safety_limit=13), trials=2)
        self.assertTrue(any("Synthetic fixture" in gap for gap in official_rules_gaps(CupRules(tie_policy="fixture_lots"))))

    def test_reproducibility_and_input_hash_change(self):
        args = dict(mapped_strength={"GB1": 0.2}, rules=CupRules(tie_policy="fixture_lots"),
                    trials=70, seed=42)
        one, two = simulate_cup(**args), simulate_cup(**args)
        self.assertEqual(one, two)
        changed = simulate_cup(**dict(args, seed=43))
        self.assertNotEqual(one["input_hash"], changed["input_hash"])


if __name__ == "__main__":
    unittest.main()
