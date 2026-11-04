"""Small independent source, filter and knowledge-time regression fixtures.

These tests contain no archive telemetry and do not establish model calibration.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from pipeline.identity import resolve_identity
from pipeline.prediction.models import LegTimeModel
from pipeline.prediction.simulation import simulate_race
from pipeline.prediction.source import BUFFER_MS, read_source
from pipeline.prediction.state import CausalRace, PositionFilter, certify_outages, transition


LAT, LON = 37., 14.


def row(aid, timestamp, *, x=0., y=0., field="gnss_position", value=None):
    return {"asset_id": aid, "timestamp_ms": timestamp,
            "available_at_ms": timestamp + BUFFER_MS, "source_ordinal": timestamp,
            "field": field, "value": value,
            "latitude": LAT + y / 111320 if field == "gnss_position" else None,
            "longitude": LON + x / (111320 * math.cos(math.radians(LAT))) if field == "gnss_position" else None}


def session(timestamp=0):
    return {"timestamp": timestamp, "race_start": 1000,
            "race_course": {"course_length": 1000, "sequences": [
                {"gate": {"port_asset_id": "s_p", "starboard_asset_id": "s_s"}},
                {"gate": {"port_asset_id": "t_p", "starboard_asset_id": "t_s"}},
                {"gate": {"port_asset_id": "s_p", "starboard_asset_id": "s_s"}},
            ]}}


def metadata():
    return {"sessions": [session()], "competitor_events": [
        {"asset_id": "a", "timestamp": 1000, "start_state": {"started": True},
         "leg_timings": [{"leg_number": 0, "gate_time": 1000}]}],
        "boat_ids": ["a"], "date": "2026-05-22", "gun_ms": 1000, "practice": False}


def observations():
    values = [row("a", t, y=100 + t / 100) for t in range(0, 21000, 1000)]
    for aid, x, y in [("s_p", -50, 0), ("s_s", 50, 0), ("t_p", -50, 1000), ("t_s", 50, 1000)]:
        values.extend(row(aid, t, x=x, y=y) for t in range(0, 21000, 1000))
    values.extend(row("a", t, field="course_over_ground", value=0.) for t in range(0, 21000, 1000))
    return sorted(values, key=lambda r: r["timestamp_ms"])


class ForwardStateTests(unittest.TestCase):
    def test_continuous_white_acceleration_covariance_and_growth(self):
        f, q = transition(2., 2.)
        np.testing.assert_allclose(f[:2, 2:], 2 * np.eye(2))
        self.assertAlmostEqual(q[0, 0], 16 / 3)
        self.assertAlmostEqual(q[0, 2], 4.)
        self.assertAlmostEqual(q[2, 2], 4.)
        self.assertGreaterEqual(np.linalg.eigvalsh(q).min(), 0.)
        filt = PositionFilter()
        filt.observe(0, [0., 0.])
        _, short = filt.predict(1000)
        _, long = filt.predict(10000)
        self.assertGreater(np.trace(long[:2, :2]), np.trace(short[:2, :2]))

    def test_forward_filter_never_accepts_a_backward_observation(self):
        filt = PositionFilter()
        filt.observe(1000, [0., 0.])
        with self.assertRaises(ValueError):
            filt.observe(999, [200., 300.])
        with self.assertRaises(ValueError):
            filt.predict(999)

    def test_appending_future_positions_and_events_cannot_change_earlier_state(self):
        meta, rows = metadata(), observations()
        before = CausalRace(meta, rows).features("a", 11000)
        self.assertEqual(before["quality"], "available")
        extended = deepcopy(meta)
        future_session = session(19000)
        future_session["race_start"] = 5000
        extended["sessions"].append(future_session)
        extended["competitor_events"].append({"asset_id": "a", "timestamp": 19000,
                                             "start_state": {"started": True},
                                             "leg_timings": [{"leg_number": 0, "gate_time": 1000},
                                                             {"leg_number": 1, "gate_time": 18000}]})
        rows.append(row("a", 30000, x=3000, y=900))
        after = CausalRace(extended, rows).features("a", 11000)
        self.assertEqual(before, after)

    def test_invalid_gnss_row_cannot_shift_valid_state_index_into_the_future(self):
        invalid = row("a", 1000)
        invalid["latitude"] = None
        race = CausalRace(metadata(), [row("a", 0), invalid, row("a", 2000, y=500)])
        state = race.position("a", 1500)
        self.assertIsNotNone(state)
        self.assertEqual(state["source_age_ms"], 1500)
        np.testing.assert_allclose(state["xy"], [0., 0.], atol=1e-8)

    def test_unobserved_position_is_missing_rather_than_held_from_a_future_endpoint(self):
        race = CausalRace(metadata(), [row("a", 5000, y=600)])
        self.assertIsNone(race.position("a", 4999))

    def test_invalid_leading_coordinate_cannot_poison_the_local_origin(self):
        invalid = row("a", 0)
        invalid["latitude"] = float("nan")
        race = CausalRace(metadata(), [invalid, row("a", 1000), row("a", 2000, y=10)])
        self.assertTrue(np.isfinite(race.position("a", 2000)["xy"]).all())

    def test_freshness_and_uncertified_outage_are_distinct(self):
        race = CausalRace(metadata(), [r for r in observations() if r["asset_id"] != "a" or r["timestamp_ms"] <= 11000])
        self.assertEqual(race.features("a", 12000)["quality"], "available")
        gap = race.features("a", 16000)
        self.assertEqual(gap["quality"], "unavailable")
        self.assertEqual(gap["reason"], "outage_horizon_not_certified")
        estimated = race.features("a", 16000, {"steady": {"horizon_s": 10}})
        self.assertEqual(estimated["quality"], "estimated")
        self.assertEqual(estimated["source_age_ms"], 5000)

    def test_predicted_gate_crossing_does_not_establish_the_next_leg(self):
        values = observations()
        for observation in values:
            if observation["asset_id"] == "a" and observation["field"] == "gnss_position":
                observation["latitude"] = LAT + (800 + observation["timestamp_ms"] / 50) / 111320
        feature = CausalRace(metadata(), values).features("a", 15000)
        self.assertEqual(feature["quality"], "gate_ambiguous")
        self.assertNotIn("current_leg", feature)

    def test_stale_false_start_flag_is_ambiguous_even_if_later_gates_exist(self):
        meta = metadata()
        meta["competitor_events"][0]["start_state"]["started"] = False
        meta["competitor_events"][0]["leg_timings"].append({"leg_number": 1, "gate_time": 10000})
        feature = CausalRace(meta, observations()).features("a", 11000)
        self.assertEqual(feature["quality"], "gate_ambiguous")
        self.assertEqual(feature["reason"], "start_not_validated")

    def test_finish_is_available_only_after_the_competitor_message(self):
        meta = metadata()
        meta["competitor_events"].append({"asset_id": "a", "timestamp": 20000,
            "start_state": {"started": True}, "leg_timings": [
                {"leg_number": 0, "gate_time": 1000}, {"leg_number": 1, "gate_time": 15000},
                {"leg_number": 2, "gate_time": 18000}]})
        race = CausalRace(meta, observations())
        self.assertNotIn("terminal_status", race.features("a", 19000))
        terminal = race.features("a", 20000)
        self.assertEqual(terminal["terminal_status"], "finished")
        self.assertEqual(terminal["finished_at_s"], 17.)

    def test_missing_or_reversed_gate_chain_cannot_certify_a_valid_finish(self):
        for timings in ([{"leg_number": 0, "gate_time": 1000},
                         {"leg_number": 2, "gate_time": 18000}],
                        [{"leg_number": 0, "gate_time": 1000},
                         {"leg_number": 1, "gate_time": 19000},
                         {"leg_number": 2, "gate_time": 18000}]):
            with self.subTest(timings=timings):
                meta = metadata()
                meta["competitor_events"].append({"asset_id": "a", "timestamp": 20000,
                    "start_state": {"started": True}, "leg_timings": timings})
                feature = CausalRace(meta, observations()).features("a", 20000)
                self.assertEqual(feature["quality"], "gate_ambiguous")
                self.assertNotIn("terminal_status", feature)

    def test_definitive_raw_retirement_or_dns_is_known_even_after_gnss_stops(self):
        for classification, status in (("COMPETITOR_CLASSIFICATION_RETIRED", "ret"),
                                       ("COMPETITOR_CLASSIFICATION_DID_NOT_START", "dns")):
            with self.subTest(classification=classification):
                meta = metadata()
                meta["competitor_events"].append({"asset_id": "a", "timestamp": 19000,
                    "classification": classification, "start_state": {"started": False}, "leg_timings": []})
                race = CausalRace(meta, [])
                self.assertNotIn("terminal_status", race.features("a", 18999))
                state = race.features("a", 19000)
                self.assertEqual(state["quality"], "available")
                self.assertEqual(state["terminal_status"], status)

    def test_reconstructed_ret_shortcut_is_not_treated_as_a_definitive_source_status(self):
        meta = metadata()
        meta["competitor_events"][0]["classification"] = "RET"
        state = CausalRace(meta, []).features("a", 20000)
        self.assertEqual(state["quality"], "unavailable")
        self.assertNotIn("terminal_status", state)

    def test_first_received_finish_cannot_resolve_a_missing_opponent(self):
        result = simulate_race(LegTimeModel(), ["a", "b"], [{"distance_m": 1000}], None,
                               state={"a": {"quality": "available", "terminal_status": "finished", "finished_at_s": 100.},
                                      "b": {"quality": "unavailable", "reason": "missing_position"}}, n=10)
        self.assertFalse(result.available)
        self.assertEqual(result.boat_ids, ["a", "b"])
        self.assertIsNone(result.win_probabilities["a"])
        self.assertIsNone(result.win_probabilities["b"])
        result = simulate_race(LegTimeModel(), ["a", "b"], [{"distance_m": 1000}], None,
                               state={"a": {"quality": "available", "terminal_status": "finished", "finished_at_s": 100.},
                                      "b": {"quality": "available"}}, n=10)
        self.assertFalse(result.available)
        self.assertIn("globally resolved", result.reason)

    def test_resolved_terminal_causal_state_matches_simulator_leg_index_contract(self):
        meta = metadata()
        meta["competitor_events"].append({"asset_id": "a", "timestamp": 20000,
            "start_state": {"started": True}, "leg_timings": [
                {"leg_number": 0, "gate_time": 1000}, {"leg_number": 1, "gate_time": 15000},
                {"leg_number": 2, "gate_time": 18000}]})
        terminal = CausalRace(meta, observations()).features("a", 20000)
        later = dict(terminal, finished_at_s=18.)
        result = simulate_race(LegTimeModel(), ["a", "b"], [{"distance_m": 1000}] * 2, None,
                               state={"a": terminal, "b": later}, n=20,
                               global_finish_order_resolved=True)
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.win_probabilities, {"a": 1., "b": 0.})


class OutageCertificationAggregationTests(unittest.TestCase):
    class MaskRace:
        """Controlled noisy truth isolates certification aggregation from filtering."""
        def __init__(self, meta, rows, **parameters):
            self.meta, self.q, self.r = meta, 0., 9.
            self.by_stream = {("a", "gnss_position"): [
                row("a", 1000 * i, x=100.) for i in range(1001)]}
            self.origin = (LAT, LON)
            self.positions = {"a": [(1000 * i, np.zeros(4), np.eye(4) * 1e6)
                                    for i in range(1001)]}
            self.position_available_times = {"a": [1000 * i for i in range(1001)]}

        def features(self, aid, cutoff):
            if self.meta.get("ambiguous"):
                return {"quality": "gate_ambiguous", "reason": "crossing_uncertain"}
            return {"quality": "available", "stratum": "steady", "leg_length_m": self.meta["length"]}

        def latest(self, aid, field, cutoff):
            return row(aid, cutoff, x=100.)

    def mask_meta(self, date, length, **extra):
        return {"date": date, "length": length, "boat_ids": ["a"], "gun_ms": 0,
                "sessions": [{"race_course": {"course_length": length}}], **extra}

    def test_short_course_errors_cannot_be_certified_by_processing_a_long_course_last(self):
        races = [(self.mask_meta("2026-05-22", 500), []),
                 (self.mask_meta("2026-05-23", 500), []),
                 (self.mask_meta("2026-05-24", 10000), [])]
        with patch("pipeline.prediction.state.CausalRace", self.MaskRace):
            forward = certify_outages(races, horizons=(2,))
            backward = certify_outages(list(reversed(races)), horizons=(2,))
        self.assertEqual(forward, backward)
        steady = forward["steady"]
        self.assertGreaterEqual(steady["masks"]["2"]["count"], 50)
        self.assertGreaterEqual(steady["masks"]["2"]["median_normalized_error"], .19)
        self.assertEqual(steady["horizon_s"], 0)

    def test_ambiguous_gate_masks_do_not_default_to_the_steady_stratum(self):
        races = [(self.mask_meta("2026-05-22", 1000, ambiguous=True), []),
                 (self.mask_meta("2026-05-23", 1000, ambiguous=True), [])]
        with patch("pipeline.prediction.state.CausalRace", self.MaskRace):
            certificate = certify_outages(races, horizons=(2,))
        self.assertEqual(certificate["steady"]["masks"]["2"]["count"], 0)
        self.assertEqual(certificate["steady"]["horizon_s"], 0)


class StreamingSourceContractTests(unittest.TestCase):
    def write_source(self, directory, name, telemetry):
        gun = int(datetime(2026, 9, 26, 12, tzinfo=timezone.utc).timestamp() * 1000)
        meta = session(gun - 10000)
        meta.update(race_start=gun, window_start=gun - 10000, window_end=gun + 100000,
                    competitors=[{"asset_id": "hull"}],
                    assets=[{"id": "hull", "abbreviation": "ITA B", "official_name": "Luna Rossa"}])
        path = Path(directory) / name
        records = [{"session": meta}, *telemetry]
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path, gun

    @staticmethod
    def telemetry(t, latitude, *, aid="hull"):
        return {"telemetry": {"asset_id": aid, "timestamp": t,
                               "gnss_position": {"latitude": latitude, "longitude": LON}}}

    def test_retains_last_observed_sample_timestamp_ordinal_and_modeled_latency(self):
        with TemporaryDirectory() as directory:
            path, _ = self.write_source(directory, "26 09 26 NAP IPR Race 1.jsonl", [
                self.telemetry(1001, 37.), self.telemetry(1999, 37.1), self.telemetry(1500, 37.2)])
            meta, rows = read_source(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["timestamp_ms"], 1999)
            self.assertEqual(rows[0]["source_ordinal"], 3)
            self.assertEqual(rows[0]["bucket_closed_at_ms"], 2000)
            self.assertEqual(rows[0]["available_at_ms"], 2000 + BUFFER_MS)
            self.assertEqual(rows[0]["latitude"], 37.1)
            self.assertEqual(meta["max_disorder_ms"], 499)
            self.assertEqual(meta["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            race = CausalRace(meta, rows)
            self.assertIsNone(race.latest("hull", "gnss_position", 1999))
            self.assertIsNone(race.position("hull", 1999))
            self.assertEqual(race.latest("hull", "gnss_position", 2000)["timestamp_ms"], 1999)
            self.assertEqual(race.position("hull", 2000)["source_age_ms"], 1)

    def test_effective_gun_date_overrides_the_filename_and_practice_is_explicit(self):
        with TemporaryDirectory() as directory:
            path, gun = self.write_source(directory, "26 09 25 NAP IPR Race 3.jsonl", [])
            meta, _ = read_source(path)
            self.assertEqual(meta["date"], "2026-09-26")
            self.assertEqual(meta["gun_ms"], gun)
            self.assertFalse(meta["practice"])
            path, _ = self.write_source(directory, "26 09 22 NAP IPR PR1.jsonl", [])
            practice, _ = read_source(path)
            self.assertTrue(practice["practice"])

    def test_reordering_contract_is_not_silently_assumed_beyond_six_seconds(self):
        with TemporaryDirectory() as directory:
            path, _ = self.write_source(directory, "26 09 26 NAP IPR Race 1.jsonl", [
                self.telemetry(10000, 37.), self.telemetry(3999, 37.)])
            meta, _ = read_source(path)
            self.assertFalse(meta["reorder_contract_valid"])
            self.assertEqual(meta["max_disorder_ms"], 6001)

    def test_session_identity_can_change_without_renaming_the_physical_hull(self):
        old = resolve_identity("hull", {"hull": {"abbreviation": "ITA G", "official_name": "Luna Rossa"}}, timestamp_ms=1000)
        new = resolve_identity("hull", {"hull": {"abbreviation": "ITA B", "official_name": "Luna Rossa"}}, timestamp_ms=2000)
        self.assertEqual(old["asset_id"], new["asset_id"])
        self.assertNotEqual(old["entry_id"], new["entry_id"])
        self.assertEqual(new["effective_from_ms"], 2000)
        unknown = resolve_identity("new-hull", {}, timestamp_ms=3000)
        self.assertEqual(unknown["entry_id"], "new-hull")


if __name__ == "__main__":
    unittest.main()
