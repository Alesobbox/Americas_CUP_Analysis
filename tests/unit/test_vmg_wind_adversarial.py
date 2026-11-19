"""Adversarial Verification Suite for Milestone 2 Challenger 2:
1. VMG 7-step color scale Euclidean distance ΔC >= 50 and WCAG contrast vs #0a0e17.
2. Wind flow field rendering math: downwind orientation ((twd + 180) % 360) and 0.10 opacity.
"""

from __future__ import annotations

import math
import re
import unittest
from pathlib import Path
from typing import Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def srgb_to_linear(c_8bit: int) -> float:
    s = c_8bit / 255.0
    return s / 12.92 if s <= 0.04045 else math.pow((s + 0.055) / 1.055, 2.4)


def relative_luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)


def wcag_contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    l1 = relative_luminance(*rgb1)
    l2 = relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def euclidean_rgb_distance(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    return math.sqrt(
        (rgb1[0] - rgb2[0]) ** 2 +
        (rgb1[1] - rgb2[1]) ** 2 +
        (rgb1[2] - rgb2[2]) ** 2
    )


class TestVmgTrailColorScaleAdversarial(unittest.TestCase):
    """Adversarial stress-testing of 7-step VMG color scale."""

    @classmethod
    def setUpClass(cls):
        cls.source_file = WORKSPACE_ROOT / "src" / "components" / "canvas" / "DynamicVesselLayer.ts"
        assert cls.source_file.exists(), f"Missing {cls.source_file}"
        cls.content = cls.source_file.read_text(encoding="utf-8")

        # Parse VMG_COLOR_STEPS from source
        # Pattern: { minKt: X, maxKt: Y, hex: '#...', rgb: [R, G, B], name: '...' }
        pattern = re.compile(
            r"minKt:\s*(\d+),\s*maxKt:\s*(\d+),\s*hex:\s*'([^']+)',\s*rgb:\s*\[(\d+),\s*(\d+),\s*(\d+)\]"
        )
        matches = pattern.findall(cls.content)
        assert len(matches) == 7, f"Expected 7 VMG_COLOR_STEPS in source, found {len(matches)}"

        cls.steps = []
        for m in matches:
            cls.steps.append({
                "minKt": int(m[0]),
                "maxKt": int(m[1]),
                "hex": m[2],
                "rgb": (int(m[3]), int(m[4]), int(m[5])),
            })

        cls.bg_rgb = (10, 14, 23)  # #0a0e17

    def test_step_count_and_range_continuity(self):
        """Verifies exactly 7 steps covering 0 to 60 kt with zero gaps."""
        self.assertEqual(len(self.steps), 7)
        self.assertEqual(self.steps[0]["minKt"], 0)
        self.assertEqual(self.steps[0]["maxKt"], 10)
        self.assertEqual(self.steps[-1]["maxKt"], 60)

        for i in range(len(self.steps) - 1):
            self.assertEqual(
                self.steps[i]["maxKt"],
                self.steps[i + 1]["minKt"],
                f"Discontinuity between step {i} and {i+1}",
            )

    def test_hex_matches_rgb(self):
        """Verifies hex string matches RGB integer triplet."""
        for step in self.steps:
            hex_val = step["hex"].lstrip("#")
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            self.assertEqual((r, g, b), step["rgb"])

    def test_euclidean_rgb_distance_all_adjacent_pairs(self):
        """Verifies ΔC >= 50 for every adjacent step pair across 10-35 kt."""
        # Active fleet speed range spans steps across 10-35 kt:
        # Step 0 (0-10) -> Step 1 (10-15)
        # Step 1 (10-15) -> Step 2 (15-20)
        # Step 2 (15-20) -> Step 3 (20-25)
        # Step 3 (20-25) -> Step 4 (25-30)
        # Step 4 (25-30) -> Step 5 (30-35)
        # Step 5 (30-35) -> Step 6 (35-60)
        deltas = []
        for i in range(len(self.steps) - 1):
            c1 = self.steps[i]["rgb"]
            c2 = self.steps[i + 1]["rgb"]
            dc = euclidean_rgb_distance(c1, c2)
            deltas.append(dc)
            self.assertGreaterEqual(
                dc,
                50.0,
                f"Step {i} ({self.steps[i]['hex']}) vs Step {i+1} ({self.steps[i+1]['hex']}) "
                f"ΔC = {dc:.2f} is below 50.0 threshold!",
            )

        # Minimum across all adjacent pairs is >= 60.0
        min_dc = min(deltas)
        self.assertGreaterEqual(min_dc, 60.0)

    def test_wcag_contrast_against_dark_background(self):
        """Verifies WCAG contrast ratio vs #0a0e17 is >= 4.5:1 (AA) for all steps."""
        bg_lum = relative_luminance(*self.bg_rgb)
        self.assertAlmostEqual(bg_lum, 0.004337, delta=0.0005)

        for step in self.steps:
            cr = wcag_contrast_ratio(step["rgb"], self.bg_rgb)
            self.assertGreaterEqual(
                cr,
                4.5,
                f"Step {step['hex']} has contrast ratio {cr:.2f}:1 < 4.5:1 against #0a0e17",
            )


class TestWindFlowFieldRenderingMathAdversarial(unittest.TestCase):
    """Adversarial stress-testing of wind flow field vectors and opacity."""

    @classmethod
    def setUpClass(cls):
        cls.source_file = WORKSPACE_ROOT / "src" / "components" / "canvas" / "DynamicVesselLayer.ts"
        assert cls.source_file.exists()
        cls.content = cls.source_file.read_text(encoding="utf-8")

    def test_downwind_formula_in_source(self):
        """Verifies downwind angle formula ((wind.twd + 180) % 360) is present in drawWindFlowField."""
        pattern = r"\(\(\(wind\.twd\s*\+\s*180\)\s*%\s*360\)\s*\*\s*Math\.PI\)\s*/\s*180"
        self.assertRegex(self.content, pattern, "drawWindFlowField must calculate downwind via (wind.twd + 180) % 360")

    def test_low_contrast_opacity_in_source(self):
        """Verifies opacity is low-contrast (0.10) to avoid distracting from fleet hulls."""
        self.assertRegex(self.content, r"strokeStyle\s*=\s*COURSE_PALETTE\.airflow")
        palette = (self.source_file.parent / "renderPalette.ts").read_text(encoding="utf-8")
        match = re.search(r"airflow:\s*'rgba\(\d+,\s*\d+,\s*\d+,\s*([\d.]+)\)'", palette)
        self.assertIsNotNone(match, "Wind vectors must have an explicit shared RGBA color")
        self.assertAlmostEqual(float(match.group(1)), 0.10)

    def test_downwind_vector_projection_math(self):
        """Verifies trigonometric projection for True North (0), East (90), South (180), West (270)."""
        # North wind (TWD = 0) -> downwind = 180 -> flow travels South (dy < 0 in world, vy > 0 in screen)
        # East wind (TWD = 90) -> downwind = 270 -> flow travels West (dx < 0 in world, vx < 0 in screen)
        # South wind (TWD = 180) -> downwind = 0 -> flow travels North (dy > 0 in world, vy < 0 in screen)
        # West wind (TWD = 270) -> downwind = 90 -> flow travels East (dx > 0 in world, vx > 0 in screen)
        directions = [
            (0, 180, 0.0, -1.0, 0.0, 1.0),     # North: world=(0, -1), screen=(0, +1) -> Down
            (90, 270, -1.0, 0.0, -1.0, 0.0),   # East: world=(-1, 0), screen=(-1, 0) -> Left
            (180, 0, 0.0, 1.0, 0.0, -1.0),     # South: world=(0, +1), screen=(0, -1) -> Up
            (270, 90, 1.0, 0.0, 1.0, 0.0),     # West: world=(+1, 0), screen=(+1, 0) -> Right
        ]

        for twd, expected_downwind, exp_wx, exp_wy, exp_sx, exp_sy in directions:
            downwind = (twd + 180) % 360
            self.assertEqual(downwind, expected_downwind)
            rad = math.radians(downwind)
            wx = math.sin(rad)
            wy = math.cos(rad)
            self.assertAlmostEqual(wx, exp_wx, places=5)
            self.assertAlmostEqual(wy, exp_wy, places=5)

            # In North-Up screen projection: vx = wx, vy = -wy
            sx = wx
            sy = -wy
            self.assertAlmostEqual(sx, exp_sx, places=5)
            self.assertAlmostEqual(sy, exp_sy, places=5)

    def test_course_up_rotation_downwind_alignment(self):
        """In Course-Up mode (40° vertical), wind from 40° blows straight DOWN on the screen (vx=0, vy>0)."""
        course_axis = 40.0
        twd = 40.0  # Wind directly down the course axis
        downwind = (twd + 180) % 360  # 220°
        rad = math.radians(downwind)
        world_vec = (math.sin(rad), math.cos(rad))

        # World to screen rotation by 40°:
        # vx = (cos(40) * wx - sin(40) * wy)
        # vy = -(sin(40) * wx + cos(40) * wy)
        rot_rad = math.radians(course_axis)
        vx = math.cos(rot_rad) * world_vec[0] - math.sin(rot_rad) * world_vec[1]
        vy = -(math.sin(rot_rad) * world_vec[0] + math.cos(rot_rad) * world_vec[1])

        self.assertAlmostEqual(vx, 0.0, places=5)
        self.assertGreater(vy, 0.0)  # Straight down screen along leeward course direction

    def test_wind_rendered_beneath_vessels(self):
        """Verifies in drawDynamicVessels that drawWindFlowField is executed before drawBoat and drawCourseGeometry."""
        pos_flow = self.content.find("drawWindFlowField(")
        pos_geometry = self.content.find("drawCourseGeometry(")
        pos_boats = self.content.find("drawBoat(")

        self.assertGreater(pos_flow, 0)
        self.assertGreater(pos_geometry, pos_flow, "drawCourseGeometry must come after drawWindFlowField")
        self.assertGreater(pos_boats, pos_flow, "drawBoat must come after drawWindFlowField")


if __name__ == "__main__":
    unittest.main()
