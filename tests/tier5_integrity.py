"""Final white-box checks against the generated replay and race catalog."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReplayIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        live_replay = ROOT / "public/data/replays/naples_pr1.json"
        live_catalog = ROOT / "public/data/manifests.json"
        if not live_replay.is_file() or not live_catalog.is_file():
            raise unittest.SkipTest("Full public/data/ archive not generated locally")
        cls.replay = json.loads(live_replay.read_text(encoding="utf-8"))
        cls.catalog = json.loads(live_catalog.read_text(encoding="utf-8"))

    def test_generated_output_inventory(self):
        races = [race for group in self.catalog["regattas"] for race in group["races"]]
        race_ids = [race["id"] for race in races]
        self.assertEqual((len(race_ids), len(set(race_ids))), (28, 28))
        self.assertEqual(sum(race["competitors_count"] for race in races), 224)
        self.assertEqual({path.stem for path in (ROOT / "public/data/replays").glob("*.json")},
                         set(race_ids))
        self.assertEqual({path.stem for path in (ROOT / "public/data/analysis").glob("*.json")
                          if path.stem != "index"}, set(race_ids))

    def test_catalog_references_the_generated_race(self):
        self.assertEqual({group["id"]: len(group["races"]) for group in self.catalog["regattas"]},
                         {"cagliari_2026": 9, "naples_2026": 19})
        self.assertEqual(len(self.catalog["races"]), 28)
        for regatta in self.catalog["regattas"]:
            for race in regatta["races"]:
                relative = Path(race["replay_file"])
                self.assertEqual(relative.parts[0], "replays")
                self.assertNotIn("..", relative.parts)
                target = ROOT / "public/data" / relative
                self.assertTrue(target.is_file(), target)
                replay = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(replay["id"], race["id"])
                self.assertEqual(replay["venue"], regatta["venue"])
                self.assertEqual(len(replay["competitors"]), race["competitors_count"])
                self.assertEqual(replay["course"]["start_marks"],
                                 {"port": replay["course"]["sequences"][0]["port_mark"],
                                  "starboard": replay["course"]["sequences"][0]["starboard_mark"]})
                detail = ROOT / "public/data/analysis" / f"{race['id']}.json"
                self.assertTrue(detail.is_file(), detail)
                analysis = json.loads(detail.read_text(encoding="utf-8"))
                self.assertEqual(analysis["race"]["id"], race["id"])
                feed = analysis["event_feed"]
                self.assertEqual((feed["schema_version"], feed["method_version"]),
                                 ("1.0", "event-feed-1"))
                events = feed["events"]
                self.assertEqual(len({event["id"] for event in events}), len(events))
                self.assertEqual(events, sorted(events,
                                                key=lambda event: (event["timestamp_ms"], event["id"])))
                self.assertTrue(all(isinstance(event["timestamp_ms"], int)
                                    and event["source"] and event["quality"] for event in events))

    def test_every_published_output_is_discoverable(self):
        data = ROOT / "public/data"
        inventory = json.loads((data / "artifacts.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["summary"], {"race_count": 28, "replayed_boat_races": 224})
        entries = inventory["artifacts"]
        self.assertEqual(len({entry["url"] for entry in entries}), len(entries))
        actual = {"/data/" + path.relative_to(data).as_posix() for path in data.rglob("*") if path.is_file() and path.name != "artifacts.json"}
        self.assertEqual({entry["url"] for entry in entries}, actual)
        self.assertTrue(all(entry["view"] and entry["bytes"] > 0 for entry in entries))

    def test_history_counts_boat_races_and_six_leg_course(self):
        index = json.loads((ROOT / "public/data/analysis/index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["races"]), 28)
        self.assertEqual(sum(race["boat_count"] for race in index["races"]), 224)
        self.assertEqual(sum(history["race_count"] for history in index["histories"]), 224)

        race_id = "26_05_24_cag_ipr_mr_final"
        replay = json.loads((ROOT / "public/data/replays" / f"{race_id}.json").read_text(encoding="utf-8"))
        detail = json.loads((ROOT / "public/data/analysis" / f"{race_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(replay["course"]["start_marks"], {"port": "RM3", "starboard": "RM7"})
        self.assertEqual([leg["leg"] for leg in replay["course"]["sequences"]], list(range(7)))
        winner = next(boat for boat in replay["competitors"] if boat["classification"] == "RANK_1")
        self.assertEqual([gate["leg"] for gate in winner["gates"]], list(range(1, 7)))
        self.assertEqual(winner["summary"]["finish_rank"], 1)
        self.assertEqual([leg["leg"] for leg in detail["boats"][0]["legs"]], list(range(1, 7)))
        fleet = json.loads((ROOT / "public/data/replays/26_05_22_cag_ipr_race_3.json").read_text(encoding="utf-8"))
        gbr = next(boat for boat in fleet["competitors"] if boat["team_code"] == "GBR B")
        self.assertEqual(len(gbr["gates"]), 6)
        self.assertTrue(gbr["classification"].startswith("RANK_"))

    def test_naples_benchmark_and_unfinished_practice(self):
        self.assertEqual(len(self.replay["telemetry"]["timestamps"]), 19_488)
        self.assertEqual(len(self.replay["virtual_contact_incidents"]), 6)
        self.assertEqual(self.replay["provenance"]["source_records"], 1_481_064)
        self.assertEqual(next(boat["team_code"] for boat in self.replay["competitors"]
                              if boat["classification"] == "RANK_1"), "FRA")
        catalog_entry = next(race for race in self.catalog["races"]
                             if race["id"] == "26_09_23_nap_ipr_pr1")
        self.assertIsNone(catalog_entry["winner"])
        self.assertEqual(catalog_entry["result_provenance"], "unavailable")
        # This filename says 25 Sep, while its session gun is on 26 Sep UTC.
        shifted = next(race for race in self.catalog["races"]
                       if race["id"] == "26_09_25_nap_ipr_race_3")
        self.assertEqual(shifted["date"], "2026-09-26")

    def test_timestamps_and_boat_columns_align(self):
        times = self.replay["telemetry"]["timestamps"]
        self.assertGreater(len(times), 1_000)
        self.assertEqual(times[0], self.replay["chronology"]["window_start"])
        self.assertEqual(times[-1], self.replay["chronology"]["window_end"])
        self.assertTrue(all(b - a == 100 for a, b in zip(times, times[1:])))
        competitors = self.replay["competitors"]
        self.assertEqual(set(self.replay["telemetry"]["boats"]), {boat["id"] for boat in competitors})
        for boat in competitors:
            columns = self.replay["telemetry"]["boats"][boat["id"]]
            for name, values in columns.items():
                self.assertEqual(len(values), len(times), (boat["team_code"], name))
                self.assertTrue(all(math.isfinite(value) for value in values), (boat["team_code"], name))
            for name in ("heading", "cog", "twd"):
                self.assertTrue(all(0 <= angle < 360 for angle in columns[name]), (boat["team_code"], name))
            self.assertTrue(all(b >= a for a, b in zip(columns["progress_m"], columns["progress_m"][1:])), boat["team_code"])

    def test_boundary_revisions_follow_source_session_times(self):
        course = self.replay["course"]
        timeline = course["boundary_timeline"]
        self.assertEqual(len(timeline), 4)
        self.assertEqual([len(item["race"]) for item in timeline], [8, 8, 4, 4])
        self.assertTrue(all(len(item["safety"]) == 8 for item in timeline))
        self.assertLess(timeline[0]["t"], timeline[1]["t"])
        self.assertEqual(course["boundaries"]["race"], timeline[0]["race"])

    def test_events_are_ordered_and_classification_is_consistent(self):
        window = self.replay["chronology"]
        ranks = []
        for boat in self.replay["competitors"]:
            gates = [gate["crossing_time"] for gate in boat["gates"]]
            manoeuvres = [event["timestamp"] for event in boat["manoeuvres"]]
            self.assertEqual(gates, sorted(gates), boat["team_code"])
            self.assertEqual(manoeuvres, sorted(manoeuvres), boat["team_code"])
            self.assertTrue(all(window["window_start"] <= t <= window["window_end"] for t in gates + manoeuvres))
            if boat["classification"].startswith("RANK_"):
                self.assertGreater(boat["summary"]["elapsed_s"], 0)
                ranks.append(boat["summary"]["finish_rank"])
            else:
                self.assertEqual(boat["summary"]["elapsed_s"], 0)
        self.assertEqual(ranks, list(range(1, len(ranks) + 1)))


if __name__ == "__main__":
    unittest.main()
