from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np

from pipeline.prediction.ac38_evidence import build_eligibility_ledger, is_valid_independent_evidence
from pipeline.prediction.ac38_forecast import build_ac38_forecast_candidate, publish_ac38_forecast
from pipeline.prediction.ac38_model import (
    compute_pairwise_and_series,
    draw_ac38_ac75_worlds,
    fit_ac38_ac40_strengths,
    map_ac38_entries_to_ac75_syndicates,
)
from pipeline.prediction.ac38_telemetry import (
    TELEM_DIMS,
    apply_fold_standardization,
    fit_fold_standardization,
    fit_pl_with_telemetry,
)
from pipeline.prediction.contracts import validate_ac38_forecast
from pipeline.prediction.cup import TEAM_IDS, CupRules, CupScenario, simulate_cup
from pipeline.prediction.transfer_fit import fit_transfer_from_arrays
from pipeline.prediction.transfer_num import evaluate_grid, extract_percentiles, helmert_contrasts


ROOT = Path(__file__).resolve().parents[2]


def _synthetic_transfer_data(true_beta: float, seed: int = 42, kappa: float = 1.0):
    rng = np.random.default_rng(seed)
    q_mat = helmert_contrasts(6)
    z40 = rng.normal(0.0, 1.2, size=5)
    z75 = true_beta * z40 + rng.normal(0.0, 0.35, size=5)
    th40 = q_mat @ z40
    th75 = q_mat @ z75
    d40_stages: list[np.ndarray] = []
    for _ in range(45):
        rem = list(range(6))
        while len(rem) >= 2:
            logits = kappa * th40[rem]
            p = np.exp(logits - np.max(logits))
            p /= np.sum(p)
            pick = int(rng.choice(len(rem), p=p))
            reordered = [rem[pick]] + [r for idx, r in enumerate(rem) if idx != pick]
            d40_stages.append(q_mat[reordered, :])
            rem = reordered[1:]
    d75_matches: list[np.ndarray] = []
    for i in range(6):
        for j in range(i + 1, 6):
            for _ in range(5):
                p = 1.0 / (1.0 + np.exp(-kappa * (th75[i] - th75[j])))
                d75_matches.append(q_mat[i] - q_mat[j] if rng.random() < p else q_mat[j] - q_mat[i])
    return d40_stages, np.asarray(d75_matches, dtype=float)


class Ac38TransferModelTests(unittest.TestCase):
    def test_synthetic_positive_zero_negative_transfer_recovery(self) -> None:
        for idx, (true_beta, sign_check) in enumerate(((1.1, "pos"), (0.0, "zero"), (-1.0, "neg"))):
            d40_stages, d75_matches = _synthetic_transfer_data(true_beta, seed=100 + idx, kappa=1.0)
            res = fit_transfer_from_arrays(
                d40_stages, d75_matches, sigma_40=1.2, kappa=1.0,
                n_beta=31, n_eta=25, check_refinement=False,
            )
            self.assertTrue(res.grid_converged)
            self.assertEqual(res.kappa, 1.0)
            if sign_check == "pos":
                self.assertGreater(res.beta_percentiles["p50"], 0.35)
            elif sign_check == "zero":
                self.assertLess(res.beta_percentiles["p05"], 0.45)
                self.assertGreater(res.beta_percentiles["p95"], -0.45)
            else:
                self.assertLess(res.beta_percentiles["p50"], -0.35)

    def test_coarse_boundary_grid_flags_excess_boundary_mass(self) -> None:
        d40_stages, d75_matches = _synthetic_transfer_data(1.5, seed=7, kappa=1.0)
        betas = np.linspace(-0.2, 0.2, 5)
        etas = np.linspace(np.log(0.1), np.log(0.5), 5)
        _, weights, _, mode_info = evaluate_grid(betas, etas, d40_stages, d75_matches, sigma_40=1.2, kappa=1.0)
        self.assertTrue(mode_info["all_points_converged"])
        self.assertGreater(mode_info["boundary_mass"], 1e-3)
        b_pct, tau_pct, _ = extract_percentiles(betas, etas, weights, sigma_40=1.2)
        self.assertLessEqual(b_pct["p05"], b_pct["p50"])
        self.assertLessEqual(b_pct["p50"], b_pct["p95"])
        self.assertGreater(tau_pct["p05"], 0.0)


class Ac38TelemetryAndCutoffTests(unittest.TestCase):
    def test_missing_telemetry_never_imputed_to_zero(self) -> None:
        orders = [["A", "B", "C"], ["B", "A", "C"], ["A", "C", "B"], ["C", "B", "A"]]
        entrants = ["A", "B", "C"]
        z1 = [{e: np.array([1.0, 0.5, -0.5, 0.2]) for e in o} for o in orders]
        z2 = [{e: np.array([99.0, -99.0, 42.0, -77.0]) for e in o} for o in orders]
        m_false = [{e: np.zeros(len(TELEM_DIMS), dtype=bool) for e in o} for o in orders]
        fit1 = fit_pl_with_telemetry(orders, z1, m_false, entrants=entrants)
        fit2 = fit_pl_with_telemetry(orders, z2, m_false, entrants=entrants)
        for e in entrants:
            self.assertAlmostEqual(fit1["theta"][e], fit2["theta"][e], places=10)
        for g1, g2 in zip(fit1["gamma"].values(), fit2["gamma"].values()):
            self.assertAlmostEqual(g1, 0.0, places=8)
            self.assertAlmostEqual(g2, 0.0, places=8)

        lagged = [
            {
                "A": {
                    "values": {"upwind_vmg": None, "downwind_vmg": 0.1, "tack_retention": None, "gybe_retention": 0.2},
                    "available": {"upwind_vmg": False, "downwind_vmg": True, "tack_retention": False, "gybe_retention": True},
                },
                "B": {
                    "values": {"upwind_vmg": 0.3, "downwind_vmg": -0.2, "tack_retention": 0.4, "gybe_retention": -0.1},
                    "available": {"upwind_vmg": True, "downwind_vmg": True, "tack_retention": True, "gybe_retention": True},
                },
            },
            {
                "A": {
                    "values": {"upwind_vmg": 0.5, "downwind_vmg": 0.3, "tack_retention": 0.1, "gybe_retention": 0.4},
                    "available": {"upwind_vmg": True, "downwind_vmg": True, "tack_retention": True, "gybe_retention": True},
                },
                "B": {
                    "values": {"upwind_vmg": -0.2, "downwind_vmg": 0.0, "tack_retention": -0.3, "gybe_retention": 0.1},
                    "available": {"upwind_vmg": True, "downwind_vmg": True, "tack_retention": True, "gybe_retention": True},
                },
            },
        ]
        stats = fit_fold_standardization(lagged, [["A", "B"], ["A", "B"]])
        z_map, m_map = apply_fold_standardization(lagged[0], stats, ["A", "B"])
        self.assertFalse(bool(m_map["A"][0]))
        self.assertEqual(float(z_map["A"][0]), 0.0)
        self.assertTrue(bool(m_map["A"][1]))

    def test_cutoff_leakage_blocks_future_races(self) -> None:
        early = fit_ac38_ac40_strengths(ROOT, issuance_cutoff_utc="2026-05-21T00:00:00Z")
        full = fit_ac38_ac40_strengths(ROOT, issuance_cutoff_utc="2026-10-01T00:00:00Z")
        self.assertEqual(len(early["race_ids"]), 0)
        self.assertGreaterEqual(len(full["race_ids"]), 16)
        ledger = build_eligibility_ledger(ROOT, issuance_cutoff_utc="2026-05-21T00:00:00Z", write=False)
        self.assertTrue(any(row["exclusion_reason"] == "after_issuance_cutoff_utc" for row in ledger["ac38_observations"]))


class Ac38MappingAndUpdatesTests(unittest.TestCase):
    def test_mapping_preserves_australia_prior_and_rejects_race_count_mixture(self) -> None:
        fit = fit_ac38_ac40_strengths(ROOT, issuance_cutoff_utc="2026-10-01T00:00:00Z")
        default_map = map_ac38_entries_to_ac75_syndicates(ROOT, fit)
        equal_map = map_ac38_entries_to_ac75_syndicates(ROOT, fit, mapping_policy="equal")
        by_def = {r["team_id"]: r for r in default_map.provenance}
        by_eq = {r["team_id"]: r for r in equal_map.provenance}
        self.assertFalse(by_def["AUSTRALIA"]["observed"])
        self.assertEqual(by_def["AUSTRALIA"]["basis"], "population_prior")
        self.assertIsNone(by_def["AUSTRALIA"]["mapped_ac40_mean"])
        self.assertTrue(by_def["ETNZ"]["observed"])
        self.assertEqual(len(by_def["ETNZ"]["source_entries"]), 1)
        if len(by_eq["ETNZ"]["source_entries"]) > 1:
            self.assertNotAlmostEqual(
                by_def["ETNZ"]["mapped_ac40_mean"], by_eq["ETNZ"]["mapped_ac40_mean"], places=4
            )

    def test_ac75_update_rejects_generic_url_duplicate_and_future_cutoff(self) -> None:
        post = json.loads((ROOT / ".forecast" / "ac38" / "transfer_posterior.json").read_text(encoding="utf-8"))
        fit = fit_ac38_ac40_strengths(ROOT, issuance_cutoff_utc="2026-10-01T00:00:00Z")
        mapping = map_ac38_entries_to_ac75_syndicates(ROOT, fit)

        with tempfile.TemporaryDirectory() as tmp:
            troot = Path(tmp)
            shutil.copytree(ROOT / "docs", troot / "docs")
            notice_dir = troot / ".forecast" / "evidence_sources"
            notice_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = notice_dir / "notice.json"
            payload = b'{"race":"r1","winner":"ETNZ"}\n'
            tmp_path.write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()
            valid_ev = {
                "supporting_source": "https://ac38noticeboard.acofficials.org/official-race-1.json",
                "captured_path": ".forecast/evidence_sources/notice.json",
                "captured_bytes": len(payload),
                "source_sha256": sha,
                "result_scope": "match_winner",
                "available_at_utc": "2026-09-25T12:00:00Z",
                "review_status": "independently_anchored",
            }
            rec = {"race_id": "ac75_test_r1", "competitor_a": "ETNZ", "competitor_b": "LUNA_ROSSA", "winner": "ETNZ", "evidence": valid_ev}

            ok_res = draw_ac38_ac75_worlds(troot, post, fit, mapping, n_worlds=2000, seed=11, ac75_updates=[rec])
            self.assertEqual(ok_res["applied_ac75_updates"], ["ac75_test_r1"])
            self.assertLess(ok_res["effective_sample_size"], 2000.0)

            with self.assertRaises(ValueError):
                draw_ac38_ac75_worlds(troot, post, fit, mapping, n_worlds=500, seed=11, ac75_updates=[rec, rec])

            bad_ev = dict(valid_ev, supporting_source="https://www.americascup.com/results")
            ok_flag, _ = is_valid_independent_evidence(troot, bad_ev, required_scopes=("match_winner",))
            self.assertFalse(ok_flag)
            with self.assertRaises(ValueError):
                draw_ac38_ac75_worlds(troot, post, fit, mapping, n_worlds=500, seed=11, ac75_updates=[{**rec, "evidence": bad_ev}])

            future_ev = dict(valid_ev, available_at_utc="2026-10-05T00:00:00Z")
            with self.assertRaises(ValueError):
                draw_ac38_ac75_worlds(troot, post, fit, mapping, n_worlds=500, seed=11, ac75_updates=[{**rec, "evidence": future_ev}])


class Ac38TournamentAndPublicationTests(unittest.TestCase):
    def test_equal_strengths_symmetric_and_unresolved_rule_bounds_null_points(self) -> None:
        worlds = np.zeros((4000, len(TEAM_IDS)), dtype=float)
        pair = compute_pairwise_and_series(worlds)
        self.assertAlmostEqual(pair["single_match"]["ETNZ"]["LUNA_ROSSA"], 0.5, places=6)
        self.assertAlmostEqual(pair["series_best_of_9_first_to_5"]["ETNZ"]["LUNA_ROSSA"], 0.5, places=6)
        self.assertAlmostEqual(pair["series_best_of_13_first_to_7"]["ETNZ"]["LUNA_ROSSA"], 0.5, places=6)

        mean_map = {t: 0.0 for t in TEAM_IDS}
        var_map = {t: 0.0 for t in TEAM_IDS}
        sim = simulate_cup(
            {},
            scenario=CupScenario(rho=1.0, sigma_multiplier=1.0, match_concentration=1.0, hazard_multiplier=1.0),
            rules=CupRules(),
            trials=4000,
            seed=2027,
            posterior_world_draws=worlds,
            forecast_prior_mean=mean_map,
            forecast_prior_var=var_map,
        )
        self.assertGreater(sim["unresolved_trials"], 0)
        for t in TEAM_IDS:
            self.assertIsNone(sim["probabilities"][t])
            self.assertLessEqual(sim["rule_bounds"][t]["lower"], sim["rule_bounds"][t]["upper"])
        chall_top3 = [sim["diagnostics"]["top3_challenger_frequency"][t] for t in TEAM_IDS if t != "ETNZ"]
        self.assertAlmostEqual(sum(chall_top3), 3.0, places=2)
        self.assertTrue(all(abs(v - 0.5) < 0.05 for v in chall_top3))

    def test_candidate_validation_tamper_rejection_and_atomic_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            troot = Path(tmp) / "repo"
            shutil.copytree(ROOT / "public" / "data" / "predictions", troot / "public" / "data" / "predictions")
            idx_p = troot / "public" / "data" / "predictions" / "index.json"
            idx_clean = json.loads(idx_p.read_text(encoding="utf-8"))
            idx_clean.pop("ac38_forecast_path", None)
            idx_p.write_text(json.dumps(idx_clean), encoding="utf-8")
            shutil.copytree(ROOT / "docs", troot / "docs")
            shutil.copytree(ROOT / ".forecast" / "ac38", troot / ".forecast" / "ac38", ignore=shutil.ignore_patterns("candidates"))
            shutil.copytree(ROOT / ".forecast" / "evidence_sources", troot / ".forecast" / "evidence_sources")
            (troot / ".forecast" / "dataset").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / ".forecast" / "dataset" / "index.json", troot / ".forecast" / "dataset" / "index.json")

            built = build_ac38_forecast_candidate(
                troot, issuance_cutoff_utc="2026-10-01T00:00:00Z", trials=2000, seed=2027, sensitivity_trials=500
            )
            art_hash = built["artifact_hash"]
            validate_ac38_forecast(built["artifact"])

            cand_file = Path(built["candidate_dir"]) / f"{art_hash}.json"
            orig_bytes = cand_file.read_bytes()
            tampered = json.loads(orig_bytes.decode("utf-8"))
            tampered["header"]["trials"] = 1999
            cand_file.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(ValueError):
                publish_ac38_forecast(troot, candidate_hash=art_hash)
            idx_before = json.loads((troot / "public" / "data" / "predictions" / "index.json").read_text(encoding="utf-8"))
            self.assertNotIn("ac38_forecast_path", idx_before)

            cand_file.write_bytes(orig_bytes)
            pub = publish_ac38_forecast(troot, candidate_hash=art_hash)
            idx_after = json.loads((troot / "public" / "data" / "predictions" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(idx_after["ac38_forecast_path"], pub["ac38_forecast_path"])
            pub_dir = troot / "public" / "data" / "predictions"
            for fname in ("ac38_model_card.json", "ac38_evaluation.json", "ac38_source_inventory.json", "ac38_report.md"):
                self.assertTrue((pub_dir / fname).is_file(), f"Missing published summary {fname}")
            mc_doc = json.loads((pub_dir / "ac38_model_card.json").read_text(encoding="utf-8"))
            self.assertTrue(mc_doc["private_posterior_omitted"])
            self.assertNotIn("active_conditionals", mc_doc)
            self.assertNotIn("grid_axes", mc_doc)
            report_p = pub_dir / "ac38_report.md"
            report_txt = report_p.read_text(encoding="utf-8")
            for heading in ("Grouped Log Loss", "Source Inventory Summary", "Comparison vs Previous Cup Publication", "Verification & Completion Tracking"):
                self.assertIn(heading, report_txt)

    def test_validate_ac38_forecast_rejects_contract_parity_violations(self) -> None:
        import copy
        from pipeline.prediction.contracts import validate_ac38_forecast

        pub_idx = json.loads((ROOT / "public" / "data" / "predictions" / "index.json").read_text(encoding="utf-8"))
        fc_path = ROOT / "public" / "data" / "predictions" / pub_idx["ac38_forecast_path"]
        base = json.loads(fc_path.read_text(encoding="utf-8"))
        self.assertTrue(validate_ac38_forecast(base))

        cases = []
        # 1. scale_kappa != 1
        d = copy.deepcopy(base); d["header"]["scale_kappa"] = 1.8; cases.append(d)
        # 2. bool trials
        d = copy.deepcopy(base); d["header"]["trials"] = True; cases.append(d)
        # 3. invalid cutoff ISO
        d = copy.deepcopy(base); d["header"]["issuance_cutoff_utc"] = "not-a-date"; cases.append(d)
        # 4. campaign_team_id mismatch
        d = copy.deepcopy(base); d["teams"][0]["campaign_team_id"] = "ETNZ"; cases.append(d)
        # 5. status vs unresolved_trials mismatch (0 unresolved must be experimental_conditional)
        d = copy.deepcopy(base); d["rules"]["unresolved_trials"] = 0; d["rules"]["resolved_trials"] = d["header"]["trials"]; d["rules"]["unresolved_fraction"] = 0.0; d["rules"]["resolved_fraction"] = 1.0; d["rules"]["first_unresolved_stage_counts"] = {}; cases.append(d)
        # 6. fleet_position_distribution bad row sum
        d = copy.deepcopy(base); d["forecast"]["fleet_position_distribution"]["ETNZ"][0] = 0.99; cases.append(d)
        # 7. duplicate structural sensitivity configuration
        d = copy.deepcopy(base); dup = copy.deepcopy(d["structural_sensitivities"][0]); dup["scenario_id"] = "dup_id"; d["structural_sensitivities"].append(dup); cases.append(d)
        # 8. bad percentile ordering
        d = copy.deepcopy(base); d["uncertainty"]["transfer_parameter_summary"]["beta_percentiles"]["p05"] = 99.0; cases.append(d)
        # 9. leaked private posterior keys
        d = copy.deepcopy(base); d["active_conditionals"] = [[0.1]]; cases.append(d)
        # 10. non-boolean telemetry_retained
        d = copy.deepcopy(base); d["header"]["telemetry_retained"] = "no"; cases.append(d)

        for idx, bad in enumerate(cases):
            with self.subTest(case=idx):
                with self.assertRaises(ValueError):
                    validate_ac38_forecast(bad)

    def test_completion_status_and_markdown_report_match_backtest_and_diagnostics(self) -> None:
        import copy
        from pipeline.prediction.ac38_forecast import _compute_completion_status, render_ac38_markdown_report

        pub_idx = json.loads((ROOT / "public" / "data" / "predictions" / "index.json").read_text(encoding="utf-8"))
        base = json.loads((ROOT / "public" / "data" / "predictions" / pub_idx["ac38_forecast_path"]).read_text(encoding="utf-8"))

        # Missing diagnostics must fail engineering_verified instead of defaulting to True.
        no_diag = _compute_completion_status(base, post=None)
        self.assertFalse(no_diag["engineering_verified"])

        bad_bm = _compute_completion_status(
            base,
            post={"diagnostics": {"all_points_converged": True, "failed_grid_points": 0, "refinement_ok": True, "boundary_mass": 0.01}},
        )
        self.assertFalse(bad_bm["engineering_verified"])
        self.assertFalse(bad_bm["details"]["posterior_boundary_mass_below_1e_3"])

        # Positive backtest claim must set accuracy_improvement_demonstrated=True and not emit hardcoded negative text.
        pos = copy.deepcopy(base)
        pos["historical_evaluation"]["ac75_chronological"]["transfer_results_only"]["grouped_mean_log_loss"] = 0.50
        pos["historical_evaluation"]["ac75_chronological"]["ac75_carryover"]["grouped_mean_log_loss"] = 0.65
        pos["historical_evaluation"]["ac75_loto"]["results_only_transfer"]["grouped_mean_log_loss"] = 0.50
        pos["historical_evaluation"]["ac75_loto"]["results_only_transfer"]["grouped_se_log_loss"] = 0.02
        pos["historical_evaluation"]["ac75_loto"]["no_transfer"]["grouped_mean_log_loss"] = 0.69
        pos["historical_evaluation"]["accuracy_claim"] = "Transfer outperformed AC75 carryover (0.500 vs 0.650) and beat LOTO no-transfer by >1 SE (0.500 vs 0.690); telemetry retained=False."
        pos_comp = _compute_completion_status(
            pos,
            post={"diagnostics": {"all_points_converged": True, "failed_grid_points": 0, "refinement_ok": True, "boundary_mass": 1e-5}},
        )
        self.assertTrue(pos_comp["engineering_verified"])
        self.assertTrue(pos_comp["accuracy_improvement_demonstrated"])
        md = render_ac38_markdown_report(pos, "0" * 64, completion_status=pos_comp)
        self.assertIn("Transfer outperformed AC75 carryover", md)
        self.assertNotIn("backtest claim does not claim overall AC75 accuracy gain", md)

    def test_backtest_calibration_and_coverage_are_non_degenerate(self) -> None:
        bt = json.loads((ROOT / ".forecast" / "ac38" / "backtest_report.json").read_text(encoding="utf-8"))
        for sec, key in (
            ("ac40_chronological", "results_only"),
            ("ac75_chronological", "transfer_results_only"),
            ("ac75_loto", "results_only_transfer"),
        ):
            m = bt[sec][key]
            cal = m["calibration"]
            self.assertLess(cal["mean_obs"], 0.9)
            self.assertGreater(cal["mean_obs"], 0.05)
            self.assertLess(abs(cal["intercept"]), 5.0)
            self.assertIsNotNone(m["coverage_50"])
            self.assertIsNotNone(m["coverage_90"])


if __name__ == "__main__":
    unittest.main()
