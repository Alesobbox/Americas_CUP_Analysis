"""Print a small, deterministic analysis status for AI-assisted work.

Run this before opening multi-megabyte replay or source files in a prompt.
"""

import argparse
import json
from pathlib import Path


def snapshot(root: Path, race_id: str | None = None) -> dict:
    analysis = root / "public" / "data" / "analysis"
    index = json.loads((analysis / "index.json").read_text(encoding="utf-8"))
    result = {"schema_version": index["schema_version"],
              "race_count": len(index["races"]),
              "boat_race_count": sum(r["boat_count"] for r in index["races"]),
              "races": [{"id": r["id"], "date": r["date"], "type": r["race_type"],
                         "class": r["boat_class"], "boats": r["boat_count"],
                         "limitations": len(r.get("limitations", []))} for r in index["races"]]}
    if race_id:
        if race_id not in {r["id"] for r in index["races"]}:
            raise ValueError(f"race is absent from index: {race_id}")
        detail = json.loads((analysis / f"{race_id}.json").read_text(encoding="utf-8"))
        result["selected_race"] = {"id": race_id,
                                   "metric_method": detail["method_version"],
                                   "wind_samples": detail["wind"].get("sample_count", 0),
                                   "pairs": len(detail["pairs"]),
                                   "boats": [{"code": b["team_code"], "status": b["classification"],
                                              "complete_legs": sum(bool(l["complete"]) for l in b["legs"]),
                                              "manoeuvres": len(b["manoeuvres"]),
                                              "unavailable_metrics": sum(m["value"] is None for m in b["metrics"].values()),
                                              "partial_metrics": sum(m["quality"] == "partial" for m in b["metrics"].values())}
                                             for b in detail["boats"]]}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", help="Add one race's compact coverage and quality summary")
    args = parser.parse_args()
    print(json.dumps(snapshot(Path(__file__).resolve().parents[1], args.race), separators=(",", ":"), sort_keys=True))
