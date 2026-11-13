"""Unit tests for evaluation evidence qualification, pre-race input policies, and Gate A Criterion 5 (Work Packet P2)."""
from __future__ import annotations

import unittest

from pipeline.kinematic_ml.evidence.basis import (
    EvidenceBasis,
    ReviewState,
    QualifiedFieldEvidence,
)
from pipeline.kinematic_ml.evidence.policy import (
    EvidencePolicy,
)
from pipeline.kinematic_ml.evidence.qualifier import (
    QualificationResult,
    qualify_evaluation_targets,
)


class TestAC75Evidence(unittest.TestCase):
    def setUp(self):
        self.default_policy = EvidencePolicy()

    def test_evidence_basis_separated_from_review_state(self):
        """Verify evidence basis tiering is distinct from review and verification state."""
        # Field with candidate unverified basis but verified=False
        ev_unverified = QualifiedFieldEvidence(
            field_name="winner",
            value="ac37:ETNZ",
            evidence_basis=EvidenceBasis.CANDIDATE_UNVERIFIED.value,
            review_state=ReviewState.UNVERIFIED.value,
            verified=False,
            source_ref="candidate_results.json",
            source_hash="sha256-abc",
            race_id="ac37_fpr1_match_1",
            attempt_id="ac37_fpr1_match_1_att1",
            timing_basis="reported_results",
            coverage=0.8,
        )
        self.assertFalse(ev_unverified.is_qualified_for_primary())
        self.assertEqual(ev_unverified.evidence_basis, "candidate_unverified")
        self.assertEqual(ev_unverified.review_state, "unverified")

        # Field with official results basis and verified=True
        ev_verified = QualifiedFieldEvidence(
            field_name="winner",
            value="ac37:ETNZ",
            evidence_basis=EvidenceBasis.OFFICIAL_RESULTS.value,
            review_state=ReviewState.VERIFIED.value,
            verified=True,
            source_ref="official_ac37_doc.json",
            source_hash="sha256-def",
            race_id="ac37_fpr1_match_1",
            attempt_id="ac37_fpr1_match_1_att1",
            timing_basis="gun_to_line",
            coverage=1.0,
        )
        self.assertTrue(ev_verified.is_qualified_for_primary())

        # Unavailable field is rejected regardless of verified flag
        ev_unavail = QualifiedFieldEvidence(
            field_name="delta_s",
            value=None,
            evidence_basis=EvidenceBasis.UNAVAILABLE.value,
            review_state=ReviewState.UNVERIFIED.value,
            verified=False,
        )
        self.assertFalse(ev_unavail.is_qualified_for_primary())

    def test_primary_evaluator_rejects_unverified_candidate_fields(self):
        """Gate A Criterion 5: Primary evaluator rejects unverified candidate fields without explicit qualifying evidence record."""
        target_unverified_candidate = {
            "race_id": "ac37_fpr1_match_1",
            "attempt_id": "ac37_fpr1_match_1_att1",
            "evidence_basis": EvidenceBasis.CANDIDATE_UNVERIFIED.value,
            "verified": False,
            "finish_time_a_s": 1420.0,
            "finish_time_b_s": 1445.0,
            "race_margin_s": -25.0,
            "winner": "ac37:ETNZ",
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
        }
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_unverified_candidate)
        self.assertFalse(is_ok)
        self.assertIn("candidate", reason)

        # Same target with explicit qualifying evidence (verified = True and source-confirmed on water)
        target_qualified = dict(
            target_unverified_candidate,
            evidence_basis=EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value,
            verified=True,
        )
        is_ok_q, reason_q, field_records = self.default_policy.qualify_race_target(target_qualified)
        self.assertTrue(is_ok_q)
        self.assertEqual(reason_q, "qualified")
        self.assertIn("winner", field_records)
        self.assertIn("race_margin_s", field_records)
        self.assertTrue(field_records["winner"].verified)

    def test_candidate_values_cannot_enter_primary_merely_because_non_null(self):
        """Non-null candidate fields cannot enter primary selection without verified status."""
        target_non_null_candidate = {
            "race_id": "ac37_fpr1_match_2",
            "attempt_id": "ac37_fpr1_match_2_att1",
            "evidence_basis": EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value,
            "verified": True,
            "finish_time_a_s": 1300.0,
            "finish_time_b_s": 1320.0,
            "race_margin_s": -20.0,
            "winner": "ac37:ETNZ",
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
            "field_evidence": {
                "winner": {
                    "value": "ac37:ETNZ",
                    "evidence_basis": EvidenceBasis.CANDIDATE_UNVERIFIED.value,  # Unverified candidate!
                    "verified": False,
                }
            },
        }
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_non_null_candidate)
        self.assertFalse(is_ok)
        self.assertEqual(reason, "candidate_unverified_cannot_enter_primary")

    def test_race_target_policy_supported_timed_finishes(self):
        """Primary margin scoring requires supported timed finishes for both boats in the same valid attempt."""
        base_target = {
            "race_id": "ac37_fpr1_match_3",
            "attempt_id": "ac37_fpr1_match_3_att1",
            "evidence_basis": EvidenceBasis.OFFICIAL_RESULTS.value,
            "verified": True,
            "race_margin_s": -15.0,
            "winner": "ac37:ETNZ",
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
        }

        # 1. Missing boat B finish time
        target_missing_b = dict(base_target, finish_time_a_s=1200.0, finish_time_b_s=None)
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_missing_b)
        self.assertFalse(is_ok)
        self.assertEqual(reason, "missing_timed_finish_for_both_boats")

        # 2. Non-finite boat A finish time
        target_nan_a = dict(base_target, finish_time_a_s=float("nan"), finish_time_b_s=1215.0)
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_nan_a)
        self.assertFalse(is_ok)
        self.assertEqual(reason, "non_finite_finish_times")

        # 3. Negative finish time
        target_neg = dict(base_target, finish_time_a_s=-10.0, finish_time_b_s=1215.0)
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_neg)
        self.assertFalse(is_ok)
        self.assertEqual(reason, "non_finite_finish_times")

        # 4. Valid finishes qualify
        target_valid = dict(base_target, finish_time_a_s=1200.0, finish_time_b_s=1215.0)
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_valid)
        self.assertTrue(is_ok)
        self.assertEqual(reason, "qualified")

    def test_primary_winner_must_match_physical_margin(self):
        """Primary on-water winner scoring must match the physical margin target."""
        base_target = {
            "race_id": "ac37_fpr1_match_4",
            "attempt_id": "ac37_fpr1_match_4_att1",
            "evidence_basis": EvidenceBasis.OFFICIAL_RESULTS.value,
            "verified": True,
            "finish_time_a_s": 1200.0,
            "finish_time_b_s": 1220.0,
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
        }

        # Boat A won physically (margin = -20s), but winner marked as Team B -> mismatch!
        target_mismatch = dict(base_target, race_margin_s=-20.0, winner="ac37:INEOS")
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_mismatch)
        self.assertFalse(is_ok)
        self.assertEqual(reason, "winner_physical_margin_mismatch")

        # Boat B won physically (margin = +20s), but winner marked as Team A -> mismatch!
        target_mismatch_b = dict(base_target, race_margin_s=20.0, winner="ac37:ETNZ")
        is_ok_b, reason_b, _ = self.default_policy.qualify_race_target(target_mismatch_b)
        self.assertFalse(is_ok_b)
        self.assertEqual(reason_b, "winner_physical_margin_mismatch")

        # Matching physical winner qualifies
        target_match = dict(base_target, race_margin_s=-20.0, winner="ac37:ETNZ")
        is_ok_m, reason_m, _ = self.default_policy.qualify_race_target(target_match)
        self.assertTrue(is_ok_m)
        self.assertEqual(reason_m, "qualified")

    def test_missing_records_do_not_prove_retirement_or_completion(self):
        """Missing records do not prove retirement or completion."""
        target_unverified_status = {
            "race_id": "ac37_fpr1_match_5",
            "attempt_id": "ac37_fpr1_match_5_att1",
            "evidence_basis": EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value,
            "verified": True,
            "finish_status": "unverified_or_retired",
            "finish_time_a_s": 1200.0,
            "finish_time_b_s": None,  # Missing record cannot prove completion or retirement!
            "race_margin_s": None,
            "winner": "ac37:ETNZ",
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
        }
        is_ok, reason, _ = self.default_policy.qualify_race_target(target_unverified_status)
        self.assertFalse(is_ok)

    def test_pre_race_input_policy_weather_and_latency(self):
        """Pre-race input policy: gun-time issue time, latency enforcement, rejection of averages & defaults."""
        race_gun_ms = 1727352900000

        # 1. Valid pre-race weather (arrived 1s before gun)
        valid_weather = {
            "race_gun_ms": race_gun_ms,
            "available_at_ms": race_gun_ms - 1000,
            "tws_mps": 6.8,
            "wind_from_deg": 185.0,
            "is_whole_race_average": False,
            "is_invented_default": False,
        }
        is_ok, reason = self.default_policy.validate_pre_race_inputs(valid_weather)
        self.assertTrue(is_ok)
        self.assertEqual(reason, "valid")

        # 2. Weather arrived within 6000ms latency tolerance
        within_latency = dict(valid_weather, available_at_ms=race_gun_ms + 5000)
        is_ok_l, reason_l = self.default_policy.validate_pre_race_inputs(within_latency)
        self.assertTrue(is_ok_l)

        # 3. Weather arrived after registered latency limit (> 6000ms after race gun)
        too_late = dict(valid_weather, available_at_ms=race_gun_ms + 7000)
        is_ok_late, reason_late = self.default_policy.validate_pre_race_inputs(too_late)
        self.assertFalse(is_ok_late)
        self.assertEqual(reason_late, "weather_available_after_race_gun_limit")

        # 4. Whole-race-average weather strictly forbidden
        avg_weather = dict(valid_weather, is_whole_race_average=True)
        is_ok_avg, reason_avg = self.default_policy.validate_pre_race_inputs(avg_weather)
        self.assertFalse(is_ok_avg)
        self.assertEqual(reason_avg, "whole_race_average_weather_forbidden")

        # 5. Invented default weather strictly forbidden
        default_weather = dict(valid_weather, is_invented_default=True)
        is_ok_def, reason_def = self.default_policy.validate_pre_race_inputs(default_weather)
        self.assertFalse(is_ok_def)
        self.assertEqual(reason_def, "invented_default_weather_forbidden")

        # 6. Missing pre-race context marks case unavailable
        is_ok_none, reason_none = self.default_policy.validate_pre_race_inputs(None)
        self.assertFalse(is_ok_none)
        self.assertEqual(reason_none, "missing_pre_race_weather_context")

        is_ok_empty, reason_empty = self.default_policy.validate_pre_race_inputs({})
        self.assertFalse(is_ok_empty)
        self.assertEqual(reason_empty, "missing_pre_race_weather_context")

    def test_batch_qualification_insufficient_qualified_race_targets(self):
        """When no targets qualify, return insufficient_qualified_race_targets."""
        # Batch where all targets are unverified candidates
        targets = [
            {
                "race_id": f"race_{i}",
                "evidence_basis": EvidenceBasis.CANDIDATE_UNVERIFIED.value,
                "verified": False,
                "finish_time_a_s": 1200.0,
                "finish_time_b_s": 1210.0,
                "race_margin_s": -10.0,
                "winner": "ac37:ETNZ",
                "team_a": "ac37:ETNZ",
                "team_b": "ac37:INEOS",
            }
            for i in range(5)
        ]
        result = qualify_evaluation_targets(targets, self.default_policy)
        self.assertEqual(result.status, "insufficient_qualified_race_targets")
        self.assertEqual(result.qualified_count, 0)
        self.assertEqual(result.total_evaluated, 5)
        self.assertGreater(result.rejection_reasons.get("unverified_candidate_basis_rejected", 0), 0)


if __name__ == "__main__":
    unittest.main()
