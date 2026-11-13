"""Compute event entries and update docs/ac38_roster.json with event_entries."""
from collections import defaultdict
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    dataset_dir = root / ".forecast" / "dataset"
    race_files = sorted([p for p in dataset_dir.glob("*.json") if p.name != "index.json"])

    entry_team_role = {
        "NZL B": ("ETNZ", "senior"),
        "NZL G": ("ETNZ", "youth_women"),
        "GBR B": ("GB1", "senior"),
        "GBR G": ("GB1", "youth_women"),
        "ITA B": ("LUNA_ROSSA", "senior"),
        "ITA G": ("LUNA_ROSSA", "youth_women"),
        "SUI": ("ALINGHI", "principal"),
        "FRA": ("LA_ROCHE_POSAY", "principal"),
        "USA": ("ARC_USA", "principal"),
    }

    event_counts = defaultdict(lambda: {"total": 0, "competitive": 0})
    for p in race_files:
        meta = json.loads(p.read_text(encoding="utf-8"))
        ev_id = "cagliari_2026" if meta["date"] < "2026-07-01" else "naples_2026"
        is_comp = not meta.get("practice", False)
        for aid in meta["boat_ids"]:
            eid = meta["identities"][aid]["entry_id"]
            key = (ev_id, eid)
            event_counts[key]["total"] += 1
            if is_comp:
                event_counts[key]["competitive"] += 1

    event_entries = []
    for (ev_id, eid), cnt in sorted(event_counts.items()):
        team_id, role = entry_team_role.get(eid, ("UNKNOWN", "senior"))
        event_entries.append({
            "event_entry_id": f"{ev_id}::{eid}",
            "event_id": ev_id,
            "entry_id": eid,
            "team_id": team_id,
            "role": role,
            "n_races": cnt["total"],
            "n_competitive_races": cnt["competitive"]
        })

    roster_path = root / "docs" / "ac38_roster.json"
    doc = json.loads(roster_path.read_text(encoding="utf-8"))
    doc["event_entries"] = event_entries

    roster_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {roster_path} with {len(event_entries)} event_entries:")
    for ee in event_entries:
        print(f"  {ee['event_entry_id']}: total={ee['n_races']}, competitive={ee['n_competitive_races']}, team={ee['team_id']}")


if __name__ == "__main__":
    main()
