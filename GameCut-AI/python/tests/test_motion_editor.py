import sys
import unittest
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

from agents.agent_tools import create_deterministic_plan
from agents.schemas import AgentPreferences
from agents.validator import PlanValidationError, validate_editing_plan
from processing.basic_editor import atempo_filter, build_basic_plan, motion_settings


class MotionEditorTestCase(unittest.TestCase):
    def test_slow_motion_accepts_user_speed(self):
        settings = motion_settings("Slow Motion", 0.25)
        self.assertEqual(settings, {"mode": "slow_motion", "speed": 0.25})

    def test_fast_motion_accepts_user_speed(self):
        settings = motion_settings("Fast Motion", 8)
        self.assertEqual(settings, {"mode": "fast_motion", "speed": 8.0})

    def test_speed_is_limited_to_safe_mode_range(self):
        self.assertEqual(motion_settings("Slow Motion", 2)["speed"], 1.0)
        self.assertEqual(motion_settings("Fast Motion", 99)["speed"], 8.0)

    def test_fast_montage_is_not_full_video_fast_motion(self):
        self.assertEqual(motion_settings("Fast Montage", 4), {"mode": "normal", "speed": 1.0})

    def test_fast_motion_uses_more_source_timeline(self):
        candidates = [
            {"start": index * 12, "end": index * 12 + 5, "score": 1 - index / 100}
            for index in range(30)
        ]
        plan = build_basic_plan(candidates, 400, target_duration=100, padding_before=0,
                                padding_after=0, style="Fast Motion", speed=4)
        selected_seconds = sum(clip["end"] - clip["start"] for clip in plan["clips"])
        self.assertGreaterEqual(selected_seconds, 25)
        self.assertEqual(plan["speed"], 4.0)

    def test_motion_mode_uses_the_complete_source_range(self):
        plan = build_basic_plan(
            [{"start": 20, "end": 25, "score": 1}],
            120,
            target_duration=30,
            style="Fast Motion",
            speed=4,
        )
        self.assertEqual(plan["clips"], [{
            "start": 0.0,
            "end": 120.0,
            "score": 1.0,
            "reason": "Full-video motion effect",
        }])

    def test_deterministic_motion_plan_does_not_cap_full_video_to_one_clip(self):
        plan = create_deterministic_plan(
            {"video_duration": 120, "candidates": [{"start": 20, "end": 25, "score": 1}]},
            AgentPreferences(target_duration=30, motion_mode="slow_motion", speed=0.5),
        )
        self.assertEqual(plan["clips"][0]["start"], 0.0)
        self.assertEqual(plan["clips"][0]["end"], 120.0)

    def test_audio_speed_chain_supports_extreme_presets(self):
        self.assertEqual(atempo_filter(4), "atempo=2.000000,atempo=2.000000")
        self.assertEqual(atempo_filter(0.25), "atempo=0.500000,atempo=0.500000")

    def test_validator_keeps_motion_fields(self):
        plan = validate_editing_plan({
            "target_duration": 120,
            "style": "Fast Motion",
            "motion_mode": "fast_motion",
            "speed": 4,
            "clips": [{"start": 0, "end": 20}],
        }, 200)
        self.assertEqual(plan["speed"], 4.0)
        self.assertEqual(plan["style"], "Fast Motion")

    def test_validator_rejects_unsafe_speed(self):
        with self.assertRaises(PlanValidationError):
            validate_editing_plan({"target_duration": 30, "speed": 9, "clips": []}, 50)


if __name__ == "__main__":
    unittest.main()
