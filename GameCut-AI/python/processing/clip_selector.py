def _duration(clip):
    return max(0.0, float(clip["end"]) - float(clip["start"]))


def _overlap(a, b):
    return max(0.0, min(float(a["end"]), float(b["end"])) - max(float(a["start"]), float(b["start"])))


def select_final_clips(candidates, target_duration=45, min_duration=3, max_duration=30, overlap_threshold=0.5):
    # The worker accepts a requested final duration from the product layer.
    # Do not silently cap long-form edits here; callers can still apply their
    # own product quota before queueing the job.
    target_duration = max(float(min_duration), float(target_duration))
    valid = []
    for candidate in candidates:
        try:
            start = float(candidate["start"])
            end = float(candidate["end"])
        except (KeyError, TypeError, ValueError):
            continue
        duration = end - start
        if start < 0 or duration < min_duration:
            continue
        if duration > max_duration:
            end = start + max_duration
            duration = max_duration
        item = dict(candidate)
        item.update({"start": round(start, 3), "end": round(end, 3), "duration": round(duration, 3)})
        valid.append(item)

    selected = []
    total = 0.0
    for candidate in sorted(valid, key=lambda item: float(item.get("score", 0)), reverse=True):
        # The plan validator and concat renderer require *strictly*
        # non-overlapping source ranges.  Keeping a fractional threshold here
        # produced plans that could pass selection but fail validation later.
        if any(_overlap(candidate, kept) > 0 for kept in selected):
            continue
        if total >= target_duration:
            break
        remaining = target_duration - total
        if candidate["duration"] > remaining:
            if selected and remaining < min_duration:
                continue
            candidate = dict(candidate)
            candidate["end"] = round(candidate["start"] + remaining, 3)
            candidate["duration"] = round(remaining, 3)
        selected.append(candidate)
        total += candidate["duration"]

    return sorted(selected, key=lambda item: item["start"])
