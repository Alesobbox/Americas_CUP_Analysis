"""Unit tests for observed ground-speed polar and conditional residual attribution (polar-1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from pipeline.polar_analysis import (
    POLAR_CAVEATS,
    POLAR_METHOD_VERSION,
    POLAR_SCHEMA_VERSION,
    attach_single_race_polar_fallback,
    extract_race_polar_cells,
    refresh_archive_polar_models,
)


def _synthetic_race_pair(
    race_id: str,
    date: str,
    *,
    day_offset_kt: float = 0.0,
    stbd_minus_port_kt: float = 0.8,
    team_a_offset_kt: float = 1.2,
    traffic_overlap: bool = False,
    manoeuvre_at_s: int | None = None,
    sharp_turn_at_s: int | None = None,
) -> dict:
    """Create a 1 Hz synthetic race detail + replay telemetry with known ground-speed physics."""
    gun = 1_790_000_000_000
    n = 120
    ts = [gun + i * 1000 for i in range(n)]
    # Boat A sails starboard on leg 1 (upwind) and port on leg 1 second half; Boat B opposite
    boats_detail = []
    boats_tel = {}
    for idx, (bid, code, base_off, is_stbd_first) in enumerate(
        [("a", "TEAM_A", team_a_offset_kt, True), ("b", "TEAM_B", -team_a_offset_kt, False)]
    ):
        hdg, cog, sog, twd, tws, xs, ys = [], [], [], [], [], [], []
        for s in range(n):
            in_leg2 = s >= 60
            in_second_half = (s % 60) >= 30
            stbd = is_stbd_first if not in_second_half else (not is_stbd_first)
            twd_s = 0.0
            twa = 45.0 if not in_leg2 else 135.0
            signed_twa = twa if stbd else -twa
            hdg_s = (twd_s - signed_twa) % 360.0
            if sharp_turn_at_s is not None and s == sharp_turn_at_s and bid == "a":
                hdg_s = (hdg_s + 25.0) % 360.0
            tws_s = 12.0 + 0.02 * s
            expected_sog = (
                18.0 + 0.8 * tws_s + (0.0 if not in_leg2 else 3.0)
                + day_offset_kt
                + (0.5 * stbd_minus_port_kt if stbd else -0.5 * stbd_minus_port_kt)
                + base_off
            )
            hdg.append(hdg_s)
            cog.append(hdg_s)
            sog.append(expected_sog)
            twd.append(twd_s)
            tws.append(tws_s)
            if traffic_overlap and bid == "b" and 20 <= s <= 40:
                xs.append(0.0 + 10.0)
                ys.append(float(s) * 10.0)
            else:
                xs.append(float(idx) * 200.0)
                ys.append(float(s) * 10.0)
        boats_tel[bid] = {
            "x": xs,
            "y": ys,
            "heading": hdg,
            "cog": cog,
            "sog": sog,
            "twd": twd,
            "tws": tws,
        }
        mans = (
            [{"type": "TACK", "timestamp": ts[manoeuvre_at_s]}]
            if manoeuvre_at_s is not None and bid == "a"
            else []
        )
        boats_detail.append(
            {
                "id": bid,
                "team_code": code,
                "team_name": code,
                "color": "#1a73e8",
                "classification": "RANK_1" if idx == 0 else "RANK_2",
                "start": {"crossing_time_ms": ts[0], "ocs": False},
                "source_conflicts": [],
                "manoeuvres": mans,
                "gates": [
                    {"leg": 1, "crossing_time_ms": ts[59]},
                    {"leg": 2, "crossing_time_ms": ts[-1]},
                ],
                "legs": [
                    {"leg": 1, "complete": True, "start_ms": ts[0], "end_ms": ts[59]},
                    {"leg": 2, "complete": True, "start_ms": ts[59], "end_ms": ts[-1]},
                ],
                "source_coverage": {
                    fld: {"first_ms": ts[0], "last_ms": ts[-1], "gaps": []}
                    for fld in ("gnss", "heading", "sog", "cog", "twd", "tws")
                },
            }
        )
    detail = {
        "schema_version": "2.0",
        "method_version": "historical-2",
        "race": {"id": race_id, "name": race_id, "date": date, "race_type": "RACE_TYPE_FLEET"},
        "boats": boats_detail,
    }
    replay = {"telemetry": {"timestamps": ts, "boats": boats_tel}}
    extract_race_polar_cells(detail, replay_doc=replay)
    return detail


class PolarAnalysisTests(unittest.TestCase):
    def test_steady_state_filters_exclude_traffic_manoeuvres_and_turns(self):
        clean = _synthetic_race_pair("r_clean", "2026-09-22")
        noised = _synthetic_race_pair(
            "r_noise",
            "2026-09-22",
            traffic_overlap=True,
            manoeuvre_at_s=25,
            sharp_turn_at_s=35,
        )
        clean_s = clean["boats"][0]["polar_filter"]["steady_coverage_s"]
        noisy_s = noised["boats"][0]["polar_filter"]["steady_coverage_s"]
        self.assertGreater(clean_s, noisy_s)
        self.assertGreater(noised["boats"][0]["polar_filter"]["traffic_excluded_s"], 0.0)
        self.assertGreater(noised["boats"][0]["polar_filter"]["manoeuvre_excluded_s"], 0.0)
        self.assertGreater(noised["boats"][0]["polar_filter"]["turn_rate_excluded_s"], 0.0)

    def test_ingest_namespace_without_tws_degrades_gracefully(self):
        detail = _synthetic_race_pair("r_mock", "2026-09-22")
        mock_ingest = SimpleNamespace(
            grid_timestamps_ms=[1_000_000, 1_001_000],
            boats={
                "A": SimpleNamespace(
                    asset_id="a",
                    x=[0.0, 0.0],
                    y=[0.0, 10.0],
                    heading=[0.0, 0.0],
                    cog=[0.0, 0.0],
                    sog_kt=[10.0, 10.0],
                    twd_deg=[0.0, 0.0],
                )
            },
        )
        res = extract_race_polar_cells(detail, ingest_result=mock_ingest)
        self.assertFalse(res["extracted"])
        attach_single_race_polar_fallback(detail)
        self.assertEqual(detail["polar_analysis"]["quality"], "unavailable")

    def test_fixed_effect_tack_day_grouped_cv_and_bootstrap_cis(self):
        details = {
            "d1_r1": _synthetic_race_pair("d1_r1", "2026-09-22", day_offset_kt=1.5, stbd_minus_port_kt=0.9),
            "d1_r2": _synthetic_race_pair("d1_r2", "2026-09-22", day_offset_kt=1.5, stbd_minus_port_kt=0.9),
            "d2_r1": _synthetic_race_pair("d2_r1", "2026-09-23", day_offset_kt=-1.5, stbd_minus_port_kt=0.9),
            "d2_r2": _synthetic_race_pair("d2_r2", "2026-09-23", day_offset_kt=-1.5, stbd_minus_port_kt=0.9),
        }
        model = refresh_archive_polar_models(copy.deepcopy(details))
        assert model is not None
        self.assertEqual(model["schema_version"], POLAR_SCHEMA_VERSION)
        self.assertEqual(model["method_version"], POLAR_METHOD_VERSION)
        self.assertEqual(model["caveats"], POLAR_CAVEATS)
        self.assertIn("fixed effect", model["tack_fixed_effect"]["specification"].lower())

        # Fixed tack contrast (~+0.9 kt) is recovered accurately
        overall_tack = model["tack_fixed_effect"]["overall"]
        assert overall_tack is not None
        self.assertAlmostEqual(overall_tack["contrast_kt"], 0.9, delta=0.25)
        self.assertLessEqual(overall_tack["ci_low_kt"], overall_tack["contrast_kt"])
        self.assertLessEqual(overall_tack["contrast_kt"], overall_tack["ci_high_kt"])

        # Day-grouped CV reflects cross-day current shift (higher RMSE than same-day LORO)
        val = model["validation"]
        self.assertEqual(val["leave_one_race_out"]["folds"], 4)
        self.assertEqual(val["leave_one_day_out"]["folds"], 2)
        self.assertGreater(val["leave_one_day_out"]["sog_rmse_kt"], val["leave_one_race_out"]["sog_rmse_kt"])

        # Team residuals distinguish TEAM_A > TEAM_B and carry bounded 95% bootstrap confidence intervals
        by_team = {row["team_code"]: row for row in model["team_residuals"]}
        res_a = by_team["TEAM_A"]["lodo_sog_residual_kt"]
        res_b = by_team["TEAM_B"]["lodo_sog_residual_kt"]
        assert res_a is not None and res_b is not None
        self.assertGreater(res_a["value"], res_b["value"])
        self.assertLessEqual(res_a["ci_low_kt"], res_a["value"])
        self.assertLessEqual(res_a["value"], res_a["ci_high_kt"])

        # Curves export p90 >= p50
        for pts in (b["points"] for lst in model["curves"].values() for b in lst):
            for pt in pts:
                self.assertGreaterEqual(pt["p90_sog_kt"], pt["p50_sog_kt"])

        # Deterministic repeat run
        model_repeat = refresh_archive_polar_models(copy.deepcopy(details))
        self.assertEqual(
            json.dumps(model, sort_keys=True),
            json.dumps(model_repeat, sort_keys=True),
        )

    def test_live_archive_polar_contract_when_present(self):
        index_path = Path(__file__).resolve().parents[2] / "public/data/analysis/index.json"
        if not index_path.is_file():
            self.skipTest("public/data/analysis/index.json is excluded from git; skipping live polar check")
        index_doc = json.loads(index_path.read_text(encoding="utf-8"))
        model = index_doc.get("polar_model")
        if model is None:
            self.skipTest("polar_model not yet refreshed on local archive")
        self.assertEqual(model["method_version"], POLAR_METHOD_VERSION)
        val = model["validation"]
        self.assertLess(val["leave_one_day_out"]["sog_rmse_kt"], val["baseline_mode_only"]["sog_rmse_kt"])
        self.assertLess(val["leave_one_race_out"]["sog_rmse_kt"], val["leave_one_day_out"]["sog_rmse_kt"])
        self.assertGreater(val["leave_one_day_out"]["sog_r2"], 0.70)


if __name__ == "__main__":
    unittest.main()
