"""Offline environment acquisition tests; no provider requests in verification."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.environment import (build_archive, build_race, catalog_metadata, fetch_bytes,
                                  parse_response, replay_metadata, request_url, validate_metadata, verify_archive)


START = int(datetime(2026, 9, 22, 12, tzinfo=timezone.utc).timestamp())
METADATA = {"race_id": "test_race", "latitude": 40.81, "longitude": 14.25,
            "start_date": "2026-09-22", "end_date": "2026-09-22",
            "window_start_ms": START * 1000, "window_end_ms": (START + 1800) * 1000}


def response(source="air", *, times=None):
    times = times or [START, START + 3600]
    units = {"time": "unixtime"}
    hourly = {"time": times}
    if source == "air":
        units["temperature_2m"] = "°C"
        hourly["temperature_2m"] = [25.5, None]
    else:
        units.update(wave_height="m", sea_surface_temperature="°C")
        hourly.update(wave_height=[0.3, None], sea_surface_temperature=[26.0, 26.1])
    return {"latitude": 40.8, "longitude": 14.3, "utc_offset_seconds": 0,
            "hourly_units": units, "hourly": hourly}


def raw(source):
    return json.dumps(response(source)).encode()


def fetch_fixture(url, timeout):
    return raw("marine" if "marine-api" in url else "air")


def replay():
    return {"id": "test_race", "date": "misleading-date",
            "course": {"origin": {"lat": 40.81, "lon": 14.25}},
            "chronology": {"window_start": START * 1000, "window_end": (START + 1800) * 1000},
            "telemetry": {"timestamps": [START * 1000]}}


class EnvironmentTests(unittest.TestCase):
    def test_exact_origin_and_utc_window_override_catalog_name(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            path.write_text(json.dumps(replay()))
            metadata = replay_metadata(path)
            self.assertEqual(metadata, METADATA)
            url = request_url("marine", metadata)
            self.assertIn("start_date=2026-09-22", url)
            self.assertIn("latitude=40.81", url)
            self.assertIn("cell_selection=sea", url)
            self.assertIn("timeformat=unixtime", url)

    def test_cross_midnight_uses_both_dates_and_rejects_invalid_location_window(self):
        source = replay()
        source["chronology"]["window_end"] = (START + 13 * 3600) * 1000
        self.assertEqual(validate_metadata(source)["end_date"], "2026-09-23")
        for bad in (float("nan"), True, 95):
            source = replay()
            source["course"]["origin"]["lat"] = bad
            with self.assertRaises(ValueError):
                validate_metadata(source)

    def test_metadata_stops_before_telemetry_and_has_a_bounded_prefix(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            content = json.dumps(replay()).split('"telemetry"')[0] + '"telemetry": [INVALID UNREAD CONTENT'
            path.write_text(content)
            self.assertEqual(replay_metadata(path), METADATA)
            path.write_text('{"padding":"' + "x" * (1024 * 1024) + '","course":{}}')
            with self.assertRaisesRegex(ValueError, "bounded prefix"):
                replay_metadata(path)

    def test_nulls_and_missing_provider_hours_remain_aligned(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def different_hours(url, timeout):
                body = response("marine" if "marine-api" in url else "air")
                if "marine-api" in url:
                    body["hourly"]["time"] = [START + 3600, START + 7200]
                return json.dumps(body).encode()
            artifact = build_race(METADATA, root / "public", root / "cache", fetcher=different_hours)
            self.assertEqual(artifact["hourly"]["time_ms"], [START * 1000, (START + 3600) * 1000, (START + 7200) * 1000])
            self.assertEqual(artifact["hourly"]["air_temperature_c"], [25.5, None, None])
            self.assertEqual(artifact["hourly"]["wave_height_m"], [None, 0.3, None])
            self.assertEqual(artifact["hourly"]["water_temperature_c"], [None, 26.0, 26.1])
            self.assertEqual(artifact["context"], "historical_replay_only")

    def test_partial_failure_preserves_other_source_and_exact_response_provenance(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def partial(url, timeout):
                if "marine-api" in url:
                    raise ValueError("HTTP 503")
                return raw("air")
            artifact = build_race(METADATA, root / "public", root / "cache", fetcher=partial,
                                  clock=lambda: "2026-10-16T12:00:00Z")
            self.assertEqual(artifact["hourly"]["air_temperature_c"], [25.5, None])
            self.assertEqual(artifact["hourly"]["wave_height_m"], [None, None])
            self.assertNotIn("marine", artifact["sources"])
            self.assertEqual(artifact["errors"], {"marine": "HTTP 503"})
            source = artifact["sources"]["air"]
            data = (root / "public" / source["response_file"]).read_bytes()
            self.assertEqual(data, raw("air"))
            self.assertEqual(hashlib.sha256(data).hexdigest(), source["response_sha256"])
            self.assertEqual(source["retrieved_at"], "2026-10-16T12:00:00Z")
            self.assertEqual(source["grid_location"], {"latitude": 40.8, "longitude": 14.3})

    def test_cache_reuse_is_offline_and_detects_modified_raw_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = build_race(METADATA, root / "public", root / "cache", fetcher=fetch_fixture)
            def forbidden(*args, **kwargs):
                self.fail("Verified cache must not call the network")
            again = build_race(METADATA, root / "public", root / "cache", fetcher=forbidden)
            self.assertEqual(first, again)
            (root / "public" / first["sources"]["marine"]["response_file"]).write_bytes(b'{}')
            artifact = build_race(METADATA, root / "public", root / "cache", fetcher=forbidden)
            self.assertIn("hash mismatch", artifact["errors"]["marine"])
            self.assertEqual(artifact["hourly"]["air_temperature_c"], [25.5, None])

    def test_response_validation_units_alignment_timezone_and_finite_values(self):
        variants = []
        body = response(); body["hourly_units"]["temperature_2m"] = "°F"; variants.append(body)
        body = response(); body["hourly"]["temperature_2m"] = [2]; variants.append(body)
        body = response(); body["hourly"]["temperature_2m"] = [True, 2]; variants.append(body)
        body = response(); body["hourly"]["temperature_2m"] = [float("nan"), 2]; variants.append(body)
        body = response(); body["utc_offset_seconds"] = 3600; variants.append(body)
        body = response(); body["hourly"]["time"] = [START, START]; variants.append(body)
        body = response(); body["hourly"]["time"] = [START + 1, START + 3600]; variants.append(body)
        body = response(); body["hourly"]["time"] = [START, START + 86400]; variants.append(body)
        body = response(); body["hourly"]["time"] = [str(START), START + 3600]; variants.append(body)
        for body in variants:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_response(json.dumps(body).encode(), "air", METADATA)
        with self.assertRaisesRegex(ValueError, "provider error"):
            parse_response(b'{"error":true,"reason":"Unsupported date"}', "air", METADATA)
        with self.assertRaisesRegex(ValueError, "malformed JSON"):
            parse_response(b'<html>not JSON</html>', "air", METADATA)
        body = response("marine"); body["hourly"]["wave_height"][0] = -1
        with self.assertRaisesRegex(ValueError, "Invalid finite"):
            parse_response(json.dumps(body).encode(), "marine", METADATA)

    def test_http_response_requires_json_and_size_limit(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "text/html"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b"x" * limit
        with patch("pipeline.environment.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(ValueError, "not JSON"):
                fetch_bytes("https://example.test")
            FakeResponse.headers = {"Content-Type": "application/json"}
            with self.assertRaisesRegex(ValueError, "size limit"):
                fetch_bytes("https://example.test")

    def test_catalog_path_confinement_and_complete_offline_build(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "public" / "data"
            (data / "replays").mkdir(parents=True)
            (data / "replays" / "test_race.json").write_text(json.dumps(replay()))
            manifest = {"races": [{"id": "test_race", "file": "replays/test_race.json"}]}
            (data / "manifests.json").write_text(json.dumps(manifest))
            summary = build_archive(root, fetcher=fetch_fixture)
            self.assertEqual(summary["races"], 1)
            self.assertEqual(summary["races_with_available_field"], {
                "air_temperature_c": 1, "wave_height_m": 1, "water_temperature_c": 1})
            self.assertEqual(verify_archive(root)["status"], "pass")
            artifact_path = data / "environment" / "test_race.json"
            artifact = json.loads(artifact_path.read_bytes())
            artifact["hourly"]["air_temperature_c"][1] = 0
            artifact_path.write_text(json.dumps(artifact))
            with self.assertRaisesRegex(ValueError, "differ from original"):
                verify_archive(root)
            build_archive(root, fetcher=fetch_fixture)
            artifact = json.loads(artifact_path.read_bytes())
            raw_path = data / "environment" / artifact["sources"]["air"]["response_file"]
            raw_path.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_archive(root)
            manifest["races"][0]["file"] = "../outside.json"
            (data / "manifests.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "remain within"):
                list(catalog_metadata(root))


if __name__ == "__main__":
    unittest.main()
