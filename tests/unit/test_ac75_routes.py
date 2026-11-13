"""Unit tests for AC75 route templates, support tiers, and course transformation (T08)."""
import math
import unittest
import numpy as np

from pipeline.kinematic_ml.routes import (
    LegRouteTemplate,
    RouteSegment,
    RouteTemplateLibrary,
    transform_template_to_course,
)


class TestAC75Routes(unittest.TestCase):
    def setUp(self):
        # Create dummy route templates
        self.segments = [
            RouteSegment(
                segment_type="straight",
                start_pos=(0.0, 0.0),
                end_pos=(100.0, 500.0),
                distance_m=509.9,
                target_cog_deg=11.3,
                target_heading_deg=8.3,
            ),
            RouteSegment(
                segment_type="maneuver",
                start_pos=(100.0, 500.0),
                end_pos=(120.0, 520.0),
                distance_m=28.3,
                target_cog_deg=45.0,
                target_heading_deg=42.0,
                turn_type="tack",
                turn_rotation_deg=80.0,
                maneuver_duration_s=8.5,
                recovery_s=4.0,
                is_censored=False,
            ),
            RouteSegment(
                segment_type="straight",
                start_pos=(120.0, 520.0),
                end_pos=(0.0, 1000.0),
                distance_m=504.4,
                target_cog_deg=345.0,
                target_heading_deg=342.0,
            ),
        ]

    def test_team_support_tier_thresholds(self):
        """Verify that team-specific tier requires >= 10 legs across >= 3 training days."""
        library = RouteTemplateLibrary()

        # Add 5 legs for INEOS across 2 days -> should be pooled tier
        for i in range(5):
            t = LegRouteTemplate(
                template_id=f"tpl_ineos_{i}",
                attempt_id=f"att_{i}",
                team_id="ac37:INEOS",
                date_str="2024-08-29" if i < 3 else "2024-08-30",
                stage="round_robin",
                leg_number=1,
                leg_type=1,
                mean_tws_mps=8.0,
                leg_length_m=1000.0,
                segments=self.segments,
            )
            library.add_template(t)

        tier, legs, days = library.team_support_level("ac37:INEOS", leg_type=1)
        self.assertEqual(tier, "pooled")
        self.assertEqual(legs, 5)
        self.assertEqual(days, 2)

        # Now add more legs to reach 10 legs across 3 days
        for i in range(5, 12):
            t = LegRouteTemplate(
                template_id=f"tpl_ineos_{i}",
                attempt_id=f"att_{i}",
                team_id="ac37:INEOS",
                date_str="2024-09-01",  # 3rd distinct day
                stage="round_robin",
                leg_number=1,
                leg_type=1,
                mean_tws_mps=8.5,
                leg_length_m=1050.0,
                segments=self.segments,
            )
            library.add_template(t)

        tier_qualified, legs_q, days_q = library.team_support_level("ac37:INEOS", leg_type=1)
        self.assertEqual(tier_qualified, "team_specific")
        self.assertEqual(legs_q, 12)
        self.assertEqual(days_q, 3)

    def test_nearest_template_query_weights(self):
        """Verify inverse-distance weights and standardized distance calculation."""
        library = RouteTemplateLibrary()
        # Add 2 templates with different TWS
        t1 = LegRouteTemplate(
            template_id="t1",
            attempt_id="att_1",
            team_id="ac37:LUNA_ROSSA",
            date_str="2024-08-29",
            stage="round_robin",
            leg_number=1,
            leg_type=1,
            mean_tws_mps=7.0,
            leg_length_m=1000.0,
            segments=self.segments,
        )
        t2 = LegRouteTemplate(
            template_id="t2",
            attempt_id="att_2",
            team_id="ac37:LUNA_ROSSA",
            date_str="2024-08-30",
            stage="round_robin",
            leg_number=1,
            leg_type=1,
            mean_tws_mps=15.0,
            leg_length_m=1000.0,
            segments=self.segments,
        )
        library.add_template(t1)
        library.add_template(t2)

        # Query at TWS = 7.1 m/s: t1 should have much higher weight than t2
        results, tier = library.query_nearest_templates("ac37:LUNA_ROSSA", leg_type=1, target_tws_mps=7.1, target_leg_length_m=1000.0)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0].template_id, "t1")
        self.assertGreater(results[0][1], 0.90)  # Over 90% weight on t1

    def test_template_course_transformation(self):
        """Verify transforming normalized template to course bearing and distance."""
        tpl = LegRouteTemplate(
            template_id="t_test",
            attempt_id="att_test",
            team_id="ac37:ETNZ",
            date_str="2024-08-29",
            stage="round_robin",
            leg_number=1,
            leg_type=1,
            mean_tws_mps=8.0,
            leg_length_m=1000.0,
            segments=self.segments,
        )
        # Transform to 1500m leg at bearing 090 (due East)
        trans = transform_template_to_course(tpl, course_bearing_deg=90.0, course_length_m=1500.0, leeway_deg=4.0)
        self.assertEqual(len(trans), 3)

        # Scaling factor is 1.5
        # Segment 1 original distance was 509.9 -> should be ~ 764.85
        self.assertAlmostEqual(trans[0].distance_m, 509.9 * 1.5, delta=1.0)
        # Turn parameters preserved
        self.assertEqual(trans[1].turn_type, "tack")
        self.assertEqual(trans[1].turn_rotation_deg, 80.0)
        self.assertEqual(trans[1].maneuver_duration_s, 8.5)

    def test_compass_rotation_cardinal_bearings(self):
        """Verify that a northbound leg-aligned vector (0, L) rotates clockwise to 0, 90, 180, 270 deg."""
        north_seg = RouteSegment(
            segment_type="straight",
            start_pos=(0.0, 0.0),
            end_pos=(0.0, 1000.0),
            distance_m=1000.0,
            target_cog_deg=0.0,
            target_heading_deg=0.0,
        )
        tpl = LegRouteTemplate(
            template_id="t_cardinal",
            attempt_id="att_cardinal",
            team_id="ac37:ETNZ",
            date_str="2024-08-29",
            stage="round_robin",
            leg_number=1,
            leg_type=1,
            mean_tws_mps=8.0,
            leg_length_m=1000.0,
            segments=[north_seg],
        )

        # 0 deg (North) -> end_pos = (0, 1000), COG = 0.0
        s0 = transform_template_to_course(tpl, course_bearing_deg=0.0, course_length_m=1000.0, leeway_deg=0.0)[0]
        self.assertEqual(s0.end_pos, (0.0, 1000.0))
        self.assertAlmostEqual(s0.target_cog_deg, 0.0, places=1)

        # 90 deg (East) -> end_pos = (1000, 0), COG = 90.0
        s90 = transform_template_to_course(tpl, course_bearing_deg=90.0, course_length_m=1000.0, leeway_deg=0.0)[0]
        self.assertEqual(s90.end_pos, (1000.0, 0.0))
        self.assertAlmostEqual(s90.target_cog_deg, 90.0, places=1)

        # 180 deg (South) -> end_pos = (0, -1000), COG = 180.0
        s180 = transform_template_to_course(tpl, course_bearing_deg=180.0, course_length_m=1000.0, leeway_deg=0.0)[0]
        self.assertEqual(s180.end_pos, (0.0, -1000.0))
        self.assertAlmostEqual(s180.target_cog_deg, 180.0, places=1)

        # 270 deg (West) -> end_pos = (-1000, 0), COG = 270.0
        s270 = transform_template_to_course(tpl, course_bearing_deg=270.0, course_length_m=1000.0, leeway_deg=0.0)[0]
        self.assertEqual(s270.end_pos, (-1000.0, 0.0))
        self.assertAlmostEqual(s270.target_cog_deg, 270.0, places=1)


if __name__ == "__main__":
    unittest.main()
