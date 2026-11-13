"""Reproducible offline fit/build. No inference or probability repair in the UI."""
from __future__ import annotations
from datetime import datetime, timezone
from importlib import metadata as packages
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from .contracts import STATUSES, atomic_json, content_hash, validate_cup, validate_race, verify_public
from .labels import race_labels, leg_rows, load_reviews, before_day, source_completion_records, current_along_leg_mps, select_training_order_rows, attach_official_results
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
    print("Verifying dataset archive (28 raw files, 6.87 GB)...", file=sys.stderr, flush=True)
    metadata = metadata_archive(root)
    env_dir = root / "public" / "data" / "environment"
    for meta in metadata:
        env_file = env_dir / (meta["race_id"] + ".json")
        if env_file.exists():
            try:
                meta["environment"] = json.loads(env_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta["environment"] = None
    labels, transitions = [], []
    for meta in metadata:
        raw = root / "Data" / meta["source_file"]
        if not raw.exists():
            raw = root / "Data" / "AC38" / meta["source_file"]
        if not raw.exists():
            for match in (root / "Data").rglob(meta["source_file"]):
                raw = match
                break
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
    return metadata, labels, transitions, completion_records(root, metadata, labels)


def completion_records(root, metadata, labels):
    """Independent reviews override; otherwise source reconstructions (tiered)."""
    reviews = load_reviews(root, metadata)
    reviewed = {r["race_id"] for r in reviews}
    by_id = {m["race_id"]: m for m in metadata}
    source = [r for label in labels if label["race_id"] not in reviewed
              for r in source_completion_records(by_id[label["race_id"]], label)]
    return reviews + source


def fitted_before(date, labels, transitions, reviews):
    return (StrengthModel.fit(before_day(labels, date), strength_sd=1.2, practice_weight=0.5, discrimination_scale=1.8),
            LegTimeModel.fit(before_day(transitions, date)),
            CompletionModel.fit(before_day(reviews, date)))


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
    axis = course.get("course_axis")
    return [{"distance_m":float(course["course_length"]),"leg_kind":"odd" if i%2==0 else "even",
             "c_parallel_mps": current_along_leg_mps(meta.get("environment"), cutoff, axis, i)}
            for i in range(len(course["sequences"])-1)]


def simulation_states(features, times, legs):
    """The same causal conditioner is used for evaluation and deployment."""
    states={entry:dict(feature,started=True) for entry,feature in features.items()}
    for entry,state in states.items():
        if state.get("vmg_mps",0)>0 and state.get("leg_length_m",0)>0 and 0<=state.get("current_leg",-1)<len(legs):
            leg = legs[state["current_leg"]]
            c = float(leg.get("c_parallel_mps") or 0.0)
            vmg_water = state["vmg_mps"] - c
            if vmg_water > 0:
                full_water = times.median_seconds(entry, {**leg, "c_parallel_mps": 0.0})
                state["pace_ratio"] = vmg_water * full_water / state["leg_length_m"]
            else:
                full = times.median_seconds(entry, leg)
                state["pace_ratio"] = state["vmg_mps"] * full / state["leg_length_m"]
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
    pre_available = simulation.available and completion.scheduled_audited > 0
    pre = {"status":"estimated" if pre_available else "unavailable",
           "reason":None if pre_available else (simulation.reason or "No earlier competitive scheduled-entry completion denominator"),
           "expected_position_by_boat":{b:(simulation.expected_position_by_boat[entries[b]] if pre_available else None) for b in boats},
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


def export_archive(root: Path, *, race_id=None, pre_n=100000, live_n=20000, cup_trials=5000, cup_seed=2027):
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
    print(f"Building {len(selected)} race prediction artifact(s)...", file=sys.stderr, flush=True)
    fits={}
    for idx, meta in enumerate(sorted(selected,key=lambda x:(x["date"],x["race_id"])), 1):
        print(f"  [{idx}/{len(selected)}] Simulating {meta['race_id']}...", file=sys.stderr, flush=True)
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
    # Select the Cup source explicitly; do not inherit the final loop variable.
    cup_cutoff = max(fits)
    cup_model_ref = fits[cup_cutoff][-1]
    cup_model = json.loads((directory / "models" / (cup_model_ref + ".json")).read_text())
    cup = _cup_from_pinned_model(root, cup_model_ref, cup_model, manifest_hash,
                                 trials=cup_trials, seed=cup_seed)
    index["cup_path"] = "cup/" + content_hash(cup) + ".json"
    atomic_json(directory / index["cup_path"], cup)
    # Validate the staged index before publication; immutable objects keep the
    # previously published index usable if any preceding step fails.
    verify_public(root,index=index)
    atomic_json(directory/"index.json",index)  # publish index last
    atomic_json(directory/"cup_2027.json",cup)  # convenient stable download alias
    if (root/"public"/"data"/"manifests.json").is_file():
        from scripts.build_artifact_inventory import build_inventory
        build_inventory(root)
    report=verify_public(root)
    report.update(seconds=round(time.perf_counter()-started,3),unavailable_reason="Audited completion denominator absent" if not reviews else None)
    atomic_json(root/".forecast"/"build_report.json",report)
    return report


def _cup_from_pinned_model(root, model_ref, model, manifest_hash, *, trials, seed,
                           roster_policy: str = "equal",
                           propagate_covariance: bool = False,
                           transfer_variance_tau_sq: float = 0.0,
                           feasible_slot_rule_bounds: bool = True):
    from .cup import (
        TEAM_IDS,
        cup_mapping_provenance,
        map_ac40_to_cup,
        map_ac40_to_cup_with_covariance,
        public_cup_artifact,
        standard_scenarios,
    )
    if content_hash(model) != model_ref or model["source_manifest_hash"] != manifest_hash:
        raise ValueError("Pinned Cup model/source hash mismatch")
    cutoff = model["training_before_day"]
    lineage = {"model_ref": model_ref, "training_before_day": cutoff,
               "training_cutoff_ms": int(datetime.fromisoformat(cutoff).replace(tzinfo=timezone.utc).timestamp() * 1000),
               "selection_policy": "Explicit pinned chronological strength model; source outcomes on/after its training-before-day are excluded.",
               "strength_method": model["strength"]["method"],
               "source_manifest_hash": manifest_hash}
    effects = model["strength"]["effects"]

    direct_dist = None
    posterior_draws_by_scenario = None
    if propagate_covariance or roster_policy != "equal":
        cov_matrix = model["strength"].get("covariance") or model["strength"].get("covariance_matrix")
        entries = model["strength"].get("boat_order") or model["strength"].get("entries") or sorted(effects.keys())
        if cov_matrix is not None:
            cov_arr = np.array(cov_matrix, dtype=float)
            mapped_str, _, cov_syndicate = map_ac40_to_cup_with_covariance(
                effects, cov_arr, entries, policy=roster_policy
            )
            cov_clean = 0.5 * (cov_syndicate + cov_syndicate.T) + 1e-9 * np.eye(7)
            mu_vec = np.array([float(mapped_str.get(t, 0.0)) for t in TEAM_IDS], dtype=float)
            missing_mask = np.array([t not in mapped_str for t in TEAM_IDS], dtype=bool)
            rng_cup = np.random.default_rng(seed)
            base_cov_draws = rng_cup.multivariate_normal(mu_vec, cov_clean, size=trials)
            pop_draws = rng_cup.normal(0.0, 0.5, size=(trials, 7))
            base_worlds = np.where(missing_mask[None, :], pop_draws, base_cov_draws)
            res_noise = rng_cup.normal(0.0, 1.0, size=(trials, 7))
            posterior_draws_by_scenario = {}
            for sc in standard_scenarios():
                res_sd = math.sqrt((sc.sigma_multiplier * 0.5) ** 2 + (transfer_variance_tau_sq if transfer_variance_tau_sq > 0 else 0.0))
                posterior_draws_by_scenario[sc.scenario_id] = sc.rho * base_worlds + res_noise * res_sd
            if transfer_variance_tau_sq > 0.0:
                for t in mapped_str:
                    if t in TEAM_IDS:
                        idx = TEAM_IDS.index(t)
                        cov_syndicate[idx, idx] += transfer_variance_tau_sq
            direct_dist = {
                "team_order": list(TEAM_IDS),
                "covariance": cov_syndicate.tolist(),
                "mean": mapped_str
            }
            target_strengths = mapped_str
        else:
            target_strengths = map_ac40_to_cup(effects)
    else:
        target_strengths = map_ac40_to_cup(effects)

    cup = public_cup_artifact(
        source_manifest_hash=manifest_hash,
        mapped_strength=target_strengths,
        trials=trials,
        seed=seed,
        model_lineage=lineage,
        mapping_provenance=cup_mapping_provenance(effects, policy=roster_policy),
        feasible_slot_rule_bounds=feasible_slot_rule_bounds,
        direct_ac75_distribution=direct_dist,
        posterior_draws_by_scenario=posterior_draws_by_scenario,
    )
    cup["header"]["model_ref"] = model_ref
    cup["header"]["method_version"] = "cup-ac38-conditional-2"
    cup["build_provenance"] = {"policy": "Reuse the hashed strength model and its original source manifest; record current Cup-generation code separately.",
        "code_sha256": {str(path): digest(root / path) for path in
                        ("pipeline/prediction/cup.py", "pipeline/prediction/build.py", "pipeline/prediction/contracts.py")
                        if (root / path).is_file()}}
    validate_cup(cup)
    return cup


def build_cup_candidate(root: Path, *, model_ref=None, trials=5000, seed=2027, output_path=None):
    """Build only a reviewable Cup candidate from an already pinned model.

    Never reads raw telemetry or updates the public index. The unchanged model
    source manifest remains the model's provenance, not the new generator code.
    """
    root = Path(root)
    directory = root / "public" / "data" / "predictions"
    index = json.loads((directory / "index.json").read_text())
    refs = {entry["model_ref"] for entry in index["races"]}
    if not refs or any(not isinstance(ref, str) or not re.fullmatch(r"[a-f0-9]{64}", ref) for ref in refs):
        raise ValueError("Active Cup model references must be content hashes")
    manifest_hash = index["source_manifest_hash"]
    if not isinstance(manifest_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", manifest_hash):
        raise ValueError("Invalid pinned Cup source manifest hash")
    source_manifest = json.loads((directory / "manifests" / (manifest_hash + ".json")).read_text())
    if content_hash(source_manifest) != manifest_hash:
        raise ValueError("Pinned Cup source manifest content hash mismatch")
    if model_ref is not None and model_ref not in refs:
        raise ValueError("Requested Cup strength model is not pinned by the active forecast index")
    models = {ref: json.loads((directory / "models" / (ref + ".json")).read_text()) for ref in refs}
    if model_ref is None:
        model_ref = max(models, key=lambda ref: (models[ref]["training_before_day"], ref))
    cup = _cup_from_pinned_model(root, model_ref, models[model_ref], index["source_manifest_hash"], trials=trials, seed=seed)
    destination = Path(output_path) if output_path is not None else root / ".forecast" / "cup_candidate.json"
    if destination.resolve().is_relative_to((root / "public").resolve()):
        raise ValueError("Cup candidate output must stay outside public; use publish_cup_candidate after review")
    atomic_json(destination, cup)
    return {"candidate_path": str(destination), "content_hash": content_hash(cup), "model_ref": model_ref,
            "training_before_day": models[model_ref]["training_before_day"], "trials_per_scenario": trials,
            "seed": seed, "status": cup["status"]}


def publish_cup_candidate(root: Path, candidate_path: Path):
    """Publish a reviewed candidate with the existing atomic index contract."""
    root = Path(root)
    directory = root / "public" / "data" / "predictions"
    cup = json.loads(Path(candidate_path).read_text())
    validate_cup(cup)
    index = json.loads((directory / "index.json").read_text())
    ref = cup["header"].get("model_ref")
    model_file = directory / "models" / (ref + ".json")
    if ref not in {entry["model_ref"] for entry in index["races"]} and not model_file.is_file():
        raise ValueError("Cup candidate model is not in the active forecast index")
    model = json.loads(model_file.read_text())
    if (content_hash(model) != ref or model["source_manifest_hash"] != index["source_manifest_hash"]
            or cup["header"]["source_manifest_hash"] != index["source_manifest_hash"]):
        raise ValueError("Cup candidate provenance differs from active forecast publication")
    if cup.get("scenario_analysis"):
        from .cup import cup_mapping_provenance
        evidence = cup["scenario_analysis"]
        lineage = evidence["model_lineage"]
        expected_cutoff = int(datetime.fromisoformat(model["training_before_day"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        if (lineage.get("training_before_day") != model["training_before_day"]
                or lineage.get("training_cutoff_ms") != expected_cutoff
                or lineage.get("strength_method") != model["strength"]["method"]
                or evidence["mapping_provenance"] != cup_mapping_provenance(model["strength"]["effects"])):
            raise ValueError("Cup candidate model cutoff or mapping differs from the pinned strength model")
    index["cup_path"] = "cup/" + content_hash(cup) + ".json"
    atomic_json(directory / index["cup_path"], cup)
    verify_public(root, index=index)
    atomic_json(directory / "index.json", index)
    atomic_json(directory / "cup_2027.json", cup)
    return {"cup_path": index["cup_path"], "model_ref": ref, "verification": "passed"}


def build_private_forecast_bundle(
    root: Path,
    *,
    output_dir: Path | None = None,
    prefer_official: bool = True,
    entry_id_mode: str = "event_entry",
    roster_policy: str = "equal",
    condition_effects: bool = False,
    strength_sd: float = 0.55,
    propagate_covariance: bool = True,
    include_transfer_uncertainty: bool = False,
    trials: int = 5000,
    seed: int = 2027,
    training_before_day: str = "2026-09-26",
    use_official_results: bool | None = None,
    feasible_slot_rule_bounds: bool = True,
) -> dict:
    """Build an isolated candidate forecast bundle under .forecast/candidates/<bundle_hash>/

    Never updates the public directory or public index.
    """
    if use_official_results is not None:
        prefer_official = bool(use_official_results)
        if not use_official_results:
            propagate_covariance = False

    root = Path(root)
    predictions_dir = root / "public" / "data" / "predictions"
    index = json.loads((predictions_dir / "index.json").read_text())
    source_manifest_hash = index["source_manifest_hash"]

    # 1. Evidence manifest
    evidence_files = [
        "docs/official_results_ac38_prelims.json",
        "docs/ac37_verified_anchors.json",
        "docs/ac37_results.json",
        "docs/ac37_ac40_2023_results.json",
        "docs/ac38_rules_extracted.json",
        "docs/ac38_roster.json",
        "docs/ac38_team_covariates.json",
        "docs/forecast_rules_sources.json",
        "docs/rules_tie_audit.md",
        "docs/market_odds.json",
        ".forecast/transfer/ac37_transfer.json",
    ]
    fit_config = {
        "prefer_official": prefer_official,
        "entry_id_mode": entry_id_mode,
        "roster_policy": roster_policy,
        "condition_effects": condition_effects,
        "strength_sd": strength_sd,
        "propagate_covariance": propagate_covariance,
        "include_transfer_uncertainty": include_transfer_uncertainty,
    }
    evidence_manifest = {
        "schema_version": "evidence-manifest-2",
        "retrieved_at": "2026-11-08T12:00:00+00:00",
        "files": {},
        "fit_config": fit_config,
    }
    for rel in evidence_files:
        fpath = root / rel
        if fpath.exists():
            evidence_manifest["files"][rel] = digest(fpath)
    evidence_manifest_hash = content_hash(evidence_manifest)

    # 2. Refit or reuse model
    refs = {entry["model_ref"] for entry in index["races"]}
    models = {ref: json.loads((predictions_dir / "models" / (ref + ".json")).read_text()) for ref in refs}
    matching_ref = next((ref for ref in refs if models[ref].get("training_before_day") == training_before_day), None)

    official_path = root / "docs" / "official_results_ac38_prelims.json"
    has_official_diff = False
    if prefer_official and official_path.exists():
        off_doc = json.loads(official_path.read_text(encoding="utf-8"))
        for r in off_doc.get("races", []):
            if r.get("date", "") < training_before_day:
                if r.get("official_order") != r.get("on_water_finish_order"):
                    has_official_diff = True
                    break

    has_custom_config = (
        entry_id_mode != "event_entry"
        or roster_policy != "equal"
        or condition_effects is True
        or abs(strength_sd - 0.55) > 1e-6
        or propagate_covariance is True
        or include_transfer_uncertainty is True
    )

    if matching_ref and not has_official_diff and not has_custom_config and not prefer_official:
        candidate_model_ref = matching_ref
        candidate_model = dict(models[matching_ref])
    else:
        metadata = metadata_archive(root)
        labels = [race_labels(meta) for meta in metadata]
        if prefer_official:
            attach_official_results({l["race_id"]: l for l in labels}, official_path)
        cutoff_ms = int(datetime.fromisoformat(training_before_day).replace(tzinfo=timezone.utc).timestamp() * 1000)
        rows = before_day(labels, training_before_day)
        fit_rows = select_training_order_rows(
            rows,
            prefer_official=prefer_official,
            cutoff_ms=cutoff_ms,
        )
        from .models import StrengthModel
        strength = StrengthModel.fit(
            fit_rows,
            strength_sd=strength_sd,
            practice_weight=0.5,
            discrimination_scale=1.8,
            condition_effects=condition_effects,
        )
        str_dict = strength.to_dict()
        if "covariance" in str_dict and "covariance_matrix" not in str_dict:
            str_dict["covariance_matrix"] = str_dict["covariance"]
        if "boat_order" in str_dict and "entries" not in str_dict:
            str_dict["entries"] = str_dict["boat_order"]

        candidate_model = {
            "schema_version": "prediction-model-1",
            "training_before_day": training_before_day,
            "source_manifest_hash": source_manifest_hash,
            "evidence_manifest_hash": evidence_manifest_hash,
            "strength": str_dict,
            "selected": "joint_pl_reference",
            "calibration": "identity; no empirical calibrated-accuracy claim",
            "training_labels_source": "official_results" if prefer_official else "on_water",
            "fit_config": fit_config,
        }
        candidate_model_ref = content_hash(candidate_model)

    # 3. Build Cup candidate with optional covariance & transfer uncertainty
    tau_sq = 0.0
    if include_transfer_uncertainty:
        transfer_file = root / ".forecast" / "transfer" / "ac37_transfer.json"
        if transfer_file.exists():
            t_doc = json.loads(transfer_file.read_text(encoding="utf-8"))
            tau_val = float(t_doc.get("tau_mode", 0.54))
            tau_sq = tau_val ** 2

    cup = _cup_from_pinned_model(
        root,
        candidate_model_ref,
        candidate_model,
        source_manifest_hash,
        trials=trials,
        seed=seed,
        roster_policy=roster_policy,
        propagate_covariance=propagate_covariance,
        transfer_variance_tau_sq=tau_sq,
        feasible_slot_rule_bounds=feasible_slot_rule_bounds,
    )
    validate_cup(cup)
    cup_hash = content_hash(cup)

    # 4. Write into isolated bundle directory
    bundle_content = {
        "model_ref": candidate_model_ref,
        "cup_hash": cup_hash,
        "source_manifest_hash": source_manifest_hash,
        "evidence_manifest_hash": evidence_manifest_hash,
        "training_before_day": training_before_day,
        "trials": trials,
        "seed": seed,
        "fit_config": fit_config,
    }
    bundle_hash = content_hash(bundle_content)
    bundle_dir = output_dir if output_dir is not None else root / ".forecast" / "candidates" / bundle_hash
    if bundle_dir.resolve().is_relative_to((root / "public").resolve()):
        raise ValueError("Private bundle must stay outside public directory")

    atomic_json(bundle_dir / "models" / (candidate_model_ref + ".json"), candidate_model)
    atomic_json(bundle_dir / "manifests" / (evidence_manifest_hash + ".json"), evidence_manifest)
    atomic_json(bundle_dir / "cup" / (cup_hash + ".json"), cup)
    atomic_json(bundle_dir / "bundle.json", bundle_content)

    # 5. Build evaluation.json
    eval_doc = {
        "schema_version": "candidate-evaluation-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_model_ref": candidate_model_ref,
        "fit_config": fit_config,
        "market_comparison": {"status": "no_verified_market_snapshots", "snapshots_count": 0},
    }
    atomic_json(bundle_dir / "evaluation.json", eval_doc)

    # 6. Build diff_vs_public.json
    diff_doc: dict[str, Any] = {
        "schema_version": "candidate-diff-vs-public-1",
        "candidate_cup_hash": cup_hash,
        "public_cup_path": index.get("cup_path"),
        "team_diffs": {},
    }
    public_cup_file = predictions_dir / index.get("cup_path", "cup_2027.json")
    if not public_cup_file.is_file():
        public_cup_file = predictions_dir / "cup_2027.json"
    if public_cup_file.is_file():
        try:
            pub_cup = json.loads(public_cup_file.read_text(encoding="utf-8"))
            pub_bounds = pub_cup.get("rule_bounds_by_team", {})
            pub_envelope = pub_cup.get("scenario_envelope_by_team", {})
            cand_bounds = cup.get("rule_bounds_by_team", {})
            cand_envelope = cup.get("scenario_envelope_by_team", {})
            from .cup import TEAM_IDS
            for t in TEAM_IDS:
                pb = pub_bounds.get(t, {"lower": 0.0, "upper": 1.0})
                cb = cand_bounds.get(t, {"lower": 0.0, "upper": 1.0})
                pe = pub_envelope.get(t, {"lower": 0.0, "upper": 1.0})
                ce = cand_envelope.get(t, {"lower": 0.0, "upper": 1.0})
                diff_doc["team_diffs"][t] = {
                    "rule_bounds": {
                        "candidate": cb,
                        "public": pb,
                        "delta_lower": round(cb["lower"] - pb["lower"], 4),
                        "delta_upper": round(cb["upper"] - pb["upper"], 4),
                        "delta_width": round((cb["upper"] - cb["lower"]) - (pb["upper"] - pb["lower"]), 4),
                    },
                    "scenario_envelope": {
                        "candidate": ce,
                        "public": pe,
                        "delta_lower": round(ce["lower"] - pe["lower"], 4),
                        "delta_upper": round(ce["upper"] - pe["upper"], 4),
                        "delta_width": round((ce["upper"] - ce["lower"]) - (pe["upper"] - pe["lower"]), 4),
                    }
                }
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            diff_doc["diff_error"] = str(exc)
    atomic_json(bundle_dir / "diff_vs_public.json", diff_doc)

    return {
        "bundle_dir": str(bundle_dir),
        "bundle_hash": bundle_hash,
        "candidate_model_ref": candidate_model_ref,
        "cup_hash": cup_hash,
        "evidence_manifest_hash": evidence_manifest_hash,
        "source_manifest_hash": source_manifest_hash,
        "status": cup["status"],
        "evaluation_path": str(bundle_dir / "evaluation.json"),
        "diff_vs_public_path": str(bundle_dir / "diff_vs_public.json"),
    }


def publish_forecast_bundle(root: Path, bundle_dir: Path) -> dict:
    """Promote a reviewed private bundle to public/data/predictions/."""
    root = Path(root)
    bundle_dir = Path(bundle_dir)
    bundle_file = bundle_dir / "bundle.json"
    if not bundle_file.exists():
        raise ValueError(f"No bundle.json found in {bundle_dir}")
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))

    model_ref = bundle["model_ref"]
    cup_hash = bundle["cup_hash"]
    evidence_manifest_hash = bundle.get("evidence_manifest_hash")

    model_path = bundle_dir / "models" / (model_ref + ".json")
    cup_path = bundle_dir / "cup" / (cup_hash + ".json")
    if not model_path.exists() or not cup_path.exists():
        raise ValueError("Missing bundle artifact files")

    model = json.loads(model_path.read_text(encoding="utf-8"))
    cup = json.loads(cup_path.read_text(encoding="utf-8"))
    validate_cup(cup)

    public_dir = root / "public" / "data" / "predictions"
    index = json.loads((public_dir / "index.json").read_text(encoding="utf-8"))

    # Copy model
    atomic_json(public_dir / "models" / (model_ref + ".json"), model)

    # Copy evidence manifest if present
    if evidence_manifest_hash:
        ev_path = bundle_dir / "manifests" / (evidence_manifest_hash + ".json")
        if ev_path.exists():
            ev_doc = json.loads(ev_path.read_text(encoding="utf-8"))
            atomic_json(public_dir / "manifests" / (evidence_manifest_hash + ".json"), ev_doc)
            index["evidence_manifest_hash"] = evidence_manifest_hash
            index["evidence_manifest_path"] = "manifests/" + evidence_manifest_hash + ".json"

    # Copy Cup
    index["cup_path"] = "cup/" + cup_hash + ".json"
    atomic_json(public_dir / index["cup_path"], cup)

    # Verify and publish index atomically
    verify_public(root, index=index)
    atomic_json(public_dir / "index.json", index)
    atomic_json(public_dir / "cup_2027.json", cup)

    if (root / "public" / "data" / "manifests.json").is_file():
        from scripts.build_artifact_inventory import build_inventory
        build_inventory(root)

    return {
        "bundle_dir": str(bundle_dir),
        "model_ref": model_ref,
        "cup_path": index["cup_path"],
        "evidence_manifest_hash": evidence_manifest_hash,
        "verification": "passed"
    }


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
    if (root/"public"/"data"/"manifests.json").is_file():
        from scripts.build_artifact_inventory import build_inventory
        build_inventory(root)
    return {"path":relative,"status":artifact["pre_race"]["status"],"reason":artifact["pre_race"].get("reason")}
