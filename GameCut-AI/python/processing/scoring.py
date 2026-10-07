def score_candidates(scenes, audio_peaks, visual_activity, transcript):
    """
    Evaluates scenes and assigns a highlight score.
    """
    scored_clips = []
    hype_words = ["let's go", "no way", "wait", "what", "omg", "insane", "crazy"]
    
    for start, end in scenes:
        duration = end - start
        if duration < 3 or duration > 30:
            continue
            
        scene_audio = [p['energy'] for p in audio_peaks if start <= p['start_time'] <= end]
        audio_score = sum(scene_audio) / len(scene_audio) if scene_audio else 0.1
        
        scene_visual = [v['activity'] for v in visual_activity if start <= v['time'] <= end]
        visual_score = sum(scene_visual) / len(scene_visual) if scene_visual else 0.1
        
        speech_score = 0.0
        context_score = 0.0
        scene_words = []
        for segment in transcript:
            if start <= segment['start'] <= end or start <= segment['end'] <= end:
                speech_score += segment.get('confidence', 0.5)
                text = segment.get('text', '').lower()
                scene_words.append(text)
                for word in hype_words:
                    if word in text:
                        context_score += 0.3
                        
        speech_score = min(1.0, speech_score / max(1, len(scene_words))) if scene_words else 0.1
        context_score = min(1.0, context_score)
        
        final_score = (
            (speech_score * 0.2) + 
            (audio_score * 0.3) + 
            (visual_score * 0.2) + 
            (context_score * 0.3)
        )
        
        scored_clips.append({
            "start": start,
            "end": end,
            "score": round(final_score, 3)
        })
        
    return scored_clips

def remove_overlapping_clips(scored_clips, overlap_threshold=2.0):
    """
    Sorts by score (descending), keeps best clips, and discards overlapping ones.
    """
    sorted_clips = sorted(scored_clips, key=lambda x: x['score'], reverse=True)
    selected = []
    
    for clip in sorted_clips:
        overlap = False
        for s in selected:
            overlap_start = max(clip['start'], s['start'])
            overlap_end = min(clip['end'], s['end'])
            if (overlap_end - overlap_start) > overlap_threshold:
                overlap = True
                break
                
        if not overlap:
            selected.append(clip)
            
    return selected
