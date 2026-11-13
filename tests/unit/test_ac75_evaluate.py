"""Unit tests for AC75 evaluation metrics, analytical fixtures, and model selection (T15)."""
import math
import unittest

import numpy as np

from pipeline.kinematic_ml.calibration import ChronologicalInnerSplit
from pipeline.kinematic_ml.evaluate_ac75 import (
    _build_race_target_record,
    _validate_race_pre_context,
    brier_score,
    fit_and_calibrate_predictor_suite,
    log_loss,
    normal_crps,
    select_best_candidate,
)
from pipeline.kinematic_ml.evidence.policy import EvidencePolicy
from pipeline.kinematic_ml.evidence.qualifier import qualify_evaluation_targets
from pipeline.kinematic_ml.routes import LegRouteTemplate, RouteSegment
from pipeline.kinematic_ml.selection import select_default_model_from_races


class TestAC75Evaluation(unittest.TestCase):
    def test_analytical_crps_fixture(self):
        """Verify normal_crps matches the analytical Gaussian formula."""
        # For y = mu = 0, sigma = 1:
        # Analytical CRPS = (sqrt(2) - 1) / sqrt(pi) ~= 0.2336946
        expected = (math.sqrt(2.0) - 1.0) / math.sqrt(math.pi)
        computed = normal_crps(0.0, 0.0, 1.0)
        self.assertAlmostEqual(computed, expected, places=5)

        # For zero error and zero variance: CRPS = 0
        self.assertEqual(normal_crps(10.0, 10.0, 0.0), 0.0)

    def test_brier_and_log_loss_fixtures(self):
        """Verify binary scoring metrics against hand-calculated values."""
        # Perfect prediction: y=1, p=1.0 -> Brier=0, LogLoss~0
        self.assertEqual(brier_score(1, 1.0), 0.0)
        self.assertAlmostEqual(log_loss(1, 1.0), 0.0, delta=1e-4)

        # Total miss: y=1, p=0.0 -> Brier=1, LogLoss=-ln(1e-6)
        self.assertEqual(brier_score(1, 0.0), 1.0)
        self.assertAlmostEqual(log_loss(1, 0.0), -math.log(1e-6), places=3)

        # Fair coin: y=1, p=0.5 -> Brier=0.25, LogLoss=ln(2) ~= 0.69315
        self.assertEqual(brier_score(1, 0.5), 0.25)
        self.assertAlmostEqual(log_loss(1, 0.5), math.log(2.0), places=4)

    def test_candidate_selection_rule(self):
        """Verify that simplest candidate within 1 SE of minimum CRPS is selected."""
        scores = {
            "neural_network_silu": {"crps": 1.20, "complexity_order": 3},
            "regularized_spline_polar": {"crps": 1.23, "complexity_order": 2},
            "empirical_binned_polar": {"crps": 1.35, "complexity_order": 1},
        }
        # Spline is within 0.05 of Neural (1.23 <= 1.20 + 0.05), but Spline is simpler (2 < 3)
        selected, rationale = select_best_candidate(scores)
        self.assertEqual(selected, "regularized_spline_polar")
        self.assertIn("Selected 'regularized_spline_polar'", rationale)

    def test_evidence_policy_rejects_candidate_outcomes_and_falls_back_to_empirical(self):
        """Verify candidate_* unverified ledger rows are excluded and force empirical fallback."""
        policy = EvidencePolicy(allow_candidate_in_primary=False)
        dates = [f"2024-09-{d:02d}" for d in range(10, 17)]
        records = []
        race_crps = {"empirical_binned_polar": {}, "regularized_spline_polar": {}, "neural_network_silu": {}}
        race_dates = {}
        for idx, d_str in enumerate(dates):
            fid = f"ac37_test_r{idx}"
            out_row = {
                "race_id": fid,
                "team_a": "ac37:ETNZ",
                "team_b": "ac37:INEOS",
                "finish_status": {"value": "Completed", "verified": False, "provenance": "candidate_results"},
                "winner": {"value": "ac37:ETNZ", "verified": False, "provenance": "candidate_results"},
                "delta_s": {"value": 15.0 + idx, "verified": False, "provenance": "candidate_results"},
            }
            rec, _ = _build_race_target_record(fid, d_str, out_row)
            records.append(rec)
            race_dates[fid] = d_str
            race_crps["empirical_binned_polar"][fid] = 12.0
            race_crps["regularized_spline_polar"][fid] = 8.0
            race_crps["neural_network_silu"][fid] = 7.5

        qual = qualify_evaluation_targets(records, policy)
        self.assertEqual(qual.qualified_count, 0)
        self.assertEqual(sum(qual.rejection_reasons.values()), len(dates))
        self.assertEqual(qual.status, "insufficient_qualified_race_targets")

        decision = select_default_model_from_races(
            race_crps,
            race_dates,
            qualified_race_ids={t["race_id"] for t in qual.qualified_targets},
        )
        self.assertTrue(decision.is_fallback)
        self.assertEqual(decision.fallback_reason, "insufficient_qualified_race_targets")
        self.assertEqual(decision.selected_model_id, "empirical_binned_polar")

    def test_validate_race_pre_context_rejects_whole_race_average_and_missing_defaults(self):
        """Verify pre-race context rejects hindsight averages, invented defaults, and missing geometry."""
        policy = EvidencePolicy()
        valid_rc = {
            "course_context_status": "available",
            "prestart_context_status": "available",
            "prestart_tws_mps": 8.4,
            "prestart_twd_deg": 205.0,
            "prestart_available_at_ms": 1_000_000,
            "race_gun_ms": 1_006_000,
            "prestart_is_whole_race_average": False,
            "prestart_is_invented_default": False,
            "course_axis_deg": 200.0,
            "leg_length_m": 1600.0,
            "leg_count": 4,
        }
        ok, reason, parsed = _validate_race_pre_context(valid_rc, policy)
        self.assertTrue(ok)
        self.assertEqual(reason, "valid")
        self.assertAlmostEqual(parsed["tws_mps"], 8.4)
        self.assertAlmostEqual(parsed["twd_deg"], 205.0)

        for bad_patch in (
            {"prestart_is_whole_race_average": True},
            {"prestart_is_invented_default": True},
            {"prestart_available_at_ms": 1_013_000},
            {"prestart_context_status": "unavailable", "prestart_unavailable_reason": "missing_prestart_wind"},
            {"prestart_tws_mps": None},
            {"prestart_twd_deg": None},
            {"course_axis_deg": None},
            {"leg_length_m": None},
        ):
            bad_rc = dict(valid_rc, **bad_patch)
            ok_bad, _, parsed_bad = _validate_race_pre_context(bad_rc, policy)
            self.assertFalse(ok_bad, f"Should have rejected {bad_patch}")
            self.assertEqual(parsed_bad, {})

    def test_fit_and_calibrate_predictor_suite_isolates_predictors(self):
        """Verify each predictor gets independent chronological calibration and residual samplers."""
        train_dates = ["2024-08-22", "2024-08-23", "2024-08-24", "2024-08-25"]
        inner_split = ChronologicalInnerSplit.from_outer_dates(train_dates, ["2024-08-26"])

        rows = []
        mans = []
        starts = []
        for d_idx, d_str in enumerate(train_dates):
            att_id = f"att_{d_idx}"
            base_ts = 1_724_000_000_000 + d_idx * 10_000_000
            for block_idx in range(18):
                tws = 7.0 + (block_idx % 4) * 1.5 + d_idx * 0.2
                leg_t = 1 if (block_idx // 6) % 2 == 0 else 0
                t_start = base_ts + block_idx * 5000
                for team, team_bonus in (("ac37:ETNZ", 0.6), ("ac37:INEOS", -0.4)):
                    sog = 11.0 + 1.15 * tws + (1.2 if leg_t == 0 else -0.8) + team_bonus
                    rows.append({
                        "attempt_id": att_id,
                        "family_id": att_id,
                        "date_str": d_str,
                        "team_id": team,
                        "t_start_ms": t_start,
                        "t_end_ms": t_start + 5000,
                        "duration_s": 5.0,
                        "tws_mps": tws,
                        "twd_deg": 195.0,
                        "twa_sin": 0.7 if leg_t == 1 else 0.5,
                        "twa_cos": 0.714 if leg_t == 1 else -0.866,
                        "tack_side": 1,
                        "leg_type": leg_t,
                        "heading_cog_offset_deg": 2.5,
                        "course_wind_angle_deg": 42.0 if leg_t == 1 else 138.0,
                        "practice_domain": 0,
                        "sog_mps": sog,
                    })
                mans.append({
                    "attempt_id": att_id,
                    "family_id": att_id,
                    "date_str": d_str,
                    "team_id": "ac37:ETNZ",
                    "t_start_ms": base_ts + block_idx * 30_000,
                    "turn_type": "tack" if block_idx % 2 == 0 else "gybe",
                    "rotation_deg": 75.0,
                    "tws_mps": 9.0,
                    "twa_sin": 0.7,
                    "twa_cos": 0.71,
                    "tack_side": 1,
                    "leg_type": 1,
                    "heading_cog_offset_deg": 2.5,
                    "course_wind_angle_deg": 42.0,
                    "practice_domain": 0,
                    "duration_s": 8.0 if block_idx % 2 == 0 else 6.0,
                    "recovery_s": 5.0,
                    "censoring": False,
                })
            for team in ("ac37:ETNZ", "ac37:INEOS"):
                starts.append({
                    "attempt_id": att_id,
                    "family_id": att_id,
                    "date_str": d_str,
                    "team_id": team,
                    "gun_to_steady_s": 14.0 if team == "ac37:ETNZ" else 16.0,
                    "tws_mps": 9.5,
                })

        segs = [
            RouteSegment("straight", (0.0, 0.0), (100.0, 750.0), 756.6, 12.0, 9.0),
            RouteSegment("maneuver", (100.0, 750.0), (120.0, 770.0), 28.3, 45.0, 42.0, "tack", 75.0, 8.0, 4.0),
            RouteSegment("straight", (120.0, 770.0), (0.0, 1500.0), 739.8, 348.0, 345.0),
        ]
        tpls = []
        for team in ("ac37:ETNZ", "ac37:INEOS"):
            for leg_type in (0, 1):
                tpls.append(
                    LegRouteTemplate(
                        template_id=f"tpl_{team}_{leg_type}",
                        attempt_id="att_0",
                        team_id=team,
                        date_str="2024-08-22",
                        stage="round_robin",
                        leg_number=1 if leg_type == 1 else 2,
                        leg_type=leg_type,
                        mean_tws_mps=9.5,
                        leg_length_m=1500.0,
                        segments=segs,
                    )
                )

        suite_no_races = fit_and_calibrate_predictor_suite(
            rows,
            inner_split,
            maneuvers=mans,
            start_intervals=starts,
            route_templates=tpls,
            qualified_cal_races=(),
            seed=2027,
            neural_max_epochs=6,
            neural_patience=3,
        )
        preds = suite_no_races["predictors"]
        self.assertEqual(
            set(preds.keys()),
            {"empirical_binned_polar", "regularized_spline_polar", "neural_network_silu"},
        )
        # Each predictor gets its own residual blocks on calibration date (never shared spline residuals)
        emp_res0 = np.array(preds["empirical_binned_polar"]["residual_sampler"].blocks[0][0])
        spl_res0 = np.array(preds["regularized_spline_polar"]["residual_sampler"].blocks[0][0])
        nn_res0 = np.array(preds["neural_network_silu"]["residual_sampler"].blocks[0][0])
        self.assertGreater(float(np.max(np.abs(emp_res0 - spl_res0))), 1e-4)
        self.assertGreater(float(np.max(np.abs(nn_res0 - spl_res0))), 1e-4)
        for c_name, p_info in preds.items():
            cal = p_info["calibration"]
            self.assertEqual(cal.calibration_date, "2024-08-25")
            self.assertTrue(cal.verified_no_test_leakage)
            self.assertGreater(cal.motion_residual_scale, 0.0)
            self.assertEqual(cal.margin_interval_scale, 1.0, f"{c_name} should keep 1.0 without cal races")

        # Multi-date chronological OOF pooling accumulates strictly OOF blocks across trailing dates
        suite_oof2 = fit_and_calibrate_predictor_suite(
            rows,
            inner_split,
            maneuvers=mans,
            start_intervals=starts,
            route_templates=tpls,
            qualified_cal_races=(),
            seed=2027,
            neural_max_epochs=6,
            neural_patience=3,
            oof_residual_max_dates=2,
        )
        for c_name in preds:
            self.assertGreater(
                suite_oof2["predictors"][c_name]["paired_block_count"],
                preds[c_name]["paired_block_count"],
            )

        # Now supply 4 verified calibration-date races to exercise margin_interval_scale fitting
        cal_races = [
            {
                "race_id": f"cal_r{i}",
                "date_str": "2024-08-25",
                "observed_delta_t_s": d_obs,
                "scenario_request": {
                    "schema_version": "kinematic-race-sim-2",
                    "model_id": "eval_test",
                    "team_a": "ac37:ETNZ",
                    "team_b": "ac37:INEOS",
                    "course_id": "barcelona_4leg_1500m",
                    "environment": {"tws_mps": 9.0 + i * 0.5, "twd_deg": 195.0},
                    "purpose": "preview",
                    "scenario_policy_id": "training_observed_routes_v1",
                    "seed": 2027 + i,
                    "trial_count": 40,
                },
            }
            for i, d_obs in enumerate((18.0, 24.0, 12.0, 30.0))
        ]
        suite_with_races = fit_and_calibrate_predictor_suite(
            rows,
            inner_split,
            maneuvers=mans,
            start_intervals=starts,
            route_templates=tpls,
            qualified_cal_races=cal_races,
            seed=2027,
            neural_max_epochs=6,
            neural_patience=3,
        )
        for p_info in suite_with_races["predictors"].values():
            gamma = p_info["calibration"].margin_interval_scale
            self.assertTrue(math.isfinite(gamma))
            self.assertGreaterEqual(gamma, 0.5)
            self.assertLessEqual(gamma, 2.5)


if __name__ == "__main__":
    unittest.main()
