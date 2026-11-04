"""Tier 4: Real-World Application Workloads E2E Tests.

Validates end-to-end data integrity against the authoritative raw dataset:
`Data/26 09 22 NAP IPR PR1.jsonl` (324 MB, 1,481,064 records).

Verifies:
1. Full dataset structural taxonomy and session configuration.
2. All 9 competitor boats and 4 gate marks catalog extraction.
3. Official race chronology, gun time T=0 (1790079000000), and race window.
4. GBR B OCS infraction penalty record.
5. Official finish rankings and finish times match ground truth:
   FRA: 17m 39.5s, NZL G: +15.3s, ITA B: +18.4s, USA: +53.6s, ITA G: +88.4s, GBR G: +107.0s.
6. Web replay artifact schema validation (if generated).
"""

from __future__ import annotations
import unittest
import os
import json
import math
from pathlib import Path
from typing import Dict, List, Any

from tests.e2e.e2e_types import (
    GUN_TIME_MS,
    WINDOW_START_MS,
    WINDOW_END_MS,
    OFFICIAL_WIND_ASSET_ID,
    MARKS_GROUND_TRUTH,
    COMPETITORS_GROUND_TRUTH,
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = WORKSPACE_ROOT / "Data" / "26 09 22 NAP IPR PR1.jsonl"


class TestTier4RealWorldWorkloads(unittest.TestCase):
    """Tier 4: Real-World Application Workloads."""

    @classmethod
    def setUpClass(cls):
        """Scans the authoritative raw dataset for session, competitor, and telemetry headers."""
        cls.dataset_exists = DATASET_PATH.exists()
        cls.session_records: List[Dict[str, Any]] = []
        cls.competitor_records: List[Dict[str, Any]] = []
        cls.first_telemetry_records: List[Dict[str, Any]] = []
        cls.total_lines = 0

        if cls.dataset_exists:
            # Fast scan of dataset: collect session and competitor messages
            with open(DATASET_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    cls.total_lines += 1
                    # Fast substring check before JSON parse
                    if '"session"' in line:
                        cls.session_records.append(json.loads(line))
                    elif '"competitor"' in line:
                        cls.competitor_records.append(json.loads(line))
                    elif len(cls.first_telemetry_records) < 5 and '"telemetry"' in line:
                        cls.first_telemetry_records.append(json.loads(line))

    def test_raw_dataset_file_exists_and_size(self):
        """Authoritative raw dataset Data/26 09 22 NAP IPR PR1.jsonl exists and is ~324 MB."""
        self.assertTrue(self.dataset_exists, f"Dataset not found at {DATASET_PATH}")
        file_size_bytes = os.path.getsize(DATASET_PATH)
        # Exactly 323,965,659 bytes
        self.assertGreater(file_size_bytes, 300_000_000)
        self.assertLess(file_size_bytes, 350_000_000)

    def test_dataset_line_count_integrity(self):
        """Total records in JSONL file matches ground truth (1,481,064 records)."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        self.assertEqual(self.total_lines, 1481064)

    def test_session_records_count_and_id(self):
        """Dataset contains exactly 9 session records with session ID a7680985-5c0f-4cbd-8c19-99dfc8ffdab6."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        self.assertEqual(len(self.session_records), 9)
        first_session = self.session_records[0]["session"]
        self.assertEqual(first_session["id"], "a7680985-5c0f-4cbd-8c19-99dfc8ffdab6")
        self.assertEqual(first_session["name"], "26 09 22 NAP IPR PR1")

    def test_session_chronology_and_gun_time(self):
        """Session definition establishes gun time at 1790079000000 and 180s pre-start."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        sess = self.session_records[0]["session"]
        self.assertEqual(int(sess["race_start"]), GUN_TIME_MS)
        self.assertEqual(int(sess["window_start"]), WINDOW_START_MS)
        self.assertEqual(int(sess["window_end"]), WINDOW_END_MS)
        self.assertEqual(sess["official_wind_asset_id"], OFFICIAL_WIND_ASSET_ID)

    def test_session_course_geometry(self):
        """Session defines course axis ~40.0 deg and course length ~2259.4 m."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        sess = self.session_records[0]["session"]
        course = sess["race_course"]
        self.assertAlmostEqual(course["course_axis"], 40.0, places=1)
        self.assertAlmostEqual(course["course_length"], 2259.44, places=1)
        self.assertEqual(len(course["sequences"]), 5)  # 5 gates (Start, Leg 1, Leg 2, Leg 3, Finish)

    def test_session_boundaries_are_8_point_polygons(self):
        """Active race boundary and safety boundary are both 8-point polygons."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        sess = self.session_records[0]["session"]
        race_poly = sess["race_boundary"]["polygon"]["coordinates"]
        safety_poly = sess["safety_boundary"]["polygon"]["coordinates"]
        self.assertEqual(len(race_poly), 8)
        self.assertEqual(len(safety_poly), 8)

    def test_all_9_competitor_uuids_present_in_session(self):
        """All 9 competitor UUIDs are registered in session.assets."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        sess = self.session_records[0]["session"]
        asset_ids = {a["id"] for a in sess["assets"]}
        for team_code, boat in COMPETITORS_GROUND_TRUTH.items():
            self.assertIn(
                boat["uuid"], asset_ids,
                f"Competitor {team_code} ({boat['uuid']}) missing from session assets"
            )

    def test_all_4_gate_mark_uuids_present_in_session(self):
        """All 4 gate marks (RM8, RM6, RM4, RM2) are registered in session.assets."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        sess = self.session_records[0]["session"]
        asset_ids = {a["id"] for a in sess["assets"]}
        for mark_code, mark in MARKS_GROUND_TRUTH.items():
            self.assertIn(
                mark["uuid"], asset_ids,
                f"Gate mark {mark_code} ({mark['uuid']}) missing from session assets"
            )

    def test_gbr_b_ocs_penalty_in_competitor_records(self):
        """Competitor event feed contains the official GBR B OCS penalty awarded at +0.333s."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")
        gbr_b_uuid = COMPETITORS_GROUND_TRUTH["GBR B"]["uuid"]
        gbr_b_penalties = []
        for msg in self.competitor_records:
            comp = msg.get("competitor", {})
            if comp.get("asset_id") == gbr_b_uuid:
                for pen in comp.get("penalties", []):
                    gbr_b_penalties.append(pen)

        self.assertGreater(len(gbr_b_penalties), 0, "GBR B penalties missing")
        ocs_pen = gbr_b_penalties[0]
        self.assertEqual(ocs_pen["reason"], "PENALTY_REASON_OCS")
        self.assertEqual(ocs_pen["type"], "PENALTY_TYPE_RESTART")
        self.assertEqual(ocs_pen["awarded_at"], "1790079000333")

    def test_official_finish_rankings_and_times_match_ground_truth(self):
        """Official leg_timings in competitor records confirm exact finish times and ranking."""
        if not self.dataset_exists:
            self.skipTest("Dataset not available")

        # Map asset_id to last completed leg 4 timing
        finish_times: Dict[str, int] = {}
        for msg in self.competitor_records:
            comp = msg.get("competitor", {})
            asset_id = comp.get("asset_id")
            for leg in comp.get("leg_timings", []):
                if leg.get("leg_number") == 4 and leg.get("gate_time"):
                    finish_times[asset_id] = int(leg["gate_time"])

        # Check finishers
        expected_finishers = ["FRA", "NZL G", "ITA B", "USA", "ITA G", "GBR G"]
        for team in expected_finishers:
            expected_data = COMPETITORS_GROUND_TRUTH[team]
            uuid = expected_data["uuid"]
            self.assertIn(uuid, finish_times, f"{team} finish time missing in competitor records")
            actual_time = finish_times[uuid]
            self.assertEqual(
                actual_time, expected_data["finish_time_ms"],
                f"{team} finish time mismatch: got {actual_time}, expected {expected_data['finish_time_ms']}"
            )

        # Verify ordering: FRA < NZL G < ITA B < USA < ITA G < GBR G
        sorted_finishers = sorted(expected_finishers, key=lambda t: finish_times[COMPETITORS_GROUND_TRUTH[t]["uuid"]])
        self.assertEqual(sorted_finishers, ["FRA", "NZL G", "ITA B", "USA", "ITA G", "GBR G"])

    def test_winner_fra_finish_elapsed_seconds(self):
        """FRA winner finish time is 17m 39.555s (1059.555s after gun)."""
        fra_finish = COMPETITORS_GROUND_TRUTH["FRA"]["finish_time_ms"]
        elapsed_s = (fra_finish - GUN_TIME_MS) / 1000.0
        self.assertAlmostEqual(elapsed_s, 1059.555, places=3)
        minutes = int(elapsed_s // 60)
        seconds = elapsed_s % 60
        self.assertEqual(minutes, 17)
        self.assertAlmostEqual(seconds, 39.555, places=3)

    def test_web_replay_artifact_validation_if_present(self):
        """If public/data/replays/naples_pr1.json exists, validate complete schema and bounds."""
        candidate_paths = [
            WORKSPACE_ROOT / "public" / "data" / "replays" / "naples_pr1.json",
            WORKSPACE_ROOT / "data" / "replays" / "naples_pr1.json",
        ]
        target_path = None
        for p in candidate_paths:
            if p.exists():
                target_path = p
                break

        if not target_path:
            # Replay json has not been exported by downstream pipeline yet (M1/M2 in progress)
            # This is expected during parallel test development
            return

        with open(target_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("course", manifest)
        self.assertIn("competitors", manifest)
        self.assertIn("telemetry", manifest)

        # Check competitors count
        competitors = manifest["competitors"]
        self.assertEqual(len(competitors), 9)

        # Check telemetry regular 10Hz grid
        telemetry = manifest["telemetry"]
        self.assertIn("timestamps", telemetry)
        timestamps = telemetry["timestamps"]
        self.assertGreater(len(timestamps), 1000)
        # Step is strictly 100ms
        self.assertEqual(timestamps[1] - timestamps[0], 100)

    def test_dynamic_marks_physics_and_rounding_sla(self):
        """Verifies RM2 position at t = 1790079233000 (frame 4130) is within 30m of FRA rounding."""
        replay_path = WORKSPACE_ROOT / "public" / "data" / "replays" / "naples_pr1.json"
        if not replay_path.exists():
            self.skipTest("naples_pr1.json not found")

        with open(replay_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        t_rounding = 1790079233000
        timestamps = manifest["telemetry"]["timestamps"]
        self.assertIn(t_rounding, timestamps)
        frame_idx = timestamps.index(t_rounding)
        self.assertEqual(frame_idx, 4130)

        # Dynamic marks
        rm2_asset_id = manifest["course"]["marks"]["RM2"]["asset_id"]
        rm4_asset_id = manifest["course"]["marks"]["RM4"]["asset_id"]
        marks_telemetry = manifest["telemetry"]["marks"]
        self.assertIn(rm2_asset_id, marks_telemetry)
        self.assertIn(rm4_asset_id, marks_telemetry)

        rm2_x = marks_telemetry[rm2_asset_id]["x"][frame_idx]
        rm2_y = marks_telemetry[rm2_asset_id]["y"][frame_idx]
        self.assertAlmostEqual(rm2_x, 1103.60, delta=0.2)
        self.assertAlmostEqual(rm2_y, 537.55, delta=0.2)

        # Find FRA
        fra_comp = next(c for c in manifest["competitors"] if c["team_code"] == "FRA")
        fra_boat = manifest["telemetry"]["boats"][fra_comp["id"]]
        fra_x = fra_boat["x"][frame_idx]
        fra_y = fra_boat["y"][frame_idx]

        # Verify FRA rounding coordinates are around x ≈ 1000-1080m, y ≈ 530-600m
        self.assertGreater(fra_x, 1000.0)
        self.assertLess(fra_x, 1100.0)
        self.assertGreater(fra_y, 500.0)
        self.assertLess(fra_y, 600.0)

        # Compute Euclidean distance
        distance_m = math.hypot(rm2_x - fra_x, rm2_y - fra_y)
        self.assertLess(distance_m, 30.0, f"Distance {distance_m:.2f}m exceeds 30m SLA")
        self.assertAlmostEqual(distance_m, 21.04, delta=0.1)

        # Contrast with static planning target
        static_target = manifest["course"]["marks"]["RM2"]["target"]
        static_dist = math.hypot(static_target[0] - fra_x, static_target[1] - fra_y)
        self.assertGreater(static_dist, 170.0, f"Static target distance {static_dist:.2f}m should be > 170m")

    def test_dynamic_marks_full_fleet_roundings_leg1_and_leg3(self):
        """Verifies full fleet rounding alignment across Leg 1 and Leg 3 against dynamic marks."""
        replay_path = WORKSPACE_ROOT / "public" / "data" / "replays" / "naples_pr1.json"
        if not replay_path.exists():
            self.skipTest("naples_pr1.json not found")

        with open(replay_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        timestamps = manifest["telemetry"]["timestamps"]
        marks_telemetry = manifest["telemetry"]["marks"]
        rm2_stream = marks_telemetry[manifest["course"]["marks"]["RM2"]["asset_id"]]
        rm4_stream = marks_telemetry[manifest["course"]["marks"]["RM4"]["asset_id"]]

        # Leg 1 Fleet Roundings
        for comp in manifest["competitors"]:
            boat = manifest["telemetry"]["boats"][comp["id"]]
            legs = boat["leg"]

            # Find transition from leg 1 to leg 2
            leg1_trans = next((i for i in range(len(legs) - 1) if legs[i] == 1 and legs[i + 1] == 2), None)
            if leg1_trans is None:
                continue

            # Closest approach in +/- 5s window
            w_start = max(0, leg1_trans - 50)
            w_end = min(len(legs) - 1, leg1_trans + 50)
            min_dist = float("inf")
            for j in range(w_start, w_end + 1):
                bx, by = boat["x"][j], boat["y"][j]
                d2 = math.hypot(rm2_stream["x"][j] - bx, rm2_stream["y"][j] - by)
                d4 = math.hypot(rm4_stream["x"][j] - bx, rm4_stream["y"][j] - by)
                min_dist = min(min_dist, d2, d4)

            self.assertLess(min_dist, 35.0, f"Team {comp['team_code']} Leg 1 closest mark dist {min_dist:.2f}m exceeds 35m")

        # Leg 3 Fleet Roundings
        for comp in manifest["competitors"]:
            boat = manifest["telemetry"]["boats"][comp["id"]]
            legs = boat["leg"]

            leg3_trans = next((i for i in range(len(legs) - 1) if legs[i] == 3 and legs[i + 1] == 4), None)
            if leg3_trans is None:
                continue

            w_start = max(0, leg3_trans - 50)
            w_end = min(len(legs) - 1, leg3_trans + 50)
            min_dist = float("inf")
            for j in range(w_start, w_end + 1):
                bx, by = boat["x"][j], boat["y"][j]
                d2 = math.hypot(rm2_stream["x"][j] - bx, rm2_stream["y"][j] - by)
                d4 = math.hypot(rm4_stream["x"][j] - bx, rm4_stream["y"][j] - by)
                min_dist = min(min_dist, d2, d4)

            self.assertLess(min_dist, 45.0, f"Team {comp['team_code']} Leg 3 closest mark dist {min_dist:.2f}m exceeds 45m")


if __name__ == "__main__":
    unittest.main()

