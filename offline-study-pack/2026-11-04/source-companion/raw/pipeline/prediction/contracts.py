"""Fail-closed public artifact validation and atomic JSON exports."""
from __future__ import annotations
import gzip
import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

STATUSES = ["available", "estimated", "gate_ambiguous", "unavailable"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def content_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="."+path.name+".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(canonical(value)+b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                # Windows readers/antivirus can briefly deny replacement. Never
                # fall back to truncating the last successfully published file.
                if attempt == 7:
                    raise
                time.sleep(min(.1*2**attempt, 1.))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_cup(value):
    """Validate additive scenario evidence while accepting earlier cup-1 files."""
    analysis = value.get("scenario_analysis")
    if analysis is None:
        if (value.get("header", {}).get("method_version") == "cup-ac38-conditional-2"
                and value.get("status") in STATUSES[:2]):
            raise ValueError("Cup scenario evidence: required for a usable cup-ac38-conditional-2 publication")
        return
    def require(condition, message):
        if not condition:
            raise ValueError("Cup scenario evidence: " + message)
    def integer(number):
        return isinstance(number, int) and not isinstance(number, bool) and number >= 0
    def probability(number):
        return isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) and 0 <= number <= 1
    require(isinstance(analysis, dict) and analysis.get("schema_version") == "cup-scenarios-1", "unsupported schema")
    teams = {team["id"] for team in value["teams"]}
    for field in ("probabilities", "win_prob_by_team"):
        headline = value.get(field)
        require(isinstance(headline, dict) and set(headline) == teams
                and all(number is None for number in headline.values()),
                "headline Cup probability containers must include every team with null values")
    from .cup import CupScenario
    lineage = analysis["model_lineage"]
    require(lineage.get("model_ref") == value["header"].get("model_ref"), "header/model lineage mismatch")
    if lineage.get("model_ref") is not None:
        require(re.fullmatch(r"[a-f0-9]{64}", lineage["model_ref"]) is not None
                and lineage.get("source_manifest_hash") == value["header"]["source_manifest_hash"], "invalid pinned model lineage")
    records = analysis.get("records", [])
    ids = [record["scenario_id"] for record in records]
    require(bool(records) and len(set(ids)) == len(ids), "missing or duplicate scenarios")
    require(ids == value.get("evaluated_scenarios") == value.get("scenarios"), "scenario index mismatch")
    require(analysis["baseline_scenario_id"] in ids, "baseline absent from grid")
    budget = analysis["build_budget"]
    require(integer(budget["trials_per_scenario"]) and budget["trials_per_scenario"] > 0
            and budget["scenario_count"] == len(records) and integer(budget["seed"]), "invalid build budget")
    for record in records:
        scenario = CupScenario(**record["scenario"])
        scenario.validate()
        require(scenario.scenario_id == record["scenario_id"], "scenario ID/parameter mismatch")
        n, resolved, unresolved = record["trials"], record["resolved_trials"], record["unresolved_trials"]
        require(integer(n) and n > 0 and integer(resolved) and integer(unresolved) and resolved + unresolved == n, "trial counts do not reconcile")
        require(n == budget["trials_per_scenario"] and record["seed"] == budget["seed"], "scenario budget mismatch")
        require(abs(record["resolved_fraction"] - resolved / n) < 1e-12
                and abs(record["unresolved_fraction"] - unresolved / n) < 1e-12, "trial fractions do not reconcile")
        require(set(record["resolved_win_counts"]) == teams and all(integer(c) for c in record["resolved_win_counts"].values())
                and sum(record["resolved_win_counts"].values()) == resolved, "resolved wins do not reconcile")
        first = record["first_unresolved_stage_counts"]
        require(all(integer(count) and count > 0 for count in first.values()) and sum(first.values()) == unresolved, "first-stage counts are not mutually exclusive")
        require(all(integer(count) and 0 < count <= n for count in record["overlapping_reason_counts"].values()), "invalid overlapping reason counts")
        require(sum(record["overlapping_reason_counts"].values()) >= unresolved, "missing unresolved reason attribution")
        require(record["status"] == ("rule_bounds" if unresolved else "conditional_scenario"), "incorrect scenario status")
        require(set(record["rule_bounds"]) == teams and set(record["probabilities"]) == teams, "incomplete scenario field")
        for team in teams:
            bounds = record["rule_bounds"][team]
            count = record["resolved_win_counts"][team]
            require(probability(bounds["lower"]) and probability(bounds["upper"])
                    and abs(bounds["lower"] - count / n) < 1e-12
                    and abs(bounds["upper"] - min(1, (count + unresolved) / n)) < 1e-12, "bounds do not reconstruct from counts")
            require(record["probabilities"][team] is None if unresolved else
                    probability(record["probabilities"][team]) and abs(record["probabilities"][team] - count / n) < 1e-12,
                    "unresolved point estimate or invalid probability")
        numerical = record["numerical_error"]
        require(abs(numerical["worst_case_95_half_width"] - 1.96 * math.sqrt(.25 / n)) < 1e-12
                and "excludes model/rule" in numerical["scope"], "invalid Monte Carlo precision")
        require(re.fullmatch(r"[a-f0-9]{64}", record["input_hash"]) is not None, "invalid scenario input hash")
        require(content_hash(dict(analysis["simulation_inputs"], scenario=record["scenario"],
                                  seed=record["seed"], trials=n)) == record["input_hash"], "scenario input hash mismatch")
        require(record["source_manifest_hash"] == value["header"]["source_manifest_hash"], "scenario source mismatch")
        require(record.get("model_ref") == analysis["model_lineage"].get("model_ref"), "scenario model mismatch")
    baseline = next(record for record in records if record["scenario_id"] == analysis["baseline_scenario_id"])
    for team in teams:
        for side in ("lower", "upper"):
            extreme = (min if side == "lower" else max)(record["rule_bounds"][team][side] for record in records)
            require(value["scenario_envelope_by_team"][team][side] == round(extreme, 4), "envelope does not reconstruct")
            require(value["rule_bounds_by_team"][team][side] == round(baseline["rule_bounds"][team][side], 4), "baseline bounds do not reconstruct")
            expected = [record["scenario_id"] for record in records if record["rule_bounds"][team][side] == extreme]
            require(analysis["extrema_by_team"][team][side + "_scenario_ids"] == expected, "incorrect endpoint attribution")
    mapping = analysis["mapping_provenance"]["teams"]
    require({entry["team_id"] for entry in mapping} == teams and len(mapping) == len(teams), "incomplete team mapping")
    for entry in mapping:
        require(isinstance(entry["observed"], bool), "invalid observed mapping flag")
        strength = entry["mapped_strength"]
        require(isinstance(strength, (int, float)) and math.isfinite(strength) if entry["observed"] else strength is None,
                "missing history is not an estimated zero")
        supplied = analysis["simulation_inputs"]["mapped_strength"]
        require(entry["team_id"] in supplied and strength == supplied[entry["team_id"]] if entry["observed"] else entry["team_id"] not in supplied,
                "mapping disagrees with simulator missing-history semantics")


def validate_race(value):
    h, pre, live = value["header"], value["pre_race"], value["live"]
    boats = h["boat_ids"]
    if h["schema_version"] != "prediction-1" or h["boat_class"] != "AC40" or not boats or len(set(boats)) != len(boats):
        raise ValueError("Invalid race/field/schema")
    if "replay_boat_ids" in h:
        replay=h["replay_boat_ids"]
        roster=h.get("scheduled_entries",[])
        if len(replay)!=len(set(replay)) or not set(replay)<=set(boats) or len(roster)!=len(boats) or {r["id"] for r in roster}!=set(boats):
            raise ValueError("Scheduled roster/replay field mismatch")
    for key in ("source_manifest_hash", "model_ref", "scenario_hash"):
        if not isinstance(h.get(key),str) or not re.fullmatch(r"[0-9a-f]{64}",h[key]):
            raise ValueError("Missing input/model hash")
    if h.get("status_dictionary") != STATUSES or pre.get("status") not in STATUSES:
        raise ValueError("Unknown status or status dictionary")
    if h.get("pre_race_available_at_ms") is not None and h.get("train_cutoff_ms",0)>h["pre_race_available_at_ms"]:
        raise ValueError("Pre-race training leakage")
    if set(pre["expected_position_by_boat"]) != set(boats) or pre["nonfinish_score"] != "N":
        raise ValueError("Incomplete expected-position field")
    usable = pre["status"] in STATUSES[:2]
    for x in pre["expected_position_by_boat"].values():
        if (usable and (x is None or not math.isfinite(x) or not 1 <= x <= len(boats))) or (not usable and x is not None):
            raise ValueError("Invalid expected-position availability")
    count = len(live["state_timestamps_ms"])
    flat = ("published_at_ms", "progress_band", "no_finisher_prob", "status_code", "numerical_error", "reason_code")
    nested = ("win_prob_by_boat", "source_age_ms_by_boat", "position_uncertainty_summary_by_boat", "quality_code_by_boat")
    if any(len(live[k]) != count for k in flat):
        raise ValueError("Unequal checkpoint columns")
    for key in nested:
        if set(live[key]) != set(boats) or any(len(x) != count for x in live[key].values()):
            raise ValueError("Incomplete checkpoint field")
    for i, t in enumerate(live["state_timestamps_ms"]):
        publication = live["published_at_ms"][i]
        if publication < t or (i and (t <= live["state_timestamps_ms"][i-1] or publication < live["published_at_ms"][i-1])):
            raise ValueError("Noncausal chronology")
        if h.get("train_cutoff_ms", 0) > t:
            raise ValueError("Training leakage")
        if h.get("result_cutoff_ms",0) > t:
            raise ValueError("Result-label leakage")
        code=live["status_code"][i]
        if type(code) is not int or not 0<=code<len(STATUSES):
            raise ValueError("Unknown checkpoint status code")
        status = h["status_dictionary"][code]
        probabilities = [live["win_prob_by_boat"][b][i] for b in boats]+[live["no_finisher_prob"][i]]
        if status in STATUSES[:2]:
            if any(p is None or not math.isfinite(p) or not 0<=p<=1 for p in probabilities) or abs(sum(probabilities)-1)>1e-5:
                raise ValueError("Incomplete joint probability mass")
        elif any(p is not None for p in probabilities):
            raise ValueError("Unavailable probabilities must be null")
        error=live["numerical_error"][i]
        if error is not None and (not math.isfinite(error) or not 0<=error<=1):
            raise ValueError("Invalid numerical precision")
        for boat in boats:
            age=live["source_age_ms_by_boat"][boat][i]
            if age is not None and (not isinstance(age,(int,float)) or not math.isfinite(age) or age<0):
                raise ValueError("Invalid source age")
            quality=live["quality_code_by_boat"][boat][i]
            if type(quality) is not int or not 0<=quality<len(STATUSES):
                raise ValueError("Unknown boat quality code")
            if status in STATUSES[:2] and quality>=2:
                raise ValueError("Usable forecast omits an unresolved competitor")
            radius=live["position_uncertainty_summary_by_boat"][boat][i]
            if radius is not None and (not isinstance(radius,(float,int)) or not math.isfinite(radius) or radius<0):
                raise ValueError("Invalid position uncertainty")
    canonical(value)
    return True


def verify_public(root: Path, *, index=None):
    directory = root/"public"/"data"/"predictions"
    index = index or json.loads((directory/"index.json").read_text())
    if index.get("schema_version") != "prediction-index-1":
        raise ValueError("Unsupported prediction index schema")
    if len({x["race_id"] for x in index["races"]}) != len(index["races"]):
        raise ValueError("Duplicate indexed race")
    def safe_path(relative):
        path=(directory/relative.removeprefix("predictions/")).resolve()
        if not path.is_relative_to(directory.resolve()) or path.suffix != ".json":
            raise ValueError("Unsafe artifact path")
        return path
    manifest_path=safe_path(index["source_manifest_path"])
    manifest=json.loads(manifest_path.read_text())
    manifest_hash=content_hash(manifest)
    if manifest_hash != index["source_manifest_hash"] or manifest_path.stem != manifest_hash:
        raise ValueError("Source manifest content hash mismatch")
    paths = [safe_path(entry["path"]) for entry in index["races"]]
    model_paths,scenario_paths=set(),set()
    for path, entry in zip(paths, index["races"]):
        artifact = json.loads(path.read_text())
        validate_race(artifact)
        if artifact["header"]["race_id"] != entry["race_id"] or artifact["header"]["source_manifest_hash"] != manifest_hash:
            raise ValueError("Race/manifest scope mismatch")
        for key in ("boat_ids","replay_boat_ids"):
            if key in entry and entry[key]!=artifact["header"].get(key):
                raise ValueError("Index/scheduled roster mismatch")
        if not path.stem.endswith(content_hash(artifact)):
            raise ValueError("Race artifact content hash mismatch")
        for key in ("source_manifest_hash", "model_ref", "scenario_hash"):
            if artifact["header"][key] != entry[key]:
                raise ValueError("Index/artifact hash mismatch")
        model_path=safe_path("models/"+entry["model_ref"]+".json")
        card=json.loads(model_path.read_text())
        if content_hash(card) != entry["model_ref"] or card["source_manifest_hash"] != manifest_hash:
            raise ValueError("Model card content hash mismatch")
        model_paths.add(model_path)
        for preset in entry.get("presets",[]):
            if not preset.get("path"):
                continue
            scenario_path=safe_path(preset["path"])
            scenario=json.loads(scenario_path.read_text())
            validate_race(scenario)
            sh=scenario["header"]
            if scenario_path.stem != content_hash(scenario) or sh.get("scope") != "pre_race" or sh["race_id"] != entry["race_id"]:
                raise ValueError("Pre-race scenario content/scope mismatch")
            for key in ("source_manifest_hash","model_ref","scenario_hash"):
                if sh[key] != preset[key]:
                    raise ValueError("Preset reference mismatch")
            if sh.get("conditions") != {k:preset[k] for k in ("tws_kt","direction_offset_deg")}:
                raise ValueError("Preset conditions mismatch")
            scenario_manifest=json.loads(safe_path("manifests/"+sh["source_manifest_hash"]+".json").read_text())
            scenario_model_path=safe_path("models/"+sh["model_ref"]+".json")
            scenario_model=json.loads(scenario_model_path.read_text())
            if content_hash(scenario_manifest) != sh["source_manifest_hash"] or content_hash(scenario_model) != sh["model_ref"]:
                raise ValueError("Preset source/model content mismatch")
            if scenario_model["source_manifest_hash"] != sh["source_manifest_hash"]:
                raise ValueError("Preset model source mismatch")
            model_paths.add(scenario_model_path)
            scenario_paths.add(scenario_path)
    cup_path=safe_path(index["cup_path"])
    cup=json.loads(cup_path.read_text())
    if (cup.get("header",{}).get("schema_version") != "cup-1" or cup["header"].get("boat_class") != "AC75"
            or cup["header"].get("source_manifest_hash") != manifest_hash or len(cup.get("teams",[])) != 7
            or len({t["id"] for t in cup.get("teams",[])}) != 7 or cup.get("status") not in STATUSES):
        raise ValueError("Cup schema, class, field or provenance mismatch")
    if cup_path.stem != content_hash(cup):
        raise ValueError("Cup artifact content hash mismatch")
    validate_cup(cup)
    raw = sum(p.stat().st_size for p in paths)+len(canonical(index))+cup_path.stat().st_size
    compressed = sum(len(gzip.compress(p.read_bytes(), mtime=0)) for p in paths)
    if raw > 3*1024*1024:
        raise ValueError(f"Forecast baseline exceeds 3 MiB hard budget: {raw}")
    scenario_bytes=sum(p.stat().st_size for p in scenario_paths)
    if scenario_bytes>3*1024*1024:
        raise ValueError("Lazy pre-race scenarios exceed their separate 3 MiB budget")
    return {"races": len(paths), "baseline_bytes": raw, "race_gzip_bytes": compressed,
            "referenced_model_bytes":sum(p.stat().st_size for p in model_paths),
            "source_manifest_bytes":manifest_path.stat().st_size,
            "lazy_scenario_bytes":scenario_bytes,
            "target_1_5_MiB_passed": raw <= 1.5*1024*1024, "hard_3_MiB_passed": True}
