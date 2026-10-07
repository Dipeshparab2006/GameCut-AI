"""Deterministic Basic Auto Editor (Phase 13).

This module deliberately contains no agent or website concerns.  It validates a
small edit plan, adds context padding, renders normalized clips, concatenates
them, validates the result, and creates one thumbnail.
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agents.validator import PlanValidationError, validate_editing_plan
from processing.clip_renderer import generate_thumbnail, validate_output
from utils.ffmpeg import get_metadata, get_optimized_encoder_args, run_command
from utils.binaries import ffmpeg_binary


logger = logging.getLogger("gamecut.basic_editor")


class BasicEditorError(RuntimeError):
    pass


def build_basic_plan(candidates, video_duration, target_duration=45,
                     padding_before=2.0, padding_after=3.0, style="Esports", speed=None):
    """Create a chronological, padded plan from scored candidates."""
    duration = float(video_duration)
    target = max(1.0, float(target_duration))
    motion = motion_settings(style, speed)

    # Motion modes are timeline effects, not highlight-selection modes.  Keep
    # the complete source range so Fast Motion and Slow Motion affect every
    # frame of the uploaded video instead of only one AI-selected moment.
    if motion["mode"] != "normal":
        return {
            "target_duration": target,
            "clips": [{
                "start": 0.0,
                "end": duration,
                "score": 1.0,
                "reason": "Full-video motion effect",
            }],
            "style": style,
            "motion_mode": motion["mode"],
            "speed": motion["speed"],
            "output": {"format": "mp4", "resolution": "source"},
            "subtitles": False,
        }

    # Select enough source material for the requested final duration. Fast
    # motion can therefore use more moments while still producing a short reel.
    selection_target = target / motion["speed"]
    before, after = max(0.0, float(padding_before)), max(0.0, float(padding_after))
    valid = []
    for candidate in candidates or []:
        try:
            start = max(0.0, float(candidate["start"]) - before)
            end = min(duration, float(candidate["end"]) + after)
            score = float(candidate.get("score", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if end > start:
            item = dict(candidate, start=start, end=end, score=score)
            valid.append(item)

    # Stronger candidates win when overlap is excessive; output remains chronological.
    selected = []
    for candidate in sorted(valid, key=lambda item: item["score"], reverse=True):
        overlap = False
        for kept in selected:
            shared = max(0.0, min(candidate["end"], kept["end"]) - max(candidate["start"], kept["start"]))
            # The renderer/plan validator requires strictly non-overlapping ranges.
            # Padding can create even small overlaps, so resolve every overlap here.
            if shared > 0:
                overlap = True
                break
        current_total = sum(x["end"] - x["start"] for x in selected)
        if overlap or current_total >= selection_target:
            continue
        if current_total + (candidate["end"] - candidate["start"]) > selection_target:
            allowed_end = candidate["start"] + (selection_target - current_total)
            if allowed_end - candidate["start"] < 3:
                continue
            candidate = dict(candidate, end=allowed_end)
        if current_total < selection_target or not selected:
            selected.append(candidate)
    selected.sort(key=lambda item: item["start"])
    return {"target_duration": target, "clips": selected, "style": style,
            "motion_mode": motion["mode"], "speed": motion["speed"],
            "output": {"format": "mp4", "resolution": "source"}, "subtitles": False}


def motion_settings(style, requested_speed=None):
    """Return the playback speed used by the basic editor."""
    value = str(style or "").lower().replace("-", " ")
    try:
        speed = float(requested_speed)
    except (TypeError, ValueError):
        speed = None
    if "slow motion" in value:
        return {"mode": "slow_motion", "speed": min(1.0, max(0.25, speed if speed is not None else 0.5))}
    if "fast motion" in value:
        return {"mode": "fast_motion", "speed": min(8.0, max(1.0, speed if speed is not None else 2.0))}
    return {"mode": "normal", "speed": 1.0}


def atempo_filter(speed):
    """Build an FFmpeg atempo chain; each atempo stage accepts 0.5x-2x."""
    remaining = float(speed)
    factors = []
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _run(command, label):
    ok, output = run_command(command)
    if not ok:
        raise BasicEditorError(f"{label} failed: {output[:500]}")


def generate_catchy_thumbnail(video_path, output_path, label="TOP PLAY"):
    """Create a branded YouTube/Instagram-friendly thumbnail from the output."""
    command = [ffmpeg_binary(), "-y", "-ss", "1", "-i", str(video_path), "-frames:v", "1",
               "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.16:t=fill,"
                      "drawbox=x=0:y=ih-150:w=iw:h=150:color=black@0.72:t=fill,"
                      "drawtext=text='GAMECUT AI':x=36:y=30:fontsize=28:fontcolor=white:borderw=2:bordercolor=black,"
                      f"drawtext=text='{label}':x=36:y=h-105:fontsize=58:fontcolor=white:borderw=4:bordercolor=black",
               "-q:v", "2", str(output_path)]
    ok, output = run_command(command)
    if not ok:
        generate_thumbnail(video_path, output_path)
    return output_path


def _max_parallel_clips():
    """Return the number of clips to render in parallel in basic mode."""
    try:
        value = int(os.getenv("GAMECUT_RENDER_PARALLEL_CLIPS", "3"))
    except (TypeError, ValueError):
        value = 3
    return max(1, min(8, value))


def _render_single_clip(source, clip, path, scale, speed, has_audio, encoder_args):
    """Render a single clip with the given encoder settings."""
    video_filter = scale
    audio_filter = None
    if speed != 1.0:
        video_filter += f",setpts={1.0 / speed:.6f}*PTS"
        audio_filter = atempo_filter(speed)
    command = [
        ffmpeg_binary(), "-y",
        "-ss", str(clip["start"]),
        "-t", str(clip["end"] - clip["start"]),
        "-i", str(source),
        "-vf", video_filter,
        *encoder_args,
    ]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "160k", "-af", audio_filter or "loudnorm=I=-16:TP=-1.5:LRA=11"]
    else:
        command += ["-an"]
    command.append(str(path))
    _run(command, "Clip render")


def render_basic_editor(source_path, plan, output_path, work_dir):
    source = Path(source_path).resolve()
    if not source.is_file():
        raise BasicEditorError("Source video does not exist")
    metadata = get_metadata(str(source))
    if not metadata:
        raise BasicEditorError("Source metadata could not be read")
    source_duration = float(metadata.get("format", {}).get("duration") or 0)
    try:
        clean_plan = validate_editing_plan(plan, source_duration)
    except PlanValidationError as exc:
        raise BasicEditorError(str(exc)) from exc
    if not clean_plan["clips"]:
        raise BasicEditorError("No suitable highlights were found")

    work = Path(work_dir); clips_dir = work / "clips"; clips_dir.mkdir(parents=True, exist_ok=True)
    has_audio = any(s.get("codec_type") == "audio" for s in metadata.get("streams", []))
    video = next(s for s in metadata["streams"] if s.get("codec_type") == "video")
    width = int(video.get("width") or 1280) // 2 * 2
    height = int(video.get("height") or 720) // 2 * 2
    scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    speed = float(clean_plan.get("speed", 1.0))
    encoder_args = get_optimized_encoder_args()

    # --- Build clip tasks ---
    clip_tasks = []
    for index, clip in enumerate(clean_plan["clips"], 1):
        path = clips_dir / f"clip_{index:02d}.mp4"
        clip_tasks.append((index, clip, path))

    max_workers = min(_max_parallel_clips(), len(clip_tasks))
    rendered = [None] * len(clip_tasks)
    errors = []

    if max_workers > 1 and len(clip_tasks) > 1:
        logger.info("Basic editor rendering %d clips in parallel (max_workers=%d)", len(clip_tasks), max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {}
            for idx_zero, (index, clip, path) in enumerate(clip_tasks):
                future = pool.submit(_render_single_clip, source, clip, path, scale, speed, has_audio, encoder_args)
                future_to_idx[future] = (idx_zero, path)
            for future in as_completed(future_to_idx):
                idx_zero, path = future_to_idx[future]
                exc = future.exception()
                if exc:
                    errors.append(str(exc))
                else:
                    rendered[idx_zero] = path
    else:
        for idx_zero, (index, clip, path) in enumerate(clip_tasks):
            _render_single_clip(source, clip, path, scale, speed, has_audio, encoder_args)
            rendered[idx_zero] = path

    if errors:
        raise BasicEditorError(f"Clip rendering failed: {'; '.join(errors[:3])}")

    list_path = work / "concat_list.txt"
    list_path.write_text("".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in rendered), encoding="utf-8")
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
    _run([ffmpeg_binary(), "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", "-movflags", "+faststart", str(output)], "Clip concat")
    result = validate_output(output)
    thumbnail = output.with_name(output.stem + "_thumbnail.jpg")
    generate_catchy_thumbnail(output, thumbnail, label=str(plan.get("thumbnail_label", "TOP PLAY")))
    return {"output_path": str(output), "thumbnail_path": str(thumbnail), "metadata": result, "clips": clean_plan["clips"], "subtitles": False}


def write_basic_manifest(result, path):
    Path(path).write_text(json.dumps(result, indent=2), encoding="utf-8")
