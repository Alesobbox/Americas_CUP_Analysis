"""Unit tests for chronological splits, holdout isolation, and registration (T09)."""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.kinematic_ml.splits import (
    ChronologicalSplitManager,
    FinalTargetAccessGuard,
    register_experiment,
)


class TestAC75Splits(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

        # Mock frozen splits file
        self.frozen_splits_file = self.tmp_path / "frozen_evaluation_families.json"
        mock_frozen = {
            "status": "frozen",
            "holdout_dates": ["2024-10-01", "2024-10-02"],
            "reserved_holdout_families": ["fam_final_1", "fam_final_2"],
            "development_families": [f"fam_dev_{i}" for i in range(10)],
            "content_sha256": "mock_hash_123",
        }
        self.frozen_splits_file.write_text(json.dumps(mock_frozen), encoding="utf-8")

        self.consumed_ledger_file = self.tmp_path / "consumed_holdout_ledger.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chronological_outer_folds_isolation(self):
        """Verify expanding folds have no date overlap and strictly exclude holdout families."""
        mgr = ChronologicalSplitManager(self.frozen_splits_file)

        # 8 dates, 1 family per date
        family_dates = {
            "fam_dev_0": "2024-09-01",
            "fam_dev_1": "2024-09-02",
            "fam_dev_2": "2024-09-03",
            "fam_dev_3": "2024-09-04",
            "fam_dev_4": "2024-09-05",
            "fam_dev_5": "2024-09-06",
            "fam_dev_6": "2024-09-07",
            "fam_final_1": "2024-10-01",  # holdout
            "fam_final_2": "2024-10-02",  # holdout
        }

        folds = mgr.build_expanding_folds(family_dates, min_train_days=3, val_days_count=1)
        self.assertGreaterEqual(len(folds), 1)

        for fold in folds:
            # Check disjointness of train, val, and test dates
            train_set = set(fold.train_dates)
            val_set = set(fold.val_dates)
            test_set = set(fold.test_dates)

            self.assertEqual(len(train_set & test_set), 0, "Train and test dates must not overlap")
            self.assertEqual(len(val_set & test_set), 0, "Val and test dates must not overlap")
            self.assertEqual(len(train_set & val_set), 0, "Pure train and val dates must not overlap")

            # Check no holdout family leaked
            for fid in fold.train_families + fold.val_families + fold.test_families:
                self.assertFalse(mgr.is_holdout_family(fid), f"Holdout family {fid} leaked into fold {fold.fold_id}")

    def test_consumed_holdout_access_guard(self):
        """Verify that accessing final evaluation targets writes a permanent consumption entry."""
        guard = FinalTargetAccessGuard(self.consumed_ledger_file)
        guard.record_holdout_access("eval_runner", "gate_d_evaluation", ["fam_final_1", "fam_final_2"])

        ledger = json.loads(self.consumed_ledger_file.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["access_log"]), 1)
        entry = ledger["access_log"][0]
        self.assertEqual(entry["caller"], "eval_runner")
        self.assertEqual(entry["family_count"], 2)
        self.assertIn("fam_final_1", entry["families"])

    def test_experiment_registration(self):
        """Verify registering immutable experiment hashes."""
        reg_file = self.tmp_path / "experiment_registration.json"
        manifest_file = self.tmp_path / "dataset_manifest.json"
        manifest_file.write_text(json.dumps({"total_rows": 100}), encoding="utf-8")

        reg = register_experiment(
            "exp_001_nn_silu",
            ["tws_mps", "twa_sin", "twa_cos"],
            ["sog_mps"],
            "feedforward_nn_silu",
            {"lr": 0.001, "batch_size": 512},
            manifest_file,
            out_path=reg_file,
        )
        self.assertEqual(reg["experiment_id"], "exp_001_nn_silu")
        self.assertTrue(reg_file.exists())


if __name__ == "__main__":
    unittest.main()
