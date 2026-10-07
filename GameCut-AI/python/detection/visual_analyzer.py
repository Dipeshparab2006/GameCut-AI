import json
import time
from dataclasses import dataclass
from pathlib import Path


try:
    import cv2
except ImportError:
    cv2 = None


class VisualAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualAnalysisConfig:
    samples_per_region: int = 8
    frame_width: int = 160
    frame_height: int = 90
    max_regions: int = 80


def config_from_env():
    import os

    return VisualAnalysisConfig(
        samples_per_region=int(os.getenv("GAMECUT_VISUAL_SAMPLES_PER_REGION", "8")),
        frame_width=int(os.getenv("GAMECUT_VISUAL_FRAME_WIDTH", "160")),
        frame_height=int(os.getenv("GAMECUT_VISUAL_FRAME_HEIGHT", "90")),
        max_regions=int(os.getenv("GAMECUT_VISUAL_MAX_REGIONS", "80")),
    )


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def _sample_region(cap, fps, start, end, config):
    if cv2 is None:
        raise VisualAnalysisError("OpenCV is not installed")

    duration = end - start
    if duration <= 0:
        return {"activity_raw": 0.0, "transition_raw": 0.0, "brightness_change_raw": 0.0, "samples": 0}

    sample_count = max(2, config.samples_per_region)
    times = [start + ((duration * i) / (sample_count - 1)) for i in range(sample_count)]
    previous = None
    diffs = []
    brightness = []
    samples = 0

    for timestamp in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (config.frame_width, config.frame_height))
        brightness.append(float(small.mean()) / 255.0)
        samples += 1

        if previous is not None:
            diff = cv2.absdiff(small, previous)
            diffs.append(float(diff.mean()) / 255.0)
        previous = small

    if not diffs:
        return {"activity_raw": 0.0, "transition_raw": 0.0, "brightness_change_raw": 0.0, "samples": samples}

    return {
        "activity_raw": sum(diffs) / len(diffs),
        "transition_raw": max(diffs),
        "brightness_change_raw": max(brightness) - min(brightness) if brightness else 0.0,
        "samples": samples,
    }


def _normalize_regions(regions):
    max_activity = max((item["visual"]["activity_raw"] for item in regions), default=0.0) or 1.0
    max_transition = max((item["visual"]["transition_raw"] for item in regions), default=0.0) or 1.0
    max_brightness = max((item["visual"]["brightness_change_raw"] for item in regions), default=0.0) or 1.0

    for item in regions:
        visual = item["visual"]
        visual["activity"] = round(_clamp(visual.pop("activity_raw") / max_activity), 3)
        visual["transition"] = round(_clamp(visual.pop("transition_raw") / max_transition), 3)
        visual["brightness_change"] = round(_clamp(visual.pop("brightness_change_raw") / max_brightness), 3)
        visual["score"] = round(
            _clamp((visual["activity"] * 0.55) + (visual["transition"] * 0.30) + (visual["brightness_change"] * 0.15)),
            3,
        )
    return regions


def analyze_visual_regions(video_path, regions, output_path=None, config=None, job_id=None):
    if cv2 is None:
        raise VisualAnalysisError("OpenCV is not installed")

    config = config or VisualAnalysisConfig()
    started = time.perf_counter()
    selected_regions = list(regions)[: config.max_regions]
    analyzed = []
    errors = []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VisualAnalysisError("Video could not be opened for visual analysis")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        for index, region in enumerate(selected_regions):
            start = _as_float(region.get("start"))
            end = _as_float(region.get("end"))
            if end <= start:
                continue
            try:
                stats = _sample_region(cap, fps, start, end, config)
                analyzed.append(
                    {
                        "index": index,
                        "start": round(start, 3),
                        "end": round(end, 3),
                        "duration": round(end - start, 3),
                        "visual": stats,
                    }
                )
            except VisualAnalysisError as exc:
                errors.append({"index": index, "start": start, "end": end, "error": str(exc)[:300]})
    finally:
        cap.release()

    result = {
        "job_id": job_id,
        "video": str(video_path),
        "region_count": len(selected_regions),
        "analyzed_count": len(analyzed),
        "failed_count": len(errors),
        "errors": errors,
        "regions": _normalize_regions(analyzed),
        "processing_time_seconds": round(time.perf_counter() - started, 3),
    }

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def analyze_visual_activity(video_path, sample_rate_fps=1):
    """
    Backward-compatible wrapper for older tests/imports.
    """
    cap = cv2.VideoCapture(str(video_path)) if cv2 else None
    if cap is None or not cap.isOpened():
        return []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frame_count / fps if fps else 0
    finally:
        cap.release()
    result = analyze_visual_regions(video_path, [{"start": 0.0, "end": duration}], config=VisualAnalysisConfig(samples_per_region=max(2, int(duration * sample_rate_fps))))
    return [{"time": item["start"], "activity": item["visual"]["activity"]} for item in result["regions"]]
