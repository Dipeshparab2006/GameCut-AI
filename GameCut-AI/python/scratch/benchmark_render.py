import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import time
import tempfile
import os
import subprocess
import shutil
from utils.binaries import ffmpeg_binary
from utils.ffmpeg import run_command, get_optimized_encoder_args, generate_srt
from processing.clip_renderer import render_highlight_video


def run_benchmark():
    # 1. Create a 30s dummy video with video and audio
    temp_dir = Path(tempfile.mkdtemp(prefix="gamecut_bench_"))
    source_video = temp_dir / "test_source.mp4"
    out_old = temp_dir / "out_old.mp4"
    out_new = temp_dir / "out_new.mp4"
    
    print("Generating 30-second test video...")
    subprocess.run([
        ffmpeg_binary(), '-y',
        '-f', 'lavfi', '-i', 'testsrc=duration=30:size=1280x720:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
        str(source_video)
    ], capture_output=True, check=True)
    
    clips = [
        {"start": 2.0, "end": 7.0},
        {"start": 10.0, "end": 15.0},
        {"start": 20.0, "end": 25.0}
    ]
    transcript = [
        {"start": 2.5, "end": 6.5, "text": "Clip one hype moment!"},
        {"start": 11.0, "end": 14.5, "text": "Unbelievable play!"},
        {"start": 21.0, "end": 24.5, "text": "Victory royale!"}
    ]

    print("\n--- Testing Encoder Detection ---")
    enc_args = get_optimized_encoder_args()
    print("Detected Encoder Args:", enc_args)
    
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_benchmark()
