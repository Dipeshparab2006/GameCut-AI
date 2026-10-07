import json
import os
import time
from pathlib import Path

from scenedetect import ContentDetector, detect

from utils.ffmpeg import get_metadata


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


class VideoValidationError(ValueError):
    pass


def _round_seconds(value):
    return round(float(value), 3)


def _duration_from_metadata(metadata):
    try:
        return float(metadata.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_video_stream(metadata):
    return any(stream.get("codec_type") == "video" for stream in metadata.get("streams", []))


def validate_video(video_path):
    path = Path(video_path)
    if not path.is_file():
        raise VideoValidationError("Video file does not exist")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError("Unsupported video file type")

    if not os.access(path, os.R_OK):
        raise VideoValidationError("Video file is not readable")

    metadata = get_metadata(str(path))
    if not metadata:
        raise VideoValidationError("Video metadata could not be read")

    if not _has_video_stream(metadata):
        raise VideoValidationError("File does not contain a video stream")

    duration = _duration_from_metadata(metadata)
    if duration <= 0:
        raise VideoValidationError("Video duration must be greater than zero")

    return metadata, duration


def _detect_scene_boundaries(video_path, duration, threshold, min_scene_len):
    scene_list = detect(
        video_path,
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
    )

    scenes = []
    for start_time, end_time in scene_list:
        start = _round_seconds(start_time.get_seconds())
        end = _round_seconds(end_time.get_seconds())
        if end <= start:
            continue
        scenes.append(
            {
                "start": start,
                "end": end,
                "duration": _round_seconds(end - start),
            }
        )

    if not scenes:
        scenes.append(
            {
                "start": 0.0,
                "end": _round_seconds(duration),
                "duration": _round_seconds(duration),
            }
        )

    return scenes


def detect_scenes(video_path, threshold=30.0, min_scene_len=15):
    """
    Detect scene boundaries and return seconds-based scene dictionaries.
    """
    _, duration = validate_video(video_path)
    return _detect_scene_boundaries(video_path, duration, threshold, min_scene_len)


def analyze_video_scenes(video_path, output_path, threshold=30.0, min_scene_len=15):
    started = time.perf_counter()
    metadata, duration = validate_video(video_path)
    scenes = _detect_scene_boundaries(video_path, duration, threshold, min_scene_len)

    result = {
        "video": str(video_path),
        "duration": _round_seconds(duration),
        "scene_count": len(scenes),
        "scenes": scenes,
        "metadata": {
            "format_name": metadata.get("format", {}).get("format_name"),
            "size": int(metadata.get("format", {}).get("size") or 0),
        },
        "processing_time_seconds": _round_seconds(time.perf_counter() - started),
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
