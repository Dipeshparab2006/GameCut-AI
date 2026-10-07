import json
import os
import time
from pathlib import Path

from agents.agent_tools import create_deterministic_plan, get_highlight_candidates, get_transcript
from agents.schemas import AgentPreferences
from agents.validator import validate_editing_plan


class AgentError(RuntimeError):
    pass


class LLMProvider:
    name = "base"

    def generate_editing_plan(self, context, preferences):
        raise NotImplementedError


class DeterministicProvider(LLMProvider):
    name = "deterministic"

    def generate_editing_plan(self, context, preferences):
        return create_deterministic_plan(context, preferences)


def provider_from_env():
    provider = os.getenv("GAMECUT_AGENT_PROVIDER", "deterministic").strip().lower()
    if provider in {"", "deterministic", "mock"}:
        return DeterministicProvider()
    raise AgentError(f"Configured agent provider is unavailable: {provider}")


def build_agent_context(job_dir):
    candidates_data = get_highlight_candidates(job_dir)
    transcript = get_transcript(job_dir)
    return {
        "video_duration": float(candidates_data.get("video_duration") or 0),
        "candidates": candidates_data.get("candidates", []),
        "transcript_segments": transcript.get("segments", [])[:80],
        "candidate_count": len(candidates_data.get("candidates", [])),
    }


def generate_validated_plan(job_dir, preferences=None, provider=None):
    started = time.perf_counter()
    preferences = preferences or AgentPreferences()
    provider = provider or provider_from_env()
    context = build_agent_context(job_dir)
    plan = provider.generate_editing_plan(context, preferences)
    validated = validate_editing_plan(plan, context["video_duration"])
    validated["agent"] = {
        "provider": provider.name,
        "fallback_used": provider.name == "deterministic",
        "processing_time_seconds": round(time.perf_counter() - started, 3),
    }

    output_path = Path(job_dir) / "editing_plan.json"
    output_path.write_text(json.dumps(validated, indent=2), encoding="utf-8")
    return validated
