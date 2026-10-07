import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.audio_analyzer import AudioAnalysisError, analyze_audio_regions
from detection.highlight_scorer import score_candidates
from detection.visual_analyzer import analyze_visual_regions


class Phase8AnalysisTestCase(unittest.TestCase):
    def test_audio_analyzer_normalizes_region_signals(self):
        samples = [0.0, 0.1, -0.2, 0.4, -0.8, 0.2]
        with patch("detection.audio_analyzer._read_region_audio", return_value=samples):
            result = analyze_audio_regions("sample.mp4", [{"start": 0, "end": 2}], job_id=1)

        self.assertEqual(result["analyzed_count"], 1)
        audio = result["regions"][0]["audio"]
        self.assertGreater(audio["energy"], 0)
        self.assertGreater(audio["peak"], 0)
        self.assertLessEqual(audio["score"], 1)

    def test_audio_analysis_failure_is_recorded_per_region(self):
        with patch("detection.audio_analyzer._read_region_audio", side_effect=AudioAnalysisError("audio failed")):
            result = analyze_audio_regions("sample.mp4", [{"start": 0, "end": 2}], job_id=1)

        self.assertEqual(result["analyzed_count"], 0)
        self.assertEqual(result["failed_count"], 1)

    def test_scorer_uses_audio_and_visual_signals(self):
        scene_analysis = {
            "duration": 20,
            "scenes": [{"start": 5, "end": 12, "duration": 7}],
        }
        audio_analysis = {
            "regions": [{"start": 5, "end": 12, "audio": {"score": 1.0, "peak": 1.0, "energy": 0.9, "change": 0.8}}],
        }
        visual_analysis = {
            "regions": [{"start": 5, "end": 12, "visual": {"score": 1.0, "activity": 0.9, "transition": 0.8}}],
        }
        result = score_candidates(
            scene_analysis,
            transcript={"segments": []},
            audio_analysis=audio_analysis,
            visual_analysis=visual_analysis,
        )

        candidate = result["candidates"][0]
        self.assertEqual(candidate["signals"]["audio"], 1.0)
        self.assertEqual(candidate["signals"]["visual"], 1.0)
        self.assertIn("strong audio peak", candidate["reason"])
        self.assertIn("high visual activity", candidate["reason"])

    def test_scorer_falls_back_when_optional_analysis_missing(self):
        result = score_candidates(
            {"duration": 20, "scenes": [{"start": 0, "end": 10, "duration": 10}]},
            transcript={"segments": []},
        )
        candidate = result["candidates"][0]
        self.assertEqual(candidate["signals"]["audio"], 0)
        self.assertEqual(candidate["signals"]["visual"], 0)
        self.assertTrue(result["audio_analysis_missing"])
        self.assertTrue(result["visual_analysis_missing"])

    def test_visual_analyzer_can_record_output_with_mocked_frames(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "visual_analysis.json"
            with patch("detection.visual_analyzer.cv2") as cv2_mock:
                cap = cv2_mock.VideoCapture.return_value
                cap.isOpened.return_value = True
                cap.get.return_value = 30
                cap.read.return_value = (False, None)

                result = analyze_visual_regions("sample.mp4", [{"start": 0, "end": 2}], output_path=output_path)
                output_exists = output_path.exists()

        self.assertEqual(result["analyzed_count"], 1)
        self.assertTrue(output_exists)


if __name__ == "__main__":
    unittest.main()
