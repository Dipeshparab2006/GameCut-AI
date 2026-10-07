"""Game-agnostic montage event selection from existing analysis signals."""

def _impact(candidate):
    signals = candidate.get("signals", {}) or {}
    return round(float(candidate.get("score", 0)) * .55 + float(signals.get("audio", 0)) * .18 + float(signals.get("visual", 0)) * .17 + float(signals.get("speech", 0)) * .10, 4)

def _overlap(a, b):
    return max(0.0, min(float(a["end"]), float(b["end"])) - max(float(a["start"]), float(b["start"])))

def detect_montage_events(candidates, video_duration, max_events=12, minimum_gap=1.0):
    """Rank distinct action/reaction moments and return them chronologically."""
    ranked = []
    for candidate in candidates or []:
        try: start, end = float(candidate["start"]), float(candidate["end"])
        except (KeyError, TypeError, ValueError): continue
        if start < 0 or end <= start or end > float(video_duration): continue
        item = dict(candidate, montage_score=_impact(candidate), montage_reason="high-impact montage moment")
        ranked.append(item)
    selected = []
    for item in sorted(ranked, key=lambda value: value["montage_score"], reverse=True):
        if any(_overlap(item, kept) > 0 or abs(item["start"] - kept["end"]) < minimum_gap or abs(kept["start"] - item["end"]) < minimum_gap for kept in selected): continue
        selected.append(item)
        if len(selected) >= max_events: break
    return sorted(selected, key=lambda value: value["start"])
