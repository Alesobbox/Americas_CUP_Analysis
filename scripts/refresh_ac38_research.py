"""Rebuild AC38 sample-level analysis and retrospective research artifacts."""

from __future__ import annotations
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.polar.extraction import extract_race_polar_cells  # noqa: E402


def write_json(path, value):
    content = json.dumps(value, separators=(",", ":"), allow_nan=False)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf8")
    temporary.replace(path)


def load_details(root, extract=False):
    data = root / "public" / "data"
    catalog = json.loads((data / "manifests.json").read_text(encoding="utf8"))
    races = [race for group in catalog["regattas"] for race in group["races"]]
    details = {}
    for race in races:
        path = data / "analysis" / (race["id"] + ".json")
        detail = json.loads(path.read_text(encoding="utf8"))
        if extract or any("polar_samples" not in boat for boat in detail["boats"]):
            replay_path = data / "replays" / (race["id"] + ".json")
            content = replay_path.read_bytes()
            replay = json.loads(content)
            summary = extract_race_polar_cells(detail, replay_doc=replay)
            detail["polar_sample_provenance"] = {
                "schema_version": "polar-samples-2",
                "input": replay_path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "input_precision": "exported replay precision",
                "availability_basis": "retrospective source coverage; live arrival not established",
                **summary,
            }
            write_json(path, detail)
            print(json.dumps({"race": race["id"], **summary}), flush=True)
        details[race["id"]] = detail
    return details


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    details = load_details(ROOT, extract=args.extract or args.extract_only)
    if not args.extract_only:
        from pipeline.research.archive import refresh_research

        refresh_research(details, ROOT)


if __name__ == "__main__":
    main()
