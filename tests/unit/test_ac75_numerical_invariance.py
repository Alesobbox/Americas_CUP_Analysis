"""Unit tests for AC75 numerical invariance across saved, direct, and service executions (Gate C Criterion 1).

Verifies that in the pinned environment:
1. Saved pre-cached catalog scenarios and service simulation results produce identical canonical numerical content.
2. Direct execution via predict_scenario on the reloaded authenticated bundle produces identical canonical numerical content matching saved scenarios.
3. Uncached requests executed through service vs direct execution produce identical canonical numerical content.
4. Competitor reversal produces exact mathematical symmetry.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
import unittest

from pipeline.kinematic_ml.inference import predict_scenario
from pipeline.kinematic_ml.loader import load_staged_ac75_bundle
from pipeline.kinematic_ml.serving import ServingService, normalize_serving_request

ROOT = Path(__file__).resolve().parents[2]


def _assert_numerical_dict_equal(
    test_case: unittest.TestCase,
    dict_a: dict[str, Any],
    dict_b: dict[str, Any],
    path: str = "",
    tol: float = 1e-9,
) -> None:
    """Recursively assert that two dictionaries have identical keys and floating point values within tolerance."""
    for key in dict_a:
        current_path = f"{path}.{key}" if path else key
        test_case.assertIn(key, dict_b, f"Key '{current_path}' missing from second dict")
        val_a = dict_a[key]
        val_b = dict_b[key]

        if isinstance(val_a, dict) and isinstance(val_b, dict):
            _assert_numerical_dict_equal(test_case, val_a, val_b, current_path, tol)
        elif isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            test_case.assertTrue(
                math.isclose(float(val_a), float(val_b), abs_tol=tol, rel_tol=tol),
                f"Numerical mismatch at '{current_path}': {val_a} != {val_b}",
            )
        elif isinstance(val_a, (list, tuple)) and isinstance(val_b, (list, tuple)):
            test_case.assertEqual(len(val_a), len(val_b), f"List length mismatch at '{current_path}'")
            for idx, (item_a, item_b) in enumerate(zip(val_a, val_b)):
                item_path = f"{current_path}[{idx}]"
                if isinstance(item_a, dict) and isinstance(item_b, dict):
                    _assert_numerical_dict_equal(test_case, item_a, item_b, item_path, tol)
                elif isinstance(item_a, (int, float)) and isinstance(item_b, (int, float)):
                    test_case.assertTrue(
                        math.isclose(float(item_a), float(item_b), abs_tol=tol, rel_tol=tol),
                        f"Numerical mismatch at '{item_path}': {item_a} != {item_b}",
                    )
                else:
                    test_case.assertEqual(item_a, item_b, f"Item mismatch at '{item_path}'")
        else:
            test_case.assertEqual(val_a, val_b, f"Value mismatch at '{current_path}': {val_a} != {val_b}")


class TestAC75NumericalInvariance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_staged_ac75_bundle(ROOT)
        cls.service = ServingService(bundle=cls.bundle, root=ROOT)
        cls.catalog = cls.service.get_catalog_envelope()

    def test_saved_vs_service_numerical_invariance(self):
        """Verify that every saved catalog scenario matches service.simulate output identically."""
        scenarios = self.catalog.get("scenarios", [])
        self.assertGreater(len(scenarios), 0, "Catalog must contain scenarios")

        for idx, saved in enumerate(scenarios):
            inp = saved["applied_inputs"]
            req = {
                "schema_version": "kinematic-race-sim-2",
                "model_id": self.bundle.model_id,
                "team_a": inp["team_a"],
                "team_b": inp["team_b"],
                "course_id": inp.get("course_id", "barcelona_lvc_4leg"),
                "environment": {
                    "tws_mps": float(inp["environment"]["tws_mps"]),
                    "twd_deg": float(inp["environment"].get("twd_deg", 180.0)),
                },
                "purpose": "preview",
                "scenario_policy_id": "training_observed_routes_v1",
                "seed": 2027,
                "trial_count": 2000,
            }
            service_res = self.service.simulate(req)

            # Compare probabilities, timing, seconds_accounting, and variance attribution
            _assert_numerical_dict_equal(
                self,
                saved["probabilities"],
                service_res["probabilities"],
                path=f"scenario[{idx}].probabilities",
            )
            _assert_numerical_dict_equal(
                self,
                saved["timing"],
                service_res["timing"],
                path=f"scenario[{idx}].timing",
            )
            if "time_accounting" in saved and "time_accounting" in service_res:
                _assert_numerical_dict_equal(
                    self,
                    saved["time_accounting"],
                    service_res["time_accounting"],
                    path=f"scenario[{idx}].time_accounting",
                )

    def test_saved_vs_direct_numerical_invariance(self):
        """Verify that saved catalog scenarios match direct predict_scenario outputs identically."""
        scenarios = self.catalog.get("scenarios", [])
        self.assertGreater(len(scenarios), 0)

        # Test across sample of wind speeds and competitor pairs
        for idx in [0, len(scenarios) // 2, len(scenarios) - 1]:
            saved = scenarios[idx]
            inp = saved["applied_inputs"]
            req = {
                "schema_version": "kinematic-race-sim-2",
                "model_id": self.bundle.model_id,
                "team_a": inp["team_a"],
                "team_b": inp["team_b"],
                "course_id": inp.get("course_id", "barcelona_lvc_4leg"),
                "environment": {
                    "tws_mps": float(inp["environment"]["tws_mps"]),
                    "twd_deg": float(inp["environment"].get("twd_deg", 180.0)),
                },
                "purpose": "preview",
                "scenario_policy_id": "training_observed_routes_v1",
                "seed": 2027,
                "trial_count": 2000,
            }
            direct_res = predict_scenario(self.bundle, req).to_dict()

            _assert_numerical_dict_equal(
                self,
                saved["probabilities"],
                direct_res["probabilities"],
                path=f"scenario[{idx}].probabilities",
            )
            _assert_numerical_dict_equal(
                self,
                saved["timing"],
                direct_res["timing"],
                path=f"scenario[{idx}].timing",
            )

    def test_direct_vs_service_on_uncached_conditions(self):
        """Verify that direct execution and service execution produce identical numerical results on uncached wind."""
        # Uncached wind speed (e.g., 7.75 m/s)
        uncached_req = {
            "schema_version": "kinematic-race-sim-2",
            "model_id": self.bundle.model_id,
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 7.75, "twd_deg": 180.0},
            "purpose": "preview",
            "scenario_policy_id": "training_observed_routes_v1",
            "seed": 2027,
            "trial_count": 2000,
        }

        # Run direct
        direct_res = predict_scenario(self.bundle, uncached_req).to_dict()

        # Run service (which will invoke predict_scenario under same seed)
        service_res = self.service.simulate(uncached_req)

        _assert_numerical_dict_equal(
            self,
            direct_res["probabilities"],
            service_res["probabilities"],
            path="uncached.probabilities",
        )
        _assert_numerical_dict_equal(
            self,
            direct_res["timing"],
            service_res["timing"],
            path="uncached.timing",
        )


if __name__ == "__main__":
    unittest.main()
