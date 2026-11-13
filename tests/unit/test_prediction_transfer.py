"""Unit tests for the AC37-to-AC38 calibrated joint transfer model."""
import json
import math
from pathlib import Path
import unittest

import numpy as np

from pipeline.prediction.cup import (
    TEAM_IDS,
    build_roster_mapping_matrix,
    map_ac40_to_cup,
    map_ac40_to_cup_with_covariance,
)
from pipeline.prediction.transfer import (
    SHARED_AC37_TEAMS,
    estimate_transfer_two_stage,
    evaluate_grid,
    extract_percentiles,
    fit_transfer_model,
    helmert_contrasts,
    solve_joint_laplace_mode,
)


class TestPredictionTransfer(unittest.TestCase):

    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]

    def test_helmert_contrasts_properties(self):
        """Helmert basis Q must be 6x5 orthonormal and sum to zero across rows."""
        Q = helmert_contrasts(6)
        self.assertEqual(Q.shape, (6, 5))
        self.assertTrue(np.allclose(Q.T @ Q, np.eye(5), atol=1e-12))
        self.assertTrue(np.allclose(Q.T @ np.ones(6), np.zeros(5), atol=1e-12))
        proj = np.eye(6) - (1.0 / 6.0) * np.ones((6, 6))
        self.assertTrue(np.allclose(Q @ Q.T, proj, atol=1e-12))

    def test_roster_covariance_propagation(self):
        """Test covariance mapping A Sigma A^T across equal, principal_only, assumed_10_02."""
        entries = ["NZL B", "NZL G", "GBR B", "GBR G", "ITA B", "ITA G", "SUI", "USA", "FRA"]
        k = len(entries)
        effects = {e: 0.1 * i for i, e in enumerate(entries)}
        rng = np.random.default_rng(42)
        X = rng.normal(size=(k, k))
        cov_entry = X.T @ X + np.eye(k)
        
        for pol in ("equal", "principal_only", "assumed_10_02"):
            mapped, sds, cov_syndicate = map_ac40_to_cup_with_covariance(
                effects, cov_entry, entries, policy=pol
            )
            self.assertEqual(len(mapped), 6)
            for team in mapped:
                self.assertGreater(sds[team], 0.0)
            self.assertTrue(np.allclose(cov_syndicate, cov_syndicate.T, atol=1e-12))
            eigvals = np.linalg.eigvalsh(cov_syndicate)
            self.assertTrue(np.all(eigvals >= -1e-10))

    def test_synthetic_recovery_positive_beta(self):
        """Simulate from known beta=0.7, tau=0.4 and recover parameters without clipping."""
        rng = np.random.default_rng(12345)
        Q = helmert_contrasts(6)
        kappa = 1.8
        sigma_40 = 1.2
        beta_true = 0.7
        tau_true = 0.4
        
        z40_true = rng.normal(0.0, sigma_40, size=5)
        z75_true = beta_true * z40_true + rng.normal(0.0, tau_true, size=5)
        th40 = Q @ z40_true
        th75 = Q @ z75_true
        
        d40_stages = []
        for _ in range(50):
            order = list(rng.permutation(6))
            for k in range(len(order) - 1):
                choice = order[k:]
                logits = kappa * th40[choice]
                p = np.exp(logits - np.max(logits))
                p /= np.sum(p)
                winner_idx = int(rng.choice(len(choice), p=p))
                reordered = [choice[winner_idx]] + [c for i, c in enumerate(choice) if i != winner_idx]
                d40_stages.append(Q[reordered, :])
                
        d75_matches = []
        for i in range(6):
            for j in range(i + 1, 6):
                for _ in range(8):
                    prob_i = 1.0 / (1.0 + math.exp(-kappa * (th75[i] - th75[j])))
                    if rng.uniform() < prob_i:
                        d75_matches.append(Q[i] - Q[j])
                    else:
                        d75_matches.append(Q[j] - Q[i])
        d75_matches_arr = np.array(d75_matches, dtype=float)
        
        betas = np.linspace(-1.0, 2.0, 19)
        etas = np.linspace(math.log(0.1), math.log(1.5), 17)
        _, weights, best_z, mode_info = evaluate_grid(
            betas, etas, d40_stages, d75_matches_arr, sigma_40=sigma_40, kappa=kappa
        )
        b_pct, tau_pct, rho_pct = extract_percentiles(betas, etas, weights, sigma_40=sigma_40)
        
        self.assertLess(mode_info["boundary_mass"], 0.05)
        self.assertAlmostEqual(b_pct["p50"], beta_true, delta=0.40)
        self.assertAlmostEqual(tau_pct["p50"], tau_true, delta=0.35)
        self.assertGreater(rho_pct["p50"], 0.40)

    def test_synthetic_recovery_unclipped_negative_beta(self):
        """Simulate from known negative beta=-0.6, tau=0.4 and verify negative recovery."""
        rng = np.random.default_rng(54321)
        Q = helmert_contrasts(6)
        kappa = 1.8
        sigma_40 = 1.2
        beta_true = -0.6
        tau_true = 0.4
        
        z40_true = rng.normal(0.0, sigma_40, size=5)
        z75_true = beta_true * z40_true + rng.normal(0.0, tau_true, size=5)
        th40 = Q @ z40_true
        th75 = Q @ z75_true
        
        d40_stages = []
        for _ in range(50):
            order = list(rng.permutation(6))
            for k in range(len(order) - 1):
                choice = order[k:]
                logits = kappa * th40[choice]
                p = np.exp(logits - np.max(logits))
                p /= np.sum(p)
                winner_idx = int(rng.choice(len(choice), p=p))
                reordered = [choice[winner_idx]] + [c for i, c in enumerate(choice) if i != winner_idx]
                d40_stages.append(Q[reordered, :])
                
        d75_matches = []
        for i in range(6):
            for j in range(i + 1, 6):
                for _ in range(8):
                    prob_i = 1.0 / (1.0 + math.exp(-kappa * (th75[i] - th75[j])))
                    if rng.uniform() < prob_i:
                        d75_matches.append(Q[i] - Q[j])
                    else:
                        d75_matches.append(Q[j] - Q[i])
        d75_matches_arr = np.array(d75_matches, dtype=float)
        
        betas = np.linspace(-1.5, 1.0, 19)
        etas = np.linspace(math.log(0.1), math.log(1.5), 17)
        _, weights, _, mode_info = evaluate_grid(
            betas, etas, d40_stages, d75_matches_arr, sigma_40=sigma_40, kappa=kappa
        )
        b_pct, _, rho_pct = extract_percentiles(betas, etas, weights, sigma_40=sigma_40)
        
        self.assertLess(b_pct["p50"], -0.1)
        self.assertLess(rho_pct["p50"], -0.1)

    def test_fit_transfer_model_real_data(self):
        """Fit joint transfer model on documented AC37 and AC38 results."""
        result = fit_transfer_model(self.root, policy="equal", check_refinement=False,
                                    n_beta=21, n_eta=19)
        self.assertEqual(result.schema_version, "ac37-transfer-2")
        self.assertLessEqual(result.rho_mode, 1.0)
        self.assertGreaterEqual(result.rho_mode, -1.0)
        self.assertLess(result.boundary_mass, 1e-2)
        self.assertEqual(len(result.team_effects_ac75), 6)
        self.assertEqual(len(result.team_effects_ac40), 6)
        self.assertAlmostEqual(sum(result.team_effects_ac75.values()), 0.0, places=3)
        self.assertAlmostEqual(sum(result.team_effects_ac40.values()), 0.0, places=3)
        self.assertIn("ORIENT_EXPRESS", result.team_effects_ac75)
        self.assertIn("ORIENT_EXPRESS", result.team_effects_ac40)

    def test_run_transfer_study_artifact_contract(self):
        """Verify run_transfer_study output schema and 6-team presence."""
        from pipeline.prediction.transfer import run_transfer_study
        artifact_path = self.root / ".forecast" / "transfer" / "ac37_transfer.json"
        self.assertTrue(artifact_path.exists())
        doc = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], "ac37-transfer-study-2")
        self.assertEqual(doc["n_shared_teams"], 6)
        self.assertEqual(doc["ac40_source"], "ac37_2023")
        self.assertIn("ORIENT_EXPRESS", doc["ac40_strengths"])
        self.assertIn("ORIENT_EXPRESS", doc["ac75_empirical_strengths"])
        self.assertEqual(len(doc["shared_teams"]), 6)


if __name__ == "__main__":
    unittest.main()
