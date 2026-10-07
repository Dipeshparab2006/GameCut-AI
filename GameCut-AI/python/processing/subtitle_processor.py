from html import escape


def _format_srt_time(seconds):
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    if milliseconds >= 1000:
        whole_seconds += 1
        milliseconds -= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def map_transcript_to_clips(clips, transcript_segments, max_chars=42, playback_speed=1.0):
    """Map source transcript timing onto the final, concatenated timeline.

    A clip rendered at 2x speed must have its caption timestamps compressed by
    the same factor; without this, captions drift after every cut.
    """
    try:
        playback_speed = float(playback_speed)
    except (TypeError, ValueError) as exc:
        raise ValueError("Playback speed must be numeric.") from exc
    if not 0.25 <= playback_speed <= 8.0:
        raise ValueError("Playback speed must be between 0.25x and 8x.")

    mapped = []
    output_offset = 0.0

    for clip in clips:
        clip_start = float(clip["start"])
        clip_end = float(clip["end"])
        clip_duration = max(0.0, clip_end - clip_start)

        for segment in transcript_segments or []:
            seg_start = float(segment.get("start", 0))
            seg_end = float(segment.get("end", 0))
            text = " ".join(str(segment.get("text", "")).split())
            if not text or seg_end <= clip_start or seg_start >= clip_end:
                continue

            start = output_offset + (max(seg_start, clip_start) - clip_start) / playback_speed
            end = output_offset + (min(seg_end, clip_end) - clip_start) / playback_speed
            if end <= start:
                continue

            mapped.append({"start": round(start, 3), "end": round(end, 3), "text": _wrap_text(text, max_chars)})

        output_offset += clip_duration / playback_speed

    return sorted(mapped, key=lambda item: (item["start"], item["end"]))


def _wrap_text(text, max_chars):
    words = text.split()
    lines = []
    current = []
    for word in words:
        candidate = " ".join(current + [word])
        if len(candidate) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines[:2])


def write_srt(segments, output_path):
    with open(output_path, "w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, start=1):
            start = float(segment["start"])
            end = float(segment["end"])
            if end <= start:
                continue
            text = escape(segment["text"], quote=False)
            handle.write(f"{index}\n")
            handle.write(f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n")
            handle.write(f"{text}\n\n")
    return output_path
