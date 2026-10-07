import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.highlight_scorer import (
    HighlightScoringConfig,
    HighlightScoringError,
    generate_highlight_candidates,
    remove_overlapping_candidates,
    score_candidates,
)


def scene_analysis(scenes, duration=120):
    return {"duration": duration, "scene_count": len(scenes), "scenes": scenes}


class HighlightScorerTestCase(unittest.TestCase):
    def test_video_with_speech_scores_higher_than_no_speech(self):
        scenes = scene_analysis([{"start": 10, "end": 20, "duration": 10}])
        transcript = {"segments": [{"start": 12, "end": 16, "text": "No way, let's go!", "confidence": 0.9}]}

        with_speech = score_candidates(scenes, transcript)
        without_speech = score_candidates(scenes, {"segments": []})

        self.assertGreater(with_speech["candidates"][0]["signals"]["speech"], 0)
        self.assertGreater(with_speech["highest_score"], without_speech["highest_score"])

    def test_little_or_no_speech_does_not_crash(self):
        result = score_candidates(scene_analysis([{"start": 0, "end": 8, "duration": 8}]), {"segments": []})
        self.assertGreaterEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["signals"]["speech"], 0)

    def test_overlapping_scenes_keep_higher_score(self):
        candidates = [
            {"start": 0, "end": 10, "duration": 10, "score": 0.4},
            {"start": 2, "end": 12, "duration": 10, "score": 0.9},
        ]
        selected, removed = remove_overlapping_candidates(candidates, overlap_threshold=0.5)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["score"], 0.9)
        self.assertEqual(len(removed), 1)

    def test_very_short_scenes_are_filtered(self):
        result = score_candidates(scene_analysis([{"start": 0, "end": 1, "duration": 1}], duration=2), {"segments": []})
        self.assertEqual(result["candidate_count"], 0)

    def test_long_scenes_are_capped_to_max_duration(self):
        config = HighlightScoringConfig(max_highlight_duration=30)
        result = score_candidates(
            scene_analysis([{"start": 0, "end": 90, "duration": 90}], duration=100),
            {"segments": [{"start": 40, "end": 45, "text": "nice", "confidence": 0.8}]},
            config=config,
        )
        self.assertLessEqual(result["candidates"][0]["duration"], 30)

    def test_missing_transcript_generates_scene_only_candidates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_path = Path(tmp_dir) / "scene_analysis.json"
            transcript_path = Path(tmp_dir) / "transcript.json"
            output_path = Path(tmp_dir) / "highlight_candidates.json"
            scene_path.write_text(json.dumps(scene_analysis([{"start": 5, "end": 15, "duration": 10}])), encoding="utf-8")

            result = generate_highlight_candidates(scene_path, transcript_path, output_path, job_id=7)

        self.assertTrue(result["transcript_missing"])
        self.assertEqual(result["job_id"], 7)
        self.assertGreaterEqual(result["candidate_count"], 1)

    def test_malformed_analysis_json_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_path = Path(tmp_dir) / "scene_analysis.json"
            transcript_path = Path(tmp_dir) / "transcript.json"
            output_path = Path(tmp_dir) / "highlight_candidates.json"
            scene_path.write_text("{bad json", encoding="utf-8")
            transcript_path.write_text('{"segments":[]}', encoding="utf-8")

            with self.assertRaises(HighlightScoringError):
                generate_highlight_candidates(scene_path, transcript_path, output_path)

    def test_no_strong_candidates_is_empty_not_crash(self):
        config = HighlightScoringConfig(minimum_score=0.95)
        result = score_candidates(
            scene_analysis([{"start": 0, "end": 8, "duration": 8}]),
            {"segments": []},
            config=config,
        )
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["highest_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
