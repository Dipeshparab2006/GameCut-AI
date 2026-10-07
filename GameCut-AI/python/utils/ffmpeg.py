import subprocess
import json
import os
import logging
from utils.binaries import ffmpeg_binary, ffprobe_binary
from utils.logging import log_extra


logger = logging.getLogger("gamecut.ffmpeg")

_OPTIMIZED_ENCODER_CACHE = None


def get_optimized_encoder_args():
    """
    Detects and returns the fastest available H.264 video encoder arguments.
    Supports hardware acceleration (NVIDIA NVENC, AMD AMF, Intel QSV, Windows MF)
    with ultra-fast CPU fallback (libx264).
    """
    global _OPTIMIZED_ENCODER_CACHE
    override = os.getenv("GAMECUT_FFMPEG_ENCODER", "").lower().strip()
    if override == "libx264":
        return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "24", "-threads", "0", "-pix_fmt", "yuv420p"]

    if _OPTIMIZED_ENCODER_CACHE is not None and not override:
        return _OPTIMIZED_ENCODER_CACHE

    candidates = [
        ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "24", "-rc", "vbr", "-pix_fmt", "yuv420p"]),
        ("h264_amf", ["-c:v", "h264_amf", "-usage", "transcoding", "-quality", "speed", "-pix_fmt", "yuv420p"]),
        ("h264_qsv", ["-c:v", "h264_qsv", "-preset", "veryfast", "-pix_fmt", "yuv420p"]),
        ("h264_mf", ["-c:v", "h264_mf", "-pix_fmt", "yuv420p"]),
    ]

    import tempfile
    for name, args in candidates:
        if override and override != name:
            continue
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name
            cmd = [ffmpeg_binary(), "-y", "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240:rate=30"] + args + [tmp_path]
            ok, _ = run_command(cmd)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if ok:
                logger.info(f"Hardware video acceleration enabled using {name}")
                _OPTIMIZED_ENCODER_CACHE = args
                return args
        except Exception:
            pass

    cpu_args = ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "24", "-threads", "0", "-pix_fmt", "yuv420p"]
    _OPTIMIZED_ENCODER_CACHE = cpu_args
    return cpu_args


def run_command(cmd):
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg command failed", **log_extra(command=cmd[0], error=e.stderr[:1000]))
        return False, e.stderr

def get_metadata(video_path):
    cmd = [
        ffprobe_binary(), 
        '-v', 'quiet', 
        '-print_format', 'json', 
        '-show_format', 
        '-show_streams', 
        video_path
    ]
    success, output = run_command(cmd)
    if success:
        return json.loads(output)
    return None

def extract_audio(video_path, output_path):
    cmd = [
        ffmpeg_binary(), '-y', '-i', video_path, 
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 
        output_path
    ]
    return run_command(cmd)

def generate_proxy(video_path, output_path, resolution="854x480"):
    cmd = [
        ffmpeg_binary(), '-y', '-i', video_path, 
        '-vf', f'scale={resolution}',
        *get_optimized_encoder_args(),
        '-c:a', 'aac', '-b:a', '128k', 
        output_path
    ]
    return run_command(cmd)

def trim_clip(video_path, start, end, output_path):
    cmd = [
        ffmpeg_binary(), '-y',
        '-ss', str(start), '-to', str(end),
        '-i', video_path,
        *get_optimized_encoder_args(),
        '-c:a', 'aac',
        output_path
    ]
    return run_command(cmd)
def create_concat_file(clip_paths, list_path):
    with open(list_path, 'w') as f:
        for path in clip_paths:
            safe_path = path.replace('\\', '/')
            f.write(f"file '{safe_path}'\n")

def concat_clips(list_path, output_path):
    cmd = [
        ffmpeg_binary(), '-y', '-f', 'concat', '-safe', '0', 
        '-i', list_path, '-c', 'copy', output_path
    ]
    return run_command(cmd)

def generate_srt(transcript, output_path, offset=0.0):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(transcript):
            start = segment['start'] - offset
            end = segment['end'] - offset
            if start < 0: start = 0
            if end < 0: continue
            
            def format_time(t):
                h = int(t / 3600)
                m = int((t % 3600) / 60)
                s = int(t % 60)
                ms = int((t % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                
            f.write(f"{i+1}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{segment['text'].strip()}\n\n")

def render_final_video(input_path, output_path, srt_path=None, aspect_ratio="9:16"):
    crop_filter = "crop=ih*9/16:ih"
    filters = crop_filter
    
    if srt_path:
        safe_srt = os.path.abspath(srt_path).replace('\\', '/').replace(':', '\\:')
        filters += f",subtitles='{safe_srt}':force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1'"
        
    cmd = [
        ffmpeg_binary(), '-y', '-i', input_path,
        '-vf', filters,
        *get_optimized_encoder_args(),
        '-c:a', 'aac',
        output_path
    ]
    return run_command(cmd)
