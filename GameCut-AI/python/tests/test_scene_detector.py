import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.scene_detector import (
    VideoValidationError,
    analyze_video_scenes,
    detect_scenes,
    validate_video,
)


VALID_METADATA = {
    "format": {
        "duration": "10.0",
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "size": "1000",
    },
    "streams": [{"codec_type": "video"}],
}


def timecode(seconds):
    mock = Mock()
    mock.get_seconds.return_value = seconds
    return mock


class SceneDetectorTestCase(unittest.TestCase):
    def test_missing_video_fails_validation(self):
        with self.assertRaises(VideoValidationError):
            validate_video("missing.mp4")

    def test_invalid_extension_fails_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as handle:
            with self.assertRaises(VideoValidationError):
                validate_video(handle.name)

    @patch("detection.scene_detector.get_metadata", return_value=VALID_METADATA)
    @patch(
        "detection.scene_detector.detect",
        return_value=[(timecode(0), timecode(3.5)), (timecode(3.5), timecode(10))],
    )
    def test_detect_scenes_returns_structured_seconds(self, _detect_mock, _metadata_mock):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            scenes = detect_scenes(handle.name)

        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0], {"start": 0.0, "end": 3.5, "duration": 3.5})
        self.assertEqual(scenes[1], {"start": 3.5, "end": 10.0, "duration": 6.5})

    @patch("detection.scene_detector.get_metadata", return_value=VALID_METADATA)
    @patch("detection.scene_detector.detect", return_value=[])
    def test_analyze_writes_json_with_full_video_fallback(self, _detect_mock, _metadata_mock):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "valid.mp4"
            output_path = Path(tmp_dir) / "scene_analysis.json"
            video_path.write_bytes(b"fake")

            result = analyze_video_scenes(str(video_path), output_path)
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["scene_count"], 1)
        self.assertEqual(saved["scenes"][0]["start"], 0.0)
        self.assertEqual(saved["scenes"][0]["end"], 10.0)


if __name__ == "__main__":
    unittest.main()
