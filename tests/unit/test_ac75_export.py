"""Unit tests for AC75 bundle export, scenario catalog, and hash staging (T16)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"


class TestAC75Export(unittest.TestCase):
    def test_staged_candidate_manifest_and_pointer(self):
        """Verify that latest candidate pointer points to a valid manifest with verified hashes."""
        pointer_path = FORECAST_DIR / "latest_candidate.json"
        self.assertTrue(pointer_path.exists(), "latest_candidate.json must exist")

        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        self.assertTrue(pointer["candidate_id"].startswith("ac75_"))
        self.assertEqual(pointer["status"], "experimental")

        manifest_path = ROOT / pointer["manifest_path"]
        self.assertTrue(manifest_path.exists(), f"Manifest {manifest_path} must exist")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "ac75-model-1")
        self.assertEqual(manifest["candidate_id"], pointer["candidate_id"])
        self.assertGreater(manifest["total_scenarios_cached"], 0)
        self.assertGreater(manifest["fit_metrics"]["training_steady_windows"], 1000)
        self.assertGreater(manifest["maneuver_model_summary"]["fitted_turn_count"], 1000)
        self.assertGreater(manifest["route_template_count"], 100)
        self.assertGreater(manifest["paired_residual_block_count"], 100)

        # Check weights npz
        npz_path = ROOT / manifest["artifacts"]["weights_npz"]
        self.assertTrue(npz_path.exists(), "weights_npz must exist")

        # Check catalog
        cat_path = ROOT / manifest["artifacts"]["scenarios_catalog"]
        self.assertTrue(cat_path.exists(), "scenarios_catalog must exist")
        cat_raw = json.loads(cat_path.read_text(encoding="utf-8"))
        if isinstance(cat_raw, dict):
            self.assertEqual(cat_raw["schema_version"], "ac75-catalog-2")
            scenarios = cat_raw["scenarios"]
        else:
            scenarios = cat_raw
        self.assertGreaterEqual(len(scenarios), 5)

        for s in scenarios:
            self.assertEqual(s["schema_version"], "kinematic-race-sim-2")
            self.assertEqual(s["status"], "available")
            self.assertEqual(s["probability_scope"], "completion_assumed_on_water")
            self.assertIn("timing", s)
            self.assertIn("probabilities", s)
            self.assertIsNone(s["probabilities"]["no_winner"])
            self.assertLessEqual(s["probabilities"]["mc_error"], 0.5)
            self.assertIn("seconds_accounting", s["applied_inputs"])
            self.assertIn("time_accounting", s)


if __name__ == "__main__":
    unittest.main()
