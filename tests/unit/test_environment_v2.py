"""Offline unit tests for Packets 1-4 of the environment-2 pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from typing import Any
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from pipeline.env.cache import acquire_all_tasks, plan_acquisition_tasks, verify_cache_offline
from pipeline.env.contracts import (
    CALM_WAVE_HS_THRESHOLD_M,
    SLACK_CURRENT_SPEED_MPS,
    bearing_from_to_towards_deg,
    build_channel_provenance,
    kelvin_to_celsius,
    read_environment_artifact,
    uv_to_speed_dir_towards,
    validate_environment_v2,
)
from pipeline.env.exporter import export_all_environments
from pipeline.env.inventory import build_environment_inventory
from pipeline.env.providers import expand_bbox, open_meteo_request_url, split_request_if_oversize
from pipeline.env.registry import PROVIDER_SPECS, REJECTED_SOURCES
from pipeline.env.sampler import CachedGridField, _load_netcdf_chunk, sample_point
from pipeline.env.session_sampling import FieldSamplerCache, sample_track_points
from pipeline.kinematic_ml.inventory import build_source_inventory
from pipeline.prediction.ac38_inventory import build_inventory as build_ac38_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_nc_bytes(
    *,
    lats: list[float],
    lons: list[float],
    times_iso: list[str],
    data_vars: dict[str, np.ndarray],
    units: dict[str, str] | None = None,
    depth: list[float] | None = None,
) -> bytes:
    times = np.asarray([np.datetime64(t.replace("Z", "")) for t in times_iso])
    coords: dict[str, Any] = {"time": times, "latitude": np.asarray(lats, dtype=float), "longitude": np.asarray(lons, dtype=float)}
    dims = ("time", "latitude", "longitude")
    if depth is not None:
        coords["depth"] = np.asarray(depth, dtype=float)
        dims = ("time", "depth", "latitude", "longitude")
    ds_vars: dict[str, Any] = {}
    for name, arr in data_vars.items():
        attrs = {"units": units[name]} if units and name in units else {}
        ds_vars[name] = (dims, arr, attrs)
    ds = xr.Dataset(ds_vars, coords=coords)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sub.nc"
        try:
            ds.to_netcdf(p, engine="scipy")
        except Exception:
            ds.to_netcdf(p, engine="h5netcdf")
        return p.read_bytes()


class TestEnvironmentPacket1Reconciliation(unittest.TestCase):
    def test_ac75_inventory_classifies_ac38_and_removes_binary_double_count(self) -> None:
        src_inv = build_source_inventory()
        breakdown = src_inv["breakdown"]
        self.assertEqual(breakdown.get("unknown (excluded)", 0), 0)
        self.assertEqual(breakdown.get("ac38_ac40_replay_archive (excluded)", 0), 28)

        ac38_inv = build_ac38_inventory(REPO_ROOT, write=False)
        ac75_counts = ac38_inv["domains"]["ac37_ac75"]
        tb = ac75_counts["telemetry_breakdown"]
        self.assertEqual(ac75_counts["telemetry_windows_total"], 115)
        self.assertEqual(tb["competitive_attempts_jsonl"], 59)
        self.assertEqual(tb["official_practice_jsonl"], 41)
        self.assertEqual(tb["semifinal_binary_ac37"], 15)

    def test_reconciled_env_inventory_160_sources_and_result_only_distinction(self) -> None:
        inv = build_environment_inventory(REPO_ROOT, write=False)
        c = inv["counts"]
        self.assertEqual(c["raw_source_files"], 160)
        self.assertEqual(c["ac38_ac40_files"], 28)
        self.assertEqual(c["ac37_ac40_files"], 17)
        self.assertEqual(c["ac37_ac75_jsonl_files"], 100)
        self.assertEqual(c["ac37_ac75_binary_files"], 15)
        self.assertEqual(c["unique_sessions"], 145)
        self.assertEqual(c["attempts"], 160)
        self.assertEqual(c["canonical_families"], 159)
        self.assertEqual(c["boat_races_from_telemetry"], 539)
        self.assertEqual(c["result_only_with_binary_raw_file_records"], 15)
        self.assertEqual(c["result_only_without_raw_file_records"], 18)
        self.assertEqual(c["by_acquisition_status"].get("ready"), 145)
        self.assertEqual(c["by_acquisition_status"].get("excluded_unsupported_wire_schema"), 15)
        for rec in inv["result_only_records"]:
            if not rec["has_raw_file"]:
                self.assertEqual(rec["acquisition_status"], "excluded_missing_location_time")


class TestEnvironmentPacket2Contracts(unittest.TestCase):
    def test_vector_conventions_thresholds_and_v1_reader(self) -> None:
        spd, d_tw = uv_to_speed_dir_towards(0.0, 1.0)
        self.assertAlmostEqual(spd or 0.0, 1.0)
        self.assertAlmostEqual(d_tw or 0.0, 0.0)
        spd_e, d_e = uv_to_speed_dir_towards(1.0, 0.0)
        self.assertAlmostEqual(spd_e or 0.0, 1.0)
        self.assertAlmostEqual(d_e or 0.0, 90.0)
        spd_slack, d_slack = uv_to_speed_dir_towards(SLACK_CURRENT_SPEED_MPS * 0.5, 0.0)
        self.assertLess(spd_slack or 1.0, SLACK_CURRENT_SPEED_MPS)
        self.assertIsNone(d_slack)
        self.assertAlmostEqual(bearing_from_to_towards_deg(270.0) or 0.0, 90.0)
        self.assertAlmostEqual(kelvin_to_celsius(293.15), 20.0)
        self.assertIn("parthenope_rms3_currents", REJECTED_SOURCES)

        v1_doc = {
            "schema_version": "environment-1",
            "race_id": "test_v1",
            "hourly": {"time_ms": [1700000000000], "air_temperature_c": [21.5], "wave_height_m": [0.8], "water_temperature_c": [19.0]},
        }
        norm_v1 = read_environment_artifact(v1_doc)
        self.assertEqual(norm_v1["native_schema_version"], "environment-1")
        self.assertEqual(norm_v1["course_centre"]["wave_height_m"], [0.8])
        self.assertEqual(norm_v1["course_centre"]["wave_period_s"], [None])

    def test_v2_validator_rejects_calm_wave_direction(self) -> None:
        prov = {
            ch: build_channel_provenance(
                channel=ch, provider="Test", provider_id="test", dataset="ds", dataset_version="v1",
                variables=["x"], native_spatial_support={}, native_temporal_support="hourly_instantaneous",
                averaging_bounds={}, depth_m=None, temperature_convention=None, units={"x": "m"},
                mask_handling="test", interpolation="bilinear", quality_status="available",
                request_spec={}, returned_coordinates={}, retrieval_time_utc="2026-01-01T00:00:00Z",
                raw_subset_sha256="a" * 64, metadata_sha256="b" * 64, valid_time_bounds={},
            )
            for ch in ("currents", "waves", "air_temperature", "water_temperature")
        }
        bad = {
            "schema_version": "environment-2",
            "race_id": "r1",
            "context": "historical_replay_only",
            "registry_version": "env-registry-1",
            "location": {"latitude": 40.8, "longitude": 14.2},
            "window": {"start_ms": 1700000000000, "end_ms": 1700003600000},
            "channels": prov,
            "course_centre": {
                "time_ms": [1700000000000],
                "current_u_mps": [0.1], "current_v_mps": [0.0],
                "current_speed_mps": [0.1], "current_dir_towards_deg": [90.0],
                "wave_height_m": [CALM_WAVE_HS_THRESHOLD_M * 0.5],
                "wave_period_s": [4.0], "wave_dir_from_deg": [180.0],
                "air_temperature_c": [22.0], "water_temperature_c": [21.0],
            },
        }
        with self.assertRaises(ValueError):
            validate_environment_v2(bad)


class TestEnvironmentPacket3Acquisition(unittest.TestCase):
    def test_dotenv_loading_and_copernicus_credential_check(self) -> None:
        import os
        from pipeline.env.adapters_grid import _parse_env_file, has_copernicus_credentials
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / ".env"
            env_file.write_text("COPERNICUSMARINE_SERVICE_USERNAME=test_user\nCOPERNICUSMARINE_SERVICE_PASSWORD=test_pw\n", encoding="utf-8")
            orig_u = os.environ.pop("COPERNICUSMARINE_SERVICE_USERNAME", None)
            orig_p = os.environ.pop("COPERNICUSMARINE_SERVICE_PASSWORD", None)
            try:
                _parse_env_file(env_file)
                self.assertEqual(os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME"), "test_user")
                self.assertEqual(os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD"), "test_pw")
                self.assertTrue(has_copernicus_credentials())
            finally:
                if orig_u:
                    os.environ["COPERNICUSMARINE_SERVICE_USERNAME"] = orig_u
                else:
                    os.environ.pop("COPERNICUSMARINE_SERVICE_USERNAME", None)
                if orig_p:
                    os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"] = orig_p
                else:
                    os.environ.pop("COPERNICUSMARINE_SERVICE_PASSWORD", None)

    def test_bbox_expansion_dedup_splitting_retries_fallback_and_tamper(self) -> None:
        bb = {"lat_min": 40.8, "lat_max": 40.82, "lon_min": 14.2, "lon_max": 14.22}
        exp = expand_bbox(bb, 0.05, cells=2)
        self.assertAlmostEqual(exp["lat_min"], 40.7)
        self.assertAlmostEqual(exp["lat_max"], 40.92)

        spec = PROVIDER_SPECS["copernicus_med_currents"]
        url = open_meteo_request_url(PROVIDER_SPECS["open_meteo_icon_2i"], {"variables": ["temperature_2m"], "bbox": bb, "start_ms": 1789988400000, "end_ms": 1789992000000})
        self.assertIn("models=italia_meteo_arpae_icon_2i", url)
        self.assertNotIn("best_match", url)

        big_req = {"variables": ["uo", "vo"], "bbox": {"lat_min": 35.0, "lat_max": 45.0, "lon_min": 5.0, "lon_max": 20.0}, "start_ms": 1700000000000, "end_ms": 1700000000000 + 20 * 86_400_000}
        splits = split_request_if_oversize(spec, big_req, max_bytes=1_000_000)
        self.assertGreater(len(splits), 1)
        one_step_req = {"variables": ["uo", "vo"], "bbox": bb, "start_ms": 1700000000000, "end_ms": 1700003600000}
        var_splits = split_request_if_oversize(spec, one_step_req, max_bytes=100, est_bytes=200)
        self.assertEqual([r["variables"] for r in var_splits], [["uo"], ["vo"]])

        # Overlapping sessions deduplicate to 1 task per variable group, with retry & fallback
        t0 = int(datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
        inv = {
            "sources": [
                {"race_id": "nap_1", "venue_id": "naples", "utc_date": "2026-09-22", "acquisition_status": "ready", "window_start_ms": t0, "window_end_ms": t0 + 1800_000, "bbox": {**bb, "center_lat": 40.81, "center_lon": 14.21}},
                {"race_id": "nap_2", "venue_id": "naples", "utc_date": "2026-09-22", "acquisition_status": "ready", "window_start_ms": t0 + 600_000, "window_end_ms": t0 + 2400_000, "bbox": {**bb, "center_lat": 40.81, "center_lon": 14.21}},
            ]
        }
        tasks = plan_acquisition_tasks(inv)
        self.assertEqual(len(tasks), 4)
        self.assertEqual(tasks[0]["covered_races"], ["nap_1", "nap_2"])

        calls: dict[str, int] = {"wrf5": 0, "ww33": 0, "rms3": 0, "icon": 0}
        wrf_nc = _make_nc_bytes(
            lats=[40.78, 40.81, 40.84], lons=[14.18, 14.21, 14.24],
            times_iso=["2026-09-22T12:00:00Z"],
            data_vars={"T2C": np.full((1, 3, 3), 24.5)}, units={"T2C": "degC"},
        )
        rms_nc = _make_nc_bytes(
            lats=[40.78, 40.81, 40.84], lons=[14.18, 14.21, 14.24],
            times_iso=["2026-09-22T12:00:00Z"], depth=[3.166, 5.5],
            data_vars={"tempSurface": np.full((1, 2, 3, 3), 296.15)}, units={"tempSurface": "Kelvin"},
        )
        icon_json = json.dumps({
            "latitude": 40.81, "longitude": 14.21, "utc_offset_seconds": 0,
            "hourly_units": {"time": "unixtime", "temperature_2m": "°C"},
            "hourly": {"time": [int(t0 // 1000) + h * 3600 for h in range(-1, 3)], "temperature_2m": [23.0, 23.5, 24.0, 24.5]},
        }).encode("utf-8")

        def fake_http(req_url: str, _timeout: float) -> tuple[int, bytes, dict[str, str]]:
            if "wrf5" in req_url:
                calls["wrf5"] += 1
                return 503, b"unavailable", {}
            if "ww33" in req_url:
                calls["ww33"] += 1
                if ".dds" in req_url:
                    return 200, b"Dataset { Grid { Float32 hs[time = 1][latitude = 3][longitude = 3]; } hs; } ww33;", {}
                return 200, _make_nc_bytes(
                    lats=[40.78, 40.81, 40.84], lons=[14.18, 14.21, 14.24],
                    times_iso=["2026-09-22T12:00:00Z"],
                    data_vars={"hs": np.full((1, 3, 3), 0.7), "period": np.full((1, 3, 3), 5.2), "dir": np.full((1, 3, 3), 210.0)},
                ), {}
            if "rms3" in req_url:
                calls["rms3"] += 1
                if ".dds" in req_url:
                    return 200, b"Dataset { Grid { Float32 depth[depth = 2]; } rms3;", {}
                return 200, rms_nc, {}
            calls["icon"] += 1
            return 200, icon_json, {}

        class FakeCopernicus:
            def open_dataset(self, **kwargs: Any) -> xr.Dataset:
                vars_l = kwargs["variables"]
                ds_vars = {vn: (("time", "depth", "latitude", "longitude"), np.full((4, 1, 3, 3), 0.25)) for vn in vars_l}
                return xr.Dataset(
                    ds_vars,
                    coords={
                        "time": np.asarray([np.datetime64(f"2026-09-22T{h:02d}:30:00") for h in range(11, 15)]),
                        "depth": np.asarray([1.018]),
                        "latitude": np.asarray([40.76, 40.81, 40.86]),
                        "longitude": np.asarray([14.16, 14.21, 14.26]),
                    },
                )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = acquire_all_tasks(root, inv, max_workers=1, http_get=fake_http, copernicus_client=FakeCopernicus(), sleep_fn=lambda _s: None)
            self.assertEqual(calls["wrf5"], 3)
            air_task = [t for t in manifest["tasks"] if t["group"] == "air_temperature"][0]
            self.assertEqual(air_task["status"], "fallback")
            self.assertEqual(air_task["selected_provider_id"], "open_meteo_icon_2i")
            self.assertIn("parthenope_naples_wrf", air_task["fallback_reason"])
            self.assertEqual(verify_cache_offline(root)["status"], "pass")

            # Tamper cached object and verify failure
            obj_p = root / ".forecast" / "environment" / "cache" / air_task["chunks"][0]["object_relpath"]
            obj_p.write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                verify_cache_offline(root)


class TestEnvironmentPacket4SamplingAndExport(unittest.TestCase):
    def test_spatial_barrier_circular_wave_daily_bounds_and_parity(self) -> None:
        t0 = int(datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
        t1 = t0 + 3_600_000
        # 2x2 grid where one corner is dry, leaving nearest-wet vs diagonal barrier
        lats = np.asarray([40.80, 40.82])
        lons = np.asarray([14.20, 14.22])
        u = np.asarray([[[0.2, np.nan], [0.4, 0.6]]])
        v = np.asarray([[[0.0, np.nan], [0.0, 0.0]]])
        cur_f = CachedGridField(lats=lats, lons=lons, times_ms=np.asarray([t0]), arrays={"uo": u, "vo": v}, temporal_support="hourly_mean", native_step_s=3600, depth_m=1.0, temperature_convention=None)

        # Near dry corner (0,1), adjacent wet cells (0,0) and (1,1) are wet so no barrier -> nearest wet cell picked with dist > 0
        s_near = sample_point({"currents": cur_f}, {"currents": ("uo", "vo")}, 40.802, 14.219, t0 + 100)
        self.assertIsNotNone(s_near["current_u_mps"])
        self.assertEqual(s_near["_meta"]["currents"]["method"], "nearest_wet_1cell")
        self.assertGreater(s_near["_meta"]["currents"]["distance_m"], 0.0)

        # Diagonal land barrier: only (0,0) wet; (0,1), (1,0), (1,1) all NaN while query is near (1,1)
        u_bar = np.asarray([[[0.5, np.nan], [np.nan, np.nan]]])
        bar_f = CachedGridField(lats=lats, lons=lons, times_ms=np.asarray([t0]), arrays={"uo": u_bar, "vo": u_bar}, temporal_support="hourly_mean", native_step_s=3600, depth_m=1.0, temperature_convention=None)
        s_bar = sample_point({"currents": bar_f}, {"currents": ("uo", "vo")}, 40.819, 14.219, t0)
        self.assertIsNone(s_bar["current_u_mps"])
        self.assertEqual(s_bar["_meta"]["currents"]["status"], "unavailable_land_barrier")

        # Circular wave wrap: 350 deg and 10 deg -> 0 deg
        hs = np.full((2, 2, 2), 0.8)
        per = np.full((2, 2, 2), 6.0)
        wdir = np.asarray([[[350.0, 10.0], [350.0, 10.0]], [[350.0, 10.0], [350.0, 10.0]]])
        wav_f = CachedGridField(lats=lats, lons=lons, times_ms=np.asarray([t0, t1]), arrays={"hs": hs, "period": per, "dir": wdir}, temporal_support="hourly_instantaneous", native_step_s=3600, depth_m=None, temperature_convention=None)
        sw = sample_point({"waves": wav_f}, {"waves": ("hs", "period", "dir")}, 40.81, 14.21, t0 + 1800_000)
        self.assertAlmostEqual(sw["wave_dir_from_deg"] or 99.0, 0.0, places=4)

        # Daily mean water temp Kelvin -> Celsius & does not cross day boundary
        wt_nc = _make_nc_bytes(
            lats=[40.80, 40.82], lons=[14.20, 14.22],
            times_iso=["2026-09-22T12:00:00Z"],
            data_vars={"thetao": np.full((1, 2, 2), 298.15)}, units={"thetao": "K"},
        )
        with tempfile.TemporaryDirectory() as td_wt:
            wt_p = Path(td_wt) / "wt.nc"
            wt_p.write_bytes(wt_nc)
            wt_f = _load_netcdf_chunk(wt_p, {"depth_m": 1.018, "temperature_convention": "potential"}, "daily_mean", 86400)
        air_f = CachedGridField(lats=lats, lons=lons, times_ms=np.asarray([t0, t1]), arrays={"T2C": np.full((2, 2, 2), 22.0)}, temporal_support="hourly_instantaneous", native_step_s=3600, depth_m=2.0, temperature_convention=None)

        s_next_day = sample_point({"water_temperature": wt_f}, {"water_temperature": ("thetao",)}, 40.81, 14.21, t0 + 86_400_000)
        self.assertIsNone(s_next_day["water_temperature_c"])

        # Batched sampler parity with sample_point
        var_map = {"currents": ("uo", "vo"), "waves": ("hs", "period", "dir"), "air_temperature": ("T2C",), "water_temperature": ("thetao",)}
        samplers = {
            "currents": FieldSamplerCache(cur_f, var_map["currents"]),
            "waves": FieldSamplerCache(wav_f, var_map["waves"]),
            "air_temperature": FieldSamplerCache(air_f, var_map["air_temperature"]),
            "water_temperature": FieldSamplerCache(wt_f, var_map["water_temperature"]),
        }
        q_t = np.asarray([t0 + 1800_000], dtype=np.int64)
        q_la = np.asarray([40.81], dtype=float)
        q_lo = np.asarray([14.21], dtype=float)
        batch_series, _ = sample_track_points(samplers, var_map, q_t, q_la, q_lo)
        ref = sample_point({"currents": cur_f, "waves": wav_f, "air_temperature": air_f, "water_temperature": wt_f}, var_map, 40.81, 14.21, t0 + 1800_000)
        self.assertAlmostEqual(batch_series["current_u_mps"][0], ref["current_u_mps"], places=4)
        self.assertAlmostEqual(batch_series["wave_dir_from_deg"][0], ref["wave_dir_from_deg"], places=2)
        self.assertAlmostEqual(batch_series["water_temperature_c"][0], ref["water_temperature_c"], places=3)

        # Full export_all_environments end-to-end offline on synthetic repo
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pq_p = root / "tracks.parquet"
            pq.write_table(pa.Table.from_pylist([{"asset_id": "boat_a", "timestamp_ms": t0 + 500_000, "lat_deg": 40.81, "lon_deg": 14.21}]), pq_p)
            env_dir = root / ".forecast" / "environment"
            env_dir.mkdir(parents=True, exist_ok=True)
            inv_doc = {
                "counts": {"ac37_ac75_binary_files": 0, "result_only_without_raw_file_records": 0},
                "sources": [{
                    "race_id": "r_pub", "venue_id": "naples", "utc_date": "2026-09-22",
                    "acquisition_status": "ready", "in_public_replay_catalog": True,
                    "domain": "competitive", "cycle": "ac38", "boat_class": "AC40",
                    "window_start_ms": t0, "window_end_ms": t0 + 1800_000, "gun_ms": t0 + 300_000,
                    "position_source": "tracks.parquet",
                    "bbox": {"lat_min": 40.80, "lat_max": 40.82, "lon_min": 14.20, "lon_max": 14.22, "center_lat": 40.81, "center_lon": 14.21},
                }],
            }
            (env_dir / "inventory.json").write_text(json.dumps(inv_doc), encoding="utf-8")

            def fake_all(spec_url: str, _t: float) -> tuple[int, bytes, dict[str, str]]:
                if ".dds" in spec_url:
                    return 200, b"Dataset { Grid { Float32 depth[depth = 2]; } d;", {}
                m_hr = re.search(r"20260922Z(\d{2})00", spec_url)
                t_iso = f"2026-09-22T{m_hr.group(1) if m_hr else '12'}:00:00Z"
                glats = [40.78, 40.80, 40.82, 40.84]
                glons = [14.18, 14.20, 14.22, 14.24]
                if "ww33" in spec_url:
                    return 200, _make_nc_bytes(lats=glats, lons=glons, times_iso=[t_iso], data_vars={"hs": np.full((1, 4, 4), 0.7), "period": np.full((1, 4, 4), 5.0), "dir": np.full((1, 4, 4), 200.0)}), {}
                if "wrf5" in spec_url:
                    return 200, _make_nc_bytes(lats=glats, lons=glons, times_iso=[t_iso], data_vars={"T2C": np.full((1, 4, 4), 24.0)}, units={"T2C": "degC"}), {}
                return 200, _make_nc_bytes(lats=glats, lons=glons, times_iso=[t_iso], depth=[3.1657, 5.5], data_vars={"tempSurface": np.full((1, 2, 4, 4), 298.15)}, units={"tempSurface": "K"}), {}

            class FakeCop:
                def open_dataset(self, **kwargs: Any) -> xr.Dataset:
                    ds_vars = {vn: (("time", "depth", "latitude", "longitude"), np.full((2, 1, 2, 2), 0.3)) for vn in kwargs["variables"]}
                    return xr.Dataset(ds_vars, coords={"time": np.asarray([np.datetime64("2026-09-22T12:30:00"), np.datetime64("2026-09-22T13:30:00")]), "depth": np.asarray([1.018]), "latitude": np.asarray([40.76, 40.86]), "longitude": np.asarray([14.16, 14.26])})

            acquire_all_tasks(root, inv_doc, max_workers=1, http_get=fake_all, copernicus_client=FakeCop(), sleep_fn=lambda _s: None)
            exp_sum = export_all_environments(root, verify_cache=True, write=True)
            self.assertEqual(exp_sum["public_replay_exports"], 1)
            pub_doc = json.loads((root / "public" / "data" / "environment" / "r_pub.json").read_text(encoding="utf-8"))
            self.assertEqual(pub_doc["channels"]["water_temperature"]["depth_m"], 3.1657)
            self.assertAlmostEqual(pub_doc["course_centre"]["water_temperature_c"][0], 25.0, places=2)
            boats_doc = json.loads((root / "public" / "data" / "environment" / "boats" / "r_pub.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(boats_doc["boats"]["boat_a"]["water_temperature_c"][0], 25.0, places=2)


if __name__ == "__main__":
    unittest.main()
