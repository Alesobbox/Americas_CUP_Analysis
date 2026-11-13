"""Unit tests for AC75 learned simulator inference entry point (T14)."""
import math
import unittest
import numpy as np

from pipeline.kinematic_ml.contracts import validate_scenario_v2
from pipeline.kinematic_ml.events import ManeuverDurationModel, StartBehaviorModel
from pipeline.kinematic_ml.inference import (
    InstalledModelBundle,
    predict_scenario,
)
from pipeline.kinematic_ml.routes import (
    LegRouteTemplate,
    RouteSegment,
    RouteTemplateLibrary,
)
from pipeline.kinematic_ml.uncertainty import PairedResidualSampler, VarianceLedger


def _make_test_template_library() -> RouteTemplateLibrary:
    lib = RouteTemplateLibrary()
    segs = [
        RouteSegment("straight", (0.0, 0.0), (100.0, 700.0), 707.1, 10.0, 7.0),
        RouteSegment("maneuver", (100.0, 700.0), (120.0, 720.0), 28.3, 45.0, 42.0, "tack", 80.0, 9.0, 4.0),
        RouteSegment("straight", (120.0, 720.0), (0.0, 1500.0), 792.0, 350.0, 347.0),
    ]
    for team in ("ac37:INEOS", "ac37:LUNA_ROSSA", "ac37:ETNZ"):
        for leg_type in (0, 1):
            lib.add_template(
                LegRouteTemplate(
                    template_id=f"tpl_{team}_{leg_type}",
                    attempt_id="att_001",
                    team_id=team,
                    date_str="20240901",
                    stage="round_robin",
                    leg_number=1 if leg_type == 1 else 2,
                    leg_type=leg_type,
                    mean_tws_mps=10.0,
                    leg_length_m=1500.0,
                    segments=segs,
                )
            )
    return lib


class TestAC75Inference(unittest.TestCase):
    def setUp(self):
        weights = {
            "fc1.weight": np.zeros((32, 14), dtype=np.float32),
            "fc1.bias": np.zeros(32, dtype=np.float32),
            "fc2.weight": np.zeros((32, 32), dtype=np.float32),
            "fc2.bias": np.zeros(32, dtype=np.float32),
            "fc_out.weight": np.zeros((2, 32), dtype=np.float32),
            "fc_out.bias": np.array([np.log(20.0), -1.5], dtype=np.float32),
        }
        scaler_mean = np.zeros(8, dtype=np.float32)
        scaler_scale = np.ones(8, dtype=np.float32)

        self.bundle = InstalledModelBundle(
            model_id="ac75_nn_v1",
            motion_weights=weights,
            scaler_mean=scaler_mean,
            scaler_scale=scaler_scale,
            template_library=_make_test_template_library(),
            maneuver_model=ManeuverDurationModel(),
            start_model=StartBehaviorModel(mean_start_dur_s=15.0, stdev_s=0.5),
            residual_sampler=PairedResidualSampler(),
            variance_ledger=VarianceLedger(),
        )

    def test_identical_profiles_exchangeability(self):
        """Verify that identical competitors produce symmetric win probabilities and exchangeable margins."""
        req_ab = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:LUNA_ROSSA",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 10.0, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 1000,
        }
        res_ab = predict_scenario(self.bundle, req_ab)
        self.assertEqual(res_ab.status, "available")
        self.assertEqual(res_ab.probability_scope, "completion_assumed_on_water")
        validate_scenario_v2(res_ab.to_dict())

        # Swap competitors
        req_ba = dict(req_ab)
        req_ba["team_a"] = "ac37:LUNA_ROSSA"
        req_ba["team_b"] = "ac37:INEOS"
        res_ba = predict_scenario(self.bundle, req_ba)

        # Delta T must be exact negation and win probabilities swapped
        delta_ab = res_ab.timing.mean_delta_t_s
        delta_ba = res_ba.timing.mean_delta_t_s
        self.assertAlmostEqual(delta_ab, -delta_ba, places=2)
        self.assertAlmostEqual(res_ab.probabilities.win_a, res_ba.probabilities.win_b, places=4)
        self.assertAlmostEqual(res_ab.probabilities.win_b, res_ba.probabilities.win_a, places=4)

    def test_seconds_accounting_sums_to_delta(self):
        """Verify that straight, maneuver, and start deltas sum to total mean delta T."""
        req = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:ETNZ",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 12.0, "twd_deg": 190.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 500,
        }
        res = predict_scenario(self.bundle, req)
        acct = res.applied_inputs["seconds_accounting"]
        sum_components = (
            acct["straight_delta_s"]
            + acct["maneuver_delta_s"]
            + acct["start_delta_s"]
        )
        self.assertAlmostEqual(sum_components, acct["total_mean_delta_s"], places=2)

    def test_missing_route_support_returns_unavailable(self):
        """Verify missing route templates return unavailable with reason_codes (no synthetic fallback)."""
        empty_bundle = InstalledModelBundle(
            model_id="ac75_nn_v1",
            motion_weights=self.bundle.motion_weights,
            scaler_mean=self.bundle.scaler_mean,
            scaler_scale=self.bundle.scaler_scale,
            template_library=RouteTemplateLibrary(),
            maneuver_model=ManeuverDurationModel(),
            start_model=StartBehaviorModel(),
            residual_sampler=PairedResidualSampler(),
            variance_ledger=VarianceLedger(),
        )
        req = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:ETNZ",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 10.0, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 200,
        }
        res = predict_scenario(empty_bundle, req)
        self.assertEqual(res.status, "unavailable")
        self.assertIn("missing_route_template_support", res.reason_codes)
        self.assertIsNone(res.probabilities)
        self.assertIsNone(res.timing)

    def test_course_id_and_maneuver_model_change_simulated_time(self):
        """Verify course_id and maneuver model parameters directly affect simulated race times."""
        base_req = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:ETNZ",
            "course_id": "barcelona_4leg_1500m",
            "environment": {"tws_mps": 10.0, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 400,
        }
        res_4leg = predict_scenario(self.bundle, base_req)
        req_6leg = dict(base_req, course_id="barcelona_6leg_1852m")
        res_6leg = predict_scenario(self.bundle, req_6leg)

        self.assertGreater(res_6leg.timing.mean_time_a_s, res_4leg.timing.mean_time_a_s + 100.0)
        self.assertNotEqual(res_4leg.scenario_id, res_6leg.scenario_id)

        # Slow down maneuvers and verify simulated race time increases
        slow_man = ManeuverDurationModel()
        slow_man.intercept_tack = math.log(28.0)
        slow_bundle = InstalledModelBundle(
            model_id="ac75_nn_v1",
            motion_weights=self.bundle.motion_weights,
            scaler_mean=self.bundle.scaler_mean,
            scaler_scale=self.bundle.scaler_scale,
            template_library=self.bundle.template_library,
            maneuver_model=slow_man,
            start_model=self.bundle.start_model,
            residual_sampler=self.bundle.residual_sampler,
            variance_ledger=self.bundle.variance_ledger,
        )
        res_slow_man = predict_scenario(slow_bundle, base_req)
        self.assertGreater(res_slow_man.timing.mean_time_a_s, res_4leg.timing.mean_time_a_s + 20.0)

    def test_scenario_input_allowlist_enforcement(self):
        """Verify SCENARIO_INPUT_ALLOWLIST rejects unknown or forbidden keys."""
        bad_req = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:LUNA_ROSSA",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 10.0, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "forbidden_extra_param": 123,
        }
        with self.assertRaises(ValueError):
            predict_scenario(self.bundle, bad_req)

    def test_calibration_scales_and_unrounded_tws_precision(self):
        """Verify motion_residual_scale, margin_interval_scale, and unrounded tws_mps precision."""
        feat = {
            "team_id": "ac37:INEOS",
            "tws_mps": 10.0,
            "twa_sin": 0.7,
            "twa_cos": 0.71,
            "tack_side": 1,
            "leg_type": 1,
            "heading_cog_offset_deg": 2.0,
            "course_wind_angle_deg": 42.0,
            "practice_domain": 0,
        }
        mu1, sig1 = self.bundle.predict_motion_distribution(feat)

        motion_scaled_bundle = InstalledModelBundle(
            model_id="ac75_nn_v1",
            motion_weights=self.bundle.motion_weights,
            scaler_mean=self.bundle.scaler_mean,
            scaler_scale=self.bundle.scaler_scale,
            template_library=self.bundle.template_library,
            maneuver_model=self.bundle.maneuver_model,
            start_model=self.bundle.start_model,
            residual_sampler=self.bundle.residual_sampler,
            variance_ledger=self.bundle.variance_ledger,
            motion_residual_scale=1.5,
            margin_interval_scale=1.0,
        )
        mu2, sig2 = motion_scaled_bundle.predict_motion_distribution(feat)
        self.assertAlmostEqual(mu1, mu2, places=6)
        self.assertAlmostEqual(sig2, sig1 * 1.5, places=6)

        margin_scaled_bundle = InstalledModelBundle(
            model_id="ac75_nn_v1",
            motion_weights=self.bundle.motion_weights,
            scaler_mean=self.bundle.scaler_mean,
            scaler_scale=self.bundle.scaler_scale,
            template_library=self.bundle.template_library,
            maneuver_model=self.bundle.maneuver_model,
            start_model=self.bundle.start_model,
            residual_sampler=self.bundle.residual_sampler,
            variance_ledger=self.bundle.variance_ledger,
            motion_residual_scale=1.0,
            margin_interval_scale=2.0,
        )

        req_60 = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": "ac75_nn_v1",
            "team_a": "ac37:INEOS",
            "team_b": "ac37:ETNZ",
            "course_id": "barcelona_4leg_1500m",
            "environment": {"tws_mps": 6.0, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 300,
        }
        res_base = predict_scenario(self.bundle, req_60)
        res_scaled = predict_scenario(margin_scaled_bundle, req_60)

        # Scaled bundle widens margin_std_s and central 80% interval half-width by gamma=2.0 without shifting mean
        base_half = res_base.timing.central_80_margin_interval_s[1] - res_base.timing.mean_delta_t_s
        scaled_half = res_scaled.timing.central_80_margin_interval_s[1] - res_scaled.timing.mean_delta_t_s
        self.assertAlmostEqual(res_scaled.timing.mean_delta_t_s, res_base.timing.mean_delta_t_s, places=4)
        self.assertAlmostEqual(
            res_scaled.time_accounting["margin_std_s"] / max(1e-6, res_base.time_accounting["margin_std_s"]),
            2.0,
            places=2,
        )
        self.assertAlmostEqual(scaled_half / max(1e-6, base_half), 2.0, places=2)

        # Subtle unrounded tws_mps difference (6.0004 vs 6.0) must not collapse to same scenario_id
        req_60004 = dict(req_60, environment={"tws_mps": 6.0004, "twd_deg": 180.0})
        res_60004 = predict_scenario(self.bundle, req_60004)
        self.assertEqual(res_60004.applied_inputs["environment"]["tws_mps"], 6.0004)
        self.assertNotEqual(res_60004.scenario_id, res_base.scenario_id)


if __name__ == "__main__":
    unittest.main()
