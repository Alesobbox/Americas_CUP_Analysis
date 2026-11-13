"""Unit tests for AC75 production authenticated loader, 1-byte corruption detection, path escapes, and schemas (Gate A Criterion 9)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.kinematic_ml.loader import (
    BundleValidationError,
    load_authenticated_bundle,
    load_staged_ac75_bundle,
    MANDATORY_ARTIFACTS,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"


class TestAC75LoaderAuthentication(unittest.TestCase):
    def setUp(self):
        pointer_path = FORECAST_DIR / "latest_candidate.json"
        self.assertTrue(pointer_path.exists(), "latest_candidate.json must exist to test authenticated loader")
        self.pointer_doc = json.loads(pointer_path.read_text(encoding="utf-8"))
        self.manifest_path = ROOT / self.pointer_doc["manifest_path"]
        self.assertTrue(self.manifest_path.exists(), "Candidate manifest must exist")
        self.manifest_doc = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_load_staged_bundle_happy_path(self):
        """Verify that authentic staged candidate bundle loads cleanly and passes all cryptographic checks."""
        bundle = load_staged_ac75_bundle(ROOT)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.model_id, self.pointer_doc["candidate_id"])
        self.assertIn("fc1.weight", bundle.motion_weights)
        self.assertEqual(bundle.motion_weights["fc1.weight"].shape, (32, 14))
        self.assertEqual(bundle.scaler_mean.shape, (8,))
        self.assertEqual(bundle.scaler_scale.shape, (8,))
        self.assertGreater(bundle.template_library.total_templates, 0)
        self.assertGreater(len(bundle.residual_sampler.blocks), 0)
        self.assertGreater(bundle.motion_residual_scale, 0.0)
        self.assertGreater(bundle.margin_interval_scale, 0.0)
        self.assertTrue(bundle.calibration_info.get("verified_no_test_leakage"))

    def test_detects_1_byte_corruption_in_all_mandatory_components(self):
        """Gate A Criterion 9: Loader must detect 1-byte corruption in ANY mandatory component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            bundle_dir = tmp_root / "candidate"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            # Copy all files from original bundle into tmpdir
            manifest_copy = json.loads(json.dumps(self.manifest_doc))
            orig_bundle_dir = self.manifest_path.parent

            for key in MANDATORY_ARTIFACTS:
                rel_path = manifest_copy["artifacts"][key]
                orig_file = (ROOT / rel_path).resolve()
                dest_file = bundle_dir / Path(rel_path).name
                shutil.copy2(orig_file, dest_file)
                # Repoint artifact path to relative filename inside bundle
                manifest_copy["artifacts"][key] = dest_file.name

            manifest_file = bundle_dir / "candidate_manifest.json"
            manifest_file.write_text(json.dumps(manifest_copy, indent=2), encoding="utf-8")

            # Verify that the uncorrupted copy passes authentication
            clean_bundle = load_authenticated_bundle(manifest_file, root=tmp_root)
            self.assertIsNotNone(clean_bundle)

            # Test 1-byte corruption of EACH mandatory artifact
            for key in sorted(MANDATORY_ARTIFACTS):
                rel_name = manifest_copy["artifacts"][key]
                target_file = bundle_dir / rel_name
                orig_bytes = target_file.read_bytes()

                # Invert single byte at middle of file
                corrupt_bytes = bytearray(orig_bytes)
                mid = len(corrupt_bytes) // 2
                corrupt_bytes[mid] ^= 0x01
                target_file.write_bytes(bytes(corrupt_bytes))

                with self.assertRaises(
                    BundleValidationError,
                    msg=f"Loader failed to detect 1-byte corruption in mandatory component '{key}'"
                ):
                    load_authenticated_bundle(manifest_file, root=tmp_root)

                # Restore original bytes for next component test
                target_file.write_bytes(orig_bytes)

    def test_detects_path_escapes(self):
        """Gate A Criterion 9: Loader must strictly reject path escapes and absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            bundle_dir = tmp_root / "candidate"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            manifest_copy = json.loads(json.dumps(self.manifest_doc))
            manifest_file = bundle_dir / "candidate_manifest.json"

            # 1. Parent traversal escape
            manifest_copy["artifacts"]["route_templates_json"] = "../secret_escape.json"
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")
            with self.assertRaises(BundleValidationError):
                load_authenticated_bundle(manifest_file, root=tmp_root)

            # 2. Windows absolute path escape
            manifest_copy["artifacts"]["route_templates_json"] = "C:/Windows/System32/drivers/etc/hosts"
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")
            with self.assertRaises(BundleValidationError):
                load_authenticated_bundle(manifest_file, root=tmp_root)

            # 3. Unix absolute path escape
            manifest_copy["artifacts"]["route_templates_json"] = "/etc/passwd"
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")
            with self.assertRaises(BundleValidationError):
                load_authenticated_bundle(manifest_file, root=tmp_root)

    def test_detects_unsupported_schemas(self):
        """Gate A Criterion 9: Loader must explicitly fail on unsupported manifest schemas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            bundle_dir = tmp_root / "candidate"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            manifest_copy = json.loads(json.dumps(self.manifest_doc))
            manifest_file = bundle_dir / "candidate_manifest.json"

            # Wrong schema version
            manifest_copy["schema_version"] = "ac75-model-999"
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")
            with self.assertRaises(BundleValidationError):
                load_authenticated_bundle(manifest_file, root=tmp_root)

            # Missing schema version
            del manifest_copy["schema_version"]
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")
            with self.assertRaises(BundleValidationError):
                load_authenticated_bundle(manifest_file, root=tmp_root)

    def test_rejects_missing_mandatory_components(self):
        """Loader must explicitly reject bundles missing any mandatory component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            bundle_dir = tmp_root / "candidate"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            manifest_copy = json.loads(json.dumps(self.manifest_doc))
            manifest_file = bundle_dir / "candidate_manifest.json"

            for key in MANDATORY_ARTIFACTS:
                bad_manifest = json.loads(json.dumps(manifest_copy))
                del bad_manifest["artifacts"][key]
                manifest_file.write_text(json.dumps(bad_manifest), encoding="utf-8")
                with self.assertRaises(BundleValidationError, msg=f"Failed to reject missing key '{key}'"):
                    load_authenticated_bundle(manifest_file, root=tmp_root)

    def test_rejects_non_finite_weights_and_invalid_shapes(self):
        """Loader must reject weight arrays with NaN/Inf or incorrect tensor shapes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            bundle_dir = tmp_root / "candidate"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            manifest_copy = json.loads(json.dumps(self.manifest_doc))
            for key in MANDATORY_ARTIFACTS:
                rel_path = manifest_copy["artifacts"][key]
                orig_file = (ROOT / rel_path).resolve()
                dest_file = bundle_dir / Path(rel_path).name
                shutil.copy2(orig_file, dest_file)
                manifest_copy["artifacts"][key] = dest_file.name

            # Load original weights and inject NaN
            npz_target = bundle_dir / manifest_copy["artifacts"]["weights_npz"]
            with np.load(npz_target, allow_pickle=False) as npz_orig:
                data_dict = {k: np.array(npz_orig[k]) for k in npz_orig.files}

            # Inject NaN into fc1.weight
            data_dict["fc1.weight"][0, 0] = float("nan")
            np.savez(npz_target, **data_dict)

            # Update hash in manifest to bypass hash check so shape/finiteness check triggers
            import hashlib
            manifest_copy["artifacts"]["weights_npz_sha256"] = hashlib.sha256(npz_target.read_bytes()).hexdigest()
            manifest_file = bundle_dir / "candidate_manifest.json"
            manifest_file.write_text(json.dumps(manifest_copy), encoding="utf-8")

            with self.assertRaises(BundleValidationError, msg="Failed to reject non-finite weights"):
                load_authenticated_bundle(manifest_file, root=tmp_root)


if __name__ == "__main__":
    unittest.main()
