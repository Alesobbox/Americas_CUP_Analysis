"""Reproducible offline fit/build. No inference or probability repair in the UI."""
from __future__ import annotations
from datetime import datetime, timezone
from importlib import metadata as packages
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from .contracts import STATUSES, atomic_json, content_hash, validate_race, verify_public
from .labels import race_labels, leg_rows, load_reviews, before_day
from .models import StrengthModel, CompletionModel, LegTimeModel
from .source import BUFFER_MS, digest, load_dataset
from .state import CausalRace, certify_outages, fit_filter_parameters


def metadata_archive(root):
    base = root/".forecast"/"dataset"
    index = json.loads((base/"index.json").read_text())
    return [json.loads((base/(r["race_id"]+".json")).read_text()) for r in index["races"]]


def provenance(root, metadata):
    git = shutil.which("git") or str(Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")
    def query(*args):
        try:
            return subprocess.check_output([git,"-c",f"safe.directory={root.as_posix()}",*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    files = sorted([*root.glob("pipeline/**/*.py"), *root.glob("src/**/*.ts"), *root.glob("src/**/*.tsx"),
                    *root.glob("src/**/*.css"),root/".python-version",root/"AGENTS.md",root/"PROJECT.md",root/"run.ps1",
                    root/"pyproject.toml", root/"uv.lock", root/"package.json",root/"package-lock.json",root/"vite.config.ts",
                    *root.glob("docs/forecast*.json")])
    source_paths=("pipeline","src","scripts","tests","docs","pyproject.toml","uv.lock","package.json","package-lock.json","vite.config.ts","PROJECT.md","run.ps1")
    dirty=query("status","--porcelain","--",*source_paths)
    return {"source_commit": query("log","-1","--format=%H","--",*source_paths),
            "source_dirty": None if dirty is None else bool(dirty),
            "files": {p.relative_to(root).as_posix(): digest(p) for p in files if p.is_file()},
            "raw_sources": {m["source_file"]: {"sha256":m["sha256"],"bytes":m["bytes"],
                "derived_table_sha256":m.get("derived_table_sha256"),"metadata_sha256":m.get("metadata_sha256")} for m in metadata},
            "python_version": sys.version.split()[0],
            "packages": {p:packages.version(p) for p in ("numpy","scipy","pyarrow")},
            "weights": {}, "source_time_basis": "event-time reconstruction with modeled latency"}


def prepare(root):
    metadata = metadata_archive(root)
    labels, transitions = [], []
    for meta in metadata:
        raw=root/"Data"/meta["source_file"]
        if raw.stat().st_size != meta["bytes"] or digest(raw) != meta["sha256"]:
            raise ValueError("Raw source changed after dataset creation; rebuild the dataset")
        _, rows = load_dataset(root,meta["race_id"])
        label = race_labels(meta)
        known_before_gun=meta["gun_ms"]-BUFFER_MS-1
        wind_id=meta["sessions"][-1].get("official_wind_asset_id")
        label["wind_knots"]=next((r["value"]*1.943844 for r in reversed(rows)
            if r["asset_id"]==wind_id and r["field"]=="true_wind_speed" and r["value"] is not None
            and r.get("bucket_closed_at_ms",r["timestamp_ms"])<=known_before_gun),None)
        labels.append(label)
        transitions.extend(leg_rows(meta, rows, label))
    return metadata, labels, transitions, load_reviews(root,metadata)


def fitted_before(date, labels, transitions, reviews):
    return (StrengthModel.fit(before_day(labels,date)), LegTimeModel.fit(before_day(transitions,date)),
            CompletionModel.fit(before_day(reviews,date)))


def state_before(root,date,metadata):
    earlier=[m for m in metadata if m["date"]<date and not m["practice"]]
    identity={"sources":[[m["race_id"],m["sha256"],m.get("metadata_sha256"),m.get("derived_table_sha256")] for m in earlier],
              "state_code":digest(Path(__file__).with_name("state.py")),
              "source_code":digest(Path(__file__).with_name("source.py")),
              "builder_code":digest(Path(__file__))}
    path=root/".forecast"/"state"/(content_hash(identity)+".json")
    if path.exists():
        record=json.loads(path.read_text())
        if record.get("input_identity")==identity:
            return record["parameters"],record["certificate"]
    prior=[load_dataset(root,m["race_id"]) for m in earlier]
    parameters=fit_filter_parameters(prior)
    certificate=certify_outages(prior,parameters=parameters)
    atomic_json(path,{"input_identity":identity,"parameters":parameters,"certificate":certificate})
    return parameters,certificate


def legs_for(meta, cutoff=None):
    cutoff=meta["gun_ms"] if cutoff is None else cutoff
    session=next((s for s in reversed(meta["sessions"]) if int(s["timestamp"])<=cutoff),None)
    if session is None:
        raise ValueError("No course known at prediction cutoff")
    course = session["race_course"]
    return [{"distance_m":float(course["course_length"]),"leg_kind":"odd" if i%2==0 else "even"}
            for i in range(len(course["sequences"])-1)]


def simulation_states(features, times, legs):
    """The same causal conditioner is used for evaluation and deployment."""
    states={entry:dict(feature,started=True) for entry,feature in features.items()}
    for entry,state in states.items():
        if state.get("vmg_mps",0)>0 and state.get("leg_length_m",0)>0 and 0<=state.get("current_leg",-1)<len(legs):
            full=times.median_seconds(entry,legs[state["current_leg"]])
            state["pace_ratio"]=state["vmg_mps"]*full/state["leg_length_m"]
    return states


def replay_field(root,meta):
    path=root/"public"/"data"/"replays"/(meta["race_id"]+".json")
    if not path.exists():
        return list(meta["boat_ids"])
    ids=[boat["id"] for boat in json.loads(path.read_text(encoding="utf-8"))["competitors"]]
    if len(set(ids))!=len(ids) or not set(ids)<=set(meta["boat_ids"]):
        raise ValueError("Replay field conflicts with the scheduled source field")
    return ids


def build_race(root, meta, strength, times, completion, *, manifest_hash, model_ref,
               parameters=None, certificate=None, pre_n=100000, live_n=20000, training_before_day=None,
               selected_model="joint_pl_reference"):
    from .simulation import simulate_order_reference,simulate_race
    _, rows = load_dataset(root,meta["race_id"])
    race = CausalRace(meta,rows,**{k:v for k,v in (parameters or {}).items() if k in ("q","r")})
    boats = meta["boat_ids"]
    replay_ids=replay_field(root,meta)
    entries = {b:meta["identities"][b]["entry_id"] for b in boats}
    if len(set(entries.values())) != len(boats):
        raise ValueError("Session contains duplicate entry identities")
    training_cutoff = int(datetime.fromisoformat(training_before_day or meta["date"]).replace(tzinfo=timezone.utc).timestamp()*1000)-1
    scenario = {"scope":"baseline", "field":boats, "boat_class":"AC40", "race_id":meta["race_id"],
                "conditions":"observed past only; future weather persistence with modeled uncertainty"}
    # Baseline is the conservative joint ranking reference until a candidate passes P3.
    pre_seed=int(content_hash(meta["race_id"])[:8],16)
    simulation = (simulate_race(times,list(entries.values()),legs_for(meta),completion,n=pre_n,seed=pre_seed)
                  if selected_model=="correlated_mc" else simulate_order_reference(strength,list(entries.values()),completion,n=pre_n,seed=pre_seed))
    pre = {"status":"estimated" if simulation.available else "unavailable", "reason":simulation.reason,
           "expected_position_by_boat":{b:simulation.expected_position_by_boat[entries[b]] for b in boats},
           "nonfinish_score":"N"}
    columns = {k:[] for k in ("state_timestamps_ms","published_at_ms","progress_band","no_finisher_prob",
                              "status_code","numerical_error","reason_code")}
    columns.update({k:{b:[] for b in boats} for k in ("win_prob_by_boat","source_age_ms_by_boat",
                   "position_uncertainty_summary_by_boat","quality_code_by_boat")})
    # Include terminal source-event checkpoints in addition to ten-second publication cadence.
    checkpoints = set(range(meta["gun_ms"],meta["window_end_ms"]+1,10000))
    final_leg = len(legs_for(meta))
    for event in meta["competitor_events"]:
        if any(int(g["leg_number"])==final_leg and g.get("gate_time") for g in event.get("leg_timings",[])):
            t=int(event["timestamp"])
            if meta["gun_ms"]<=t<=meta["window_end_ms"]:
                checkpoints.add(t)
    for t in sorted(checkpoints):
        features = {b:race.features(b,t,certificate) for b in boats}
        qualities = [f["quality"] for f in features.values()]
        all_terminal = all(f.get("terminal_status") in ("finished","ret","dns","disqualified") for f in features.values())
        reason = completion.reason if not completion.available and not all_terminal else None
        status = "unavailable" if reason else "estimated"
        if not meta["reorder_contract_valid"]:
            reason,status = "raw_disorder_exceeds_modeled_reorder_buffer", "unavailable"
        elif any(q not in ("available","estimated") for q in qualities):
            status = "gate_ambiguous" if "gate_ambiguous" in qualities else "unavailable"
            reason = next(f.get("reason") for f in features.values() if f["quality"] not in ("available","estimated"))
        forecast = None
        if status in STATUSES[:2]:
            known_legs=legs_for(meta,t)
            states = simulation_states({entries[b]:features[b] for b in boats},times,known_legs)
            # Do not assert the first received finish is the globally first valid one.
            all_resolved = all_terminal
            live_seed=int(content_hash([meta["race_id"],t])[:8],16)
            if selected_model=="correlated_mc":
                forecast=simulate_race(times,list(entries.values()),known_legs,completion,state=states,n=live_n,seed=live_seed,
                                       global_finish_order_resolved=all_resolved)
            else:
                forecast = simulate_order_reference(strength,list(entries.values()),completion,state=states,total_legs=len(legs_for(meta,t)),
                            n=live_n,seed=live_seed,global_finish_order_resolved=all_resolved)
            if not forecast.available:
                status,reason = "unavailable",forecast.reason
        columns["state_timestamps_ms"].append(t)
        columns["published_at_ms"].append(t+BUFFER_MS)
        progress = [(f.get("current_leg",0)+1-f["remaining_fraction"])/len(legs_for(meta,t))
                    for f in features.values() if "remaining_fraction" in f]
        columns["progress_band"].append(round(float(np.mean(progress)),2) if progress else None)
        columns["status_code"].append(STATUSES.index(status))
        columns["reason_code"].append(reason or "experimental_joint_reference; identity_calibration")
        columns["no_finisher_prob"].append(round(forecast.no_finisher_prob,6) if forecast and forecast.available else None)
        columns["numerical_error"].append(round(forecast.numerical_error_95,6) if forecast and forecast.available else None)
        for b in boats:
            f=features[b]
            columns["win_prob_by_boat"][b].append(round(forecast.win_prob_by_boat[entries[b]],6) if forecast and forecast.available else None)
            columns["source_age_ms_by_boat"][b].append(f.get("source_age_ms"))
            radius=f.get("radius_95_m")
            columns["position_uncertainty_summary_by_boat"][b].append(round(radius,1) if radius is not None else None)
            columns["quality_code_by_boat"][b].append(STATUSES.index(f["quality"]))
    artifact = {"header":{"schema_version":"prediction-1","race_id":meta["race_id"],"boat_ids":boats,
               "replay_boat_ids":replay_ids,
               "scheduled_entries":[{"id":b,"team_code":meta["identities"][b]["entry_id"],
                                     "team_name":meta["identities"][b]["name"]} for b in boats],
               "boat_class":"AC40","model_ref":model_ref,"source_manifest_hash":manifest_hash,
               "scenario_hash":content_hash(scenario),"status_dictionary":STATUSES,
               "method_and_assumption_refs":["causal-mc-1","identity-calibration; experimental source timings",
                    "nonfinish-rank-N","modeled-latency-6000ms","docs/forecasting_implementation.md"],
               "train_cutoff_ms":training_cutoff,"result_cutoff_ms":training_cutoff,"scope":"baseline",
               "pre_race_condition_cutoff_ms":meta["gun_ms"]-BUFFER_MS-1,
               "pre_race_available_at_ms":meta["gun_ms"]-1,
               "max_state_age_ms":20000,"units":{"probability":"0..1","position":"rank; nonfinish=N",
                    "timestamps":"Unix ms","uncertainty":"95% ellipse major radius metres"}},
               "pre_race":pre,"live":columns}
    validate_race(artifact)
    return artifact


def export_archive(root: Path, *, race_id=None, pre_n=100000, live_n=20000):
    started=time.perf_counter()
    metadata, labels, transitions, reviews = prepare(root)
    provenance_doc = provenance(root,metadata)
    manifest_hash=content_hash(provenance_doc)
    backtest_path=root/".forecast"/"backtest.json"
    backtest=json.loads(backtest_path.read_text()) if backtest_path.exists() else {}
    selected_model=("correlated_mc" if backtest.get("source_manifest_hash")==manifest_hash
                    and backtest.get("promotion",{}).get("promoted") else "joint_pl_reference")
    directory=root/"public"/"data"/"predictions"
    directory.mkdir(parents=True,exist_ok=True)
    manifest_path=f"manifests/{manifest_hash}.json"
    atomic_json(directory/manifest_path,provenance_doc)
    index={"schema_version":"prediction-index-1","races":[],
           "source_manifest_path":manifest_path,"source_manifest_hash":manifest_hash}
    selected=[m for m in metadata if not race_id or m["race_id"]==race_id]
    if not selected:
        raise ValueError("No matching dataset race")
    fits={}
    for meta in sorted(selected,key=lambda x:(x["date"],x["race_id"])):
        # Audit days keep the candidate frozen before 26 September.
        date=min(meta["date"],"2026-09-26")
        if date not in fits:
            strength,times,completion=fitted_before(date,labels,transitions,reviews)
            parameters,certificate=state_before(root,date,metadata)
            card={"schema_version":"prediction-model-1","training_before_day":date,
                  "source_manifest_hash":manifest_hash,"strength":strength.to_dict(),
                  "leg_times_candidate":times.to_dict(),"completion":completion.to_dict(),
                  "filter_parameters":parameters,"outage_certificate":certificate,
                  "selected":selected_model,"promotion_status":backtest.get("promotion",{"reason":"No audited unconditional evaluation; reference retained"}),
                  "calibration":"identity; no empirical calibrated-accuracy claim","pre_simulations":pre_n,"live_simulations":live_n}
            ref=content_hash(card)
            atomic_json(directory/"models"/(ref+".json"),card)
            fits[date]=(strength,times,completion,parameters,certificate,ref)
        strength,times,completion,parameters,certificate,ref=fits[date]
        artifact=build_race(root,meta,strength,times,completion,manifest_hash=manifest_hash,model_ref=ref,
                            parameters=parameters,certificate=certificate,pre_n=pre_n,live_n=live_n,training_before_day=date,
                            selected_model=selected_model)
        relative="races/"+meta["race_id"]+"_"+content_hash(artifact)+".json"
        atomic_json(directory/relative,artifact)
        presets=[{"id":f"wind_{w}_{d+15}","tws_kt":w,"direction_offset_deg":d,"scope":"pre_race",
                  "status":"unavailable","reason":"Audited completion and condition support required; build custom scenarios in Python"}
                 for w in (8,12,16,20) for d in (-15,0,15)]
        index["races"].append({"race_id":meta["race_id"],"path":relative,
                "boat_ids":artifact["header"]["boat_ids"],"replay_boat_ids":artifact["header"]["replay_boat_ids"],
                **{k:artifact["header"][k] for k in ("source_manifest_hash","model_ref","scenario_hash")},"presets":presets})
    from .cup import public_cup_artifact
    cup=public_cup_artifact(source_manifest_hash=manifest_hash)
    index["cup_path"]="cup/"+content_hash(cup)+".json"
    atomic_json(directory/index["cup_path"],cup)
    # Validate the staged index before publication; immutable objects keep the
    # previously published index usable if any preceding step fails.
    verify_public(root,index=index)
    atomic_json(directory/"index.json",index)  # publish index last
    atomic_json(directory/"cup_2027.json",cup)  # convenient stable download alias
    report=verify_public(root)
    report.update(seconds=round(time.perf_counter()-started,3),unavailable_reason="Audited completion denominator absent" if not reviews else None)
    atomic_json(root/".forecast"/"build_report.json",report)
    return report


def export_pre_race_scenario(root: Path, race_id: str, *, tws_kt: float, direction_offset_deg: float, n=100000):
    """Exact custom pre-race artifact; never mutates the live/Cup baseline."""
    from .simulation import simulate_order_reference
    from .weather import condition_support
    metadata,labels,transitions,reviews=prepare(root)
    meta=next((m for m in metadata if m["race_id"]==race_id),None)
    if not meta:
        raise ValueError("Unknown race field")
    date=min(meta["date"],"2026-09-26")
    strength,times,completion=fitted_before(date,labels,transitions,reviews)
    support,reason=condition_support(before_day(transitions,date),tws_kt=tws_kt,direction_offset_deg=direction_offset_deg)
    manifest=provenance(root,metadata)
    mh=content_hash(manifest)
    card={"schema_version":"prediction-model-1","training_before_day":date,"strength":strength.to_dict(),
          "completion":completion.to_dict(),"source_manifest_hash":mh,"selected":"joint_pl_reference",
          "wind_response":"zero-effect reference retained; conditional response not promoted"}
    ref=content_hash(card)
    artifact=build_race(root,meta,strength,times,completion,manifest_hash=mh,model_ref=ref,training_before_day=date,
                        pre_n=n,live_n=20000)
    conditions={"tws_kt":tws_kt,"direction_offset_deg":direction_offset_deg}
    artifact["header"].update(scope="pre_race",conditions=conditions,scenario_hash=content_hash({"scope":"pre_race","field":meta["boat_ids"],**conditions}))
    artifact["live"]={key:({b:[] for b in value} if isinstance(value,dict) else []) for key,value in artifact["live"].items()}
    if support:
        entries={b:meta["identities"][b]["entry_id"] for b in meta["boat_ids"]}
        prediction=simulate_order_reference(strength,list(entries.values()),completion,n=n,seed=42,wind_knots=tws_kt)
        artifact["pre_race"].update(status="estimated" if prediction.available else "unavailable",reason=prediction.reason,
            expected_position_by_boat={b:prediction.expected_position_by_boat[entries[b]] for b in entries})
    else:
        artifact["pre_race"].update(status="unavailable",reason=reason,
            expected_position_by_boat=dict.fromkeys(meta["boat_ids"]))
    validate_race(artifact)
    directory=root/"public"/"data"/"predictions"
    relative="scenarios/"+content_hash(artifact)+".json"
    atomic_json(directory/relative,artifact)
    atomic_json(directory/"models"/(ref+".json"),card)
    atomic_json(directory/"manifests"/(mh+".json"),manifest)
    # Add this exact condition to the matching race without replacing the live
    # model/reference. Index publication is the final operation.
    index=json.loads((directory/"index.json").read_text())
    target=next(e for e in index["races"] if e["race_id"]==race_id)
    preset={"id":content_hash(conditions),"path":relative,"scope":"pre_race",**conditions,
            "boat_ids":artifact["header"]["boat_ids"],"replay_boat_ids":artifact["header"]["replay_boat_ids"],
            "status":artifact["pre_race"]["status"],"reason":artifact["pre_race"].get("reason"),
            "model_ref":ref,"source_manifest_hash":mh,"scenario_hash":artifact["header"]["scenario_hash"]}
    target["presets"]=[p for p in target.get("presets",[]) if not(p["tws_kt"]==tws_kt and p["direction_offset_deg"]==direction_offset_deg)]+[preset]
    verify_public(root,index=index)
    atomic_json(directory/"index.json",index)
    return {"path":relative,"status":artifact["pre_race"]["status"],"reason":artifact["pre_race"].get("reason")}
