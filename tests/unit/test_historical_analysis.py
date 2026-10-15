"""Hand-checkable edge cases for the versioned historical analysis contract."""

from __future__ import annotations

import math
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pipeline.historical_analysis import (
    SCHEMA_VERSION,
    build_event_feed,
    build_historical_index,
    build_race_analysis,
    circular_delta_deg,
    leg_course_vmg_kt,
    signed_polygon_distance_m,
    start_line_geometry,
    wind_relative_vmg_kt,
)


def synthetic_race(*, mark_y=0.0, revise_boundary=True, official_wind=True):
    """Small race with exact 1 s timestamps and four distinct race outcomes."""
    gun = 1_000_000
    times = list(range(gun - 30_000, gun + 20_001, 1000))
    n = len(times)
    boundary = [(-100.0, -100.0), (100.0, -100.0),
                (100.0, 100.0), (-100.0, 100.0)]
    revised = [(-100.0, -100.0), (100.0, -100.0),
               (100.0, 20.0), (-100.0, 20.0)]
    session = SimpleNamespace(
        boat_class="AC40", race_type="FLEET", course_axis_deg=0.0,
        race_boundary=boundary,
        boundary_timeline=[{"t": gun + 5_000, "race": revised}]
        if revise_boundary else [],
    )
    boats = {}
    comps = {}
    legs = {}
    for code, status, x_offset in (("FIN", "FINISHED", 0.0),
                                   ("DNF", "DNF", 20.0),
                                   ("RET", "RET", 40.0),
                                   ("OCS", "OCS", 60.0)):
        rel_s = [(t - gun) / 1000 for t in times]
        y = [-20.0 if s <= 1 else 5.0 * (s - 1) if s <= 6
             else 25.0 - 5.0 * (s - 6) for s in rel_s]
        sog = [10.0 if s < 4 else 5.0 for s in rel_s]
        boats[code] = SimpleNamespace(
            asset_id=code.lower(), name=f"Team {code}", color="#ffffff",
            x=[x_offset] * n, y=y,
            heading=[0.0 if s <= 6 else 180.0 for s in rel_s],
            cog=[0.0 if s <= 6 else 180.0 for s in rel_s],
            sog_kt=sog, twd_deg=[0.0] * n,
        )
        gate = SimpleNamespace(leg=1, crossing_time=gun + 6_000,
                               mark_chosen="RM8", side="PORT", is_official=True)
        comps[code] = SimpleNamespace(
            team_code=code, classification=status,
            start=SimpleNamespace(crossing_time=gun + 1_000, ocs=status == "OCS"),
            gates=[gate] if code == "FIN" else [],
            finish_time_ms=gun + 12_000 if code == "FIN" else None,
            official_rank=1 if code == "FIN" else None,
            elapsed_s=11.0 if code == "FIN" else None,
        )
        legs[code] = [0 if s < 1 else 1 if s <= 6 else 2 for s in rel_s]
    mark_y_series = [mark_y] * n
    marks = {
        "RM8": SimpleNamespace(x=[-10.0] * n, y=mark_y_series),
        "RM6": SimpleNamespace(x=[10.0] * n, y=mark_y_series),
    }
    wind = ([{"t": gun, "twd_deg": 359.0, "tws_kt": 12.0},
             {"t": gun + 1_000, "twd_deg": 1.0, "tws_kt": 12.0}]
            if official_wind else [])
    ingestion = SimpleNamespace(
        session=session, grid_timestamps_ms=times, boats=boats, marks=marks,
        official_wind=SimpleNamespace(raw_timeline=wind),
    )
    reconstruction = SimpleNamespace(
        chronology=SimpleNamespace(gun_time=gun, window_end=times[-1]),
        competitors=comps,
    )
    tack = SimpleNamespace(type="TACK", timestamp=gun + 4_000,
                           entry_speed_kt=10.0, min_speed_kt=5.0,
                           speed_loss_kt=5.0)
    return ingestion, reconstruction, {"FIN": [tack]}, legs


def analyze_synthetic(**kwargs):
    ingestion, reconstruction, manoeuvres, legs = synthetic_race(**kwargs)
    return build_race_analysis(
        ingestion, reconstruction, manoeuvres, legs,
        "synthetic", "Synthetic race", "2026-10-08", "Test course",
    )


class TestDirectionalMetrics(unittest.TestCase):
    def test_circular_shift_uses_shortest_arc_across_north(self):
        self.assertAlmostEqual(circular_delta_deg(359.0, 1.0), 2.0)
        self.assertAlmostEqual(circular_delta_deg(1.0, 359.0), -2.0)
        self.assertAlmostEqual(circular_delta_deg(45.0, 55.0), 10.0)

    def test_leg_course_vmg_reverses_axis_on_downwind_legs(self):
        # The same physical course-axis trace is positive on leg 1 and
        # negative on leg 2; each leg's forward direction must be positive.
        self.assertAlmostEqual(leg_course_vmg_kt(12.0, 0.0, 0.0, 1), 12.0)
        self.assertAlmostEqual(leg_course_vmg_kt(12.0, 180.0, 0.0, 2), 12.0)
        self.assertAlmostEqual(leg_course_vmg_kt(12.0, 180.0, 0.0, 1), -12.0)
        self.assertAlmostEqual(leg_course_vmg_kt(12.0, 0.0, 0.0, 2), -12.0)
        self.assertAlmostEqual(leg_course_vmg_kt(12.0, 0.0, 0.0, 3), 12.0)

    def test_wind_relative_vmg_respects_wind_from_convention(self):
        # A north wind comes *from* north. Northbound is upwind; southbound
        # is downwind, regardless of the fixed course-axis VMG sign.
        self.assertAlmostEqual(wind_relative_vmg_kt(10.0, 0.0, 0.0, True), 10.0)
        self.assertAlmostEqual(wind_relative_vmg_kt(10.0, 180.0, 0.0, False), 10.0)
        self.assertAlmostEqual(wind_relative_vmg_kt(10.0, 180.0, 0.0, True), -10.0)
        self.assertAlmostEqual(wind_relative_vmg_kt(10.0, 0.0, 0.0, False), -10.0)
        self.assertAlmostEqual(wind_relative_vmg_kt(10.0, 359.0, 1.0, True),
                               10.0 * math.cos(math.radians(2.0)), places=6)


class TestMovingCourseGeometry(unittest.TestCase):
    def test_polygon_distance_has_correct_magnitude_and_side(self):
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        inside = signed_polygon_distance_m((5.0, 5.0), square)
        outside = signed_polygon_distance_m((15.0, 5.0), square)
        edge = signed_polygon_distance_m((10.0, 5.0), square)
        self.assertAlmostEqual(abs(inside), 5.0)
        self.assertAlmostEqual(abs(outside), 5.0)
        self.assertLess(inside * outside, 0.0)
        self.assertAlmostEqual(edge, 0.0)

    def test_boundary_revision_changes_exposure_at_same_boat_position(self):
        boat = (9.0, 5.0)
        old_boundary = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        revised_boundary = [(0.0, 0.0), (8.0, 0.0), (8.0, 10.0), (0.0, 10.0)]
        before = signed_polygon_distance_m(boat, old_boundary)
        after = signed_polygon_distance_m(boat, revised_boundary)
        self.assertAlmostEqual(abs(before), 1.0)
        self.assertAlmostEqual(abs(after), 1.0)
        self.assertLess(before * after, 0.0)

    def test_moving_start_line_changes_signed_distance(self):
        bow = (0.0, -5.0)
        port, starboard = (-10.0, 0.0), (10.0, 0.0)
        old_distance, old_fraction, nx, ny = start_line_geometry(
            bow, port, starboard, 0.0
        )
        moved_distance, moved_fraction, _, _ = start_line_geometry(
            bow, (-10.0, -10.0), (10.0, -10.0), 0.0
        )
        self.assertAlmostEqual(old_distance, -5.0)
        self.assertAlmostEqual(moved_distance, 5.0)
        self.assertAlmostEqual(old_fraction, 0.5)
        self.assertAlmostEqual(moved_fraction, 0.5)
        self.assertAlmostEqual(nx, 0.0)
        self.assertAlmostEqual(ny, 1.0)

    def test_start_position_fraction_is_not_clamped_to_segment(self):
        port, starboard = (-10.0, 0.0), (10.0, 0.0)
        self.assertAlmostEqual(start_line_geometry(port, port, starboard, 0.0)[1], 0.0)
        self.assertAlmostEqual(start_line_geometry(starboard, port, starboard, 0.0)[1], 1.0)
        self.assertAlmostEqual(
            start_line_geometry((-15.0, 0.0), port, starboard, 0.0)[1], -0.25
        )
        self.assertAlmostEqual(
            start_line_geometry((15.0, 0.0), port, starboard, 0.0)[1], 1.25
        )


class TestRaceAnalysisContract(unittest.TestCase):
    def test_event_feed_uses_recorded_times_and_provenance(self):
        result = analyze_synthetic()
        feed = result["event_feed"]
        self.assertEqual(feed["schema_version"], "1.0")
        self.assertEqual(feed["method_version"], "event-feed-1")
        events = feed["events"]
        self.assertEqual(len({event["id"] for event in events}), len(events))
        self.assertEqual(events, sorted(events, key=lambda event: (event["timestamp_ms"], event["id"])))
        self.assertTrue(all(event["source"] and event["quality"] for event in events))
        self.assertEqual(next(event for event in events if event["type"] == "gun")["timestamp_ms"], 1_000_000)
        tack = next(event for event in events if event["type"] == "tack")
        self.assertEqual((tack["boat_id"], tack["timestamp_ms"], tack["quality"]),
                         ("fin", 1_004_000, "ambiguous_rounding"))
        gate = next(event for event in events if event["type"] == "gate")
        self.assertEqual((gate["boat_id"], gate["timestamp_ms"], gate["quality"]),
                         ("fin", 1_006_000, "source_timing"))
        self.assertFalse(any(event["type"] == "finish" for event in events))

    def test_event_feed_omits_missing_times_and_detects_circular_wind_shift(self):
        detail = {"race": {"id": "wind", "gun_time_ms": None},
                  "boats": [{"id": "boat", "team_code": "BOAT", "classification": "DNF",
                             "start": {"crossing_time_ms": None},
                             "gates": [{"leg": 1, "crossing_time_ms": None}],
                             "manoeuvres": [{"type": "TACK", "timestamp": None}]}],
                  "wind": {"timeline": [
                      {"timestamp": 1_000_000, "shift_deg": 0.0},
                      {"timestamp": 1_010_000, "shift_deg": 11.0},
                      {"timestamp": 1_030_000, "shift_deg": 179.0},
                      {"timestamp": 1_061_000, "shift_deg": -179.0},
                      {"timestamp": 1_092_000, "shift_deg": -166.0}]}}
        events = build_event_feed(detail)["events"]
        self.assertEqual([event["timestamp_ms"] for event in events],
                         [1_030_000, 1_092_000])
        self.assertEqual([event["type"] for event in events], ["wind_shift", "wind_shift"])
        self.assertEqual(events[1]["label"], "Official wind shift +15.0°")
        self.assertTrue(all("boat_id" not in event for event in events))

    def test_circular_official_wind_shift_and_sparse_source(self):
        result = analyze_synthetic()
        self.assertEqual(result["wind"]["sample_count"], 2)
        self.assertEqual(result["wind"]["shift_min_deg"], 0.0)
        self.assertEqual(result["wind"]["shift_max_deg"], 2.0)
        missing = analyze_synthetic(official_wind=False)
        self.assertEqual(missing["wind"]["sample_count"], 0)
        self.assertEqual(missing["wind"]["timeline"], [])
        self.assertIn("reason", missing["wind"])

    def test_moving_boundary_and_mark_affect_exported_metrics(self):
        revised = analyze_synthetic(revise_boundary=True)
        static = analyze_synthetic(revise_boundary=False)
        revised_fin = next(b for b in revised["boats"] if b["team_code"] == "FIN")
        static_fin = next(b for b in static["boats"] if b["team_code"] == "FIN")
        self.assertGreater(revised_fin["metrics"]["boundary_outside_s"]["value"], 0)
        self.assertEqual(static_fin["metrics"]["boundary_outside_s"]["value"], 0)

        moved = analyze_synthetic(mark_y=-10.0)
        moved_fin = next(b for b in moved["boats"] if b["team_code"] == "FIN")
        self.assertAlmostEqual(
            moved_fin["metrics"]["start_distance_m"]["value"]
            - static_fin["metrics"]["start_distance_m"]["value"],
            10.0, places=4,
        )

    def test_unrecovered_tack_is_unavailable_not_zero(self):
        result = analyze_synthetic()
        fin = next(b for b in result["boats"] if b["team_code"] == "FIN")
        tack = fin["manoeuvres"][0]
        self.assertIsNone(tack["recovery_time_s"])
        self.assertIn("95%", tack["recovery_reason"])
        self.assertIsNone(fin["metrics"]["tack_recovery_median_s"]["value"])
        self.assertEqual(fin["metrics"]["tack_recovery_median_s"]["quality"],
                         "unavailable")
        self.assertEqual(fin["metrics"]["tack_loss_median_kt"]["value"], 5.0)

    def test_ocs_ret_dnf_and_incomplete_gates_keep_unknowns_null(self):
        result = analyze_synthetic()
        boats = {b["team_code"]: b for b in result["boats"]}
        for code in ("OCS", "RET"):
            metric = boats[code]["metrics"]["distance_m"]
            self.assertIsNone(metric["value"])
            self.assertEqual(metric["quality"], "unavailable")
            self.assertIn("reason", metric)
            self.assertIsNone(boats[code]["official_elapsed_s"])
        self.assertIsNone(boats["OCS"]["start"]["crossing_order"])
        self.assertIsNone(boats["DNF"]["official_rank"])
        self.assertIsNone(boats["DNF"]["official_elapsed_s"])
        self.assertFalse(boats["FIN"]["legs"][1]["complete"])
        self.assertIsNone(boats["FIN"]["legs"][2]["metrics"]["elapsed_s"]["value"])
        self.assertIn("reason", boats["FIN"]["legs"][2]["metrics"]["elapsed_s"])


class TestHistoricalIndex(unittest.TestCase):
    def test_catalog_expansion_uses_boat_races_and_separates_race_types(self):
        def metric(value, unit="kt"):
            return {"value": value, "unit": unit, "quality": "derived",
                    "coverage_s": 100.0}

        def leg(number, complete, elapsed):
            return {"leg": number, "complete": complete,
                    "metrics": {"elapsed_s": metric(elapsed, "s"),
                                "course_vmg_kt": metric(10.0),
                                "wind_vmg_kt": metric(9.0),
                                "distance_m": metric(100.0, "m")}}

        def event(kind, loss, recovery):
            return {"type": kind, "speed_loss_kt": loss,
                    "recovery_time_s": recovery}

        def boat(team, speed, *, legs=None, events=None, crossing=None):
            return {"id": team.lower(), "team_code": team,
                    "team_name": f"Team {team}", "color": "#ffffff",
                    "classification": "FINISHED", "official_rank": 1,
                    "official_elapsed_s": 100.0,
                    "metrics": {"sog_mean_kt": metric(speed)},
                    "start": {"crossing_time_ms": crossing, "crossing_order": 1,
                              "ocs": False},
                    "legs": legs or [], "manoeuvres": events or []}

        specs = [
            ("first", "FLEET", [boat(
                "A", 10.0, legs=[leg(1, True, 100.0), leg(2, False, 999.0)],
                events=[event("TACK", 2.0, 3.0), event("TACK", 4.0, None),
                        event("GYBE", 8.0, 4.0)], crossing=1_002_000)]),
            ("second", "FLEET", [
                boat("A", 20.0, legs=[leg(1, True, 120.0), leg(2, False, 777.0)],
                     events=[event("TACK", 6.0, 5.0)], crossing=999_000),
                boat("B", 15.0), boat("C", 12.0)]),
            ("future_match", "MATCH", [
                boat("A", 100.0, legs=[leg(1, True, 500.0)]), boat("D", 14.0)]),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analysis_dir = root / "analysis"
            analysis_dir.mkdir()
            catalog = {"races": []}
            for race_id, race_type, boats in specs:
                catalog["races"].append({"id": race_id, "date": "2026-10-08"})
                detail = {
                    "schema_version": SCHEMA_VERSION,
                    "race": {"id": race_id, "name": race_id, "date": "2026-10-08",
                             "boat_class": "AC40", "race_type": race_type,
                             "gun_time_ms": 1_000_000},
                    "boats": boats,
                    "telemetry": {"timestamps": list(range(100))},
                }
                (analysis_dir / f"{race_id}.json").write_text(
                    json.dumps(detail), encoding="utf-8"
                )
            catalog_path = root / "catalog.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

            index = build_historical_index(str(catalog_path), str(analysis_dir))

        self.assertEqual([r["id"] for r in index["races"]],
                         ["first", "future_match", "second"])
        self.assertEqual([r["boat_count"] for r in index["races"]], [1, 2, 3])
        fleet_a = next(h for h in index["histories"]
                       if h["team_code"] == "A" and h["race_type"] == "FLEET")
        match_a = next(h for h in index["histories"]
                       if h["team_code"] == "A" and h["race_type"] == "MATCH")
        self.assertEqual(fleet_a["race_count"], 2)
        self.assertEqual(fleet_a["summary"]["sog_mean_kt"],
                         {"median": 15.0, "min": 10.0, "max": 20.0, "count": 2})
        self.assertEqual(match_a["race_count"], 1)
        self.assertEqual(match_a["summary"]["sog_mean_kt"]["median"], 100.0)
        first_a = index["races"][0]["boats"][0]
        self.assertEqual(first_a["start"]["delta_to_gun_s"], 2.0)
        self.assertEqual(first_a["legs"][0]["elapsed_s"]["unit"], "s")
        self.assertEqual(fleet_a["leg_summary"]["1"]["elapsed_s"],
                         {"median": 110.0, "min": 100.0,
                          "max": 120.0, "count": 2})
        self.assertNotIn("2", fleet_a["leg_summary"])
        self.assertEqual(match_a["leg_summary"]["1"]["elapsed_s"]["median"],
                         500.0)
        tacks = fleet_a["manoeuvre_summary"]["TACK"]
        self.assertEqual(tacks["event_count"], 3)
        self.assertEqual(tacks["race_count"], 2)
        self.assertEqual(tacks["origin_races"], {"first": 2, "second": 1})
        self.assertEqual((tacks["loss_p10_kt"], tacks["loss_median_kt"],
                          tacks["loss_p90_kt"]), (2.0, 4.0, 6.0))
        self.assertEqual(tacks["recovery_median_s"], 4.0)
        self.assertEqual(tacks["unrecovered_count"], 1)
        self.assertEqual(fleet_a["manoeuvre_summary"]["GYBE"]["event_count"], 1)
        self.assertEqual(match_a["manoeuvre_summary"]["TACK"]["event_count"], 0)
        self.assertNotIn("telemetry", json.dumps(index))


class TestGeneratedRaceRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2] / "public" / "data"
        cls.catalog = json.loads((root / "manifests.json").read_text(encoding="utf-8"))
        cls.index = json.loads((root / "analysis" / "index.json").read_text(
            encoding="utf-8"))
        cls.details = {
            race["id"]: json.loads((root / race["analysis_file"]).read_text(
                encoding="utf-8"))
            for race in cls.index["races"]
        }

    def test_both_catalog_races_and_all_eleven_boat_entries_are_present(self):
        ids = {race["id"] for race in self.catalog["races"]}
        self.assertTrue({"naples_pr1", "naples_mr_final"}.issubset(ids))
        self.assertEqual(set(self.details), ids)
        counts = {r["id"]: r["boat_count"] for r in self.index["races"]}
        self.assertEqual(counts["naples_pr1"], 9)
        self.assertEqual(counts["naples_mr_final"], 2)
        self.assertEqual(sum(h["race_count"] for h in self.index["histories"]),
                         sum(counts.values()))
        for race in self.index["races"]:
            detail = self.details[race["id"]]
            self.assertEqual(detail["schema_version"], SCHEMA_VERSION)
            self.assertEqual(len(detail["boats"]), race["boat_count"])
            self.assertEqual(len({b["id"] for b in detail["boats"]}),
                             race["boat_count"])
            # JSON's permissive NaN/Infinity extensions would break browser use.
            json.dumps(detail, allow_nan=False)

    def test_reconstructed_examples_and_statuses_use_session_identity(self):
        fleet = {b["team_code"]: b for b in self.details["naples_pr1"]["boats"]}
        match = {b["team_code"]: b
                 for b in self.details["naples_mr_final"]["boats"]}
        self.assertAlmostEqual(fleet["FRA"]["official_elapsed_s"], 1059.555)
        self.assertAlmostEqual(match["ITA B"]["official_elapsed_s"], 1252.05, delta=0.1)
        self.assertIsNone(fleet["NZL B"]["official_elapsed_s"])
        self.assertIsNone(fleet["GBR B"]["official_elapsed_s"])
        self.assertTrue(fleet["GBR B"]["start"]["ocs"])
        self.assertIsNone(fleet["GBR B"]["start"]["crossing_order"])
        self.assertIsNone(fleet["GBR B"]["metrics"]["distance_m"]["value"])

    def test_compact_start_leg_and_event_data_match_both_details(self):
        for race in self.index["races"]:
            detail = self.details[race["id"]]
            by_team = {b["team_code"]: b for b in detail["boats"]}
            for compact in race["boats"]:
                source = by_team[compact["team_code"]]
                self.assertEqual(compact["start"]["crossing_time_ms"],
                                 source["start"]["crossing_time_ms"])
                self.assertEqual(compact["start"]["ocs"], source["start"]["ocs"])
                self.assertEqual(compact["start"]["crossing_order"],
                                 source["start"]["crossing_order"])
                if compact["start"]["ocs"]:
                    self.assertIsNone(compact["start"]["delta_to_gun_s"])
                elif compact["start"]["crossing_time_ms"] is not None:
                    self.assertAlmostEqual(
                        compact["start"]["delta_to_gun_s"],
                        (compact["start"]["crossing_time_ms"]
                         - detail["race"]["gun_time_ms"]) / 1000,
                    )
                self.assertEqual(len(compact["legs"]), len(source["legs"]))
                for indexed_leg, source_leg in zip(compact["legs"], source["legs"]):
                    self.assertEqual(indexed_leg["complete"], source_leg["complete"])
                    for key in ("elapsed_s", "course_vmg_kt", "wind_vmg_kt",
                                "distance_m"):
                        self.assertEqual(indexed_leg[key],
                                         source_leg["metrics"].get(key))

        for history in self.index["histories"]:
            self.assertEqual(history["race_count"], len(history["observations"]))
            for kind in ("TACK", "GYBE"):
                source_events = [(obs["race_id"], event)
                                 for obs in history["observations"]
                                 for boat in self.details[obs["race_id"]]["boats"]
                                 if boat["team_code"] == history["team_code"]
                                 for event in boat["manoeuvres"]
                                 if event["type"] == kind]
                summary = history["manoeuvre_summary"][kind]
                self.assertEqual(summary["event_count"], len(source_events))
                self.assertEqual(summary["race_count"],
                                 len({race_id for race_id, _ in source_events}))
                self.assertEqual(summary["unrecovered_count"],
                                 sum(event["recovery_time_s"] is None
                                     for _, event in source_events))

    def test_unavailable_exported_metrics_explain_the_gap(self):
        for race_id, detail in self.details.items():
            for boat in detail["boats"]:
                collections = [boat["metrics"]] + [leg["metrics"]
                                                   for leg in boat["legs"]]
                for metrics in collections:
                    for key, metric in metrics.items():
                        with self.subTest(race=race_id, boat=boat["team_code"],
                                          metric=key):
                            self.assertIn("unit", metric)
                            self.assertIn("coverage_s", metric)
                            if metric["value"] is None:
                                self.assertEqual(metric["quality"], "unavailable")
                                self.assertTrue(metric.get("reason"))


if __name__ == "__main__":
    unittest.main()
