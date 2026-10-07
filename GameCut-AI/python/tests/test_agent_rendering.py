import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.editing_agent import generate_validated_plan
from agents.validator import PlanValidationError, validate_editing_plan
from jobs.worker import build_production_plan
from processing import clip_renderer
from processing.clip_renderer import validate_output
from processing.subtitle_processor import map_transcript_to_clips, write_srt


class AgentRenderingTestCase(unittest.TestCase):
    def test_validator_rejects_invalid_timestamps(self):
        plan = {"target_duration": 45, "aspect_ratio": "9:16", "clips": [{"start": 10, "end": 4}]}
        with self.assertRaises(PlanValidationError):
            validate_editing_plan(plan, video_duration=100)

    def test_validator_rejects_overlapping_clips(self):
        plan = {
            "target_duration": 45,
            "aspect_ratio": "9:16",
            "clips": [{"start": 1, "end": 10}, {"start": 5, "end": 12}],
        }
        with self.assertRaises(PlanValidationError):
            validate_editing_plan(plan, video_duration=100)

    def test_deterministic_agent_generates_valid_plan(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            (job_dir / "highlight_candidates.json").write_text(
                json.dumps(
                    {
                        "video_duration": 100,
                        "candidates": [
                            {"start": 5, "end": 15, "duration": 10, "score": 0.9, "reason": ["high score"]},
                            {"start": 30, "end": 42, "duration": 12, "score": 0.8, "reason": ["visual activity"]},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = generate_validated_plan(job_dir)

        self.assertEqual(plan["aspect_ratio"], "9:16")
        self.assertEqual(len(plan["clips"]), 2)
        self.assertTrue(plan["agent"]["fallback_used"])

    def test_transcript_mapping_is_relative_to_selected_clips(self):
        clips = [{"start": 10, "end": 20}, {"start": 30, "end": 40}]
        transcript = [{"start": 12, "end": 15, "text": "hello"}, {"start": 32, "end": 34, "text": "again"}]
        mapped = map_transcript_to_clips(clips, transcript)
        self.assertEqual(mapped[0]["start"], 2)
        self.assertEqual(mapped[1]["start"], 12)

    def test_transcript_mapping_accounts_for_playback_speed(self):
        clips = [{"start": 10, "end": 20}, {"start": 30, "end": 40}]
        transcript = [{"start": 12, "end": 15, "text": "hello"}, {"start": 32, "end": 34, "text": "again"}]
        mapped = map_transcript_to_clips(clips, transcript, playback_speed=2)
        self.assertEqual(mapped[0]["start"], 1)
        self.assertEqual(mapped[1]["start"], 6)

    def test_write_srt_creates_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "captions.srt"
            write_srt([{"start": 0, "end": 1.5, "text": "hello world"}], path)
            content = path.read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 --> 00:00:01,500", content)

    def test_validate_output_rejects_missing_file(self):
        with self.assertRaises(Exception):
            validate_output("missing-output.mp4")

    def test_production_plan_is_vertical_captioned_and_speed_aware(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan = build_production_plan(
                tmp_dir,
                [
                    {"start": 0, "end": 10, "score": 0.9},
                    {"start": 30, "end": 45, "score": 0.8},
                ],
                60,
                {"target_duration": 30, "style": "Fast Motion", "playback_speed": 2, "padding_before": 0, "padding_after": 0},
            )

        self.assertEqual(plan["aspect_ratio"], "9:16")
        self.assertTrue(plan["subtitles"])
        self.assertEqual(plan["speed"], 2.0)
        self.assertTrue(plan["clips"])

    def test_vertical_renderer_burns_subtitles_when_transcript_is_available(self):
        metadata = {
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080},
                {"codec_type": "audio"},
            ]
        }
        validation = {"duration": 5.0, "width": 1080, "height": 1920, "audio": True, "size": 1}
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "published.mp4"
            with patch.object(clip_renderer, "get_metadata", return_value=metadata), patch.object(
                clip_renderer, "_trim_clip"
            ) as trim, patch.object(clip_renderer, "_concat_clips"), patch.object(
                clip_renderer, "_burn_subtitles"
            ) as burn, patch.object(clip_renderer.shutil, "copy2"), patch.object(
                clip_renderer, "validate_vertical_output", return_value=validation
            ), patch.object(clip_renderer, "generate_thumbnail"):
                result = clip_renderer.render_highlight_video(
                    "source.mp4",
                    [{"start": 0, "end": 5}],
                    [{"start": 1, "end": 2, "text": "caption"}],
                    output,
                    tmp_dir,
                    subtitles=True,
                )

        trim.assert_called_once()
        burn.assert_called_once()
        self.assertTrue(result["subtitles"])
        self.assertEqual(result["output_format"], {"width": 1080, "height": 1920, "aspect_ratio": "9:16"})

    def test_vertical_renderer_rejects_non_vertical_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "output.mp4"
            output.write_bytes(b"x")
            metadata = {
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
                "format": {"duration": "1"},
            }
            with patch.object(clip_renderer, "get_metadata", return_value=metadata):
                with self.assertRaises(clip_renderer.RenderError):
                    clip_renderer.validate_vertical_output(output)


if __name__ == "__main__":
    unittest.main()
