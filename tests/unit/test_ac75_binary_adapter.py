"""Focused unit tests for AC37 binary adapter and schema exclusions (T04)."""
import io
import unittest
from pathlib import Path

from pipeline.kinematic_ml.ac37_wire import (
    read_binary_frames,
    MalformedFrameError,
    UnsupportedWireSchemaError,
    has_verified_descriptor,
    decode_ac37_file,
    get_binary_coverage_exclusions,
)

ROOT = Path(__file__).resolve().parents[2]


class TestAC75BinaryAdapter(unittest.TestCase):
    def test_frame_reader_and_truncation_detection(self):
        """Verify 4-byte big-endian framing and exact offset truncation detection."""
        # 1. Valid stream of two frames: 'hello' (5 bytes), 'world!' (6 bytes)
        payload1 = b"hello"
        payload2 = b"world!"
        stream_bytes = (
            len(payload1).to_bytes(4, byteorder="big") + payload1 +
            len(payload2).to_bytes(4, byteorder="big") + payload2
        )
        frames = list(read_binary_frames(io.BytesIO(stream_bytes)))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].offset, 0)
        self.assertEqual(frames[0].length, 5)
        self.assertEqual(frames[0].payload, payload1)
        self.assertEqual(frames[1].offset, 9)
        self.assertEqual(frames[1].length, 6)
        self.assertEqual(frames[1].payload, payload2)

        # 2. Truncated prefix (e.g. only 2 bytes instead of 4)
        bad_prefix_stream = io.BytesIO(b"\x00\x05")
        with self.assertRaises(MalformedFrameError) as ctx:
            list(read_binary_frames(bad_prefix_stream))
        self.assertIn("Truncated frame prefix at byte offset 0", str(ctx.exception))

        # 3. Truncated payload (prefix says 10 bytes, only 4 provided)
        bad_payload_stream = io.BytesIO((10).to_bytes(4, byteorder="big") + b"four")
        with self.assertRaises(MalformedFrameError) as ctx:
            list(read_binary_frames(bad_payload_stream))
        self.assertIn("Truncated frame payload at byte offset 4", str(ctx.exception))

    def test_descriptor_dependency_and_fail_closed_exclusion(self):
        """Verify that missing .proto descriptor prevents guessed tag decoding and records exclusion."""
        self.assertFalse(has_verified_descriptor())

        # Calling decode on any real .ac37 file fails closed
        real_file = ROOT / "Data" / "AC37" / "ac75_lvc_semifinals_raw" / "24 09 14 BCN LVS Match 1 ITAvUSA.ac37"
        if real_file.exists():
            with self.assertRaises(UnsupportedWireSchemaError) as ctx:
                decode_ac37_file(real_file)
            self.assertIn("Authoritative AC37 Protobuf descriptor", str(ctx.exception))
            self.assertIn("Guessed numeric tag decoding is strictly prohibited", str(ctx.exception))

        # Coverage exclusions accurately record the 15 files
        exclusions = get_binary_coverage_exclusions()
        self.assertEqual(exclusions["status"], "complete_with_exclusions")
        self.assertEqual(exclusions["file_count"], 15)
        self.assertGreater(exclusions["total_bytes"], 1_000_000_000)
        self.assertEqual(len(exclusions["files"]), 15)


if __name__ == "__main__":
    unittest.main()
