from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPreferences:
    target_duration: float = 45.0
    # `source_selection_duration` lets the planner account for playback speed
    # without misreporting the intended final duration in the editing plan.
    source_selection_duration: float | None = None
    aspect_ratio: str = "9:16"
    subtitles: bool = True
    thumbnail: bool = True
    style: str = "gaming_highlight"
    motion_mode: str = "normal"
    speed: float = 1.0


def plan_to_dict(plan):
    return {
        "target_duration": float(plan.get("target_duration", 45)),
        "aspect_ratio": str(plan.get("aspect_ratio", "9:16")),
        "clips": list(plan.get("clips", [])),
        "subtitles": bool(plan.get("subtitles", True)),
        "thumbnail": bool(plan.get("thumbnail", True)),
        "provider": plan.get("provider", "deterministic"),
        "style": str(plan.get("style", "Esports")),
        "motion_mode": str(plan.get("motion_mode", "normal")),
        "speed": plan.get("speed", 1.0),
    }
