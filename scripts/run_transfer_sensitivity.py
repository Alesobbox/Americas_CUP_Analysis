"""Run transfer sensitivity analysis across sigma_40 in {0.8, 1.2, 1.8} and policies."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.prediction.transfer import fit_transfer_model


def main():
    root = Path(__file__).resolve().parent.parent
    
    # 1. Main model with refinement check
    print("Fitting main calibrated transfer model (sigma_40=1.2, policy=equal, with refinement check)...")
    main_res = fit_transfer_model(root, policy="equal", sigma_40=1.2, check_refinement=True)
    out_dir = root / ".forecast" / "transfer"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ac37_transfer.json").write_text(json.dumps(asdict(main_res), indent=2) + "\n", encoding="utf-8")
    print(f"  Main result: boundary_mass={main_res.boundary_mass:.6f}, grid_converged={main_res.grid_converged}")
    print(f"  Beta mode={main_res.beta_mode}, p50={main_res.beta_percentiles['p50']}")
    print(f"  Tau mode={main_res.tau_mode}, p50={main_res.tau_percentiles['p50']}")
    print(f"  Rho mode={main_res.rho_mode}, p50={main_res.rho_percentiles['p50']}")

    # 2. Sensitivity across sigma_40 in {0.8, 1.2, 1.8}
    sensitivity_results = {}
    for s in (0.8, 1.2, 1.8):
        print(f"\nRunning sensitivity for sigma_40 = {s}...")
        res = fit_transfer_model(root, policy="equal", sigma_40=s, check_refinement=False, n_beta=61, n_eta=45)
        sensitivity_results[str(s)] = {
            "sigma_40": s,
            "beta_mode": res.beta_mode,
            "beta_p50": res.beta_percentiles["p50"],
            "beta_ci": [res.beta_percentiles["p05"], res.beta_percentiles["p95"]],
            "tau_mode": res.tau_mode,
            "tau_p50": res.tau_percentiles["p50"],
            "tau_ci": [res.tau_percentiles["p05"], res.tau_percentiles["p95"]],
            "rho_mode": res.rho_mode,
            "rho_p50": res.rho_percentiles["p50"],
            "rho_ci": [res.rho_percentiles["p05"], res.rho_percentiles["p95"]],
            "boundary_mass": res.boundary_mass,
            "two_stage": res.two_stage_diagnostic
        }
        print(f"  sigma_40={s}: beta_p50={res.beta_percentiles['p50']:.4f}, tau_p50={res.tau_percentiles['p50']:.4f}, rho_p50={res.rho_percentiles['p50']:.4f}")

    sens_file = root / ".forecast" / "qa" / "transfer_sensitivity_sigma40.json"
    sens_file.parent.mkdir(parents=True, exist_ok=True)
    sens_file.write_text(json.dumps(sensitivity_results, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote sensitivity results to {sens_file}")


if __name__ == "__main__":
    main()
