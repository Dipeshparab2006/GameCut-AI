import json
import os
import time
from pathlib import Path


try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class SpeechAnalysisError(RuntimeError):
    pass


def _device_from_env():
    requested = os.getenv("WHISPER_DEVICE", "cpu").lower()
    return "cuda" if requested == "cuda" else "cpu"


def transcribe_audio(audio_path, output_path=None, model_size=None):
    started = time.perf_counter()
    model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "tiny")

    if WhisperModel is None:
        result = {
            "language": None,
            "segments": [],
            "model": model_size,
            "device": "unavailable",
            "error": "faster-whisper is not installed",
            "processing_time_seconds": round(time.perf_counter() - started, 3),
        }
    else:
        device = _device_from_env()
        try:
            model = WhisperModel(model_size, device=device, compute_type="int8")
            segments, info = model.transcribe(str(audio_path), beam_size=5)
            result_segments = []
            for segment in segments:
                text = str(segment.text or "").strip()
                if not text:
                    continue
                result_segments.append(
                    {
                        "start": round(float(segment.start), 3),
                        "end": round(float(segment.end), 3),
                        "text": text,
                        "confidence": round(float(getattr(segment, "avg_logprob", 0.0)), 3),
                    }
                )
            result = {
                "language": getattr(info, "language", None),
                "segments": result_segments,
                "model": model_size,
                "device": device,
                "processing_time_seconds": round(time.perf_counter() - started, 3),
            }
        except Exception as exc:
            raise SpeechAnalysisError(str(exc)[:500]) from exc

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
