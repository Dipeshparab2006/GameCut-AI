from agents.schemas import plan_to_dict


class PlanValidationError(ValueError):
    pass


def validate_editing_plan(plan, video_duration):
    normalized = plan_to_dict(plan or {})
    try:
        video_duration = float(video_duration)
        target_duration = float(normalized["target_duration"])
    except (TypeError, ValueError) as exc:
        raise PlanValidationError("Plan duration values must be numeric.") from exc

    if video_duration <= 0:
        raise PlanValidationError("Video duration must be greater than zero.")
    if target_duration <= 0:
        raise PlanValidationError("Target duration must be greater than zero.")
    try:
        speed = float(normalized.get("speed", 1.0))
    except (TypeError, ValueError) as exc:
        raise PlanValidationError("Playback speed must be numeric.") from exc
    if not 0.25 <= speed <= 8.0:
        raise PlanValidationError("Playback speed must be between 0.25x and 8x.")

    clips = []
    for index, clip in enumerate(normalized["clips"]):
        try:
            start = float(clip["start"])
            end = float(clip["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanValidationError(f"Clip {index + 1} must include numeric start and end values.") from exc

        if start < 0 or end > video_duration:
            raise PlanValidationError(f"Clip {index + 1} is outside the source video duration.")
        if start >= end:
            raise PlanValidationError(f"Clip {index + 1} has invalid timestamps.")

        clean_clip = dict(clip)
        clean_clip["start"] = start
        clean_clip["end"] = end
        clean_clip["duration"] = round(end - start, 3)
        clips.append(clean_clip)

    clips.sort(key=lambda item: item["start"])
    for previous, current in zip(clips, clips[1:]):
        if current["start"] < previous["end"]:
            raise PlanValidationError("Editing plan clips must not overlap.")

    normalized["target_duration"] = target_duration
    normalized["speed"] = speed
    normalized["clips"] = clips
    return normalized


def validate_and_constrain_agent_clips(agent_clips, candidates, video_duration, tolerance=1.5):
    """
    Validates agent-selected clips and constrains them to the known candidates.

    - Ensures timestamps are valid (start < end, within video duration).
    - Matches agent clips to the original candidates to prevent hallucination.
    - Rejects overlapping clips.
    - Returns a clean list of valid, non-overlapping clips.
    """
    valid_clips = []
    candidate_map = {f"{c['start']:.2f}-{c['end']:.2f}": c for c in candidates}

    def _is_overlapping(clip1, clip2):
        """Checks if two clips overlap."""
        # Using a small negative tolerance to allow clips that are perfectly adjacent
        return max(clip1['start'], clip2['start']) < min(clip1['end'], clip2['end']) - 0.1

    temp_clips = []

    for clip in agent_clips:
        start, end = clip.get("start"), clip.get("end")

        # 1. Basic validation
        if start is None or end is None:
            print(f"Validation failed: Clip missing start/end. {clip}")
            continue
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            print(f"Validation failed: Timestamps are not numbers. {clip}")
            continue
        if start >= end:
            print(f"Validation failed: Start time >= end time. {clip}")
            continue
        if start < 0 or end > video_duration:
            print(f"Validation failed: Timestamps out of bounds. {clip}")
            continue

        # 2. Constrain to a known candidate
        matching_candidate = None
        for candidate in candidates:
            # Check if the agent's selection is within a tolerance range of a known candidate
            starts_close = abs(start - candidate["start"]) <= tolerance
            ends_close = abs(end - candidate["end"]) <= tolerance
            if starts_close and ends_close:
                matching_candidate = candidate
                break
        
        if not matching_candidate:
            print(f"Validation failed: Agent clip {start}-{end} does not match any candidate.")
            continue

        # 3. Add reason and prepare for final list
        constrained_clip = dict(matching_candidate)
        constrained_clip["reason"] = clip.get("reason", "Selected by AI agent.")
        
        # Set a high score to prioritize agent's choice over others if mixing later
        constrained_clip["score"] = 1.0 

        temp_clips.append(constrained_clip)

    # 4. Sort by start time and remove overlaps
    sorted_clips = sorted(temp_clips, key=lambda x: x['start'])
    for clip in sorted_clips:
        if any(_is_overlapping(clip, existing_clip) for existing_clip in valid_clips):
            print(f"Validation failed: Agent clip {clip['start']}-{clip['end']} overlaps with another selected clip. Discarding.")
            continue
        valid_clips.append(clip)

    return valid_clips
