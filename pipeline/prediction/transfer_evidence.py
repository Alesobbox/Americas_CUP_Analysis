"""Load and gate historical and cross-cycle observations for transfer modeling."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .ac38_evidence import is_valid_independent_evidence
from .transfer_num import helmert_contrasts

SHARED_AC37_TEAMS = (
    "ALINGHI",
    "AMERICAN_MAGIC",
    "ETNZ",
    "INEOS",
    "LUNA_ROSSA",
    "ORIENT_EXPRESS",
)

BOAT_TO_AC37_TEAM = {
    "SUI": "ALINGHI",
    "USA": "AMERICAN_MAGIC",
    "NZL B": "ETNZ",
    "NZL G": "ETNZ",
    "NZL": "ETNZ",
    "GBR B": "INEOS",
    "GBR G": "INEOS",
    "GBR": "INEOS",
    "ITA B": "LUNA_ROSSA",
    "ITA G": "LUNA_ROSSA",
    "ITA": "LUNA_ROSSA",
    "FRA": "ORIENT_EXPRESS",
    "ALINGHI": "ALINGHI",
    "AMERICAN_MAGIC": "AMERICAN_MAGIC",
    "ETNZ": "ETNZ",
    "INEOS": "INEOS",
    "LUNA_ROSSA": "LUNA_ROSSA",
    "ORIENT_EXPRESS": "ORIENT_EXPRESS",
}

POLICY_BOAT_WEIGHTS = {
    "equal": {"NZL B": 0.5, "NZL G": 0.5, "GBR B": 0.5, "GBR G": 0.5, "ITA B": 0.5, "ITA G": 0.5},
    "principal_only": {"NZL B": 1.0, "NZL G": 0.0, "GBR B": 1.0, "GBR G": 0.0, "ITA B": 1.0, "ITA G": 0.0},
    "assumed_10_02": {
        "NZL B": 10.0 / 12.0,
        "NZL G": 2.0 / 12.0,
        "GBR B": 10.0 / 12.0,
        "GBR G": 2.0 / 12.0,
        "ITA B": 10.0 / 12.0,
        "ITA G": 2.0 / 12.0,
    },
}


def load_transfer_observations(
    root: Path,
    *,
    ac40_source: str = "ac37_2023",
    policy: str = "equal",
    require_independent: bool = True,
    max_ac40_date: str | None = None,
    max_ac75_date: str | None = None,
) -> dict:
    """Load gated PL stages for AC40 and BT comparisons for AC75."""
    root = Path(root)
    q_mat = helmert_contrasts(6)
    c_map = {t: i for i, t in enumerate(SHARED_AC37_TEAMS)}

    ac37_file = root / "docs" / "ac37_results.json"
    if not ac37_file.exists():
        raise FileNotFoundError(f"AC37 results file not found: {ac37_file}")
    ac37_bytes = ac37_file.read_bytes()
    ac37_doc = json.loads(ac37_bytes.decode("utf-8"))

    matches = []
    match_race_ids = []
    excluded_ac75 = []
    for r in ac37_doc.get("races", []):
        if r.get("status", "completed") != "completed":
            excluded_ac75.append((r["race_id"], f"status:{r.get('status')}"))
            continue
        if max_ac75_date and r.get("date", "") > max_ac75_date:
            continue
        if require_independent:
            ok, reason = is_valid_independent_evidence(root, r.get("evidence"), required_scopes=("match_winner",))
            if not ok:
                excluded_ac75.append((r["race_id"], reason))
                continue
        ca, cb, win = r["competitor_a"], r["competitor_b"], r["winner"]
        if ca in c_map and cb in c_map and win in c_map:
            matches.append((c_map[win], c_map[cb if win == ca else ca]))
            match_race_ids.append(r["race_id"])

    d75_matches = np.array([q_mat[w] - q_mat[l] for w, l in matches], dtype=float)
    raw_d75_pairs = [q_mat[w] - q_mat[l] for w, l in matches]

    ac40_files: list[Path] = []
    if ac40_source in ("ac37_2023", "pooled_ac37_ac38"):
        f37 = root / "docs" / "ac37_ac40_2023_results.json"
        if not f37.exists():
            raise FileNotFoundError(f"Missing required 2023 AC40 results file: {f37}")
        ac40_files.append(f37)
    if ac40_source in ("ac38_2026", "pooled_ac37_ac38"):
        f38 = root / "docs" / "official_results_ac38_prelims.json"
        if not f38.exists():
            raise FileNotFoundError(f"Missing required AC38 results file: {f38}")
        ac40_files.append(f38)
    if not ac40_files:
        raise ValueError(f"Unknown ac40_source: {ac40_source}")

    stages = []
    ac40_race_ids = []
    excluded_ac40 = []
    source_hashes = {"docs/ac37_results.json": hashlib.sha256(ac37_bytes).hexdigest()}

    for a_file in ac40_files:
        a_bytes = a_file.read_bytes()
        rel_key = a_file.relative_to(root).as_posix() if a_file.is_relative_to(root) else str(a_file)
        source_hashes[rel_key] = hashlib.sha256(a_bytes).hexdigest()
        ac40_doc = json.loads(a_bytes.decode("utf-8"))
        for r in ac40_doc.get("races", []):
            rid = r.get("race_id", "unknown")
            if r.get("practice", False):
                excluded_ac40.append((rid, "practice"))
                continue
            if r.get("status", "completed") not in ("completed", "final"):
                excluded_ac40.append((rid, r.get("exclusion_reason") or f"status:{r.get('status')}"))
                continue
            if max_ac40_date and r.get("date", "") > max_ac40_date:
                continue
            if require_independent and a_file.name == "ac37_ac40_2023_results.json":
                ok, reason = is_valid_independent_evidence(
                    root, r.get("evidence"), required_scopes=("full_fleet_order", "match_final_winner")
                )
                if not ok:
                    excluded_ac40.append((rid, reason))
                    continue

            raw_order = [b for b in (r.get("official_order") or []) if b in BOAT_TO_AC37_TEAM]
            if policy == "principal_only":
                raw_order = [b for b in raw_order if POLICY_BOAT_WEIGHTS["principal_only"].get(b, 1.0) > 0.0]
            if len(raw_order) < 2:
                excluded_ac40.append((rid, "insufficient_order"))
                continue
            ac40_race_ids.append(rid)
            v_boats = [float(POLICY_BOAT_WEIGHTS.get(policy, {}).get(b, 1.0)) for b in raw_order]
            for k in range(len(raw_order) - 1):
                t_indices = [c_map[BOAT_TO_AC37_TEAM[b]] for b in raw_order[k:]]
                stages.append((q_mat[t_indices, :], np.array(v_boats[k:], dtype=float), float(v_boats[k])))

    return {
        "q_mat": q_mat,
        "d40_stages": stages,
        "d75_matches": d75_matches,
        "raw_d75_pairs": raw_d75_pairs,
        "ac40_race_ids": ac40_race_ids,
        "ac75_race_ids": match_race_ids,
        "excluded_ac40": excluded_ac40,
        "excluded_ac75": excluded_ac75,
        "source_hashes": source_hashes,
    }
