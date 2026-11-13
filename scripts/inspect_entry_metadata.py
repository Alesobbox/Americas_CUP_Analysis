"""Inspect entry metadata across all prelim sessions and generate ac38_roster.json."""
import json
from pathlib import Path


def generate_roster():
    root = Path(__file__).resolve().parent.parent
    dataset_dir = root / ".forecast" / "dataset"
    race_files = sorted([p for p in dataset_dir.glob("*.json") if p.name != "index.json"])

    entries_data = {}
    for p in race_files:
        meta = json.loads(p.read_text(encoding="utf-8"))
        for aid, ident in meta["identities"].items():
            eid = ident["entry_id"]
            name = ident.get("name")
            color = ident.get("color")
            if eid not in entries_data:
                entries_data[eid] = {
                    "entry_id": eid,
                    "names": set(),
                    "colors": set(),
                    "races": []
                }
            entries_data[eid]["names"].add(name)
            entries_data[eid]["colors"].add(color)
            entries_data[eid]["races"].append(meta["race_id"])

    # Define the 7 registered syndicates and their mapping to event entries
    syndicates = [
        {
            "team_id": "ETNZ",
            "name": "Emirates Team New Zealand",
            "country": "NZL",
            "role": "Defender",
            "entries": [
                {"entry_id": "NZL B", "type": "senior", "name": "Emirates Team New Zealand"},
                {"entry_id": "NZL G", "type": "youth_women", "name": "Emirates Team New Zealand Women and Youth"}
            ],
            "weights_by_policy": {
                "equal": {"NZL B": 0.5, "NZL G": 0.5},
                "principal_only": {"NZL B": 1.0, "NZL G": 0.0},
                "assumed_10_02": {"NZL B": 10.0 / 12.0, "NZL G": 2.0 / 12.0}
            }
        },
        {
            "team_id": "GB1",
            "name": "INEOS Britannia",
            "country": "GBR",
            "role": "Challenger of Record",
            "entries": [
                {"entry_id": "GBR B", "type": "senior", "name": "Ineos Britannia"},
                {"entry_id": "GBR G", "type": "youth_women", "name": "Ineos Britannia Women and Youth"}
            ],
            "weights_by_policy": {
                "equal": {"GBR B": 0.5, "GBR G": 0.5},
                "principal_only": {"GBR B": 1.0, "GBR G": 0.0},
                "assumed_10_02": {"GBR B": 10.0 / 12.0, "GBR G": 2.0 / 12.0}
            }
        },
        {
            "team_id": "LUNA_ROSSA",
            "name": "Luna Rossa Prada Pirelli",
            "country": "ITA",
            "role": "Challenger",
            "entries": [
                {"entry_id": "ITA B", "type": "senior", "name": "Luna Rossa"},
                {"entry_id": "ITA G", "type": "youth_women", "name": "Luna Rossa Women and Youth"}
            ],
            "weights_by_policy": {
                "equal": {"ITA B": 0.5, "ITA G": 0.5},
                "principal_only": {"ITA B": 1.0, "ITA G": 0.0},
                "assumed_10_02": {"ITA B": 10.0 / 12.0, "ITA G": 2.0 / 12.0}
            }
        },
        {
            "team_id": "ALINGHI",
            "name": "Alinghi Red Bull Racing",
            "country": "SUI",
            "role": "Challenger",
            "entries": [
                {"entry_id": "SUI", "type": "senior", "name": "Tudor Team Alinghi"}
            ],
            "weights_by_policy": {
                "equal": {"SUI": 1.0},
                "principal_only": {"SUI": 1.0},
                "assumed_10_02": {"SUI": 1.0}
            }
        },
        {
            "team_id": "ARC_USA",
            "name": "NYYC American Magic",
            "country": "USA",
            "role": "Challenger",
            "entries": [
                {"entry_id": "USA", "type": "senior", "name": "American Racing Challenger Team USA"}
            ],
            "weights_by_policy": {
                "equal": {"USA": 1.0},
                "principal_only": {"USA": 1.0},
                "assumed_10_02": {"USA": 1.0}
            }
        },
        {
            "team_id": "LA_ROCHE_POSAY",
            "name": "Orient Express Racing Team",
            "country": "FRA",
            "role": "Challenger",
            "entries": [
                {"entry_id": "FRA", "type": "senior", "name": "La Roche-Posay Racing Team"}
            ],
            "weights_by_policy": {
                "equal": {"FRA": 1.0},
                "principal_only": {"FRA": 1.0},
                "assumed_10_02": {"FRA": 1.0}
            }
        },
        {
            "team_id": "AUSTRALIA",
            "name": "Team Australia Challenge",
            "country": "AUS",
            "role": "New Challenger",
            "entries": [],
            "weights_by_policy": {
                "equal": {},
                "principal_only": {},
                "assumed_10_02": {}
            }
        }
    ]

    doc = {
        "schema_version": "ac38-roster-2",
        "retrieved_at": "2026-11-07T12:00:00+00:00",
        "description": "Event entry roster and syndicate combination weight policies for the 38th America's Cup.",
        "policies": {
            "equal": "Equal 50/50 weighting between senior and youth/women pairs.",
            "principal_only": "100% weight to primary senior team.",
            "assumed_10_02": "Estimated pairing weight (10/12 senior, 2/12 youth/women)."
        },
        "syndicates": syndicates
    }

    out_path = root / "docs" / "ac38_roster.json"
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} with {len(syndicates)} syndicates.")


if __name__ == "__main__":
    generate_roster()
