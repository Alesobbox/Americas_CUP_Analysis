"""python -m pipeline.prediction {dataset,audit,backtest,build,verify}."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .contracts import atomic_json, verify_public


def main():
    parser=argparse.ArgumentParser(description="Offline causal regatta probabilities")
    parser.add_argument("command",choices=("dataset","audit","backtest","build","verify"))
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--race")
    parser.add_argument("--force",action="store_true")
    parser.add_argument("--include-audit",action="store_true",help="Separate frozen descriptive audit; never tune on it")
    parser.add_argument("--tws-knots",type=float,help="Build an exact pre-race-only scenario for --race")
    parser.add_argument("--direction-offset-deg",type=float,default=0)
    parser.add_argument("--simulations",type=int,default=20000,help="Backtest simulations, not model accuracy")
    args=parser.parse_args()
    root=args.root.resolve()
    if args.command=="dataset":
        from .source import source_dataset
        result=source_dataset(root,race=args.race,force=args.force)
        print(json.dumps({"races":len(result["races"]),"source_bytes":sum(r["bytes"] for r in result["races"])}))
    elif args.command=="audit":
        from .build import prepare
        metadata,labels,transitions,reviews=prepare(root)
        result={"schema_version":"prediction-audit-1","races":len(metadata),
                "source_boat_races":sum(len(m["boat_ids"]) for m in metadata),
                "practice_races":sum(m["practice"] for m in metadata),
                "official_verified_orders":sum(l["official_order_verified"] for l in labels),
                "source_started_finisher_orders":sum(l["order_valid"] for l in labels),
                "valid_gate_intervals":len(transitions),"audited_completion_records":len(reviews),
                "reorder_buffer_ms":6000,"max_tracked_disorder_ms":max(m["max_disorder_ms"] for m in metadata),
                "races_outside_reorder_contract":[m["race_id"] for m in metadata if not m["reorder_contract_valid"]],
                "time_basis":"event-time reconstruction with modeled latency"}
        atomic_json(root/".forecast"/"audit.json",result)
        print(json.dumps(result))
    elif args.command=="backtest":
        from .backtest import run_backtest
        result=run_backtest(root,n=args.simulations,include_audit=args.include_audit)
        print(json.dumps({k:result[k] for k in ("primary_status","coverage_reasons","selected","promotion")}))
    elif args.command=="build":
        from .build import export_archive,export_pre_race_scenario
        if args.tws_knots is not None:
            if not args.race:
                parser.error("Custom wind requires --race")
            print(json.dumps(export_pre_race_scenario(root,args.race,tws_kt=args.tws_knots,direction_offset_deg=args.direction_offset_deg)))
        else:
            print(json.dumps(export_archive(root,race_id=args.race)))
    else:
        print(json.dumps(verify_public(root)))


if __name__=="__main__":
    main()
