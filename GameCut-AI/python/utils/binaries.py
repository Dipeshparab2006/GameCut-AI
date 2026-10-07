import os
import shutil


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_BIN_DIR = os.path.join(PROJECT_ROOT, "bin")


def configure_binary_paths():
    """
    Adds project-local and known Windows app binary folders to PATH.
    """
    candidates = [
        LOCAL_BIN_DIR,
        os.environ.get("GAMECUT_FFMPEG_DIR", ""),
        r"C:\Program Files\Softdeluxe\Free Download Manager",
    ]

    path_parts = [p for p in candidates if p and os.path.isdir(p)]
    current_path = os.environ.get("PATH", "")
    for path in reversed(path_parts):
        if path not in current_path:
            current_path = path + os.pathsep + current_path
    os.environ["PATH"] = current_path


def ensure_static_ffmpeg():
    """
    Uses static-ffmpeg when available. This provides both ffmpeg and ffprobe.
    """
    configure_binary_paths()
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        return


def ffmpeg_binary():
    ensure_static_ffmpeg()
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_binary():
    ensure_static_ffmpeg()
    return shutil.which("ffprobe") or "ffprobe"
