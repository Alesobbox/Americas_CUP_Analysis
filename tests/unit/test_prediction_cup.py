"""Deterministic rule fixtures; no downloaded data, weights or network calls."""

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.prediction.cup import (
    TEAM_IDS, CupRules, CupScenario, MatchScore, build_cup_forecast,
    choose_semifinal_opponent, hazard_probability, official_rules_gaps,
    public_cup_artifact, simulate_cup, standard_scenarios,
    map_ac40_to_cup, cup_mapping_provenance,
)
from pipeline.prediction.contracts import content_hash, validate_cup


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


class CupEvidenceTests(unittest.TestCase):
    def test_method_two_requires_scenario_evidence_without_breaking_legacy_or_unavailable(self):
        original = public_cup_artifact(source_manifest_hash="a" * 64, mapped_strength={"ETNZ": .2}, trials=50)
        for status in ("available", "estimated"):
            for headline in (False, True):
                cup = deepcopy(original)
                cup["header"]["method_version"] = "cup-ac38-conditional-2"
                cup["status"] = status
                del cup["scenario_analysis"]
                if headline:
                    cup["probabilities"]["ETNZ"] = .9
                with self.subTest(status=status, headline=headline), self.assertRaisesRegex(ValueError, "required for a usable"):
                    validate_cup(cup)
        legacy = deepcopy(original)
        legacy.pop("scenario_analysis")
        legacy["header"]["method_version"] = "cup-ac38-conditional-1"
        validate_cup(legacy)
        unavailable = public_cup_artifact(source_manifest_hash="a" * 64)
        unavailable["header"]["method_version"] = "cup-ac38-conditional-2"
        validate_cup(unavailable)

    def test_scenario_evidence_requires_complete_null_headline_containers(self):
        original = public_cup_artifact(source_manifest_hash="a" * 64, mapped_strength={"ETNZ": .2}, trials=50)
        for field in ("probabilities", "win_prob_by_team"):
            for mutation in ("point", "missing_team", "extra_team", "missing_container", "null_container"):
                cup = deepcopy(original)
                if mutation == "point": cup[field]["ETNZ"] = .9
                if mutation == "missing_team": del cup[field]["ETNZ"]
                if mutation == "extra_team": cup[field]["INVENTED"] = None
                if mutation == "missing_container": del cup[field]
                if mutation == "null_container": cup[field] = None
                with self.subTest(field=field, mutation=mutation), self.assertRaisesRegex(ValueError, "headline Cup probability containers"):
                    validate_cup(cup)

    def test_public_mapping_distinguishes_missing_history_from_observed_zero(self):
        effects = {"NZL B": 0.0, "ITA B": .4, "ITA G": .8}
        mapped = map_ac40_to_cup(effects)
        self.assertEqual(mapped["ETNZ"], 0)
        self.assertAlmostEqual(mapped["LUNA_ROSSA"], .6)
        self.assertNotIn("AUSTRALIA", mapped)
        provenance = cup_mapping_provenance(effects)
        australia = next(team for team in provenance["teams"] if team["team_id"] == "AUSTRALIA")
        self.assertFalse(australia["observed"])
        self.assertIsNone(australia["mapped_strength"])
        result = simulate_cup(mapped, scenario=CupScenario(1, 1), trials=50)
        self.assertIn("AUSTRALIA", result["diagnostics"]["missing_strength_teams"])
        variance = result["diagnostics"]["persistent_ability_variance_by_team"]
        self.assertAlmostEqual(variance["AUSTRALIA"], .5)
        self.assertAlmostEqual(variance["ETNZ"], .25)

    def test_exported_scenario_counts_bounds_and_endpoints_reconstruct(self):
        cup = public_cup_artifact(source_manifest_hash="a" * 64, mapped_strength={"ETNZ": .2}, trials=300, seed=17)
        validate_cup(cup)
        analysis = cup["scenario_analysis"]
        self.assertEqual(len(analysis["records"]), 9)
        self.assertEqual(analysis["baseline_scenario_id"], "rho0.5_sigma1_c1_k1")
        self.assertEqual(analysis["build_budget"]["trials_per_scenario"], 300)
        for record in analysis["records"]:
            self.assertEqual(sum(record["first_unresolved_stage_counts"].values()), record["unresolved_trials"])
            self.assertEqual(sum(record["resolved_win_counts"].values()), record["resolved_trials"])
            if record["unresolved_trials"]:
                self.assertTrue(all(value is None for value in record["probabilities"].values()))
        json.dumps(cup, allow_nan=False)
        self.assertIn("not a fitted cross-class correlation", analysis["conditioning"]["transfer"])

    def test_validator_rejects_unreconciled_counts_attribution_and_points(self):
        original = public_cup_artifact(source_manifest_hash="a" * 64, mapped_strength={"ETNZ": 0}, trials=150)
        for mutation in ("count", "first_stage", "endpoint", "point", "baseline", "missing"):
            cup = deepcopy(original)
            analysis = cup["scenario_analysis"]
            record = next(item for item in analysis["records"] if item["unresolved_trials"])
            if mutation == "count": record["resolved_trials"] += 1
            if mutation == "first_stage": record["first_unresolved_stage_counts"]["invented"] = 1
            if mutation == "endpoint": analysis["extrema_by_team"]["ETNZ"]["lower_scenario_ids"] = ["invented"]
            if mutation == "point": record["probabilities"]["ETNZ"] = .5
            if mutation == "baseline": analysis["baseline_scenario_id"] = "invented"
            if mutation == "missing": next(t for t in analysis["mapping_provenance"]["teams"] if not t["observed"])["mapped_strength"] = 0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_cup(cup)

    def test_candidate_uses_latest_pinned_model_and_never_publishes(self):
        from pipeline.prediction.build import build_cup_candidate, publish_cup_candidate
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "public" / "data" / "predictions"
            (directory / "models").mkdir(parents=True)
            manifest = {"source": "synthetic fixture"}
            manifest_hash = content_hash(manifest)
            (directory / "manifests").mkdir()
            (directory / "manifests" / (manifest_hash + ".json")).write_text(json.dumps(manifest))
            models = []
            for day, effect in (("2026-05-22", .1), ("2026-09-26", .2)):
                model = {"source_manifest_hash": manifest_hash, "training_before_day": day,
                         "strength": {"method": "fixture", "effects": {"NZL B": effect}}}
                ref = content_hash(model)
                (directory / "models" / (ref + ".json")).write_text(json.dumps(model))
                models.append(ref)
            index = {"source_manifest_hash": manifest_hash, "races": [{"model_ref": ref} for ref in reversed(models)], "cup_path": "cup/old.json"}
            before = json.dumps(index)
            (directory / "index.json").write_text(before)
            result = build_cup_candidate(root, trials=60, seed=11)
            self.assertEqual(result["model_ref"], models[-1])
            self.assertEqual((directory / "index.json").read_text(), before)
            self.assertFalse((directory / "cup").exists())
            cup = json.loads(Path(result["candidate_path"]).read_text())
            self.assertEqual(cup["scenario_analysis"]["model_lineage"]["training_before_day"], "2026-09-26")
            with patch("pipeline.prediction.build.verify_public", side_effect=ValueError("fixture staged failure")):
                with self.assertRaisesRegex(ValueError, "staged failure"):
                    publish_cup_candidate(root, Path(result["candidate_path"]))
            self.assertEqual((directory / "index.json").read_text(), before)
            with self.assertRaisesRegex(ValueError, "outside public"):
                build_cup_candidate(root, trials=5, output_path=directory / "candidate.json")

    def test_feasible_slot_rule_bounds_tightness_and_consistency(self):
        # 1. Zero unresolved trials: bounds match point probabilities exactly
        forecast_resolved = simulate_cup({}, rules=fixed_results(), trials=20, seed=12,
                                         feasible_slot_rule_bounds=True)
        self.assertEqual(forecast_resolved["unresolved_trials"], 0)
        for team in TEAM_IDS:
            b = forecast_resolved["rule_bounds"][team]
            prob = forecast_resolved["probabilities"][team]
            self.assertAlmostEqual(b["lower"], prob, places=6)
            self.assertAlmostEqual(b["upper"], prob, places=6)
            self.assertLessEqual(b["lower"], b["upper"])
            self.assertGreaterEqual(b["lower"], 0.0)
            self.assertLessEqual(b["upper"], 1.0)

        # 2. Late unresolved stage: fixed semifinal / cup match tie produces tighter bounds
        # than naive outer bounds which add unresolved_trials to ALL teams
        semifinal_unresolved_rules = fixed_results()
        # Drop cup match results so cup match is unresolved
        scores_without_cup = {k: v for k, v in semifinal_unresolved_rules.known_match_scores.items()
                              if not k.startswith("cup_match:")}
        # Inject an unresolved withdrawal or stage failure at cup match
        forecast_tight = simulate_cup({}, rules=replace(semifinal_unresolved_rules,
                                                        known_match_scores=scores_without_cup),
                                      trials=30, seed=42, failure_probability=0.3,
                                      conditional_on_completed_scored_races=False,
                                      feasible_slot_rule_bounds=True)
        forecast_naive = simulate_cup({}, rules=replace(semifinal_unresolved_rules,
                                                        known_match_scores=scores_without_cup),
                                      trials=30, seed=42, failure_probability=0.3,
                                      conditional_on_completed_scored_races=False,
                                      feasible_slot_rule_bounds=False)
        self.assertGreater(forecast_tight["unresolved_trials"], 0)
        self.assertIn("feasible_slot_rule_bounds", forecast_tight["bounds_kind"])
        for team in TEAM_IDS:
            tight_b = forecast_tight["rule_bounds"][team]
            naive_b = forecast_naive["rule_bounds"][team]
            self.assertLessEqual(tight_b["lower"], tight_b["upper"])
            self.assertGreaterEqual(tight_b["lower"], 0.0)
            self.assertLessEqual(tight_b["upper"], 1.0)
            self.assertLessEqual(tight_b["upper"], naive_b["upper"] + 1e-12)

        # 3. Unresolved at repechage_1 / repechage_2: verify no NameError and bounds valid
        scores_without_rep = {k: v for k, v in semifinal_unresolved_rules.known_match_scores.items()
                              if not k.startswith("repechage_") and not k.startswith("semifinal_")
                              and not k.startswith("challenger_final:") and not k.startswith("cup_match:")}
        forecast_rep = simulate_cup({}, rules=replace(semifinal_unresolved_rules,
                                                      known_match_scores=scores_without_rep),
                                    trials=20, seed=10, failure_probability=0.3,
                                    conditional_on_completed_scored_races=False,
                                    feasible_slot_rule_bounds=True)
        self.assertGreater(forecast_rep["unresolved_trials"], 0)
        for team in TEAM_IDS:
            b = forecast_rep["rule_bounds"][team]
            self.assertLessEqual(b["lower"], b["upper"])
            self.assertGreaterEqual(b["lower"], 0.0)
            self.assertLessEqual(b["upper"], 1.0)

        # 4. Round-robin tie where 6th challenger is eliminated strictly below tie
        # Build rules where challenger 1-5 have points and challenger 6 has 0
        from pipeline.prediction.cup import MatchScore
        fixed_rr_scores = {}
        # Challengers are TEAM_IDS[1:7]
        # Match matches so team 1..5 beat team 6 always, and 4 & 5 tie
        for r_num in (1, 2):
            for i in range(1, 6):
                # i beats 6
                fixed_rr_scores[f"rr:{r_num}:{TEAM_IDS[min(i, 6)]}:{TEAM_IDS[max(i, 6)]}"] = (
                    MatchScore(TEAM_IDS[min(i, 6)], TEAM_IDS[max(i, 6)],
                               1.0 if min(i, 6) == i else 0.0,
                               0.0 if min(i, 6) == i else 1.0,
                               resolved=True)
                )
        # Leave other matches unplayed so tie for 4th/5th occurs or withdrawal/unresolved
        rr_rules = CupRules(tie_policy="unresolved", round_robins=2, fleet_races=6,
                            known_match_scores=fixed_rr_scores)
        forecast_rr_tie = simulate_cup({}, rules=rr_rules, trials=20, seed=77,
                                       failure_probability=0.0,
                                       conditional_on_completed_scored_races=True,
                                       feasible_slot_rule_bounds=True)
        if forecast_rr_tie["unresolved_trials"] > 0:
            for team in TEAM_IDS:
                b = forecast_rr_tie["rule_bounds"][team]
                self.assertLessEqual(b["lower"], b["upper"])

    def test_verify_public_checks_cup_only_model_and_evidence_manifest(self):
        from pipeline.prediction.contracts import verify_public
        from pipeline.prediction.cup import public_cup_artifact

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "public" / "data" / "predictions"
            directory.mkdir(parents=True)
            (directory / "models").mkdir()
            (directory / "manifests").mkdir()
            (directory / "cup").mkdir()

            manifest = {"source": "fixture"}
            m_hash = content_hash(manifest)
            (directory / "manifests" / (m_hash + ".json")).write_text(json.dumps(manifest))

            ev_manifest = {"files": {"doc1": "hash1"}}
            ev_hash = content_hash(ev_manifest)
            (directory / "manifests" / (ev_hash + ".json")).write_text(json.dumps(ev_manifest))

            race_model = {"source_manifest_hash": m_hash, "training_before_day": "2026-05-22",
                          "strength": {"method": "fixture", "effects": {}}}
            race_model_ref = content_hash(race_model)
            (directory / "models" / (race_model_ref + ".json")).write_text(json.dumps(race_model))

            cup_model = {"source_manifest_hash": m_hash, "training_before_day": "2026-09-26",
                         "strength": {"method": "fixture", "effects": {"NZL B": 0.5}}}
            cup_model_ref = content_hash(cup_model)
            cup_model_file = directory / "models" / (cup_model_ref + ".json")
            cup_model_file.write_text(json.dumps(cup_model))

            lineage = {"model_ref": cup_model_ref, "training_before_day": "2026-09-26",
                       "training_cutoff_ms": 1790380800000, "selection_policy": "pinned",
                       "strength_method": "fixture", "source_manifest_hash": m_hash}
            effects = {"NZL B": 0.5}
            cup = public_cup_artifact(source_manifest_hash=m_hash, mapped_strength=map_ac40_to_cup(effects),
                                      trials=10, seed=42, model_lineage=lineage, mapping_provenance=cup_mapping_provenance(effects))
            cup["header"]["model_ref"] = cup_model_ref
            cup_hash = content_hash(cup)
            cup_path = "cup/" + cup_hash + ".json"
            (directory / cup_path).write_text(json.dumps(cup))

            (directory / "races").mkdir()
            scen_hash = content_hash({"scenario": "fixture"})
            boats = ["b1", "b2"]
            race_art = {
                "header": {
                    "schema_version": "prediction-1", "race_id": "r1", "boat_ids": boats,
                    "boat_class": "AC40",
                    "source_manifest_hash": m_hash, "model_ref": race_model_ref, "scenario_hash": scen_hash,
                    "status_dictionary": ["available", "estimated", "gate_ambiguous", "unavailable"],
                    "method_and_assumption_refs": ["fixture"], "units": {}
                },
                "pre_race": {
                    "status": "unavailable",
                    "expected_position_by_boat": {b: None for b in boats},
                    "nonfinish_score": "N"
                },
                "live": {
                    "published_at_ms": [], "state_timestamps_ms": [], "progress_band": [],
                    "no_finisher_prob": [], "status_code": [], "numerical_error": [], "reason_code": [],
                    "win_prob_by_boat": {b: [] for b in boats},
                    "source_age_ms_by_boat": {b: [] for b in boats},
                    "position_uncertainty_summary_by_boat": {b: [] for b in boats},
                    "quality_code_by_boat": {b: [] for b in boats}
                }
            }
            race_art_hash = content_hash(race_art)
            race_rel = f"races/r1_{race_art_hash}.json"
            (directory / race_rel).write_text(json.dumps(race_art))

            index = {
                "schema_version": "prediction-index-1",
                "source_manifest_path": f"manifests/{m_hash}.json",
                "source_manifest_hash": m_hash,
                "evidence_manifest_path": f"manifests/{ev_hash}.json",
                "evidence_manifest_hash": ev_hash,
                "races": [{
                    "race_id": "r1", "path": race_rel, "model_ref": race_model_ref,
                    "source_manifest_hash": m_hash, "scenario_hash": scen_hash
                }],
                "cup_path": cup_path
            }
            (directory / "index.json").write_text(json.dumps(index))

            # 1. Clean verification passes
            report = verify_public(root)
            self.assertEqual(report["races"], 1)

            # 2. Tampering with Cup model fails verify_public
            cup_model_file.write_text(json.dumps({"tampered": True}))
            with self.assertRaisesRegex(ValueError, "Cup-referenced model content hash mismatch"):
                verify_public(root)
            cup_model_file.write_text(json.dumps(cup_model))

            # 3. Tampering with evidence manifest fails verify_public
            ev_file = directory / "manifests" / (ev_hash + ".json")
            ev_file.write_text(json.dumps({"tampered": True}))
            with self.assertRaisesRegex(ValueError, "Evidence manifest content hash mismatch"):
                verify_public(root)

    def test_private_bundle_refits_model_when_verified_label_changes(self):
        from pipeline.prediction.build import build_private_forecast_bundle, publish_forecast_bundle

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "public" / "data" / "predictions"
            directory.mkdir(parents=True)
            (directory / "models").mkdir()
            (directory / "manifests").mkdir()
            (directory / "cup").mkdir()

            manifest = {"source": "fixture"}
            m_hash = content_hash(manifest)
            (directory / "manifests" / (m_hash + ".json")).write_text(json.dumps(manifest))

            model = {"source_manifest_hash": m_hash, "training_before_day": "2026-09-26",
                     "strength": {"method": "fixture", "effects": {"NZL B": 0.2}}}
            model_ref = content_hash(model)
            (directory / "models" / (model_ref + ".json")).write_text(json.dumps(model))

            lineage = {"model_ref": model_ref, "training_before_day": "2026-09-26",
                       "training_cutoff_ms": 1790380800000, "selection_policy": "pinned",
                       "strength_method": "fixture", "source_manifest_hash": m_hash}
            cup = public_cup_artifact(source_manifest_hash=m_hash, mapped_strength={"ETNZ": 0.2},
                                      trials=10, seed=42, model_lineage=lineage, mapping_provenance={"teams": []})
            cup["header"]["model_ref"] = model_ref
            cup_path = "cup/" + content_hash(cup) + ".json"
            (directory / cup_path).write_text(json.dumps(cup))

            (directory / "races").mkdir()
            scen_hash = content_hash({"scenario": "fixture"})
            boats = ["b1", "b2"]
            race_art = {
                "header": {
                    "schema_version": "prediction-1", "race_id": "r1", "boat_ids": boats,
                    "boat_class": "AC40",
                    "source_manifest_hash": m_hash, "model_ref": model_ref, "scenario_hash": scen_hash,
                    "status_dictionary": ["available", "estimated", "gate_ambiguous", "unavailable"],
                    "method_and_assumption_refs": ["fixture"], "units": {}
                },
                "pre_race": {
                    "status": "unavailable",
                    "expected_position_by_boat": {b: None for b in boats},
                    "nonfinish_score": "N"
                },
                "live": {
                    "published_at_ms": [], "state_timestamps_ms": [], "progress_band": [],
                    "no_finisher_prob": [], "status_code": [], "numerical_error": [], "reason_code": [],
                    "win_prob_by_boat": {b: [] for b in boats},
                    "source_age_ms_by_boat": {b: [] for b in boats},
                    "position_uncertainty_summary_by_boat": {b: [] for b in boats},
                    "quality_code_by_boat": {b: [] for b in boats}
                }
            }
            race_rel = f"races/r1_{content_hash(race_art)}.json"
            (directory / race_rel).write_text(json.dumps(race_art))

            index = {
                "schema_version": "prediction-index-1",
                "source_manifest_path": f"manifests/{m_hash}.json",
                "source_manifest_hash": m_hash,
                "races": [{
                    "race_id": "r1", "path": race_rel, "model_ref": model_ref,
                    "source_manifest_hash": m_hash, "scenario_hash": scen_hash
                }],
                "cup_path": cup_path
            }
            (directory / "index.json").write_text(json.dumps(index))

            bundle_res = build_private_forecast_bundle(root, trials=10, seed=42, use_official_results=False)
            self.assertFalse(Path(bundle_res["bundle_dir"]).is_relative_to(directory))
            self.assertEqual(bundle_res["candidate_model_ref"], model_ref)
            self.assertTrue((Path(bundle_res["bundle_dir"]) / "bundle.json").is_file())

            pub_res = publish_forecast_bundle(root, Path(bundle_res["bundle_dir"]))
            self.assertEqual(pub_res["verification"], "passed")
            updated_index = json.loads((directory / "index.json").read_text())
            self.assertIn("evidence_manifest_hash", updated_index)

            # Test cutoff guard in select_training_order_rows
            from pipeline.prediction.labels import select_training_order_rows
            labels_sample = [{
                "race_id": "r1", "date": "2026-05-22", "order": ["A", "B"],
                "on_water_result": {"order": ["A", "B"], "available_at_ms": 1000},
                "official_result": {"order": ["B", "A"], "available_at_ms": 5000}
            }]
            pre_cutoff = select_training_order_rows(labels_sample, target="official", cutoff_ms=4000)
            self.assertEqual(pre_cutoff[0]["order"], ["A", "B"])
            self.assertEqual(pre_cutoff[0]["training_target"], "on_water_fallback")

            post_cutoff = select_training_order_rows(labels_sample, target="official", cutoff_ms=6000)
            self.assertEqual(post_cutoff[0]["order"], ["B", "A"])
            self.assertEqual(post_cutoff[0]["training_target"], "official")

    def test_market_odds_evaluation(self):
        from pipeline.prediction.evaluation import implied_probabilities, compare_market_to_forecast

        # 1. Invalid odd <= 1.0 or non-finite
        with self.assertRaises(ValueError):
            implied_probabilities({"ETNZ": 0.8, "GB1": 2.5})
        with self.assertRaises(ValueError):
            implied_probabilities({"ETNZ": float("inf"), "GB1": 2.5})

        # 2. Valid de-vigging
        devig = implied_probabilities({"A": 2.0, "B": 2.0})
        self.assertAlmostEqual(devig["overround"], 0.0)
        self.assertAlmostEqual(devig["probabilities"]["A"], 0.5)
        self.assertAlmostEqual(devig["probabilities"]["B"], 0.5)

        # 3. Causal timestamp guard
        post_snap = {"captured_at_ms": 2000, "market": "ac38_winner", "selections": {}}
        res_post = compare_market_to_forecast(post_snap, {}, forecast_issue_time_ms=1000)
        self.assertEqual(res_post["status"], "post_issue_time_excluded")

        # 4. Incomplete book guard for ac38_winner
        incomplete_snap = {
            "captured_at_ms": 500, "market": "ac38_winner",
            "selections": {"ETNZ": 1.8, "GB1": 3.0}
        }
        res_inc = compare_market_to_forecast(incomplete_snap, {}, forecast_issue_time_ms=1000)
        self.assertEqual(res_inc["status"], "incomplete_book_excluded")

        # 5. Complete book validation
        complete_odds = {
            "ETNZ": 2.0, "GB1": 6.0, "LUNA_ROSSA": 4.0, "ALINGHI": 12.0,
            "LA_ROCHE_POSAY": 15.0, "ARC_USA": 15.0, "AUSTRALIA": 20.0
        }
        complete_snap = {
            "captured_at_ms": 500, "market": "ac38_winner",
            "selections": complete_odds
        }
        dummy_forecast = {"probabilities": {t: 1.0 / 7.0 for t in complete_odds}}
        res_valid = compare_market_to_forecast(complete_snap, dummy_forecast, forecast_issue_time_ms=1000)
        self.assertEqual(res_valid["status"], "valid")
        self.assertIn("market_probabilities", res_valid)
        self.assertIn("forecast_differences", res_valid)

    def test_exposure_hazard_probability(self):
        from pipeline.prediction.cup import exposure_hazard_probability

        self.assertEqual(exposure_hazard_probability(0.0), 0.0)
        p1 = exposure_hazard_probability(0.1, duration_hours=0.2)
        p2 = exposure_hazard_probability(0.1, duration_hours=0.5)
        self.assertGreater(p2, p1)
        self.assertGreater(p1, 0.0)

        with self.assertRaises(ValueError):
            exposure_hazard_probability(-0.1)

    def test_daily_drift_sd(self):
        from pipeline.prediction.cup import CupScenario, simulate_cup

        with self.assertRaises(ValueError):
            CupScenario(daily_drift_sd=-0.1).validate()
        with self.assertRaises(ValueError):
            CupScenario(daily_drift_sd=0.6).validate()

        scen = CupScenario(daily_drift_sd=0.05)
        scen.validate()
        self.assertIn("drift", scen.scenario_id)

        sim = simulate_cup({"ETNZ": 0.2, "GB1": 0.1}, scenario=scen, trials=100, seed=42)
        self.assertEqual(sim["trials"], 100)
        self.assertIn("ETNZ", sim["probabilities"])

    def test_direct_ac75_distribution(self):
        import numpy as np
        from pipeline.prediction.cup import simulate_cup, update_cup_from_2027_results, TEAM_IDS

        # 1. Invalid covariance shape or team order
        with self.assertRaises(ValueError):
            simulate_cup({}, direct_ac75_distribution={"team_order": ["ETNZ"], "covariance": [[1.0]], "mean": {}})

        # 2. Valid direct AC75 distribution
        cov = np.eye(7) * 0.25
        mean = {t: 0.1 * i for i, t in enumerate(TEAM_IDS)}
        dist = {"team_order": list(TEAM_IDS), "covariance": cov.tolist(), "mean": mean}
        sim = simulate_cup({}, direct_ac75_distribution=dist, trials=100, seed=42)
        self.assertEqual(sim["diagnostics"]["capability_source"], "direct_ac75_posterior")

        # 3. Update from 2027 results
        orders = [
            ["ETNZ", "GB1", "LUNA_ROSSA"],
            ["GB1", "ALINGHI", "LA_ROCHE_POSAY"]
        ]
        updated = update_cup_from_2027_results(mean, cov, orders)
        self.assertEqual(updated["team_order"], list(TEAM_IDS))
        self.assertIn("ETNZ", updated["mean"])
        self.assertEqual(len(updated["covariance"]), 7)

    def test_cup_bounds_never_exclude_sixth_seed_repechage_champion_seed_521(self):
        """Audit Finding 2: conservative bounds must never exclude 6th seed repechage champion."""
        res = simulate_cup({t: 0.0 for t in TEAM_IDS}, trials=1, seed=521, feasible_slot_rule_bounds=True)
        self.assertEqual(res["rule_bounds"]["LA_ROCHE_POSAY"]["upper"], 1.0)

        # Bounds must be conservative across seeds 500..530: lower <= upper
        for s in range(500, 530):
            r = simulate_cup({t: 0.0 for t in TEAM_IDS}, trials=1, seed=s, feasible_slot_rule_bounds=True)
            for team in TEAM_IDS:
                lower = r["rule_bounds"][team]["lower"]
                upper = r["rule_bounds"][team]["upper"]
                self.assertLessEqual(lower, upper)
                self.assertGreaterEqual(lower, 0.0)
                self.assertLessEqual(upper, 1.0)



if __name__ == "__main__":
    unittest.main()
