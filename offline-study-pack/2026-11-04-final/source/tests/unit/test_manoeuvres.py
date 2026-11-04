"""Unit tests for tack and gybe manoeuvre detector."""

import math
import unittest

from pipeline.manoeuvres import (
    Manoeuvre,
    ManoeuvreDetector,
    circular_shortest_diff_deg,
    normalize_angle_180,
)


class TestAngularHelpers(unittest.TestCase):
    """Verifies angular math helpers for manoeuvre detection."""

    def test_circular_shortest_diff_angles(self):
        """Shortest signed angular difference respects wrapping across [-180, 180)."""
        self.assertAlmostEqual(circular_shortest_diff_deg(350.0, 10.0), 20.0, places=4)
        self.assertAlmostEqual(circular_shortest_diff_deg(10.0, 350.0), -20.0, places=4)
        self.assertAlmostEqual(circular_shortest_diff_deg(170.0, -170.0), 20.0, places=4)
        self.assertAlmostEqual(circular_shortest_diff_deg(-170.0, 170.0), -20.0, places=4)

    def test_normalize_angle_180(self):
        """Angle is strictly normalized into [-180.0, +180.0) degrees."""
        self.assertAlmostEqual(normalize_angle_180(0.0), 0.0)
        self.assertAlmostEqual(normalize_angle_180(180.0), -180.0)
        self.assertAlmostEqual(normalize_angle_180(190.0), -170.0)
        self.assertAlmostEqual(normalize_angle_180(-190.0), 170.0)
        self.assertAlmostEqual(normalize_angle_180(540.0), -180.0)


class TestManoeuvreDetection(unittest.TestCase):
    """Verifies tack and gybe classification, metrics, and zero false positives."""

    def setUp(self):
        self.detector = ManoeuvreDetector(
            min_heading_change_deg=50.0,
            min_rot_deg_s=5.0,
            min_speed_loss_kt=2.5,
            min_tack_stability_s=2.0,
            min_manoeuvre_separation_s=6.0,
            sample_interval_ms=100,  # 10 Hz
        )

    def test_tack_detection_through_zero_twa(self):
        """Synthetic upwind tack (TWA -45 to +45 deg, heading 0 to 90 deg) is classified as TACK."""
        # 100 frames at 10Hz = 10 seconds
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]

        # Heading starts at 0 deg, turns to 90 deg between frames 30 and 60
        heading = [0.0] * n
        twa = [-45.0] * n
        sog = [26.0] * n

        # Turn phase: frames 30 to 60 (3 seconds, ROT = 90 / 3 = 30 deg/s)
        for i in range(30, 61):
            alpha = (i - 30) / 30.0
            heading[i] = alpha * 90.0
            twa[i] = -45.0 + alpha * 90.0  # Crosses 0 at frame 45
            # Speed dips down to 18 kt at midpoint, then recovers
            sog_dip = 8.0 * (1.0 - abs(alpha - 0.5) * 2.0)
            sog[i] = 26.0 - sog_dip

        # Stabilized on new tack: frames 61 to 99
        for i in range(61, n):
            heading[i] = 90.0
            twa[i] = 45.0
            sog[i] = 25.5

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )

        self.assertEqual(len(manoeuvres), 1)
        m = manoeuvres[0]
        self.assertEqual(m.type, "TACK")
        self.assertGreaterEqual(m.entry_speed_kt, 24.0)
        self.assertLessEqual(m.min_speed_kt, 19.0)
        self.assertGreaterEqual(m.speed_loss_kt, 5.0)
        self.assertGreaterEqual(m.turn_delta_deg, 60.0)

    def test_gybe_detection_through_180_twa(self):
        """Synthetic downwind gybe (TWA +140 to -140 deg, heading 190 to 290 deg) is classified as GYBE."""
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]

        heading = [190.0] * n
        twa = [140.0] * n
        sog = [32.0] * n

        # Gybe turn phase: frames 30 to 60
        for i in range(30, 61):
            alpha = (i - 30) / 30.0
            heading[i] = 190.0 + alpha * 100.0  # 190 to 290
            # TWA crosses through 180: from +140 to +180 to -140
            if alpha < 0.5:
                twa[i] = 140.0 + alpha * 80.0  # 140 -> 180
            else:
                twa[i] = -180.0 + (alpha - 0.5) * 80.0  # -180 -> -140
            sog_dip = 9.0 * (1.0 - abs(alpha - 0.5) * 2.0)
            sog[i] = 32.0 - sog_dip

        for i in range(61, n):
            heading[i] = 290.0
            twa[i] = -140.0
            sog[i] = 31.0

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )

        self.assertEqual(len(manoeuvres), 1)
        m = manoeuvres[0]
        self.assertEqual(m.type, "GYBE")
        self.assertGreaterEqual(m.entry_speed_kt, 30.0)
        self.assertLessEqual(m.min_speed_kt, 24.0)
        self.assertGreaterEqual(m.speed_loss_kt, 6.0)

    def test_zero_false_positives_on_straight_run_with_steering_corrections(self):
        """Small heading corrections (<15 deg) during straight-line foiling produce ZERO false positives."""
        n = 200
        timestamps = [1790079000000 + i * 100 for i in range(n)]

        # Boat sailing steady starboard upwind: heading ~40 deg +/- 5 deg wave corrections
        heading = [40.0 + 4.0 * math.sin(i * 0.1) for i in range(n)]
        twa = [45.0 + 3.0 * math.sin(i * 0.1) for i in range(n)]
        sog = [27.0 + 1.0 * math.cos(i * 0.1) for i in range(n)]

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )

        # STRICT REQUIREMENT: ZERO FALSE POSITIVES
        self.assertEqual(len(manoeuvres), 0)

    def test_temporary_chatter_rejected_by_stability_filter(self):
        """A momentary twitch across 0 deg (<1 second) that returns to original tack is rejected."""
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]

        heading = [40.0] * n
        twa = [45.0] * n
        sog = [26.0] * n

        # Twitch for only 4 frames (400ms < 2.0s stability threshold)
        for i in range(40, 45):
            twa[i] = -20.0

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )

        self.assertEqual(len(manoeuvres), 0)


if __name__ == "__main__":
    unittest.main()
