import json
import os
from agents.highlight_agent import agent_select_highlights

def select_final_highlights(scored_clips, transcript, video_duration, target_duration=45, use_agent=True):
    """
    Selects the final clips for the highlight reel.
    It first tries to use the AI agent, and falls back to a deterministic approach if the agent fails.
    """
    final_clips = None

    if use_agent:
        print("Attempting to select highlights with AI Agent...")
        # The agent is expected to respect the target duration in its selection
        final_clips = agent_select_highlights(
            scored_candidates=scored_clips,
            transcript=transcript,
            video_duration=video_duration,
            target_duration=target_duration
        )

    # Fallback to deterministic selection if agent fails or is disabled
    if not final_clips:
        if use_agent:
            print("Agent selection failed or returned empty. Falling back to deterministic method.")
        else:
            print("Using deterministic highlight selection.")
        
        # Sort by score and pick until duration is met
        sorted_clips = sorted(scored_clips, key=lambda x: x['score'], reverse=True)
        return select_clips_by_duration(sorted_clips, target_duration)

    return sorted(final_clips, key=lambda x: x['start'])

def select_clips_by_duration(clips, target_duration=45):
    final_selection = []
    current_duration = 0
    
    for clip in clips:
        duration = clip['end'] - clip['start']
        if current_duration + duration <= target_duration + 5: 
            final_selection.append(clip)
            current_duration += duration
            
        if current_duration >= target_duration:
            break
            
    return sorted(final_selection, key=lambda x: x['start']) # Return sorted by timeline

def generate_editing_plan(final_clips, output_path, target_duration=45, aspect_ratio="9:16"):
    """
    Generates a JSON editing plan.
    """
    plan = {
        "target_duration": target_duration,
        "aspect_ratio": aspect_ratio,
        "clips": final_clips,
        "subtitles": True
    }
    
    with open(output_path, 'w') as f:
        json.dump(plan, f, indent=2)
        
    return plan
