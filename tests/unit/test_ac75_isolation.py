"""Unit tests for centralized family-based isolation and Gate A criteria 1-4 (Work Packet P1)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipeline.kinematic_ml.contracts import SplitRef, TrainingView
from pipeline.kinematic_ml.splits.registry import (
    FROZEN_REGISTRY_EXPECTED_SHA256,
    compute_frozen_registry_hash,
    verify_split_registry,
    load_frozen_family_registry,
    load_canonical_attempt_ledger,
    RECONCILED_FAMILY_ALIASES,
)
from pipeline.kinematic_ml.splits.manager import (
    ChronologicalSplitManager,
    OuterFold,
)
from pipeline.kinematic_ml.training_view import (
    AuthenticatedTrainingViewLoader,
    load_authenticated_training_view,
    filter_steady_windows,
    filter_maneuvers,
    filter_route_templates,
    filter_start_intervals,
    filter_completion_records,
    filter_calibration_samples,
    filter_residual_estimation_data,
    verify_steady_windows_baseline,
    assert_stopped_attempt_and_resail_co_isolation,
)

ROOT = Path(__file__).resolve().parents[2]


class TestAC75Isolation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_split_registry_verification_fails_on_missing_or_corrupt_registry(self):
        """Gate A Criterion 1: Split registry verification fails on missing or corrupt registry."""
        # 1. Missing file fails with FileNotFoundError
        missing_path = self.tmp_path / "non_existent_registry.json"
        with self.assertRaises(FileNotFoundError):
            load_frozen_family_registry(missing_path)

        # 2. Corrupt JSON fails with ValueError
        bad_json_path = self.tmp_path / "corrupt_json.json"
        bad_json_path.write_text("{ broken json: [", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_frozen_family_registry(bad_json_path)

        # 3. Corrupt content SHA-256 hash fails with ValueError
        valid_payload = {
            "status": "frozen_metadata_only",
            "holdout_dates": ["2024-10-01"],
            "reserved_holdout_families": ["fam_res_1"],
            "development_families": ["fam_dev_1", "fam_dev_2"],
        }
        correct_hash = compute_frozen_registry_hash(valid_payload)
        tampered_payload = dict(valid_payload, content_sha256="corrupted_hash_abc123")
        tampered_path = self.tmp_path / "tampered_hash.json"
        tampered_path.write_text(json.dumps(tampered_payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_frozen_family_registry(tampered_path, expected_hash=correct_hash)

        # 4. Missing required list fields fails with ValueError
        for missing_key in ("holdout_dates", "reserved_holdout_families", "development_families"):
            incomplete = {k: v for k, v in valid_payload.items() if k != missing_key}
            incomplete_path = self.tmp_path / f"missing_{missing_key}.json"
            incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_frozen_family_registry(incomplete_path, verify_hash=False)

        # 5. Internal overlap in registry fails with ValueError
        overlap_payload = {
            "status": "frozen_metadata_only",
            "holdout_dates": ["2024-10-01"],
            "reserved_holdout_families": ["fam_res_1"],
            "development_families": ["fam_res_1", "fam_dev_1"],  # Leaked overlap!
        }
        overlap_path = self.tmp_path / "overlap.json"
        overlap_path.write_text(json.dumps(overlap_payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_frozen_family_registry(overlap_path, verify_hash=False)

        # 6. Valid registry loads cleanly and matches expected hash
        legit_payload = dict(valid_payload, content_sha256=correct_hash)
        legit_path = self.tmp_path / "legit.json"
        legit_path.write_text(json.dumps(legit_payload), encoding="utf-8")
        loaded = load_frozen_family_registry(legit_path, expected_hash=correct_hash)
        self.assertEqual(loaded["registry_hash"], correct_hash)
        self.assertIn("fam_res_1", loaded["reserved_holdout_families"])
        self.assertIn("fam_dev_1", loaded["development_families"])

        # 7. Production frozen registry verification against frozen hash
        prod_reg = load_frozen_family_registry()
        self.assertEqual(prod_reg["registry_hash"], FROZEN_REGISTRY_EXPECTED_SHA256)
        self.assertEqual(len(prod_reg["reserved_holdout_families"]), 9)
        self.assertEqual(len(prod_reg["holdout_dates"]), 5)

    def test_stopped_attempt_and_resail_cannot_fall_into_different_roles(self):
        """Gate A Criterion 2: Stopped attempt and resail cannot fall into different roles."""
        # 1. Verify production attempt ledger stopped and resail attempts
        assert_stopped_attempt_and_resail_co_isolation()

        # 2. Synthetic verification: stopped attempt and resail must resolve to same family and role
        loader = AuthenticatedTrainingViewLoader()
        fam_stopped = loader.resolve_canonical_family("ac37_lvc_final_r3_att1_stopped")
        fam_resail = loader.resolve_canonical_family("ac37_lvc_final_r3_att2_resail")
        self.assertEqual(fam_stopped, fam_resail)
        self.assertEqual(fam_stopped, "ac37_lvc_final_r3")

        # Both are strictly reserved
        self.assertTrue(loader.is_reserved_family("ac37_lvc_final_r3_att1_stopped"))
        self.assertTrue(loader.is_reserved_family("ac37_lvc_final_r3_att2_resail"))
        self.assertFalse(loader.is_development_family("ac37_lvc_final_r3_att1_stopped"))
        self.assertFalse(loader.is_development_family("ac37_lvc_final_r3_att2_resail"))

    def test_canonical_family_resolution_and_reconciliation(self):
        """Verify strict canonical resolution, reconciliation of match 12 and 27, and unknown rejection."""
        loader = AuthenticatedTrainingViewLoader()

        # 1. Reconcile ac37_fpr1_match_12 and ac37_lvc_rr_match_27
        self.assertEqual(loader.resolve_canonical_family("ac37_fpr1_match_12"), "ac37_fpr1_match_12")
        self.assertEqual(loader.resolve_canonical_family("ac37_fpr1_match_12_att1"), "ac37_fpr1_match_12")
        self.assertEqual(loader.resolve_canonical_family("ac37_lvc_rr_match_27"), "ac37_lvc_rr_match_27")
        self.assertEqual(loader.resolve_canonical_family("ac37_lvc_rr_match_27_att1"), "ac37_lvc_rr_match_27")

        # Reconcile legacy aliases to canonical
        self.assertEqual(loader.resolve_canonical_family("ac37_lvc_semifinal_1_r12"), "ac37_fpr1_match_12")
        self.assertEqual(loader.resolve_canonical_family("ac37_lvc_semifinal_1_r27"), "ac37_lvc_rr_match_27")

        # Both are allowed development families
        self.assertTrue(loader.is_development_family("ac37_fpr1_match_12"))
        self.assertTrue(loader.is_development_family("ac37_lvc_rr_match_27"))
        self.assertFalse(loader.is_reserved_family("ac37_fpr1_match_12"))
        self.assertFalse(loader.is_reserved_family("ac37_lvc_rr_match_27"))

        # 2. Strict rejection of unknown identifiers (never inferred from dates or filenames)
        with self.assertRaises(ValueError):
            loader.resolve_canonical_family("unknown_attempt_999")
        with self.assertRaises(ValueError):
            loader.resolve_canonical_family("ac37_invented_race_match_99")
        with self.assertRaises(ValueError):
            loader.resolve_canonical_family("")

    def test_every_fitting_component_has_zero_reserved_family_overlap(self):
        """Gate A Criterion 3: Every fitting component has zero reserved-family overlap."""
        tv = load_authenticated_training_view()
        reserved_set = set(tv.reserved_families)

        # 1. Steady windows (motion fitting)
        raw_windows = [
            {"attempt_id": "ac37_fpr1_match_1_att1", "sog_mps": 21.0, "date": "2024-08-22"},
            {"attempt_id": "ac37_fpr1_match_12_att1", "sog_mps": 22.0, "date": "2024-08-24"},
            {"attempt_id": "ac37_lvc_rr_match_27_att1", "sog_mps": 23.0, "date": "2024-09-07"},
            {"attempt_id": "ac37_lvc_final_r3_att1_stopped", "sog_mps": 18.0, "date": "2024-09-28"},  # Reserved!
            {"attempt_id": "ac37_lvc_final_r4_att1", "sog_mps": 25.0, "date": "2024-09-29"},          # Reserved!
        ]
        dev_windows = filter_steady_windows(tv, raw_windows)
        dev_fams = [tv.resolve_family(w["attempt_id"]) for w in dev_windows]
        self.assertEqual(len(set(dev_fams) & reserved_set), 0, "Motion fitting has reserved overlap!")
        self.assertEqual(len(dev_windows), 3)

        # 2. Maneuvers
        raw_maneuvers = [
            {"attempt_id": "ac37_fpr1_match_1_att1", "duration_s": 12.0},
            {"attempt_id": "ac37_lvc_final_r5_att1", "duration_s": 14.0},  # Reserved!
        ]
        dev_maneuvers = filter_maneuvers(tv, raw_maneuvers)
        m_fams = [tv.resolve_family(m["attempt_id"]) for m in dev_maneuvers]
        self.assertEqual(len(set(m_fams) & reserved_set), 0, "Maneuvers have reserved overlap!")
        self.assertEqual(len(dev_maneuvers), 1)

        # 3. Route templates
        raw_routes = [
            {"family_id": "ac37_fpr1_match_2", "route_points": [1, 2, 3]},
            {"family_id": "ac37_lvc_final_r6", "route_points": [4, 5, 6]},  # Reserved!
        ]
        dev_routes = filter_route_templates(tv, raw_routes)
        r_fams = [tv.resolve_family(r["family_id"]) for r in dev_routes]
        self.assertEqual(len(set(r_fams) & reserved_set), 0, "Routes have reserved overlap!")
        self.assertEqual(len(dev_routes), 1)

        # 4. Start intervals
        raw_starts = [
            {"attempt_id": "ac37_lvc_rr_match_1_att1", "entry_speed_mps": 19.5},
            {"attempt_id": "ac37_lvc_final_r7_att1", "entry_speed_mps": 20.0},  # Reserved!
        ]
        dev_starts = filter_start_intervals(tv, raw_starts)
        s_fams = [tv.resolve_family(s["attempt_id"]) for s in dev_starts]
        self.assertEqual(len(set(s_fams) & reserved_set), 0, "Starts have reserved overlap!")
        self.assertEqual(len(dev_starts), 1)

        # 5. Completion models
        raw_completion = [
            {"family_id": "ac37_lvc_rr_match_2", "status": "completed"},
            {"family_id": "ac37_lvc_final_r8", "status": "completed"},  # Reserved!
        ]
        dev_comp = filter_completion_records(tv, raw_completion)
        c_fams = [tv.resolve_family(c["family_id"]) for c in dev_comp]
        self.assertEqual(len(set(c_fams) & reserved_set), 0, "Completion has reserved overlap!")
        self.assertEqual(len(dev_comp), 1)

        # 6. Calibration
        raw_calib = [
            {"attempt_id": "ac37_lvc_rr_match_3_att1", "error": 0.4},
            {"attempt_id": "ac37_lvc_final_r9_att1", "error": 1.2},  # Reserved!
        ]
        dev_cal = filter_calibration_samples(tv, raw_calib)
        cal_fams = [tv.resolve_family(c["attempt_id"]) for c in dev_cal]
        self.assertEqual(len(set(cal_fams) & reserved_set), 0, "Calibration has reserved overlap!")
        self.assertEqual(len(dev_cal), 1)

        # 7. Residual estimation
        raw_res = [
            {"attempt_id": "ac37_lvc_rr_match_4_att1", "res_mps": 0.1},
            {"attempt_id": "ac37_lvc_final_r10_att1", "res_mps": 0.9},  # Reserved!
        ]
        dev_res = filter_residual_estimation_data(tv, raw_res)
        res_fams = [tv.resolve_family(r["attempt_id"]) for r in dev_res]
        self.assertEqual(len(set(res_fams) & reserved_set), 0, "Residual estimation has reserved overlap!")
        self.assertEqual(len(dev_res), 1)

    def test_changing_excluded_targets_leaves_fitted_parameters_and_predictions_unchanged(self):
        """Gate A Criterion 4: Changing excluded targets leaves fitted parameters and predictions unchanged."""
        tv = load_authenticated_training_view()

        def fit_simple_estimator(dataset: list[dict[str, Any]]) -> dict[str, float]:
            """Simple model: estimates mean speed for dev data filtered through training view."""
            filtered = filter_steady_windows(tv, dataset)
            if not filtered:
                return {"mean_speed": 0.0}
            mean_s = sum(w["sog_mps"] for w in filtered) / len(filtered)
            return {"mean_speed": mean_s}

        # Baseline dataset with 2 dev rows and 2 reserved rows
        dataset_v1 = [
            {"attempt_id": "ac37_fpr1_match_1_att1", "sog_mps": 20.0, "date": "2024-08-22"},
            {"attempt_id": "ac37_fpr1_match_2_att1", "sog_mps": 24.0, "date": "2024-08-22"},
            {"attempt_id": "ac37_lvc_final_r3_att1_stopped", "sog_mps": 15.0, "date": "2024-09-28"},  # Excluded!
            {"attempt_id": "ac37_lvc_final_r4_att1", "sog_mps": 18.0, "date": "2024-09-29"},          # Excluded!
        ]
        model_v1 = fit_simple_estimator(dataset_v1)

        # Tampered dataset: corrupt and multiply excluded target values by 10,000x
        dataset_v2 = [
            {"attempt_id": "ac37_fpr1_match_1_att1", "sog_mps": 20.0, "date": "2024-08-22"},
            {"attempt_id": "ac37_fpr1_match_2_att1", "sog_mps": 24.0, "date": "2024-08-22"},
            {"attempt_id": "ac37_lvc_final_r3_att1_stopped", "sog_mps": 999999.0, "date": "2024-09-28"},  # Tampered!
            {"attempt_id": "ac37_lvc_final_r4_att1", "sog_mps": -888888.0, "date": "2024-09-29"},         # Tampered!
        ]
        model_v2 = fit_simple_estimator(dataset_v2)

        # Fitted parameters and predictions must be bit-for-bit identical!
        self.assertEqual(model_v1["mean_speed"], model_v2["mean_speed"])
        self.assertEqual(model_v1["mean_speed"], 22.0)

    def test_chronological_restrictions_inside_every_outer_fold(self):
        """Verify outer folds apply expanding chronological days with inner validation within train span."""
        mgr = ChronologicalSplitManager()
        family_dates = {
            "ac37_fpr1_match_1": "2024-08-22",
            "ac37_fpr1_match_5": "2024-08-23",
            "ac37_fpr1_match_9": "2024-08-24",
            "ac37_fpr1_match_13": "2024-08-25",
            "ac37_lvc_rr_match_1": "2024-08-29",
            "ac37_lvc_rr_match_5": "2024-08-30",
            "ac37_lvc_rr_match_9": "2024-08-31",
            "ac37_lvc_rr_match_13": "2024-09-01",
            "ac37_lvc_final_r3": "2024-09-29",  # Reserved!
            "ac37_lvc_final_r4": "2024-09-29",  # Reserved!
        }
        folds = mgr.build_expanding_folds(family_dates, min_train_days=3, val_days_count=1)
        self.assertGreaterEqual(len(folds), 1)

        for fold in folds:
            # Date separation
            train_dates = set(fold.train_dates)
            val_dates = set(fold.val_dates)
            test_dates = set(fold.test_dates)

            self.assertEqual(len(train_dates & test_dates), 0)
            self.assertEqual(len(val_dates & test_dates), 0)
            self.assertEqual(len(train_dates & val_dates), 0)

            # Chronological progression: all train dates < test dates
            self.assertLess(max(fold.train_dates), min(fold.test_dates))
            self.assertLess(max(fold.val_dates), min(fold.test_dates))

            # Zero reserved family leakage
            for fid in fold.train_families + fold.val_families + fold.test_families:
                self.assertFalse(mgr.is_holdout_family(fid))

    def test_steady_windows_baseline_counts(self):
        """Verify baseline against unchanged sealed dataset (steady_windows.parquet).
        
        16,128 total steady windows, 2,578 reserved-family windows excluded,
        13,550 development windows, and 539 Sept 28 stopped-attempt windows excluded.
        """
        counts = verify_steady_windows_baseline()
        self.assertEqual(counts["total_windows"], 16128)
        self.assertEqual(counts["reserved_windows_excluded"], 2578)
        self.assertEqual(counts["development_windows"], 13550)
        self.assertEqual(counts["sept28_stopped_windows_excluded"], 539)


if __name__ == "__main__":
    unittest.main()
