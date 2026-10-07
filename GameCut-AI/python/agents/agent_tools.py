import json
from pathlib import Path

from processing.clip_selector import select_final_clips


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def get_highlight_candidates(job_dir):
    data = load_json(Path(job_dir) / "highlight_candidates.json", {"candidates": [], "video_duration": 0})
    return data or {"candidates": [], "video_duration": 0}


def get_transcript(job_dir):
    data = load_json(Path(job_dir) / "transcript.json", {"segments": []})
    if isinstance(data, list):
        return {"segments": data}
    return data or {"segments": []}


def create_deterministic_plan(context, preferences):
    candidates = context.get("candidates", [])
    # Fast/slow motion must cover the complete uploaded timeline.  Do not pass
    # this through highlight selection, which intentionally caps clips and can
    # reduce a full video to a short moment.
    if preferences.motion_mode in {"fast_motion", "slow_motion"}:
        duration = float(context.get("video_duration") or 0)
        selected = [{
            "start": 0.0,
            "end": duration,
            "score": 1.0,
            "reason": "Full-video motion effect",
        }] if duration > 0 else []
    else:
        selection_duration = preferences.source_selection_duration
        if selection_duration is None:
            selection_duration = preferences.target_duration
        selected = select_final_clips(candidates, target_duration=selection_duration)
    return {
        "target_duration": float(preferences.target_duration),
        "aspect_ratio": preferences.aspect_ratio,
        "clips": [
            {
                "start": clip["start"],
                "end": clip["end"],
                "score": clip.get("score"),
                "reason": "; ".join(clip.get("reason", [])) if isinstance(clip.get("reason"), list) else clip.get("reason", "selected candidate"),
            }
            for clip in selected
        ],
        "subtitles": bool(preferences.subtitles),
        "thumbnail": bool(preferences.thumbnail),
        "provider": "deterministic",
        "style": preferences.style,
        "motion_mode": preferences.motion_mode,
        "speed": float(preferences.speed),
    }
