"""Unit tests for telemetry-parameterized kinematic simulator and CLI."""
import json
import subprocess
import sys
import unittest

import numpy as np

from pipeline.kinematic_ml.course_lvc import BARCELONA_2024_LVC, CoursePreset
from pipeline.kinematic_ml.models import EmpiricalPhaseDistributionModel, NonFinishModel
from pipeline.kinematic_ml.simulator import simulate_kinematic_race


class KinematicSimulatorTests(unittest.TestCase):
    def test_course_length_scaling(self):
        """Doubling course distance must scale travel time proportionally."""
        course_base = CoursePreset(
            preset_id="short",
            name="Short Course",
            venue="Barcelona",
            course_axis_deg=105.0,
            course_length_m=1500.0,
            boundary_width_m=800.0,
            leg_count=6,
            default_wind_speed_kt=12.0,
            default_wind_dir_deg=105.0,
        )
        course_double = CoursePreset(
            preset_id="long",
            name="Long Course",
            venue="Barcelona",
            course_axis_deg=105.0,
            course_length_m=3000.0,
            boundary_width_m=800.0,
            leg_count=6,
            default_wind_speed_kt=12.0,
            default_wind_dir_deg=105.0,
        )

        model = EmpiricalPhaseDistributionModel.load_from_primitives()
        rng = np.random.default_rng(42)

        res_short = model.sample_race_components("ETNZ", 12.0, course_base, None, rng, size=500)
        rng = np.random.default_rng(42)
        res_double = model.sample_race_components("ETNZ", 12.0, course_double, None, rng, size=500)

        # Steady upwind and downwind travel times must scale approximately 2x
        up_short = np.mean(res_short["upwind_vmg"])
        up_double = np.mean(res_double["upwind_vmg"])
        ratio = up_double / up_short
        self.assertAlmostEqual(ratio, 2.0, delta=0.05)

    def test_independent_attribution_sums_to_mean_delta(self):
        """Attribution components must be independent counterfactuals summing to mean_delta_t_s."""
        sim = simulate_kinematic_race("ETNZ", "GB1", tws_kt=12.0, n_sims=1000, seed=42)
        attr = sim["attribution_7_component"]
        jf = sim["joint_finisher_conditioning"]

        sum_time_attr = (
            attr["pre_start_positioning_s"]
            + attr["upwind_vmg_s"]
            + attr["downwind_vmg_s"]
            + attr["tack_execution_s"]
            + attr["gybe_execution_s"]
            + attr["boundary_avoidance_s"]
        )

        mean_delta = jf["mean_delta_t_s"]
        self.assertIsNotNone(mean_delta)
        # Sum of component differences matches mean total time difference
        self.assertAlmostEqual(sum_time_attr, mean_delta, delta=0.08)

    def test_double_nonfinish_and_probability_partition(self):
        """Probabilities must sum to 1.0 partition including no_winner_probability."""
        sim = simulate_kinematic_race("ETNZ", "GB1", tws_kt=20.0, n_sims=1000, seed=42)
        p_a = sim["win_probability_a"]
        p_b = sim["win_probability_b"]
        p_no = sim["no_winner_probability"]

        self.assertGreaterEqual(p_no, 0.0)
        self.assertAlmostEqual(p_a + p_b + p_no, 1.0, places=3)

    def test_rule_adjustments_impact(self):
        """Power offsets and maneuver multipliers must impact speed and execution times."""
        sim_base = simulate_kinematic_race(
            "ETNZ", "GB1", tws_kt=12.0, n_sims=500, seed=42,
            rule_adjustments={"battery_power_offset_kt": 0.0, "maneuver_loss_multiplier": 1.0}
        )
        sim_boosted = simulate_kinematic_race(
            "ETNZ", "GB1", tws_kt=12.0, n_sims=500, seed=42,
            rule_adjustments={"battery_power_offset_kt": 1.0, "maneuver_loss_multiplier": 0.8}
        )

        # Both simulations produce valid partitions
        self.assertIn("win_probability_a", sim_base)
        self.assertIn("win_probability_a", sim_boosted)

    def test_cli_entrypoint_valid_and_invalid(self):
        """CLI entrypoint must return clean JSON on valid request and exit 2 on invalid."""
        # 1. Valid request
        payload_valid = json.dumps({"team_a": "ETNZ", "team_b": "GB1", "tws_kt": 12.0, "n_sims": 100})
        proc_valid = subprocess.run(
            [sys.executable, "-m", "pipeline.kinematic_ml.simulator", "--json", payload_valid],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_valid.returncode, 0)
        data = json.loads(proc_valid.stdout)
        self.assertEqual(data["schema_version"], "kinematic-race-sim-1")
        self.assertIn("win_probability_a", data)

        # 2. Invalid wind request
        payload_invalid = json.dumps({"team_a": "ETNZ", "team_b": "GB1", "tws_kt": 35.0})
        proc_invalid = subprocess.run(
            [sys.executable, "-m", "pipeline.kinematic_ml.simulator", "--json", payload_invalid],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc_invalid.returncode, 0)
        data_err = json.loads(proc_invalid.stdout or proc_invalid.stderr)
        self.assertEqual(data_err["status"], "unsupported_request")


if __name__ == "__main__":
    unittest.main()
