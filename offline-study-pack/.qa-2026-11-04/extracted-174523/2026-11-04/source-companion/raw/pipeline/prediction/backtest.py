"""Frozen references and chronological diagnostics; no tuning on audit dates."""
from __future__ import annotations
from collections import Counter
import numpy as np
from .build import prepare, fitted_before, legs_for, state_before, simulation_states
from .source import load_dataset
from .state import CausalRace
from .contracts import atomic_json
from .evaluation import DEVELOPMENT_DAYS, AUDIT_DAYS, aggregate, scores, promotion, guardrails
from .models import EmpiricalOrderModel, StrengthModel
from .labels import before_day
from .simulation import simulate_order_reference, simulate_race


def run_backtest(root, *, n=20000, include_audit=False):
    metadata, labels, transitions, reviews = prepare(root)
    by_id={m["race_id"]:m for m in metadata}
    diagnostics={k:[] for k in ("uniform","empirical","static_pl","condition_pl","correlated_mc")}
    primary={k:[] for k in ("reference","candidate")}
    progress_rows={k:{band:[] for band in ("0-25%","25-50%","50-75%","75-100%")} for k in primary}
    prerace={k:[] for k in ("reference","candidate")}
    reasons=Counter()
    selected_days=DEVELOPMENT_DAYS+(AUDIT_DAYS if include_audit else ())
    reviewed_by_race={}
    for record in reviews:
        reviewed_by_race.setdefault(record["race_id"],[]).append(record)
    fits={}
    for label in labels:
        if label["practice"] or label["date"] not in selected_days:
            continue
        # This is a frozen descriptive audit, including the second audit date.
        date=min(label["date"],AUDIT_DAYS[0])
        if date not in fits:
            fits[date]=fitted_before(date,labels,transitions,reviews)
        strength, times, completion = fits[date]
        meta=by_id[label["race_id"]]
        order=label["order"]
        # Ex-post finisher subset diagnostics are explicitly NOT unconditional
        # live win tests or promotion evidence. No nonfinisher is ranked as weak.
        empirical=EmpiricalOrderModel.fit(before_day(labels,date))
        condition=StrengthModel.fit(before_day(labels,date),condition_effects=True)
        diagnostic_p={"uniform":dict.fromkeys(order,1/len(order)),
                      "empirical":empirical.predict_win_probabilities(order),
                      "static_pl":strength.predict_win_probabilities(order),
                      "condition_pl":condition.predict_win_probabilities(order,wind_knots=label.get("wind_knots"))} if label["order_valid"] else {}
        mc=simulate_race(times,order,legs_for(meta),completion,n=n,seed=42,conditional_complete=True) if diagnostic_p else None
        if diagnostic_p:
            diagnostic_p["correlated_mc"] = mc.win_prob_by_boat if mc.available else diagnostic_p["static_pl"]
        for model,p in diagnostic_p.items():
            values=np.array([p[b] for b in order],float)
            # Fixed tail on the full conditional-order distribution, not a score repair.
            if model != "correlated_mc" or not mc.available:
                values=(1-.0001)*values+.0001/len(order)
            diagnostics[model].append({"date":label["date"],"race_id":label["race_id"],
                                       **scores(values,0)})
        if label["race_id"] not in reviewed_by_race:
            reasons["no_audited_full_field_outcomes"]+=1
            continue
        reviewed=reviewed_by_race[label["race_id"]]
        reviewed_finishers={meta["identities"][r["asset_id"]]["entry_id"] for r in reviewed if r["completed"]}
        if label.get("order_tied") or set(order) != reviewed_finishers:
            reasons["reviewed_finishers_disagree_with_source_order"]+=1
            continue
        if not completion.available:
            reasons["no_earlier_audited_completion_denominator"]+=1
            continue
        # Full scheduled field and no-finisher outcome for eligible pre-race tests.
        entries=[meta["identities"][b]["entry_id"] for b in meta["boat_ids"]]
        reference=simulate_order_reference(strength,entries,completion,n=n,seed=42)
        candidate=simulate_race(times,entries,legs_for(meta),completion,n=n,seed=42)
        for key,result in (("reference",reference),("candidate",candidate if candidate.available else reference)):
            if not result.available:
                reasons["reference_unavailable"]+=1
                continue
            p=[result.win_prob_by_boat[b] for b in entries]+[result.no_finisher_prob]
            winner=entries.index(order[0]) if order else len(entries)
            positions=np.array([order.index(b)+1 if b in order else len(entries) for b in entries])
            cdf=(np.stack([(result.ranks<=r).mean(axis=0) for r in range(1,len(entries))],axis=1)
                 if len(entries)>1 else np.empty((1,0))) if result.ranks is not None else None
            row={"date":label["date"],"race_id":label["race_id"],**scores(p,winner,
                [result.expected_position_by_boat[b] for b in entries],positions,rank_cdf=cdf)}
            prerace[key].append(row)
        _,raw=load_dataset(root,meta["race_id"])
        parameters,certificate=state_before(root,date,metadata)
        causal=CausalRace(meta,raw,**{k:v for k,v in parameters.items() if k in ("q","r")})
        for t in range(meta["gun_ms"],meta["window_end_ms"]+1,10000):
            features={meta["identities"][aid]["entry_id"]:causal.features(aid,t,certificate) for aid in meta["boat_ids"]}
            if any(f["quality"] not in ("available","estimated") for f in features.values()):
                reasons["live_reference_state_unavailable"]+=1
                continue
            features=simulation_states(features,times,legs_for(meta,t))
            resolved=all(f.get("terminal_status") in ("finished","ret","dns","disqualified") for f in features.values())
            if resolved:
                # Recording tails must not dilute forecasting loss with repeated
                # already-known zero-loss outcomes. Terminal behavior has its own tests.
                reasons["globally_resolved_terminal_checkpoints"]+=1
                continue
            total_legs=len(legs_for(meta,t))
            progress=max((f.get("current_leg",0)+1-f.get("remaining_fraction",1))/total_legs for f in features.values())
            band=("0-25%","25-50%","50-75%","75-100%")[min(3,max(0,int(progress*4)))]
            reference=simulate_order_reference(strength,entries,completion,state=features,total_legs=len(legs_for(meta,t)),
                         n=n,seed=42,global_finish_order_resolved=resolved)
            candidate=simulate_race(times,entries,legs_for(meta,t),completion,state=features,n=n,seed=42,
                         global_finish_order_resolved=resolved)
            if not reference.available:
                reasons["live_reference_unavailable"]+=1
                continue
            for key,prediction in (("reference",reference),("candidate",candidate if candidate.available else reference)):
                p=[prediction.win_prob_by_boat[b] for b in entries]+[prediction.no_finisher_prob]
                winner=entries.index(order[0]) if order else len(entries)
                row={"date":label["date"],"race_id":label["race_id"],"checkpoint":t,**scores(p,winner)}
                primary[key].append(row)
                progress_rows[key][band].append(row)
    def split_summary(rows, days):
        return aggregate([r for r in rows if r["date"] in days])
    development={k:split_summary(v,DEVELOPMENT_DAYS) for k,v in primary.items()}
    pre_development={k:split_summary(v,DEVELOPMENT_DAYS) for k,v in prerace.items()}
    audit={k:split_summary(v,AUDIT_DAYS) for k,v in primary.items()} if include_audit else None
    pre_audit={k:split_summary(v,AUDIT_DAYS) for k,v in prerace.items()} if include_audit else None
    gates={"development_live":promotion(development["candidate"],development["reference"],applicable=("brier",)),
           "development_pre":guardrails(pre_development["candidate"],pre_development["reference"],applicable=("normalized_rps","normalized_mse"))}
    if include_audit:
        gates["audit_live"]=promotion(audit["candidate"],audit["reference"],applicable=("brier",))
        gates["audit_pre"]=guardrails(pre_audit["candidate"],pre_audit["reference"],applicable=("normalized_rps","normalized_mse"))
    passed=include_audit and all(g.get("promoted",g.get("passed",False)) for g in gates.values())
    passed=passed and development["reference"]["independent_days"]==len(DEVELOPMENT_DAYS) and audit["reference"]["independent_days"]==len(AUDIT_DAYS)
    from .build import provenance
    from .contracts import content_hash
    result={"schema_version":"prediction-backtest-1","configuration_frozen":True,
            "development_days":DEVELOPMENT_DAYS,"audit_days":AUDIT_DAYS,
            "audit_candidate_frozen_before":"2026-09-26","simulation_count":n,
            "primary_status":"unavailable" if not primary["reference"] else "available; low independent-day evidence",
            "source_manifest_hash":content_hash(provenance(root,metadata)),
            "coverage_reasons":dict(reasons),"development":development,"pre_race_development":pre_development,"descriptive_audit":audit,
            "pre_race_descriptive_audit":pre_audit,
            "development_live_progress_bands":{key:{band:split_summary(rows,DEVELOPMENT_DAYS)
                for band,rows in groups.items()} for key,groups in progress_rows.items()},
            "promotion":{"promoted":bool(passed),"gates":gates,"status":"provisional_low_evidence",
                         "reason":None if passed else "Both paired development and locked audit live/pre gates must pass"},
            "selected":"correlated_mc" if passed else "joint_pl_reference",
            "diagnostic_scope":"Pre-race conditional on the retrospectively observed source finisher subset; not official labels, not unconditional, not promotion evidence",
            "diagnostics_development":{k:split_summary(v,DEVELOPMENT_DAYS) for k,v in diagnostics.items()},
            "diagnostics_audit":{k:split_summary(v,AUDIT_DAYS) for k,v in diagnostics.items()} if include_audit else None,
            "calibration":"identity; empirical calibration not established"}
    atomic_json(root/".forecast"/"backtest.json",result)
    return result
