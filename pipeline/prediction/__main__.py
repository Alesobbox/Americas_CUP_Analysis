"""python -m pipeline.prediction {dataset,audit,backtest,build,verify,transfer,ac38}."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .contracts import atomic_json, verify_public


def _ac38_audit(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    from .ac38_evidence import build_eligibility_ledger
    from .ac38_inventory import build_inventory
    from .contracts import content_hash
    inv = build_inventory(root, write=True)
    ledger = build_eligibility_ledger(root, issuance_cutoff_utc=args.cutoff_utc, write=True)
    print(json.dumps({
        "inventory_sha256": content_hash(inv),
        "eligibility_ledger_sha256": content_hash(ledger),
        "summary": ledger["summary"],
    }))


def _ac38_fit(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    from .transfer_sample import build_transfer_posterior_artifact
    art = build_transfer_posterior_artifact(root)
    print(json.dumps({
        "schema_version": art["schema_version"],
        "active_cells": len(art["active_conditionals"]),
        "beta_percentiles": art["summary"]["beta_percentiles"],
        "tau_percentiles": art["summary"]["tau_percentiles"],
        "diagnostics": art["diagnostics"],
    }))


def _ac38_backtest(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    from .ac38_backtest import run_ac38_backtest
    from .ac38_telemetry import build_ac40_telemetry_cache
    from .contracts import content_hash
    build_ac40_telemetry_cache(root, write=True)
    rep = run_ac38_backtest(root, write=True)
    print(json.dumps({
        "selected_candidate": rep["selected_candidate"],
        "telemetry_retained": rep["telemetry_retained"],
        "backtest_report_sha256": content_hash(rep),
    }))


def _ac38_build(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    if not args.cutoff_utc:
        parser.error("ac38 build requires --cutoff-utc")
    from .ac38_forecast import build_ac38_forecast_candidate
    built = build_ac38_forecast_candidate(
        root, issuance_cutoff_utc=args.cutoff_utc,
        trials=args.trials, seed=args.seed, sensitivity_trials=args.sensitivity_trials,
    )
    print(json.dumps({
        "candidate_dir": built["candidate_dir"],
        "artifact_hash": built["artifact_hash"],
        "header": built["artifact"]["header"],
    }))


def _ac38_publish(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    from .ac38_forecast import publish_ac38_forecast
    print(json.dumps(publish_ac38_forecast(root, candidate_hash=args.candidate_hash)))


_AC38_HANDLERS = {
    "audit": _ac38_audit,
    "fit": _ac38_fit,
    "backtest": _ac38_backtest,
    "build": _ac38_build,
    "publish": _ac38_publish,
}


def _run_ac38(args: argparse.Namespace, parser: argparse.ArgumentParser, root: Path) -> None:
    handler = _AC38_HANDLERS.get(args.ac38_command or "")
    if handler is None:
        parser.error("ac38 requires one of {audit,fit,backtest,build,publish}")
    handler(args, parser, root)


def main():
    parser = argparse.ArgumentParser(description="Offline causal regatta probabilities")
    parser.add_argument("command", choices=("dataset", "audit", "backtest", "build", "verify", "transfer", "ac38"))
    parser.add_argument("ac38_command", nargs="?", choices=("audit", "fit", "backtest", "build", "publish"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--race")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-audit", action="store_true", help="Separate frozen descriptive audit; never tune on it")
    parser.add_argument("--policy", choices=("equal", "principal_only", "assumed_10_02"), default="equal", help="Syndicate roster mapping policy")
    parser.add_argument("--sigma-40", type=float, default=1.2, help="AC40 prior SD parameter")
    parser.add_argument("--ac40-source", choices=("ac37_2023", "ac38_2026", "pooled_ac37_ac38"), default="ac37_2023", help="AC40 results data source")
    parser.add_argument("--tws-knots", type=float, help="Build an exact pre-race-only scenario for --race")
    parser.add_argument("--direction-offset-deg", type=float, default=0)
    parser.add_argument("--simulations", type=int, default=20000, help="Backtest simulations, not model accuracy")
    parser.add_argument("--cutoff-utc", help="Explicit UTC issuance cutoff (required for ac38 build)")
    parser.add_argument("--trials", type=int, default=200000, help="Tournament Monte Carlo trials for ac38 build")
    parser.add_argument("--sensitivity-trials", type=int, default=25000, help="Tournament trials per sensitivity scenario")
    parser.add_argument("--seed", type=int, default=2027, help="Default RNG seed for ac38 build")
    parser.add_argument("--candidate-hash", help="Optional candidate hash for ac38 publish")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "ac38":
        _run_ac38(args, parser, root)
    elif args.command == "dataset":
        from .source import source_dataset
        result = source_dataset(root, race=args.race, force=args.force)
        print(json.dumps({"races": len(result["races"]), "source_bytes": sum(r["bytes"] for r in result["races"])}))
    elif args.command == "audit":
        from .build import prepare
        metadata, labels, transitions, reviews = prepare(root)
        result = {"schema_version": "prediction-audit-1", "races": len(metadata),
                "source_boat_races": sum(len(m["boat_ids"]) for m in metadata),
                "practice_races": sum(m["practice"] for m in metadata),
                "official_verified_orders": sum(l["official_order_verified"] for l in labels),
                "source_started_finisher_orders": sum(l["order_valid"] for l in labels),
                "valid_gate_intervals": len(transitions), "audited_completion_records": len(reviews),
                "reorder_buffer_ms": 6000, "max_tracked_disorder_ms": max(m["max_disorder_ms"] for m in metadata),
                "races_outside_reorder_contract": [m["race_id"] for m in metadata if not m["reorder_contract_valid"]],
                "time_basis": "event-time reconstruction with modeled latency"}
        atomic_json(root / ".forecast" / "audit.json", result)
        print(json.dumps(result))
    elif args.command == "backtest":
        from .backtest import run_backtest
        result = run_backtest(root, n=args.simulations, include_audit=args.include_audit)
        print(json.dumps({k: result[k] for k in ("primary_status", "coverage_reasons", "selected", "promotion")}))
    elif args.command == "build":
        from .build import export_archive, export_pre_race_scenario
        if args.tws_knots is not None:
            if not args.race:
                parser.error("Custom wind requires --race")
            print(json.dumps(export_pre_race_scenario(root, args.race, tws_kt=args.tws_knots, direction_offset_deg=args.direction_offset_deg)))
        else:
            print(json.dumps(export_archive(root, race_id=args.race)))
    elif args.command == "transfer":
        from .transfer import fit_transfer_model
        result = fit_transfer_model(root, policy=args.policy, sigma_40=args.sigma_40, ac40_source=args.ac40_source)
        result_dict = {k: v for k, v in asdict(result).items() if k != "posterior_grid"}
        out_dir = root / ".forecast" / "transfer"
        out_dir.mkdir(parents=True, exist_ok=True)
        target_name = "ac37_transfer.json" if args.ac40_source == "ac37_2023" else f"diagnostic_{args.ac40_source}.json"
        atomic_json(out_dir / target_name, result_dict)
        print(json.dumps(result_dict, indent=2))
    else:
        print(json.dumps(verify_public(root)))


if __name__=="__main__":
    main()
