"""Unit tests for private candidate forecast bundle generation, covariance propagation, and diff tracking."""
import json
from pathlib import Path
import unittest

from pipeline.prediction.build import build_private_forecast_bundle
from pipeline.prediction.cup import TEAM_IDS

ROOT = Path(__file__).resolve().parents[2]


class TestPrivateCandidateBundle(unittest.TestCase):

    def test_build_private_forecast_bundle_end_to_end(self):
        bundle = build_private_forecast_bundle(
            ROOT,
            prefer_official=True,
            propagate_covariance=True,
            include_transfer_uncertainty=True,
            trials=20,
            seed=42,
        )
        bundle_dir = Path(bundle["bundle_dir"])
        self.assertTrue(bundle_dir.is_dir())
        self.assertFalse(bundle_dir.resolve().is_relative_to((ROOT / "public").resolve()))

        # Verify artifacts
        self.assertTrue((bundle_dir / "bundle.json").is_file())
        self.assertTrue((bundle_dir / "evaluation.json").is_file())
        self.assertTrue((bundle_dir / "diff_vs_public.json").is_file())

        # Check model has covariance
        model_file = bundle_dir / "models" / f"{bundle['candidate_model_ref']}.json"
        self.assertTrue(model_file.is_file())
        model_data = json.loads(model_file.read_text(encoding="utf-8"))
        self.assertIn("covariance_matrix", model_data["strength"])

        # Check diff vs public
        diff_data = json.loads((bundle_dir / "diff_vs_public.json").read_text(encoding="utf-8"))
        self.assertEqual(diff_data["schema_version"], "candidate-diff-vs-public-1")
        for team in TEAM_IDS:
            self.assertIn(team, diff_data["team_diffs"])
            self.assertIn("rule_bounds", diff_data["team_diffs"][team])
            self.assertIn("scenario_envelope", diff_data["team_diffs"][team])


if __name__ == "__main__":
    unittest.main()
