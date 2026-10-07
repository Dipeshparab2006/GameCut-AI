import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from processing.subtitle_processor import map_transcript_to_clips, write_srt
from utils.ffmpeg import get_metadata, get_optimized_encoder_args, run_command
from utils.binaries import ffmpeg_binary


logger = logging.getLogger("gamecut.clip_renderer")


class RenderError(RuntimeError):
    pass


VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920


def _has_audio_stream(metadata):
    return any(stream.get("codec_type") == "audio" for stream in metadata.get("streams", []))


def _video_stream(metadata):
    for stream in metadata.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def _safe_subtitle_path(path):
    safe = os.path.abspath(path).replace("\\", "/")
    if len(safe) > 1 and safe[1] == ":":
        safe = safe[0] + "\\:" + safe[2:]
    return safe.replace("'", "\\'")


def validate_output(output_path):
    path = Path(output_path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RenderError("Output file was not created")

    metadata = get_metadata(str(path))
    if not metadata:
        raise RenderError("Output metadata could not be read")

    video = _video_stream(metadata)
    if not video:
        raise RenderError("Output does not contain a video stream")

    duration = float(metadata.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise RenderError("Output duration is invalid")

    return {
        "duration": round(duration, 3),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "video_codec": video.get("codec_name"),
        "audio": _has_audio_stream(metadata),
        "size": path.stat().st_size,
    }


def validate_vertical_output(output_path):
    """Validate the public short-format contract after the final render."""
    validation = validate_output(output_path)
    if (validation["width"], validation["height"]) != (VERTICAL_WIDTH, VERTICAL_HEIGHT):
        raise RenderError(
            "Output must be a 1080x1920 vertical video; "
            f"received {validation['width']}x{validation['height']}"
        )
    return validation


def _run_or_raise(command, label):
    ok, output = run_command(command)
    if not ok:
        raise RenderError(f"{label} failed: {output[:500]}")


def _atempo_filter(playback_speed):
    """Build FFmpeg's bounded atempo filter chain for 0.25x-8x playback."""
    remaining = float(playback_speed)
    factors = []
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _validated_playback_speed(playback_speed):
    try:
        speed = float(playback_speed)
    except (TypeError, ValueError) as exc:
        raise RenderError("Playback speed must be numeric") from exc
    if not 0.25 <= speed <= 8.0:
        raise RenderError("Playback speed must be between 0.25x and 8x")
    return speed


def _trim_clip(source_path, clip, output_path, has_audio, playback_speed=1.0):
    duration = float(clip["end"]) - float(clip["start"])
    if duration <= 0:
        raise RenderError("Clip duration must be positive")

    speed = _validated_playback_speed(playback_speed)
    vf = (
        f"scale={VERTICAL_WIDTH}:{VERTICAL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VERTICAL_WIDTH}:{VERTICAL_HEIGHT},setsar=1,fps=30"
    )
    if speed != 1.0:
        vf += f",setpts={1.0 / speed:.6f}*PTS"

    encoder_args = get_optimized_encoder_args()
    command = [
        ffmpeg_binary(),
        "-y",
        "-ss",
        str(float(clip["start"])),
        "-t",
        str(duration),
        "-i",
        str(source_path),
        "-vf",
        vf,
        *encoder_args,
    ]
    if has_audio:
        audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"
        if speed != 1.0:
            audio_filter += "," + _atempo_filter(speed)
        command += ["-c:a", "aac", "-b:a", "128k", "-af", audio_filter]
    else:
        command += ["-an"]
    command.append(str(output_path))
    _run_or_raise(command, "Clip render")


def _concat_clips(clip_paths, output_path):
    list_path = Path(output_path).with_name("concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as handle:
        for clip_path in clip_paths:
            handle.write("file '{}'\n".format(str(Path(clip_path).resolve()).replace("\\", "/").replace("'", "'\\''")))

    command = [
        ffmpeg_binary(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_or_raise(command, "Clip concat")


def _burn_subtitles(input_path, srt_path, output_path, has_audio):
    vf = (
        "subtitles='{}':force_style="
        "'FontName=Arial,FontSize=42,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
        "Alignment=2,MarginV=190'"
    ).format(_safe_subtitle_path(srt_path))
    encoder_args = get_optimized_encoder_args()
    command = [
        ffmpeg_binary(),
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        *encoder_args,
    ]
    if has_audio:
        command += ["-c:a", "copy"]
    else:
        command += ["-an"]
    command += ["-movflags", "+faststart"]
    command.append(str(output_path))
    _run_or_raise(command, "Subtitle burn")


def generate_thumbnail(video_path, output_path):
    command = [
        ffmpeg_binary(),
        "-y",
        "-ss",
        "1",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(output_path),
    ]
    _run_or_raise(command, "Thumbnail generation")
    return output_path


def _max_parallel_clips():
    """Return the number of clips to render in parallel.

    Hardware encoders typically have a limited session count (NVENC allows ~3-5),
    so we cap concurrency.  CPU encoding benefits from FFmpeg's internal
    threading, so parallelism is kept modest to avoid over-subscription.
    """
    try:
        value = int(os.getenv("GAMECUT_RENDER_PARALLEL_CLIPS", "3"))
    except (TypeError, ValueError):
        value = 3
    return max(1, min(8, value))


def render_highlight_video(
    source_path,
    clips,
    transcript_segments,
    output_path,
    work_dir,
    subtitles=True,
    playback_speed=1.0,
):
    """Render a publishable 9:16 short, burning captions when speech exists.

    Clips are trimmed in parallel (up to GAMECUT_RENDER_PARALLEL_CLIPS workers)
    using the best available hardware encoder, then concatenated and optionally
    subtitled.
    """
    metadata = get_metadata(str(source_path))
    if not metadata:
        raise RenderError("Source metadata could not be read")
    has_audio = _has_audio_stream(metadata)
    speed = _validated_playback_speed(playback_speed)

    work = Path(work_dir)
    clips_dir = work / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # --- Parallel clip trimming ---
    clip_tasks = []
    for index, clip in enumerate(clips, start=1):
        clip_path = clips_dir / f"clip_{index:02d}.mp4"
        clip_tasks.append((index, clip, clip_path))

    max_workers = min(_max_parallel_clips(), len(clip_tasks))
    rendered_clips = [None] * len(clip_tasks)
    errors = []

    if max_workers > 1 and len(clip_tasks) > 1:
        logger.info("Rendering %d clips in parallel (max_workers=%d)", len(clip_tasks), max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {}
            for idx_zero, (index, clip, clip_path) in enumerate(clip_tasks):
                future = pool.submit(_trim_clip, source_path, clip, clip_path, has_audio, speed)
                future_to_idx[future] = (idx_zero, clip_path)
            for future in as_completed(future_to_idx):
                idx_zero, clip_path = future_to_idx[future]
                exc = future.exception()
                if exc:
                    errors.append(str(exc))
                else:
                    rendered_clips[idx_zero] = clip_path
    else:
        for idx_zero, (index, clip, clip_path) in enumerate(clip_tasks):
            _trim_clip(source_path, clip, clip_path, has_audio, speed)
            rendered_clips[idx_zero] = clip_path

    if errors:
        raise RenderError(f"Clip rendering failed: {'; '.join(errors[:3])}")

    concat_path = work / "concat.mp4"
    _concat_clips(rendered_clips, concat_path)

    final_input = concat_path
    srt_path = None
    if subtitles and transcript_segments:
        mapped = map_transcript_to_clips(clips, transcript_segments, playback_speed=speed)
        if mapped:
            srt_path = work / "subtitles.srt"
            write_srt(mapped, srt_path)
            subtitled_path = work / "subtitled.mp4"
            _burn_subtitles(concat_path, srt_path, subtitled_path, has_audio)
            final_input = subtitled_path

    shutil.copy2(final_input, output)
    validation = validate_vertical_output(output)
    thumbnail_path = output.with_name(output.stem + "_thumbnail.jpg")
    generate_thumbnail(output, thumbnail_path)

    return {
        "output_path": str(output),
        "thumbnail_path": str(thumbnail_path),
        "metadata": validation,
        "subtitles": bool(srt_path),
        "clips": clips,
        "output_format": {"width": VERTICAL_WIDTH, "height": VERTICAL_HEIGHT, "aspect_ratio": "9:16"},
    }


def write_render_manifest(result, output_path):
    Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
