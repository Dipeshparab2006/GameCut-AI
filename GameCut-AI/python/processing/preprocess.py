import os
from utils.ffmpeg import get_metadata, extract_audio, generate_proxy

def preprocess_video(video_path, output_dir):
    """
    Analyzes and prepares a video for AI processing.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Extracting metadata for {video_path}...")
    metadata = get_metadata(video_path)
    
    audio_path = os.path.join(output_dir, 'audio.wav')
    print(f"Extracting audio to {audio_path}...")
    success, error = extract_audio(video_path, audio_path)
    if not success:
        raise RuntimeError(f"Audio extraction failed: {error}")
    
    proxy_path = os.path.join(output_dir, 'proxy.mp4')
    print(f"Generating proxy video to {proxy_path}...")
    success, error = generate_proxy(video_path, proxy_path)
    if not success:
        raise RuntimeError(f"Proxy generation failed: {error}")
    
    duration = float(metadata['format'].get('duration', 0)) if metadata else 0
    return {
        'metadata': metadata,
        'audio_path': audio_path,
        'proxy_path': proxy_path,
        'duration': duration
    }
