import json
from .providers import get_provider
from .validator import validate_and_constrain_agent_clips

def build_agent_prompt(candidates, transcript, video_duration, target_duration=45):
    """
    Formats the structured analysis data into a prompt for the LLM.
    """
    prompt_data = {
        "video_duration": video_duration,
        "target_highlight_duration": target_duration,
        "total_candidates": len(candidates),
        "candidates": []
    }

    for i, clip in enumerate(candidates):
        # Find speech segments that overlap with this clip
        clip_speech = []
        for seg in transcript:
            if clip['start'] <= seg['start'] <= clip['end'] or clip['start'] <= seg['end'] <= clip['end']:
                clip_speech.append(seg.get('text', '').strip())

        prompt_data["candidates"].append({
            "index": i + 1,
            "start": clip['start'],
            "end": clip['end'],
            "duration": round(clip['end'] - clip['start'], 2),
            "score": clip['score'],
            "speech": " | ".join(clip_speech) if clip_speech else "(no speech detected)"
        })

    prompt = f"""Analyze these candidate highlights from a {video_duration:.0f}-second gameplay video.

Select the best 3-5 clips for a 30-60 second highlight reel.

Candidate data:
{json.dumps(prompt_data, indent=2)}

Remember: respond with valid JSON only."""

    return prompt

def parse_agent_response(response_text):
    """
    Parses the LLM's JSON response into a clip selection.
    """
    try:
        # Try to extract JSON from the response (LLMs sometimes wrap it in markdown)
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        clips = data.get("selected_clips", [])

        if not clips:
            return None

        # Validate each clip has start/end
        valid_clips = []
        for clip in clips:
            # Basic check, more thorough validation happens later
            if isinstance(clip, dict) and "start" in clip and "end" in clip:
                valid_clips.append({
                    "start": float(clip["start"]),
                    "end": float(clip["end"]),
                    "reason": clip.get("reason", "")
                })

        print(f"Agent reasoning: {data.get('reasoning', 'N/A')}")
        return valid_clips

    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        print(f"Failed to parse agent response: {e}")
        print(f"Raw response: {response_text}")
        return None

def agent_select_highlights(scored_candidates, transcript, video_duration=0, top_n=15, target_duration=45):
    """
    Main entry point. Sends top candidates to the LLM agent for intelligent selection.
    Falls back to deterministic selection if the LLM is unavailable.
    """
    # Sort by score descending and take the top N for the agent to reason over
    sorted_candidates = sorted(scored_candidates, key=lambda x: x['score'], reverse=True)[:top_n]

    prompt = build_agent_prompt(sorted_candidates, transcript, video_duration, target_duration)
    provider = get_provider()
    response_text = provider.generate(prompt)

    if not response_text:
        print("Agent did not provide a response. Falling back to deterministic selection.")
        return None

    agent_clips = parse_agent_response(response_text)
    if not agent_clips:
        print("Could not parse agent response. Falling back to deterministic selection.")
        return None

    # Validate and constrain the agent's choices against our known candidates
    final_clips = validate_and_constrain_agent_clips(agent_clips, sorted_candidates, video_duration)

    if not final_clips:
        print("Agent selection was invalid or empty after validation. Falling back.")
        return None

    print(f"Agent successfully selected {len(final_clips)} clips.")
    return final_clips