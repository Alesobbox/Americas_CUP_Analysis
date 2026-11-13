"""Focused unit tests for AC75 learning contracts, identities, units, and validation."""
import math
import unittest

from pipeline.kinematic_ml.contracts import (
    KNOTS_TO_MPS,
    MPS_TO_KNOTS,
    knots_to_mps,
    mps_to_knots,
    leg_course_vmg_mps,
    wind_relative_vmg_mps,
    resolve_team_identity,
    UnsupportedIdentityError,
    validate_feature_separation,
    validate_scenario_request,
    validate_scenario_v2,
    is_legacy_scenario,
    ScenarioV2Result,
    ScenarioProbabilityDetail,
    ScenarioTimingDetail,
    ScenarioStatus,
    ProbabilityScope,
    ManeuverCensoring,
    MOTION_PREDICTOR_ALLOWLIST,
    MOTION_TARGET_ALLOWLIST,
    SplitRef,
    TrainingView,
    EvidencePolicy,
    EvidenceBasis,
    SelectionDecision,
    NormalizedScenarioRequest,
    EvaluationReceipt,
)
from pipeline.kinematic_ml.config import load_config, compute_config_hash, LearningConfig


class TestAC75Contracts(unittest.TestCase):
    def test_si_units_and_vmg_adapters_round_trip(self):
        """Verify SI unit conversion and exact VMG round-trip precision."""
        # 1. Knot / mps conversion
        speed_kt = 25.0
        speed_mps = knots_to_mps(speed_kt)
        self.assertAlmostEqual(speed_mps, 25.0 * (1852.0 / 3600.0), places=10)
        self.assertAlmostEqual(mps_to_knots(speed_mps), speed_kt, places=10)

        # Non-finite or negative speed failure
        with self.assertRaises(ValueError):
            knots_to_mps(float("nan"))
        with self.assertRaises(ValueError):
            knots_to_mps(float("inf"))
        with self.assertRaises(ValueError):
            leg_course_vmg_mps(-1.0, 45.0, 45.0, 1)

        # 2. Upwind leg (leg 1): SOG 20 kt = ~10.288 m/s, COG 45 deg, axis 45 deg -> 100% VMG
        sog_mps = knots_to_mps(20.0)
        vmg_up = leg_course_vmg_mps(sog_mps, cog_deg=45.0, axis_deg=45.0, leg=1)
        self.assertAlmostEqual(vmg_up, sog_mps, places=6)

        # 3. Downwind leg (leg 2): axis 45 deg, bearing is 225 deg. COG 225 deg -> 100% VMG
        vmg_dn = leg_course_vmg_mps(sog_mps, cog_deg=225.0, axis_deg=45.0, leg=2)
        self.assertAlmostEqual(vmg_dn, sog_mps, places=6)

        # 4. Wind relative VMG
        vmg_wind_up = wind_relative_vmg_mps(sog_mps, cog_deg=45.0, twd_deg=45.0, upwind=True)
        self.assertAlmostEqual(vmg_wind_up, sog_mps, places=6)
        vmg_wind_dn = wind_relative_vmg_mps(sog_mps, cog_deg=225.0, twd_deg=45.0, upwind=False)
        self.assertAlmostEqual(vmg_wind_dn, sog_mps, places=6)

    def test_historical_identity_resolution(self):
        """Historical GB1 resolves to INEOS only in AC37; AC38 rejects or isolates."""
        # AC37 scope
        self.assertEqual(resolve_team_identity("GB1", cycle="AC37"), "ac37:INEOS")
        self.assertEqual(resolve_team_identity("INEOS", cycle="AC37"), "ac37:INEOS")
        self.assertEqual(resolve_team_identity("ETNZ", cycle="AC37"), "ac37:ETNZ")
        self.assertEqual(resolve_team_identity("NZL", cycle="AC37"), "ac37:ETNZ")
        self.assertEqual(resolve_team_identity("LUNA_ROSSA", cycle="AC37"), "ac37:LUNA_ROSSA")
        self.assertEqual(resolve_team_identity("USA", cycle="AC37"), "ac37:AMERICAN_MAGIC")
        self.assertEqual(resolve_team_identity("SUI", cycle="AC37"), "ac37:ALINGHI")
        self.assertEqual(resolve_team_identity("FRA", cycle="AC37"), "ac37:ORIENT_EXPRESS")
        self.assertEqual(resolve_team_identity("ac37:INEOS", cycle="AC37"), "ac37:INEOS")

        # Unknown team in AC37 fails
        with self.assertRaises(UnsupportedIdentityError):
            resolve_team_identity("UNKNOWN_YACHT_CLUB", cycle="AC37")

        # AC38 team in AC37 fails
        with self.assertRaises(UnsupportedIdentityError):
            resolve_team_identity("ARC_USA", cycle="AC37")
        with self.assertRaises(UnsupportedIdentityError):
            resolve_team_identity("AUSTRALIA", cycle="AC37")

        # GB1 in non-AC37 cycle fails (does NOT resolve to ac37:INEOS)
        with self.assertRaises(UnsupportedIdentityError):
            resolve_team_identity("GB1", cycle="AC38")

    def test_feature_target_anti_leakage_allowlists(self):
        """Ensure strict separation of predictors from targets and forbidden future data."""
        # Valid motion features
        valid_motion = {
            "tws_mps": 6.5,
            "twa_sin": 0.707,
            "twa_cos": 0.707,
            "tack_side": 1,
            "leg_type": 1,
            "course_wind_angle_deg": 10.0,
            "heading_cog_offset_deg": 2.5,
            "team_id": "ac37:ETNZ",
            "practice_domain": 0,
        }
        validate_feature_separation(valid_motion, task_type="motion")

        # Target-as-feature leakage fails
        leaky_features = dict(valid_motion, sog_mps=22.4)
        with self.assertRaises(ValueError):
            validate_feature_separation(leaky_features, task_type="motion")

        # Future data leakage fails
        future_leaky = dict(valid_motion, future_heading_deg=45.0)
        with self.assertRaises(ValueError):
            validate_feature_separation(future_leaky, task_type="motion")

        # Probe tests: unlisted features (e.g. future_speed, recovery_path_length) must be strictly rejected
        probe_leaky_1 = dict(valid_motion, future_speed=24.5)
        with self.assertRaises(ValueError):
            validate_feature_separation(probe_leaky_1, task_type="motion")

        probe_leaky_2 = dict(valid_motion, recovery_path_length=120.0)
        with self.assertRaises(ValueError):
            validate_feature_separation(probe_leaky_2, task_type="motion")

        # Event target leakage fails
        valid_event = {
            "turn_type": "tack",
            "entry_speed_predicted_mps": 18.0,
            "rotation_deg": 85.0,
            "tws_mps": 6.5,
            "team_id": "ac37:INEOS",
        }
        validate_feature_separation(valid_event, task_type="event")
        leaky_event = dict(valid_event, duration_s=12.4)
        with self.assertRaises(ValueError):
            validate_feature_separation(leaky_event, task_type="event")

    def test_scenario_request_validation(self):
        """Validate request payload size, content-addressed model IDs, and parameter constraints."""
        valid_req = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": "ac75-learned-nn-v1-hash-abc123",
            "team_a": "GB1",  # Will resolve to ac37:INEOS
            "team_b": "ETNZ", # Will resolve to ac37:ETNZ
            "course_id": "bcn-course-a",
            "environment": {
                "kind": "fixed_wind",
                "tws_kt": 12.0,
                "wind_from_deg": 180.0,
            },
            "purpose": "standard",
            "scenario_policy_id": "ac37-observed-behavior-v1",
        }
        normalized = validate_scenario_request(valid_req)
        self.assertEqual(normalized["team_a"], "ac37:INEOS")
        self.assertEqual(normalized["team_b"], "ac37:ETNZ")
        self.assertAlmostEqual(normalized["environment"]["tws_mps"], 12.0 * KNOTS_TO_MPS, places=6)

        # 1. Path-based model_id rejected
        path_req = dict(valid_req, model_id="../models/weights.npz")
        with self.assertRaises(ValueError):
            validate_scenario_request(path_req)

        # 2. Unknown keys rejected
        bad_key_req = dict(valid_req, arbitrary_weight_boost=1.5)
        with self.assertRaises(ValueError):
            validate_scenario_request(bad_key_req)

        # 3. Payload size > 2 KiB rejected
        giant_req = dict(valid_req, course_id="c" * 3000)
        with self.assertRaises(ValueError):
            validate_scenario_request(giant_req)

        # 4. Invalid purpose rejected
        bad_purpose = dict(valid_req, purpose="ultra_super_mode")
        with self.assertRaises(ValueError):
            validate_scenario_request(bad_purpose)

    def test_scenario_v2_discriminated_results_and_null_semantics(self):
        """Verify available, unavailable, null, zero, and censored states round-trip distinctly."""
        # Available scenario under completion_assumed_on_water (no_winner must be None)
        probs = ScenarioProbabilityDetail(win_a=0.62, win_b=0.38, no_winner=None, mc_error=0.005)
        timing = ScenarioTimingDetail(
            mean_time_a_s=1420.0,
            mean_time_b_s=1432.5,
            mean_delta_t_s=-12.5,
            central_80_margin_interval_s=(-24.0, 1.5),
        )
        res_avail = ScenarioV2Result(
            scenario_id="scen-001",
            model_id="model-hash-123",
            status=ScenarioStatus.AVAILABLE,
            probability_scope=ProbabilityScope.COMPLETION_ASSUMED_ON_WATER,
            probabilities=probs,
            timing=timing,
            trial_counts={"requested": 10000, "completed": 10000, "unresolved": 0},
        )
        dict_avail = res_avail.to_dict()
        validate_scenario_v2(dict_avail)
        self.assertIsNone(dict_avail["probabilities"]["no_winner"])
        self.assertEqual(dict_avail["probabilities"]["win_a"], 0.62)

        # Under completion_assumed_on_water, no_winner=0.0 is rejected (must be None)
        bad_scope_dict = dict(dict_avail)
        bad_scope_dict["probabilities"] = dict(dict_avail["probabilities"], no_winner=0.0)
        with self.assertRaises(ValueError):
            validate_scenario_v2(bad_scope_dict)

        # Under unconditional_reviewed, no_winner=0.0 is valid and distinct from None
        res_uncond = ScenarioV2Result(
            scenario_id="scen-001b",
            model_id="model-hash-123",
            status=ScenarioStatus.AVAILABLE,
            probability_scope=ProbabilityScope.UNCONDITIONAL_REVIEWED,
            probabilities=ScenarioProbabilityDetail(win_a=0.62, win_b=0.38, no_winner=0.0, mc_error=0.005),
            timing=timing,
            trial_counts={"requested": 10000, "completed": 10000, "unresolved": 0},
        )
        dict_uncond = res_uncond.to_dict()
        validate_scenario_v2(dict_uncond)
        self.assertEqual(dict_uncond["probabilities"]["no_winner"], 0.0)

        # mc_error > 0.5 is rejected as not a valid probability error
        with self.assertRaises(ValueError):
            ScenarioProbabilityDetail(win_a=0.62, win_b=0.38, no_winner=None, mc_error=0.75)

        # Unavailable scenario (e.g. unresolved simulation mass)
        res_unavail = ScenarioV2Result(
            scenario_id="scen-002",
            model_id="model-hash-123",
            status=ScenarioStatus.UNAVAILABLE,
            probability_scope=ProbabilityScope.COMPLETION_ASSUMED_ON_WATER,
            probabilities=None,  # Nullable, not 0.0
            timing=None,
            reason_codes=["unresolved_simulation_timeout"],
            trial_counts={"requested": 10000, "completed": 7000, "unresolved": 3000},
        )
        dict_unavail = res_unavail.to_dict()
        validate_scenario_v2(dict_unavail)
        self.assertIsNone(dict_unavail["probabilities"])
        self.assertIsNone(dict_unavail["timing"])
        self.assertIn("unresolved_simulation_timeout", dict_unavail["reason_codes"])

        # Available with None probabilities fails validation
        with self.assertRaises(ValueError):
            validate_scenario_v2({"schema_version": "kinematic-race-sim-2", "status": "available", "probability_scope": "completion_assumed_on_water", "probabilities": None})

        # Censored states distinction
        self.assertEqual(ManeuverCensoring.UNCENSORED.value, "uncensored")
        self.assertEqual(ManeuverCensoring.RIGHT_CENSORED_TIME_LIMIT.value, "right_censored_time_limit")
        self.assertNotEqual(ManeuverCensoring.UNCENSORED, ManeuverCensoring.RIGHT_CENSORED_TIME_LIMIT)

    def test_legacy_v1_catalog_and_scenario_detection(self):
        """Existing old catalogs remain readable as explicitly legacy, not learned."""
        legacy_scen = {
            "schema_version": "kinematic-race-sim-1",
            "team_a": "ETNZ",
            "team_b": "GB1",
            "tws_kt": 12.0,
            "win_probability_a": 0.55,
            "win_probability_b": 0.45,
        }
        self.assertTrue(is_legacy_scenario(legacy_scen))

        # v2 scenario is not legacy
        v2_scen = {"schema_version": "kinematic-race-sim-2"}
        self.assertFalse(is_legacy_scenario(v2_scen))

    def test_versioned_config_and_deterministic_hash(self):
        """Verify config defaults load cleanly and compute immutable deterministic hash."""
        cfg = load_config()
        self.assertEqual(cfg.primary_class, "AC75")
        self.assertEqual(cfg.cycle, "AC37")
        self.assertEqual(cfg.neural_model.hidden_layers, 2)
        self.assertEqual(cfg.neural_model.units_per_layer, 32)
        self.assertEqual(cfg.neural_model.activation, "silu")
        self.assertEqual(cfg.neural_model.distribution, "lognormal")
        self.assertEqual(cfg.steady_windows.duration_s, 5.0)
        self.assertEqual(cfg.steady_windows.min_supported_duration_fraction, 0.95)

        h1 = compute_config_hash(cfg)
        h2 = compute_config_hash(cfg)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_wave0_shared_contracts(self):
        """Verify SplitRef, TrainingView, EvidencePolicy, SelectionDecision, NormalizedScenarioRequest, EvaluationReceipt."""
        # 1. SplitRef
        split = SplitRef(
            split_id="fold_01_2024-09-15",
            registry_hash="sha256-hash-123",
            train_start_date="2024-08-22",
            train_end_date="2024-09-14",
            test_date="2024-09-15",
            train_family_count=40,
            test_family_count=4,
        )
        self.assertEqual(split.split_id, "fold_01_2024-09-15")
        self.assertEqual(split.to_dict()["train_family_count"], 40)
        with self.assertRaises(AttributeError):
            split.split_id = "mutable"

        # 2. TrainingView
        tv = TrainingView(
            view_id="view-dev-01",
            registry_hash="hash-reg-abc",
            split_ref=split,
            development_families=("fam_a", "fam_b"),
            reserved_families=("fam_res_1", "fam_res_2"),
            allowed_dates=("2024-08-22", "2024-08-23"),
            family_mapping={"att_1": "fam_a"},
        )
        self.assertEqual(tv.resolve_family("att_1"), "fam_a")
        self.assertEqual(tv.resolve_family("fam_b"), "fam_b")
        with self.assertRaises(ValueError):
            tv.resolve_family("unknown_attempt_x")
        self.assertTrue(tv.is_allowed_family("fam_a"))
        self.assertFalse(tv.is_allowed_family("fam_res_1"))
        self.assertFalse(tv.is_allowed_family("unknown_fam"))
        self.assertTrue(tv.is_allowed_date("2024-08-22"))
        self.assertFalse(tv.is_allowed_date("2024-09-28"))
        tv.validate_no_reserved_leakage(["fam_a", "fam_b"])
        with self.assertRaises(ValueError):
            tv.validate_no_reserved_leakage(["fam_a", "fam_res_1"])

        # 3. EvidencePolicy
        pol = EvidencePolicy()
        q_target = {
            "evidence_basis": EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value,
            "status": "valid",
            "finish_time_a_s": 1200.0,
            "finish_time_b_s": 1215.5,
            "race_margin_s": -15.5,
            "winner": "ac37:ETNZ",
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
        }
        ok, reason = pol.qualify_race_target(q_target)
        self.assertTrue(ok)
        self.assertEqual(reason, "qualified")

        cand_target = dict(q_target, evidence_basis=EvidenceBasis.CANDIDATE_UNVERIFIED.value)
        ok_cand, reason_cand = pol.qualify_race_target(cand_target)
        self.assertFalse(ok_cand)
        self.assertEqual(reason_cand, "unverified_candidate_basis_rejected")

        bad_winner = dict(q_target, winner="ac37:INEOS")
        ok_mismatch, reason_mismatch = pol.qualify_race_target(bad_winner)
        self.assertFalse(ok_mismatch)
        self.assertEqual(reason_mismatch, "winner_physical_margin_mismatch")

        missing_finish = dict(q_target, finish_time_b_s=None)
        ok_miss, reason_miss = pol.qualify_race_target(missing_finish)
        self.assertFalse(ok_miss)
        self.assertEqual(reason_miss, "missing_timed_finish_for_both_boats")

        avg_weather = {"is_whole_race_average": True, "race_gun_ms": 10000, "available_at_ms": 9000}
        ok_w, reason_w = pol.validate_pre_race_inputs(avg_weather)
        self.assertFalse(ok_w)
        self.assertEqual(reason_w, "whole_race_average_weather_forbidden")

        late_weather = {"is_whole_race_average": False, "race_gun_ms": 10000, "available_at_ms": 20000}
        ok_late, reason_late = pol.validate_pre_race_inputs(late_weather)
        self.assertFalse(ok_late)
        self.assertEqual(reason_late, "weather_available_after_race_gun_limit")

        # 4. SelectionDecision
        crps_small = {
            "empirical": {"d1": 10.0, "d2": 11.0},
            "spline": {"d1": 9.5, "d2": 10.5},
            "neural": {"d1": 9.0, "d2": 10.0},
        }
        dec_fallback = SelectionDecision.compute_selection(crps_small, qualified_targets_count=10)
        self.assertTrue(dec_fallback.is_fallback)
        self.assertEqual(dec_fallback.selected_model_family, "empirical")
        self.assertIn("insufficient_eligible_dates", dec_fallback.fallback_reason)

        crps_full = {
            "empirical": {f"d{i}": 10.0 + 0.1 * i for i in range(6)},
            "spline": {f"d{i}": 9.8 + 0.1 * i for i in range(6)},
            "neural": {f"d{i}": 8.0 + 0.1 * i for i in range(6)},
        }
        dec_full = SelectionDecision.compute_selection(crps_full, qualified_targets_count=20)
        self.assertFalse(dec_full.is_fallback)
        self.assertEqual(dec_full.selected_model_family, "neural")

        crps_close = {
            "empirical": {f"d{i}": 10.0 for i in range(6)},
            "spline": {f"d{i}": 9.95 for i in range(6)},
            "neural": {f"d{i}": 9.90 for i in range(6)},
        }
        dec_close = SelectionDecision.compute_selection(crps_close, qualified_targets_count=20)
        self.assertIn(dec_close.selected_model_family, ("empirical", "spline", "neural"))

        # 5. NormalizedScenarioRequest
        raw_req = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": "model-content-hash-abc",
            "team_a": "NZL",
            "team_b": "GBR",
            "course_id": "bcn_course_1",
            "environment": {"kind": "fixed_wind", "tws_kt": 15.0, "wind_from_deg": 45.0},
            "purpose": "preview",
            "scenario_policy_id": "ac37-observed-behavior-v1",
        }
        norm_req = NormalizedScenarioRequest.from_raw_request(raw_req)
        self.assertEqual(norm_req.team_a, "ac37:ETNZ")
        self.assertEqual(norm_req.team_b, "ac37:INEOS")
        self.assertEqual(len(norm_req.authoritative_hash), 64)
        self.assertAlmostEqual(norm_req.environment["tws_mps"], 15.0 * KNOTS_TO_MPS, places=5)

        # 6. EvaluationReceipt
        rcpt = EvaluationReceipt(
            receipt_id="rcpt-001",
            timestamp="2026-11-10T20:00:00Z",
            model_id="model-hash-xyz",
            metrics={"margin_crps": 8.45, "brier_score": 0.18},
            breakdown_by_date={"2024-09-15": {"margin_crps": 7.9}},
            status="complete",
        )
        self.assertEqual(rcpt.metrics["margin_crps"], 8.45)
        self.assertEqual(rcpt.to_dict()["status"], "complete")


if __name__ == "__main__":
    unittest.main()
