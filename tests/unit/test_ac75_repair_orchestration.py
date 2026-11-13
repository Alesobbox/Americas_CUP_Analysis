"""Focused unit tests for AC75 repair experiment orchestration CLI (R1/P0)."""
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.kinematic_ml.cli import main, run_repair

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"


class TestAC75RepairOrchestration(unittest.TestCase):
    def test_repair_cli_help(self):
        """Verify repair subcommand help output and argument parsing."""
        with self.assertRaises(SystemExit) as cm:
            main(["repair", "--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_repair_prepare_phase_and_resumption(self):
        """Verify prepare phase executes preservation/environment checks and supports --resume."""
        reg_path = FORECAST_DIR / "experiments" / "repair_experiment_v1.json"
        if not reg_path.exists():
            self.skipTest("repair_experiment_v1.json not registered yet")

        # 1. Run prepare phase
        receipt = run_repair(reg_path, phase="prepare", resume=False)
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertTrue(receipt["output_ids"]["frozen_families_present"])
        self.assertTrue(receipt["output_ids"]["sealed_dataset_present"])

        # 2. Run with --resume: must return cached receipt with resumed=True
        resumed_receipt = run_repair(reg_path, phase="prepare", resume=True)
        self.assertEqual(resumed_receipt["status"], "complete")
        self.assertTrue(resumed_receipt.get("resumed", False))

    def test_repair_missing_registration_fails_gracefully(self):
        """Verify non-existent registration returns failure receipt with code 1."""
        receipt = run_repair("non_existent_registration_file.json", phase="prepare")
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["exit_code"], 1)
        self.assertTrue(any("Registration file not found" in r for r in receipt["reason_codes"]))

    def test_repair_verify_phase(self):
        """Verify verify phase runs preservation verification cleanly."""
        reg_path = FORECAST_DIR / "experiments" / "repair_experiment_v1.json"
        if not reg_path.exists():
            self.skipTest("repair_experiment_v1.json not registered yet")

        receipt = run_repair(reg_path, phase="verify")
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["counts"]["mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
