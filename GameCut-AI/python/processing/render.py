import os
from utils.ffmpeg import trim_clip, create_concat_file, concat_clips, generate_srt, render_final_video

def map_transcript_to_timeline(clips, transcript):
    """
    Converts original video transcript timestamps to the concatenated short timeline.
    """
    mapped = []
    output_offset = 0.0

    for clip in clips:
        clip_start = float(clip['start'])
        clip_end = float(clip['end'])

        for segment in transcript:
            seg_start = float(segment.get('start', 0))
            seg_end = float(segment.get('end', 0))

            if seg_end <= clip_start or seg_start >= clip_end:
                continue

            mapped.append({
                "start": output_offset + max(seg_start, clip_start) - clip_start,
                "end": output_offset + min(seg_end, clip_end) - clip_start,
                "text": segment.get('text', '').strip()
            })

        output_offset += clip_end - clip_start

    return [segment for segment in mapped if segment["text"] and segment["end"] > segment["start"]]

def process_editing_plan(video_path, plan_path, transcript, output_dir):
    """
    Executes the JSON editing plan using FFmpeg.
    """
    import json
    with open(plan_path, 'r') as f:
        plan = json.load(f)
        
    print(f"Executing plan: {len(plan['clips'])} clips, target {plan['target_duration']}s")
    if not plan['clips']:
        raise ValueError("Editing plan has no clips to render.")
    
    clip_paths = []
    
    # 1. Trim clips
    for i, clip in enumerate(plan['clips']):
        clip_path = os.path.join(output_dir, f"clip_{i}.mp4")
        print(f"Trimming clip {i}...")
        success, error = trim_clip(video_path, clip['start'], clip['end'], clip_path)
        if not success:
            raise RuntimeError(f"Clip trim failed: {error}")
        clip_paths.append(clip_path)
        
    # 2. Concat
    concat_list = os.path.join(output_dir, "concat_list.txt")
    raw_concat = os.path.join(output_dir, "raw_concat.mp4")
    create_concat_file(clip_paths, concat_list)
    
    print("Concatenating clips...")
    success, error = concat_clips(concat_list, raw_concat)
    if not success:
        raise RuntimeError(f"Clip concat failed: {error}")
    
    # 3. Subtitles
    srt_path = None
    if plan.get('subtitles'):
        srt_path = os.path.join(output_dir, "subtitles.srt")
        print("Generating subtitles...")
        generate_srt(map_transcript_to_timeline(plan['clips'], transcript), srt_path)
        
    # 4. Final Render (Crop + Burn)
    final_output = os.path.join(output_dir, "final.mp4")
    print(f"Rendering final output to {final_output}...")
    success, error = render_final_video(raw_concat, final_output, srt_path, plan['aspect_ratio'])
    if not success:
        raise RuntimeError(f"Final render failed: {error}")
    
    return final_output
