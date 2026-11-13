"""Unit tests for AC75 maneuver duration and event models (T12)."""
import unittest
import numpy as np

from pipeline.kinematic_ml.events import (
    ManeuverDurationModel,
    StartBehaviorModel,
)


class TestAC75Events(unittest.TestCase):
    def test_event_feature_allowlist_enforcement(self):
        """Verify that event duration model strictly enforces EVENT_PREDICTOR_ALLOWLIST."""
        model = ManeuverDurationModel()
        valid_features = {
            "turn_type": "tack",
            "rotation_deg": 80.0,
            "tws_mps": 11.0,
            "entry_speed_predicted_mps": 22.0,
            "team_id": "ac37:INEOS",
            "leg_type": 1,
        }
        dur = model.predict_duration_s(valid_features)
        self.assertGreater(dur, 5.0)

        # Injected leaky future predictor must raise ValueError
        invalid_features = dict(valid_features)
        invalid_features["future_exit_speed"] = 25.0
        with self.assertRaises(ValueError):
            model.predict_duration_s(invalid_features)

    def test_rotation_increases_duration(self):
        """Verify that larger turn angle increases duration smoothly."""
        model = ManeuverDurationModel()
        f_small = {
            "turn_type": "tack",
            "rotation_deg": 65.0,
            "tws_mps": 10.0,
            "entry_speed_predicted_mps": 20.0,
            "team_id": "ac37:LUNA_ROSSA",
            "leg_type": 1,
        }
        f_large = dict(f_small)
        f_large["rotation_deg"] = 100.0

        dur_small = model.predict_duration_s(f_small)
        dur_large = model.predict_duration_s(f_large)
        self.assertGreater(dur_large, dur_small)

    def test_right_censoring_increases_predicted_duration(self):
        """Verify right-censored turns increase fitted intercept and predicted duration vs uncensored."""
        base_turns = [
            {
                "turn_type": "tack",
                "total_event_s": 10.0 + (i % 4),
                "rotation_deg": 75.0 + (i % 5) * 2.0,
                "tws_mps": 10.0 + (i % 3),
                "entry_speed_predicted_mps": 19.0 + (i % 4),
                "team_id": "ac37:ETNZ",
                "censoring": False,
            }
            for i in range(16)
        ]
        # Add 6 long turns at the 30s censoring horizon
        uncensored_turns = list(base_turns) + [
            {
                "turn_type": "tack",
                "total_event_s": 30.0,
                "rotation_deg": 80.0,
                "tws_mps": 10.0,
                "entry_speed_predicted_mps": 18.0,
                "team_id": "ac37:ETNZ",
                "censoring": False,
            }
            for _ in range(6)
        ]
        censored_turns = list(base_turns) + [
            {
                "turn_type": "tack",
                "total_event_s": 30.0,
                "rotation_deg": 80.0,
                "tws_mps": 10.0,
                "entry_speed_predicted_mps": 18.0,
                "team_id": "ac37:ETNZ",
                "censoring": True,
            }
            for _ in range(6)
        ]

        m_uncens = ManeuverDurationModel()
        m_uncens.fit(uncensored_turns)

        m_cens = ManeuverDurationModel()
        m_cens.fit(censored_turns)

        self.assertNotEqual(m_uncens.intercept_tack, m_cens.intercept_tack)
        self.assertGreater(m_cens.intercept_tack, m_uncens.intercept_tack)

        probe = {
            "turn_type": "tack",
            "rotation_deg": 80.0,
            "tws_mps": 10.0,
            "entry_speed_predicted_mps": 18.0,
            "team_id": "ac37:ETNZ",
            "leg_type": 1,
        }
        self.assertGreater(
            m_cens.predict_duration_s(probe),
            m_uncens.predict_duration_s(probe),
        )

    def test_start_behavior_sampling(self):
        """Verify start behavior model samples positive durations."""
        start_model = StartBehaviorModel(mean_start_dur_s=18.0, stdev_s=2.0)
        rng = np.random.default_rng(2027)
        durs = [start_model.sample_start_time_s(rng, tws_mps=12.0) for _ in range(50)]
        self.assertTrue(all(d > 5.0 for d in durs))
        self.assertAlmostEqual(np.mean(durs), 18.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
