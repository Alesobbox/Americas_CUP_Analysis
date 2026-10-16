"""Hand-checkable coherence and generative-boundary tests for forecasting."""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from pipeline.prediction.models import (CompletionModel, ConditionalLogitModel,
                                           EmpiricalOrderModel, LegTimeModel,
                                           PositiveDelayMixture, StrengthModel,
                                           UniformOrderModel)
    from pipeline.prediction.simulation import (conditional_failure_probability,
                                                hazard_integral, simulate_order_reference,
                                                simulate_race)


@unittest.skipIf(np is None, "Install the locked forecast-core extra to run forecasting tests")
class PredictionModelTests(unittest.TestCase):
    def fixture_model(self, **overrides):
        values = dict(coefficients=[math.log(100), 1.0, -0.2], distance_reference_m=1000,
                      wind_reference_knots=12, residual_sigma=0.2,
                      crew_form_sigma=0.10, race_sigma=0.08, weather_sigma=0.08,
                      innovation_sigma=math.sqrt(0.2 ** 2 - 0.10 ** 2 - 2 * 0.08 ** 2),
                      n_rows=100, n_races=10)
        values.update(overrides)
        return LegTimeModel(**values)

    def legs(self):
        return [{"distance_m": 1000, "leg_kind": "upwind"},
                {"distance_m": 1000, "leg_kind": "downwind"}]

    def test_regularized_strength_responds_to_orders_and_ignores_practice(self):
        rows = [{"order": ["A", "B", "C"]} for _ in range(8)]
        model = StrengthModel.fit(rows)
        other = StrengthModel.fit(rows + [{"order": ["C", "B", "A"], "practice": True}] * 500)
        probabilities = model.predict_win_probabilities(["A", "B", "C"])
        self.assertGreater(probabilities["A"], probabilities["B"])
        self.assertGreater(probabilities["B"], probabilities["C"])
        self.assertAlmostEqual(sum(probabilities.values()), 1.0)
        self.assertEqual(model.to_dict(), other.to_dict())
        self.assertEqual(StrengthModel.from_dict(model.to_dict()).to_dict(), model.to_dict())

    def test_pl_sampler_matches_analytic_first_place(self):
        model = StrengthModel(effects={"A": math.log(3), "B": 0.0})
        orders = model.sample_orders(["A", "B"], 40_000, seed=74)
        self.assertAlmostEqual(float(np.mean(orders[:, 0] == 0)), 0.75, delta=0.01)

    def test_joint_order_reference_agrees_with_PL_and_retains_completion_mass(self):
        strength = StrengthModel(effects={"A": math.log(3), "B": 0.})
        result = simulate_order_reference(strength, ["A", "B"], None,
                                          conditional_complete=True, n=30_000, seed=55)
        self.assertAlmostEqual(result.win_prob_by_boat["A"], .75, delta=.015)
        self.assertAlmostEqual(result.expected_position_by_boat["A"], 2-result.win_prob_by_boat["A"], places=10)
        self.assertIsNone(result.finish_times_s)
        records = [{"audited": True, "started": True, "completed": True}] * 2
        records += [{"audited": True, "started": True, "completed": False, "failure_type": "exogenous"}] * 3
        failed = simulate_order_reference(strength, ["A", "B"], CompletionModel.fit(records), n=10_000, seed=6)
        self.assertGreater(failed.no_finisher_prob, .1)
        self.assertAlmostEqual(sum(failed.win_prob_by_boat.values()) + failed.no_finisher_prob, 1.)

    def test_joint_order_reference_live_exposure_requires_course_and_resolves_terminals(self):
        state = {"A": {"current_leg": 1, "remaining_fraction": .1, "started": True},
                 "B": {"current_leg": 0, "remaining_fraction": .9, "started": True}}
        missing = simulate_order_reference(StrengthModel(), ["A", "B"], None, state=state,
                                           conditional_complete=True, n=100)
        self.assertFalse(missing.available)
        result = simulate_order_reference(StrengthModel(), ["A", "B"], None, state=state,
                                          total_legs=2, conditional_complete=True, n=5000)
        self.assertGreater(result.win_prob_by_boat["A"], .55)
        state = {"A": {"terminal_status": "finished", "finished_at_s": 100},
                 "B": {"terminal_status": "ret"}}
        terminal = simulate_order_reference(StrengthModel(), ["A", "B"], None, state=state,
                                            global_finish_order_resolved=True, n=50)
        self.assertEqual(terminal.win_prob_by_boat, {"A": 1., "B": 0.})

    def test_completion_requires_audits_and_does_not_guess_dnf(self):
        model = CompletionModel.fit([
            {"audited": False, "started": True, "completed": False, "failure_type": "exogenous"},
            {"audited": True, "started": True, "completed": False, "failure_type": "unknown"},
            {"audited": True, "started": True, "completed": True, "practice": True},
        ])
        self.assertFalse(model.available)
        self.assertEqual(model.scheduled_audited, 1)
        self.assertEqual(model.starters_ascertained, 0)
        self.assertIsNone(model.failure_mean)
        records = [{"audited": True, "started": True, "completed": True}] * 3
        records += [{"audited": True, "started": False},
                    {"audited": True, "started": True, "completed": False, "failure_type": "exogenous"}]
        model = CompletionModel.fit(records)
        self.assertTrue(model.available)
        self.assertEqual((model.dns_events, model.scheduled_audited), (1, 5))
        self.assertEqual((model.failure_events, model.starters_ascertained), (1, 4))
        self.assertAlmostEqual(model.failure_mean, 1.5 / 5)

    def test_partially_ascertained_audited_cohort_cannot_supply_failure_denominator(self):
        records = [{"audited": True, "started": True, "completed": True}] * 20
        records += [{"audited": True, "started": True, "completed": False, "failure_type": "time_rule"}]
        model = CompletionModel.fit(records)
        self.assertFalse(model.available)
        self.assertIn("censoring", model.reason)

    def test_empirical_reference_inserts_new_entries_without_assigning_them_losses(self):
        model = EmpiricalOrderModel.fit([{"order": ["A", "B"]}])
        field = ["A", "B", "C"]
        self.assertEqual(model.predict_win_probabilities(field), {"A": 2 / 3, "B": 0., "C": 1 / 3})
        expected = model.expected_positions(field)
        self.assertAlmostEqual(expected["A"], 4 / 3)
        self.assertAlmostEqual(expected["B"], 8 / 3)
        self.assertAlmostEqual(sum(expected.values()), 6)
        sampled = model.sample_orders(field, 30_000, seed=32)
        self.assertTrue(np.all(np.argmax(sampled == 0, axis=1) < np.argmax(sampled == 1, axis=1)))
        self.assertAlmostEqual(float(np.mean(sampled[:, 0] == 2)), 1 / 3, delta=.01)
        self.assertEqual(UniformOrderModel().predict_win_probabilities(field), dict.fromkeys(field, 1 / 3))

    def test_conditional_logit_learns_current_progress_and_limits_repeated_race_weight(self):
        rows = []
        for race in range(20):
            winner, loser = ("A", "B") if race % 2 else ("B", "A")
            rows.append({"race_id": str(race), "order": [winner, loser], "state_features": {
                winner: {"lead_fraction": .2, "remaining_fraction": .5},
                loser: {"lead_fraction": -.2, "remaining_fraction": .5}}})
        fitted = ConditionalLogitModel.fit(rows)
        duplicated = ConditionalLogitModel.fit(rows + rows)
        np.testing.assert_allclose(fitted.state_coefficients, duplicated.state_coefficients, atol=1e-8)
        result = fitted.predict_win_probabilities(["A", "B"], {
            "A": {"lead_fraction": .2, "remaining_fraction": .5},
            "B": {"lead_fraction": -.2, "remaining_fraction": .5}})
        self.assertGreater(result["A"], .5)
        self.assertAlmostEqual(sum(result.values()), 1.)

    def test_unconditional_denominator_gate_and_missing_opponent(self):
        result = simulate_race(self.fixture_model(), ["A", "B"], self.legs(), CompletionModel(), n=100)
        self.assertFalse(result.available)
        self.assertIsNone(result.win_prob_by_boat["A"])
        result = simulate_race(self.fixture_model(), ["A", "B"], self.legs(), None,
                               conditional_complete=True, state={"A": {}}, n=100)
        self.assertFalse(result.available)
        self.assertIn("contender", result.reason)

    def test_joint_mass_expected_rank_and_finite_tail(self):
        model = self.fixture_model(crew_effects={"A": -5.0, "B": 5.0})
        result = simulate_race(model, ["A", "B"], self.legs(), None,
                               conditional_complete=True, n=1000, seed=8)
        self.assertAlmostEqual(sum(result.win_prob_by_boat.values()) + result.no_finisher_prob, 1.0)
        self.assertGreater(result.win_prob_by_boat["B"], 0)
        self.assertAlmostEqual(result.win_prob_by_boat["B"], 0.00005)
        self.assertAlmostEqual(sum(result.expected_positions.values()), 3.0)
        self.assertEqual(result.no_finisher_prob, 0.0)

    def test_equal_strength_and_label_swap(self):
        model = self.fixture_model()
        first = simulate_race(model, ["A", "B", "C"], self.legs(), None,
                              conditional_complete=True, n=20_000, seed=91)
        swapped = simulate_race(model, ["C", "B", "A"], self.legs(), None,
                                conditional_complete=True, n=20_000, seed=91)
        for boat in ["A", "B", "C"]:
            self.assertAlmostEqual(first.win_prob_by_boat[boat], 1 / 3, delta=0.015)
        self.assertEqual(first.win_prob_by_boat["A"], swapped.win_prob_by_boat["C"])
        self.assertEqual(first.win_prob_by_boat["C"], swapped.win_prob_by_boat["A"])

    def test_no_information_gate_boundary_is_identical_distribution(self):
        model = self.fixture_model()
        full = simulate_race(model, ["A", "B"], self.legs(), None,
                             conditional_complete=True, n=1500, seed=731)
        state = {b: {"current_leg": 0, "remaining_fraction": 1.0,
                     "elapsed_s": 0, "started": True} for b in ["A", "B"]}
        remaining = simulate_race(model, ["A", "B"], self.legs(), None, state=state,
                                  conditional_complete=True, n=1500, seed=731)
        np.testing.assert_array_equal(full.finish_times_s, remaining.finish_times_s)
        self.assertEqual(full.win_prob_by_boat, remaining.win_prob_by_boat)

    def test_causal_progress_and_measured_pace_change_continuation(self):
        model = self.fixture_model(crew_form_sigma=0.18, innovation_sigma=0.04)
        state = {b: {"current_leg": 0, "remaining_fraction": 1.0, "elapsed_s": 20,
                     "started": True} for b in ["A", "B"]}
        baseline = simulate_race(model, ["A", "B"], self.legs(), None, state=state,
                                 conditional_complete=True, n=5000, seed=11)
        state["A"].update(remaining_fraction=0.5, pace_ratio=1.5)
        ahead = simulate_race(model, ["A", "B"], self.legs(), None, state=state,
                              conditional_complete=True, n=5000, seed=11)
        self.assertGreater(ahead.win_prob_by_boat["A"], baseline.win_prob_by_boat["A"] + 0.2)
        self.assertTrue(np.all(ahead.gate_times_s[:, 0, 0] < baseline.gate_times_s[:, 0, 0]))

    def test_terminal_determinism_and_no_finisher_tied_N(self):
        state = {"A": {"terminal_status": "finished", "finished_at_s": 100},
                 "B": {"terminal_status": "dnf"}, "C": {"terminal_status": "ret"}}
        result = simulate_race(LegTimeModel(), ["A", "B", "C"], self.legs(), None,
                               state=state, global_finish_order_resolved=True, n=50)
        self.assertTrue(result.available)
        self.assertEqual(result.win_prob_by_boat, {"A": 1.0, "B": 0.0, "C": 0.0})
        self.assertEqual(result.expected_positions, {"A": 1.0, "B": 3.0, "C": 3.0})
        for s in state.values():
            s["terminal_status"] = "dnf"
        result = simulate_race(LegTimeModel(), ["A", "B", "C"], self.legs(), None, state=state, n=50)
        self.assertEqual(result.no_finisher_prob, 1.0)
        self.assertEqual(result.expected_positions, {"A": 3.0, "B": 3.0, "C": 3.0})

    def test_first_received_finish_does_not_manufacture_terminal_winner(self):
        state = {"A": {"terminal_status": "finished", "finished_at_s": 100}, "B": {"elapsed_s": 101}}
        result = simulate_race(self.fixture_model(), ["A", "B"], self.legs(), None,
                               state=state, conditional_complete=True, n=20)
        self.assertFalse(result.available)
        self.assertIn("globally resolved", result.reason)

    def test_hazard_shapes_preserve_full_race_risk_and_condition_survival(self):
        for shape in ["constant", "transition"]:
            self.assertAlmostEqual(float(hazard_integral(1, 6, shape)), 1.0)
            self.assertAlmostEqual(float(conditional_failure_probability(0.2, 0, 6, shape)), 0.2)
            self.assertEqual(float(conditional_failure_probability(0.2, 1, 6, shape)), 0.0)
            self.assertLess(float(conditional_failure_probability(0.2, 0.5, 6, shape)), 0.2)
        self.assertAlmostEqual(float(conditional_failure_probability(0.2, 0.5, 6)), 1 - math.sqrt(0.8))

    def test_failure_and_dns_mass_not_renormalized_away(self):
        records = [{"audited": True, "started": True, "completed": True}] * 4
        records += [{"audited": True, "started": True, "completed": False, "failure_type": "exogenous"}] * 4
        records += [{"audited": True, "started": False}] * 4
        result = simulate_race(self.fixture_model(), ["A", "B"], self.legs(),
                               CompletionModel.fit(records), n=20_000, seed=42)
        self.assertGreater(result.no_finisher_prob, 0.1)
        self.assertAlmostEqual(sum(result.win_prob_by_boat.values()) + result.no_finisher_prob, 1.0, places=10)
        self.assertGreater(sum(result.expected_positions.values()), 3)
        # Failures occupy a sampled future exposure, rather than every retiring
        # boat being removed from competitive presence at the gun.
        failed = result.failure_course_fractions[np.isfinite(result.failure_course_fractions)]
        self.assertTrue(np.any((failed > 0) & (failed < 1)))

    def test_shared_factors_produce_correlated_gate_times(self):
        correlated = self.fixture_model(crew_form_sigma=0, race_sigma=0.2, weather_sigma=0, innovation_sigma=0.01)
        independent = self.fixture_model(crew_form_sigma=0, race_sigma=0, weather_sigma=0, innovation_sigma=0.2)
        joint = simulate_race(correlated, ["A", "B"], self.legs(), None,
                              conditional_complete=True, n=4000, seed=5)
        separate = simulate_race(independent, ["A", "B"], self.legs(), None,
                                 conditional_complete=True, n=4000, seed=5)
        self.assertGreater(np.corrcoef(np.log(joint.finish_times_s).T)[0, 1], 0.9)
        self.assertLess(abs(np.corrcoef(np.log(separate.finish_times_s).T)[0, 1]), 0.1)

    def test_reproducibility_and_legal_gate_order(self):
        first = simulate_race(self.fixture_model(), ["A", "B"], self.legs(), None,
                              conditional_complete=True, n=1000, seed=6)
        second = simulate_race(self.fixture_model(), ["A", "B"], self.legs(), None,
                               conditional_complete=True, n=1000, seed=6)
        self.assertEqual(first.to_dict(), second.to_dict())
        np.testing.assert_array_equal(first.ranks, second.ranks)
        self.assertTrue(np.all(np.diff(first.gate_times_s, axis=2) > 0))

    def test_empirical_time_fit_uses_valid_legs_of_later_retiree(self):
        rows = []
        for race in range(5):
            for boat, pace in [("A", 0.85), ("B", 1.15)]:
                for leg in range(3):
                    rows.append({"boat_id": boat, "race_id": str(race), "leg_index": leg,
                                 "leg_kind": "upwind", "duration_s": 100 * pace * (1 + 0.01 * race),
                                 "distance_m": 1000, "wind_knots": 12,
                                 "final_status": "RET" if boat == "A" else "finished"})
        model = LegTimeModel.fit(rows)
        self.assertTrue(model.available)
        self.assertEqual(model.n_rows, 30)
        self.assertLess(model.median_seconds("A", self.legs()[0]), model.median_seconds("B", self.legs()[0]))
        self.assertFalse(model.mixture_enabled)
        self.assertIn("absent", model.mixture_reason)
        self.assertEqual(LegTimeModel.from_dict(model.to_dict()).to_dict(), model.to_dict())

    def test_positive_delay_candidate_needs_reviewed_labels_and_refits_clean_distribution(self):
        missing = PositiveDelayMixture.fit([{"boat_id": "A", "duration_s": 100,
                                            "distance_m": 1000, "date": "2026-01-01"}] * 80)
        self.assertFalse(missing.available)
        rng = np.random.default_rng(17)
        rows = []
        for i in range(400):
            loss = bool(rng.random() < .3)
            duration = 100 * math.exp(rng.normal(0, .05)) + (float(rng.gamma(3., 12.)) if loss else 0.)
            rows.append({"boat_id": "A" if i % 2 else "B", "race_id": str(i//8),
                         "date": f"2026-01-0{i%4+1}", "leg_kind": "upwind", "leg_index": i%4,
                         "distance_m": 1000, "duration_s": duration,
                         "loss_reviewed": True, "loss_episode": loss})
        baseline = LegTimeModel.fit(rows)
        candidate = PositiveDelayMixture.fit(rows, baseline=baseline)
        self.assertTrue(candidate.available)
        self.assertFalse(candidate.promoted)
        self.assertAlmostEqual(candidate.episode_probability, .3, delta=.05)
        self.assertAlmostEqual(candidate.delay_shape * candidate.delay_scale_seconds, 36., delta=10.)
        clean_model = LegTimeModel.from_dict(candidate.clean_model_payload)
        clean_median = clean_model.median_seconds("A", self.legs()[0])
        self.assertLess(clean_median, baseline.median_seconds("A", self.legs()[0]))
        self.assertAlmostEqual(clean_median, 100., delta=5.)
        samples = candidate.sample_leg_seconds(clean_median, 40_000, np.random.default_rng(5))
        expected = clean_median * math.exp(candidate.clean_sigma**2/2) + candidate.episode_probability*candidate.delay_shape*candidate.delay_scale_seconds
        self.assertAlmostEqual(float(np.mean(samples)), expected, delta=1.)

    def test_timerules_are_not_extra_random_failures(self):
        deterministic = self.fixture_model(crew_form_sigma=0, race_sigma=0, weather_sigma=0,
                                           innovation_sigma=0)
        result = simulate_race(deterministic, ["A", "B"], self.legs(), None,
                               conditional_complete=True, n=100, race_time_limit_s=150)
        self.assertEqual(result.no_finisher_prob, 1.0)
        self.assertEqual(result.expected_positions, {"A": 2.0, "B": 2.0})


if __name__ == "__main__":
    unittest.main()
