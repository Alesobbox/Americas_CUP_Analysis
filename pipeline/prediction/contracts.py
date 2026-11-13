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


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="."+path.name+".", suffix=".tmp", delete=False, mode="w", encoding="utf-8", newline="\n") as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
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
        expected_inputs = dict(analysis["simulation_inputs"], scenario=record["scenario"],
                               seed=record["seed"], trials=n)
        if "posterior_draws_sha256" in record:
            require(re.fullmatch(r"[a-f0-9]{64}", str(record["posterior_draws_sha256"])) is not None,
                    "invalid scenario posterior draws hash")
            expected_inputs["posterior_draws_sha256"] = record["posterior_draws_sha256"]
        require(content_hash(expected_inputs) == record["input_hash"], "scenario input hash mismatch")
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


def _assert_prob_dict(mapping: dict, team_ids: list[str], *, allow_null: bool = False) -> None:
    if not isinstance(mapping, dict) or set(mapping.keys()) != set(team_ids):
        raise ValueError("AC38 forecast team dictionary keys mismatch")
    for val in mapping.values():
        if val is None and allow_null:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or not 0.0 <= val <= 1.0:
            raise ValueError(f"Invalid probability value in AC38 forecast: {val}")


def _is_num(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val)


def _is_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


PRIVATE_AC38_POSTERIOR_KEYS = frozenset({
    "active_conditionals",
    "posterior_grid",
    "grid_axes",
    "weights_normalized",
    "z_grid",
    "h_grid",
})


def assert_no_private_posterior_keys(payload: Any, *, context: str = "public artifact") -> None:
    stack: list[Any] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            leaked = PRIVATE_AC38_POSTERIOR_KEYS.intersection(node.keys())
            if leaked:
                raise ValueError(f"Private posterior key(s) {sorted(leaked)} leaked into {context}")
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def validate_ac38_forecast(value: dict) -> bool:
    """Validate ac38-forecast-1 schema, bounds, lineage, probability mass, and status semantics."""
    from datetime import datetime

    if not isinstance(value, dict) or not isinstance(value.get("header"), dict):
        raise ValueError("Invalid AC38 forecast structure")
    assert_no_private_posterior_keys(value, context="ac38-forecast-1")
    h = value["header"]
    if h.get("schema_version") != "ac38-forecast-1" or h.get("experimental") is not True:
        raise ValueError("Unsupported AC38 forecast schema or missing experimental flag")
    if h.get("status") not in ("experimental_conditional", "experimental_rule_bounds"):
        raise ValueError("Invalid AC38 forecast status")
    cutoff = h.get("issuance_cutoff_utc")
    if not isinstance(cutoff, str) or not cutoff.strip():
        raise ValueError("Missing issuance_cutoff_utc")
    try:
        datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid issuance_cutoff_utc ISO datetime: {cutoff}") from exc
    if not isinstance(h.get("conditioning"), str) or not h["conditioning"].strip():
        raise ValueError("Missing or empty conditioning description")
    if not _is_num(h.get("scale_kappa")) or abs(float(h["scale_kappa"]) - 1.0) > 1e-9:
        raise ValueError("AC38 forecast scale_kappa must equal 1")
    if h.get("selected_transfer_candidate") not in ("results_only", "results_plus_telemetry"):
        raise ValueError("Invalid selected_transfer_candidate")
    if not isinstance(h.get("telemetry_retained"), bool):
        raise ValueError("AC38 forecast header.telemetry_retained must be a boolean")
    if not _is_int(h.get("trials")) or h["trials"] < 1:
        raise ValueError("AC38 forecast header.trials must be a positive integer")
    if not _is_int(h.get("seed")):
        raise ValueError("AC38 forecast header.seed must be an integer")
    for hash_key in ("transfer_posterior_sha256", "eligibility_ledger_sha256", "inventory_sha256", "backtest_report_sha256", "model_ref"):
        if not isinstance(h.get(hash_key), str) or not re.fullmatch(r"[a-f0-9]{64}", h[hash_key]):
            raise ValueError(f"Invalid lineage hash: {hash_key}")

    teams = value.get("teams", [])
    if not isinstance(teams, list) or len(teams) != 7 or not all(isinstance(t, dict) for t in teams):
        raise ValueError("AC38 forecast must define exactly 7 team objects")
    team_ids = [t.get("id") for t in teams]
    if any(not isinstance(tid, str) or not tid for tid in team_ids) or len(set(team_ids)) != 7:
        raise ValueError("AC38 forecast must define 7 unique non-empty team ids")
    for t in teams:
        if t.get("campaign_team_id") != f"ac38:{t['id']}":
            raise ValueError(f"Invalid campaign_team_id for {t['id']}")
        if not isinstance(t.get("name"), str) or not t["name"].strip():
            raise ValueError(f"Missing team name for {t['id']}")
        if not isinstance(t.get("role"), str) or not t["role"].strip():
            raise ValueError(f"Missing team role for {t['id']}")

    rules = value.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("Missing rules section")
    trials = h["trials"]
    res_trials = rules.get("resolved_trials")
    unres_trials = rules.get("unresolved_trials")
    if not _is_int(res_trials) or not _is_int(unres_trials) or res_trials < 0 or unres_trials < 0 or res_trials + unres_trials != trials:
        raise ValueError("AC38 forecast trial counts do not reconcile")
    if unres_trials > 0 and h["status"] != "experimental_rule_bounds":
        raise ValueError("Unresolved trials require status experimental_rule_bounds")
    if unres_trials == 0 and h["status"] != "experimental_conditional":
        raise ValueError("Zero unresolved trials require status experimental_conditional")
    res_frac = rules.get("resolved_fraction")
    unres_frac = rules.get("unresolved_fraction")
    if (
        not _is_num(res_frac)
        or not _is_num(unres_frac)
        or abs(float(res_frac) - res_trials / trials) > 1e-4
        or abs(float(unres_frac) - unres_trials / trials) > 1e-4
        or abs(float(res_frac) + float(unres_frac) - 1.0) > 1e-4
    ):
        raise ValueError("AC38 forecast resolved/unresolved fractions do not reconcile")
    stage_counts = rules.get("first_unresolved_stage_counts")
    if not isinstance(stage_counts, dict) or any(not _is_int(v) or v < 0 for v in stage_counts.values()) or sum(stage_counts.values()) != unres_trials:
        raise ValueError("first_unresolved_stage_counts must be non-negative ints summing to unresolved_trials")

    fc = value.get("forecast", {})
    if not isinstance(fc, dict):
        raise ValueError("Missing forecast section")
    for matrix_key in ("pairwise_single_match", "series_best_of_9", "series_best_of_13"):
        mat = fc.get(matrix_key, {})
        if not isinstance(mat, dict) or set(mat.keys()) != set(team_ids):
            raise ValueError(f"Incomplete pairwise matrix {matrix_key}")
        for ti in team_ids:
            if not isinstance(mat[ti], dict) or set(mat[ti].keys()) != set(team_ids):
                raise ValueError(f"Incomplete row {ti} in {matrix_key}")
            for tj in team_ids:
                v = mat[ti].get(tj)
                if ti == tj:
                    if v is not None:
                        raise ValueError("Self-matchup must be null")
                elif not _is_num(v) or not 0.0 <= float(v) <= 1.0 or not _is_num(mat[tj].get(ti)) or abs(float(v) + float(mat[tj][ti]) - 1.0) > 1e-4:
                    raise ValueError(f"Pairwise complementarity violation in {matrix_key}")

    trophy_probs = fc.get("trophy_probabilities", {})
    _assert_prob_dict(trophy_probs, team_ids, allow_null=(unres_trials > 0))
    if unres_trials > 0 and any(v is not None for v in trophy_probs.values()):
        raise ValueError("Unresolved forecast cannot publish point trophy probabilities")
    if unres_trials == 0 and abs(sum(float(trophy_probs[t]) for t in team_ids) - 1.0) > 1e-3:
        raise ValueError("Resolved trophy_probabilities must sum to 1")

    bounds = fc.get("trophy_rule_bounds", {})
    if not isinstance(bounds, dict) or set(bounds.keys()) != set(team_ids):
        raise ValueError("Incomplete trophy_rule_bounds")
    lower_sum = 0.0
    upper_sum = 0.0
    for tid in team_ids:
        b = bounds[tid]
        if not isinstance(b, dict) or not _is_num(b.get("lower")) or not _is_num(b.get("upper")) or not 0.0 <= float(b["lower"]) <= float(b["upper"]) <= 1.0:
            raise ValueError(f"Invalid trophy bounds for {tid}")
        lower_sum += float(b["lower"])
        upper_sum += float(b["upper"])
    if lower_sum > 1.0 + 1e-3 or upper_sum < 1.0 - 1e-3:
        raise ValueError("trophy_rule_bounds lower/upper sums violate probability simplex envelope")

    fleet_pos = fc.get("expected_fleet_position", {})
    if (
        not isinstance(fleet_pos, dict)
        or set(fleet_pos.keys()) != set(team_ids)
        or any(not _is_num(v) or not 1.0 <= float(v) <= 7.0 for v in fleet_pos.values())
        or abs(sum(float(v) for v in fleet_pos.values()) - 28.0) > 0.05
    ):
        raise ValueError("Expected fleet positions must be in [1, 7] and sum to 28")

    fleet_dist = fc.get("fleet_position_distribution", {})
    if not isinstance(fleet_dist, dict) or set(fleet_dist.keys()) != set(team_ids):
        raise ValueError("Incomplete fleet_position_distribution")
    for tid in team_ids:
        row = fleet_dist[tid]
        if (
            not isinstance(row, list)
            or len(row) != 7
            or any(not _is_num(p) or not 0.0 <= float(p) <= 1.0 for p in row)
            or abs(sum(float(p) for p in row) - 1.0) > 1e-3
        ):
            raise ValueError(f"Invalid fleet_position_distribution row for {tid}")

    adv = fc.get("advancement_probabilities", {})
    adv_caps = {
        "round_robin_top3": 3.0,
        "repechage_1_win": 1.0,
        "repechage_2_win": 1.0,
        "semifinal": 4.0,
        "semifinal_1_win": 1.0,
        "semifinal_2_win": 1.0,
        "challenger_final_win": 1.0,
    }
    if not isinstance(adv, dict) or not set(adv_caps.keys()).issubset(set(adv.keys())):
        raise ValueError("Incomplete advancement_probabilities stages")
    for stage_key, cap in adv_caps.items():
        _assert_prob_dict(adv[stage_key], team_ids, allow_null=False)
        if sum(float(v) for v in adv[stage_key].values()) > cap + 1e-3:
            raise ValueError(f"advancement_probabilities[{stage_key}] exceeds {cap}")

    sens = value.get("structural_sensitivities", [])
    if not isinstance(sens, list) or not sens:
        raise ValueError("structural_sensitivities must be a non-empty list")
    s_ids: list[str] = []
    seen_configs: set[tuple[Any, ...]] = set()
    for sc in sens:
        if not isinstance(sc, dict) or not isinstance(sc.get("scenario_id"), str) or not sc["scenario_id"]:
            raise ValueError("Invalid structural sensitivity entry")
        s_ids.append(sc["scenario_id"])
        sc_trials = sc.get("trials")
        sc_res = sc.get("resolved_trials")
        sc_unres = sc.get("unresolved_trials")
        if not _is_int(sc_trials) or sc_trials < 1 or not _is_int(sc_res) or not _is_int(sc_unres) or sc_res < 0 or sc_unres < 0 or sc_res + sc_unres != sc_trials:
            raise ValueError(f"Invalid trial counts in sensitivity {sc['scenario_id']}")
        sc_bounds = sc.get("trophy_rule_bounds", {})
        if not isinstance(sc_bounds, dict) or set(sc_bounds.keys()) != set(team_ids):
            raise ValueError(f"Incomplete trophy_rule_bounds in sensitivity {sc['scenario_id']}")
        sc_lo_sum = 0.0
        sc_hi_sum = 0.0
        for tid in team_ids:
            b = sc_bounds[tid]
            if not isinstance(b, dict) or not _is_num(b.get("lower")) or not _is_num(b.get("upper")) or not 0.0 <= float(b["lower"]) <= float(b["upper"]) <= 1.0:
                raise ValueError(f"Invalid trophy_rule_bounds for {tid} in sensitivity {sc['scenario_id']}")
            sc_lo_sum += float(b["lower"])
            sc_hi_sum += float(b["upper"])
        if sc_lo_sum > 1.0 + 1e-3 or sc_hi_sum < 1.0 - 1e-3:
            raise ValueError(f"Sensitivity {sc['scenario_id']} bounds violate simplex envelope")
        if not _is_num(sc.get("residual_scale")) or not _is_num(sc.get("failure_probability", 0.0)):
            raise ValueError(f"Invalid numeric sensitivity parameter in {sc['scenario_id']}")
        cfg = (
            round(float(sc["residual_scale"]), 6),
            bool(sc.get("zero_transfer")),
            sc.get("mapping_policy"),
            sc.get("evidence_scope"),
            bool(sc.get("conditional_on_completed", True)),
            round(float(sc.get("failure_probability", 0.0)), 6),
        )
        if cfg in seen_configs:
            raise ValueError(f"Duplicate structural sensitivity configuration for {sc['scenario_id']}")
        seen_configs.add(cfg)
    if len(set(s_ids)) != len(s_ids):
        raise ValueError("Duplicate structural sensitivity scenario IDs")

    unc = value.get("uncertainty", {})
    if not isinstance(unc, dict):
        raise ValueError("Missing uncertainty section")
    mc = unc.get("monte_carlo", {})
    if not isinstance(mc, dict) or not _is_num(mc.get("worst_case_95_half_width")) or float(mc["worst_case_95_half_width"]) < 0.0:
        raise ValueError("Invalid uncertainty.monte_carlo")
    mc_se = mc.get("actual_mc_se_by_team", {})
    if not isinstance(mc_se, dict) or set(mc_se.keys()) != set(team_ids):
        raise ValueError("Incomplete uncertainty.monte_carlo.actual_mc_se_by_team")
    for tid in team_ids:
        entry = mc_se[tid]
        if (
            not isinstance(entry, dict)
            or not _is_num(entry.get("lower"))
            or not _is_num(entry.get("upper"))
            or float(entry["lower"]) < 0.0
            or float(entry["upper"]) < 0.0
        ):
            raise ValueError(f"Invalid actual_mc_se_by_team entry for {tid}")
    pair_se = mc.get("pairwise_single_match_mc_se", {})
    if not isinstance(pair_se, dict) or set(pair_se.keys()) != set(team_ids):
        raise ValueError("Incomplete uncertainty.monte_carlo.pairwise_single_match_mc_se")
    for ti in team_ids:
        row = pair_se[ti]
        if not isinstance(row, dict) or set(row.keys()) != set(team_ids):
            raise ValueError(f"Incomplete pairwise_single_match_mc_se row for {ti}")
        for tj in team_ids:
            v = row[tj]
            if ti == tj:
                if v is not None:
                    raise ValueError("Self-matchup pairwise_single_match_mc_se must be null")
            elif not _is_num(v) or float(v) < 0.0:
                raise ValueError(f"Invalid pairwise_single_match_mc_se for {ti} vs {tj}")
    nested = unc.get("posterior_nested_intervals", {})
    if (
        not isinstance(nested, dict)
        or not isinstance(nested.get("converged_within_0_5pp"), bool)
        or not _is_num(nested.get("stabilization_target_pp"))
        or not _is_int(nested.get("computation_cap_trials"))
        or nested["computation_cap_trials"] < 1
    ):
        raise ValueError("Invalid uncertainty.posterior_nested_intervals metadata")
    ibt = nested.get("intervals_by_team", {})
    if not isinstance(ibt, dict) or set(ibt.keys()) != set(team_ids):
        raise ValueError("Incomplete posterior_nested_intervals.intervals_by_team")
    for tid in team_ids:
        entry = ibt[tid]
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid nested interval entry for {tid}")
        for band_key in ("lower_p05_p95", "upper_p05_p95"):
            band = entry.get(band_key)
            if (
                not isinstance(band, dict)
                or not all(_is_num(band.get(q)) for q in ("p05", "p50", "p95"))
                or not 0.0 <= float(band["p05"]) <= float(band["p50"]) <= float(band["p95"]) <= 1.0
            ):
                raise ValueError(f"Invalid nested interval ordering for {tid}.{band_key}")
    tps = unc.get("transfer_parameter_summary", {})
    if not isinstance(tps, dict):
        raise ValueError("Missing uncertainty.transfer_parameter_summary")
    for pkey in ("beta_percentiles", "tau_percentiles", "rho_percentiles"):
        pct = tps.get(pkey)
        if (
            not isinstance(pct, dict)
            or not all(_is_num(pct.get(q)) for q in ("p05", "p50", "p95"))
            or not float(pct["p05"]) <= float(pct["p50"]) <= float(pct["p95"])
        ):
            raise ValueError(f"Invalid percentile ordering in transfer_parameter_summary.{pkey}")

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
    if "evidence_manifest_hash" in index:
        ev_path = safe_path(index.get("evidence_manifest_path", "manifests/" + index["evidence_manifest_hash"] + ".json"))
        ev_manifest = json.loads(ev_path.read_text())
        ev_hash = content_hash(ev_manifest)
        if ev_hash != index["evidence_manifest_hash"] or ev_path.stem != ev_hash:
            raise ValueError("Evidence manifest content hash mismatch")
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
    cup_model_ref = cup.get("header", {}).get("model_ref")
    if cup_model_ref:
        cup_model_path = safe_path("models/" + cup_model_ref + ".json")
        cup_model_card = json.loads(cup_model_path.read_text())
        if content_hash(cup_model_card) != cup_model_ref:
            raise ValueError("Cup-referenced model content hash mismatch")
        model_paths.add(cup_model_path)
    raw = sum(p.stat().st_size for p in paths)+len(canonical(index))+cup_path.stat().st_size
    if index.get("ac38_forecast_path"):
        ac38_path = safe_path(index["ac38_forecast_path"])
        ac38_doc = json.loads(ac38_path.read_text(encoding="utf-8"))
        validate_ac38_forecast(ac38_doc)
        if not ac38_path.stem.endswith(content_hash(ac38_doc)):
            raise ValueError("AC38 forecast artifact content hash mismatch")
        raw += ac38_path.stat().st_size
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
