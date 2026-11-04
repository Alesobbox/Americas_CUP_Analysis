"""Presentation previews retain source identity and remain cheap to consume."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_artifact_inventory import build_inventory
from scripts.build_race_previews import build, write_previews


class CoursePreviewTests(unittest.TestCase):
    def fixture(self, root):
        data = root / "public/data"
        (data / "replays").mkdir(parents=True)
        (data / "analysis").mkdir()
        listing = {"id": "race_one", "replay_file": "replays/race_one.json", "competitors_count": 2}
        (data / "manifests.json").write_text(json.dumps({"regattas": [{"races": [listing]}]}))
        (data / "analysis/index.json").write_text(json.dumps({"races": [{"id": "race_one", "race_type": "RACE_TYPE_MATCH"}]}))
        replay = {"id": "race_one", "boat_class": "AC40", "competitors": [{"id": "a"}, {"id": "b"}],
                  "course": {"boundaries": {"race": [[0, 0], [100, 0], [100, 1000], [0, 1000]]},
                             "marks": {"P": {"target": [0, 0]}, "S": {"target": [100, 0]}},
                             "sequences": [{"port_mark": "P", "starboard_mark": "S", "gate_type": "START"}]}}
        (data / "replays/race_one.json").write_text(json.dumps(replay))
        (data / "analysis/race_one.json").write_text('{}')
        return data

    def test_preview_is_deterministic_bounded_and_tied_to_the_correct_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = self.fixture(root)
            before = (data / "replays/race_one.json").read_bytes()
            result = write_previews(root)
            output = data / "presentation/race_previews.json"
            first = output.read_bytes()
            write_previews(root)
            self.assertEqual(first, output.read_bytes())
            self.assertEqual(before, (data / "replays/race_one.json").read_bytes())
            preview = result["races"]["race_one"]
            self.assertEqual(preview["boat_count"], 2)
            self.assertEqual(preview["race_type"], "RACE_TYPE_MATCH")
            self.assertEqual(preview["source_sha256"], hashlib.sha256(before).hexdigest())
            self.assertTrue(all(0 <= x <= 420 and 0 <= y <= 250 for x, y in preview["boundary"]))
            inventory = build_inventory(root)
            entry = next(item for item in inventory["artifacts"] if item["id"] == "presentation/race_previews.json")
            self.assertEqual(entry["url"], "/data/presentation/race_previews.json")
            self.assertFalse(entry["primary_download"])

    def test_unknown_type_stays_unknown_and_outside_replay_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = self.fixture(root)
            (data / "analysis/index.json").write_text('{"races": []}')
            self.assertIsNone(build(root)["races"]["race_one"]["race_type"])
            manifest = json.loads((data / "manifests.json").read_text())
            manifest["regattas"][0]["races"][0]["replay_file"] = "../outside.json"
            (data / "manifests.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "leaves the catalog"):
                build(root)


if __name__ == "__main__":
    unittest.main()
