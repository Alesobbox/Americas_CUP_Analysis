"""Published analyst exports must reconcile with their canonical analysis."""
import csv
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "public" / "data"


class PublishedReportTests(unittest.TestCase):
    def test_all_summary_csv_values_preserve_canonical_values_and_availability(self):
        races = json.loads((DATA / "manifests.json").read_text())["regattas"]
        checked = 0
        for group in races:
            for race in group["races"]:
                detail = json.loads((DATA / "analysis" / (race["id"] + ".json")).read_text())
                with (DATA / "analysis" / (race["id"] + "_summary.csv")).open(newline="", encoding="utf-8") as stream:
                    rows = list(csv.DictReader(stream))
                expected = {(boat["id"], key): metric for boat in detail["boats"] for key, metric in boat["metrics"].items()}
                self.assertEqual(len(rows), len(expected), race["id"])
                for row in rows:
                    metric = expected[(row["boat_id"], row["metric"])]
                    self.assertEqual(row["value"], "" if metric["value"] is None else str(metric["value"]))
                    self.assertEqual(row["coverage_s"], "" if metric["coverage_s"] is None else str(metric["coverage_s"]))
                    self.assertEqual(row["quality"], metric["quality"])
                    self.assertEqual(row["reason"], metric.get("reason", ""))
                    self.assertEqual(row["method_version"], detail["method_version"])
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_current_references_and_curated_exports_are_never_classified_as_retained(self):
        inventory = json.loads((DATA / "artifacts.json").read_text())
        self.assertEqual(inventory["schema_version"], "1.1")
        items = {item["id"]: item for item in inventory["artifacts"]}
        index = json.loads((DATA / "predictions/index.json").read_text())
        active = {"predictions/index.json", "predictions/" + index["cup_path"], "predictions/" + index["source_manifest_path"]}
        for race in index["races"]:
            active.update({"predictions/" + race["path"], "predictions/models/" + race["model_ref"] + ".json"})
            active.update("predictions/" + preset["path"] for preset in race.get("presets", []) if preset.get("path"))
        for path in active:
            self.assertNotEqual(items[path]["status"], "retained", path)
        for group in json.loads((DATA / "manifests.json").read_text())["regattas"]:
            for race in group["races"]:
                primary = [item for item in items.values() if item["race_id"] == race["id"] and item["primary_download"]]
                self.assertTrue({"replay", "analysis", "summary_csv", "performance_csv"} <= {item["kind"] for item in primary})
                self.assertLessEqual(len(primary), 6)
                self.assertTrue(all(item["status"] == "current" for item in primary))
        self.assertTrue(any(item["status"] == "retained" for item in items.values()))
        self.assertTrue(all((DATA / path).stat().st_size == item["bytes"] for path, item in items.items()))


if __name__ == "__main__":
    unittest.main()
