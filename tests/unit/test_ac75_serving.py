"""Unit tests for AC75 exact serving, canonical request normalization, and service limits (Gate A Criterion 10)."""
import json
import math
import threading
import time
import unittest
from pathlib import Path

from pipeline.kinematic_ml.contracts import (
    compute_canonical_scenario_hash,
    knots_to_mps,
)
from pipeline.kinematic_ml.loader import load_staged_ac75_bundle
from pipeline.kinematic_ml.serving import (
    BROWSER_TRIAL_COUNTS,
    MAX_CONCURRENT_INFERENCE,
    MAX_PAYLOAD_BYTES,
    MAX_QUEUED_REQUESTS,
    PayloadTooLargeError,
    QueueFullError,
    ServingService,
    UnsupportedRequestError,
    is_allowed_loopback_host,
    is_allowed_same_origin,
    normalize_serving_request,
    reverse_scenario_v2_dict,
)

ROOT = Path(__file__).resolve().parents[2]


class TestAC75ServingExact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_staged_ac75_bundle(ROOT)
        cls.service = ServingService(bundle=cls.bundle, root=ROOT)

    def test_canonical_request_normalization(self):
        """Verify that requests are normalized once with SI values, canonical IDs, and authoritative hash."""
        raw_req = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": self.bundle.model_id,
            "team_a": "GB1",
            "team_b": "ETNZ",
            "course_id": "barcelona_lvc_4leg",
            "environment": {
                "tws_kt": 11.66,
                "wind_from_deg": 540.0,  # 540 % 360 = 180.0
            },
            "purpose": "preview",
        }
        norm = normalize_serving_request(raw_req, installed_model_id=self.bundle.model_id)

        # 1. Canonical competitors
        self.assertEqual(norm["team_a"], "ac37:INEOS")
        self.assertEqual(norm["team_b"], "ac37:ETNZ")

        # 2. Pinned model ID
        self.assertEqual(norm["model_id"], self.bundle.model_id)

        # 3. SI wind & normalized direction [0, 360)
        self.assertAlmostEqual(norm["environment"]["tws_mps"], knots_to_mps(11.66), places=4)
        self.assertEqual(norm["environment"]["wind_from_deg"], 180.0)

        # 4. Enforce browser trial counts
        self.assertEqual(norm["trial_count"], BROWSER_TRIAL_COUNTS["preview"])
        self.assertEqual(norm["trial_count"], 2000)

        # 5. Authoritative scenario hash
        self.assertIn("authoritative_hash", norm)
        self.assertEqual(len(norm["authoritative_hash"]), 64)

    def test_exact_serving_matches_fixtures_without_nearest_neighbor(self):
        """Gate A Criterion 10: Exact serving matches cached scenarios without nearest-neighbor fallback."""
        catalog = self.service.get_catalog_envelope()
        scenarios = catalog.get("scenarios", [])
        self.assertGreater(len(scenarios), 0, "Catalog must have pre-computed scenarios")

        # Pick a target cached scenario
        sample = next(s for s in scenarios if s.get("schema_version") == "kinematic-race-sim-2")
        inp = sample["applied_inputs"]
        ta = inp["team_a"]
        tb = inp["team_b"]
        tws_mps = float(inp["environment"]["tws_mps"])
        tws_kt = tws_mps * (3600.0 / 1852.0)
        twd_deg = float(inp["environment"].get("twd_deg", 180.0))

        # 1. Exact match returns the exact cached scenario
        req_exact = {
            "team_a": ta,
            "team_b": tb,
            "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
            "course_id": inp.get("course_id", "barcelona_lvc_4leg"),
            "purpose": "preview",
        }
        res_exact = self.service.simulate(req_exact)
        self.assertEqual(res_exact["scenario_id"], sample["scenario_id"])
        self.assertAlmostEqual(res_exact["probabilities"]["win_a"], sample["probabilities"]["win_a"], places=6)

        # 2. Exact reversal returns reversed scenario
        req_rev = {
            "team_a": tb,
            "team_b": ta,
            "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
            "course_id": inp.get("course_id", "barcelona_lvc_4leg"),
            "purpose": "preview",
        }
        res_rev = self.service.simulate(req_rev)
        self.assertAlmostEqual(res_rev["probabilities"]["win_a"], sample["probabilities"]["win_b"], places=6)
        self.assertAlmostEqual(res_rev["probabilities"]["win_b"], sample["probabilities"]["win_a"], places=6)
        self.assertAlmostEqual(res_rev["timing"]["mean_delta_t_s"], -sample["timing"]["mean_delta_t_s"], places=2)

        # 3. Off-by-small wind (e.g. 6.1 m/s vs cached 6.0 m/s) does NOT silently return nearest scenario 6.0 m/s!
        # It must compute a distinct, real on-demand simulation result
        req_off = {
            "team_a": ta,
            "team_b": tb,
            "environment": {"tws_mps": tws_mps + 0.15, "twd_deg": twd_deg},
            "course_id": inp.get("course_id", "barcelona_lvc_4leg"),
            "purpose": "preview",
        }
        res_off = self.service.simulate(req_off)
        # Must NOT return the cached scenario_id
        self.assertNotEqual(res_off["scenario_id"], sample["scenario_id"])
        self.assertAlmostEqual(res_off["applied_inputs"]["environment"]["tws_mps"], tws_mps + 0.15, places=2)

    def test_payload_limit_enforcement(self):
        """Requests exceeding 2 KiB payload limit are rejected."""
        giant_request = {
            "team_a": "ac37:ETNZ",
            "team_b": "ac37:INEOS",
            "tws_kt": 12.0,
            "padding": "x" * 2500,
        }
        with self.assertRaises(PayloadTooLargeError):
            normalize_serving_request(json.dumps(giant_request), installed_model_id=self.bundle.model_id)

    def test_wind_range_and_identity_rejection(self):
        """Unsupported wind speeds (< 6 or > 24 kt) and unknown competitors are rejected."""
        # 1. Wind speed too high
        with self.assertRaises(UnsupportedRequestError):
            normalize_serving_request(
                {"team_a": "ac37:ETNZ", "team_b": "ac37:INEOS", "tws_kt": 30.0},
                installed_model_id=self.bundle.model_id,
            )

        # 2. Wind speed too low
        with self.assertRaises(UnsupportedRequestError):
            normalize_serving_request(
                {"team_a": "ac37:ETNZ", "team_b": "ac37:INEOS", "tws_kt": 4.0},
                installed_model_id=self.bundle.model_id,
            )

        # 3. Unknown team
        with self.assertRaises(UnsupportedRequestError):
            normalize_serving_request(
                {"team_a": "ac37:ETNZ", "team_b": "INVALID_TEAM", "tws_kt": 12.0},
                installed_model_id=self.bundle.model_id,
            )

        # 4. Same competitor
        with self.assertRaises(UnsupportedRequestError):
            normalize_serving_request(
                {"team_a": "ac37:ETNZ", "team_b": "ac37:ETNZ", "tws_kt": 12.0},
                installed_model_id=self.bundle.model_id,
            )

    def test_concurrency_and_queue_depth_limits(self):
        """Enforce at most 1 running inference process and at most 4 queued requests."""
        # Create a mock slow service to test concurrency
        slow_service = ServingService(bundle=self.bundle, root=ROOT)

        results = []
        errors = []

        def worker(req_id: int):
            try:
                # Use uncached wind so it enters semaphore
                req = {
                    "team_a": "ac37:ETNZ",
                    "team_b": "ac37:INEOS",
                    "environment": {"tws_mps": 7.33 + req_id * 0.01, "twd_deg": 180.0},
                    "purpose": "preview",
                }
                res = slow_service.simulate(req)
                results.append(res)
            except Exception as e:
                errors.append(e)

        from unittest.mock import patch
        from pipeline.kinematic_ml.contracts import ScenarioV2Result

        def slow_predict(*args, **kwargs):
            time.sleep(0.05)
            return ScenarioV2Result(status="available")

        with patch("pipeline.kinematic_ml.serving.service.predict_scenario", side_effect=slow_predict):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # At least some requests should have succeeded, and overflow should have raised QueueFullError
        queue_full_errors = [e for e in errors if isinstance(e, QueueFullError)]
        self.assertGreater(len(queue_full_errors), 0, "Excess requests must raise QueueFullError")
        self.assertGreater(len(results), 0, "Allowed requests must succeed")

    def test_loopback_host_and_origin_verification(self):
        """Loopback peer, Host, and Origin constraints must be strictly verified."""
        self.assertTrue(is_allowed_loopback_host("localhost:5173"))
        self.assertTrue(is_allowed_loopback_host("127.0.0.1:5173"))
        self.assertTrue(is_allowed_loopback_host("[::1]:5173"))
        self.assertFalse(is_allowed_loopback_host("evil.com:5173"))
        self.assertFalse(is_allowed_loopback_host("192.168.1.100:5173"))

        self.assertTrue(is_allowed_same_origin("http://localhost:5173", "localhost:5173"))
        self.assertTrue(is_allowed_same_origin("http://127.0.0.1:5173", "127.0.0.1:5173"))
        self.assertFalse(is_allowed_same_origin("http://attacker.com", "localhost:5173"))

    def test_exact_unrounded_wind_and_purpose_trials_bypass_cache(self):
        """Verify 6.0004 m/s vs 6.0 m/s and standard/10000 trials do not collide on cached scenarios."""
        req_60004 = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": self.bundle.model_id,
            "team_a": "ETNZ",
            "team_b": "INEOS",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 6.0004, "twd_deg": 180.0},
            "purpose": "preview",
        }
        res_60004 = self.service.simulate(req_60004)
        self.assertEqual(res_60004["applied_inputs"]["environment"]["tws_mps"], 6.0004)
        self.assertEqual(res_60004["applied_inputs"]["purpose"], "preview")
        self.assertEqual(res_60004["applied_inputs"]["trial_count"], 2000)

        req_standard = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": self.bundle.model_id,
            "team_a": "ETNZ",
            "team_b": "INEOS",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 6.0, "twd_deg": 180.0},
            "purpose": "standard",
            "trial_count": 10000,
        }
        res_std = self.service.simulate(req_standard)
        self.assertEqual(res_std["applied_inputs"]["environment"]["tws_mps"], 6.0)
        self.assertEqual(res_std["applied_inputs"]["purpose"], "standard")
        self.assertEqual(res_std["applied_inputs"]["trial_count"], 10000)
        self.assertNotEqual(res_60004["scenario_id"], res_std["scenario_id"])

    def test_fail_closed_validation_rejects_bad_requests(self):
        """Verify unknown keys, contradictory fields, wrong model_id, and bad purpose raise UnsupportedRequestError."""
        base = {
            "schema_version": "ac75-scenario-request-1",
            "model_id": self.bundle.model_id,
            "team_a": "ETNZ",
            "team_b": "INEOS",
            "course_id": "barcelona_lvc_4leg",
            "environment": {"tws_mps": 8.0, "twd_deg": 180.0},
            "purpose": "preview",
        }
        bad_requests = [
            dict(base, unexpected_field=123),
            dict(base, environment={"tws_mps": 8.0, "twd_deg": 180.0, "extra_env": True}),
            dict(base, environment={"tws_mps": 8.0, "tws_kt": 19.0, "twd_deg": 180.0}),
            dict(base, environment={"tws_mps": 8.0, "twd_deg": 180.0, "wind_from_deg": 90.0}),
            dict(base, model_id="ac75_wrong_model_id"),
            dict(base, purpose="ultra"),
            dict(base, trial_count=-5),
            dict(base, trial_count=2000, n_sims=5000),
        ]
        for bad in bad_requests:
            with self.assertRaises(UnsupportedRequestError, msg=f"Should reject {bad}"):
                self.service.simulate(bad)


if __name__ == "__main__":
    unittest.main()
