"""Export small, deterministic course artwork metadata without changing metrics.

The browser loads this index instead of fetching every replay. Coordinates
describe static source-course targets, drawn north-up as a schematic; they are
not a boat track, a tactical route, or the moving marks at a chosen playhead.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(root: Path = ROOT) -> dict:
    data = root / "public" / "data"
    catalog = json.loads((data / "manifests.json").read_text(encoding="utf-8"))
    analysis = json.loads((data / "analysis" / "index.json").read_text(encoding="utf-8"))
    race_types = {race["id"]: race.get("race_type") for race in analysis["races"]}
    races = {}
    for group in catalog["regattas"]:
        for listing in group["races"]:
            relative = listing.get("replay_file", listing.get("file"))
            path = (data / relative).resolve()
            if not path.is_relative_to((data / "replays").resolve()):
                raise ValueError("Replay path leaves the catalog replay directory")
            source = path.read_bytes()
            replay = json.loads(source)
            course = replay["course"]
            boundary = course.get("boundaries", {}).get("race", [])
            marks = course.get("marks", {})
            points = boundary + [mark["target"] for mark in marks.values() if mark.get("target")]
            if not points:
                continue
            left, right = min(p[0] for p in points), max(p[0] for p in points)
            bottom, top = min(p[1] for p in points), max(p[1] for p in points)
            scale = min(330 / max(1, right - left), 180 / max(1, top - bottom))
            mid_x, mid_y = (left + right) / 2, (bottom + top) / 2

            def point(value):
                return [round(210 + (value[0] - mid_x) * scale, 2), round(120 - (value[1] - mid_y) * scale, 2)]

            gates, seen = [], set()
            for sequence in course.get("sequences", []):
                pair = (sequence.get("port_mark"), sequence.get("starboard_mark"))
                if pair in seen or any(name not in marks for name in pair):
                    continue
                seen.add(pair)
                gates.append({"kind": sequence["gate_type"], "points": [point(marks[name]["target"]) for name in pair]})
            races[replay["id"]] = {
                "boat_count": len(replay["competitors"]),
                "race_type": race_types.get(replay["id"]),
                "boat_class": replay.get("boat_class", "Class unavailable"),
                "boundary": [point(value) for value in boundary],
                "marks": [{"name": name, "point": point(mark["target"])} for name, mark in marks.items() if mark.get("target")],
                "gates": gates,
                "source": "data/" + relative,
                "source_sha256": hashlib.sha256(source).hexdigest(),
            }
    return {"schema_version": "1.0", "method_version": "course-preview-1", "description": "Static source-course schematic, north up; no replay tracks or historical metrics.", "races": races}


def write_previews(root: Path = ROOT) -> dict:
    output = root / "public" / "data" / "presentation" / "race_previews.json"
    result = build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    result = write_previews()
    print(f"Published {len(result['races'])} course previews")
