import json
import math
import subprocess
import time
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from utils.binaries import ffmpeg_binary


class AudioAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioAnalysisConfig:
    sample_rate: int = 16000
    context_seconds: float = 1.0
    max_regions: int = 80


def config_from_env():
    import os

    return AudioAnalysisConfig(
        sample_rate=int(os.getenv("GAMECUT_AUDIO_SAMPLE_RATE", "16000")),
        context_seconds=float(os.getenv("GAMECUT_AUDIO_CONTEXT_SECONDS", "1")),
        max_regions=int(os.getenv("GAMECUT_AUDIO_MAX_REGIONS", "80")),
    )


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def _read_region_audio(video_path, start, end, sample_rate):
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    command = [
        ffmpeg_binary(),
        "-v",
        "error",
        "-ss",
        str(max(0.0, start)),
        "-t",
        str(duration),
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "wav",
        "pipe:1",
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise AudioAnalysisError(error or "FFmpeg audio extraction failed")

    try:
        with wave.open(BytesIO(result.stdout), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            width = wav.getsampwidth()
    except wave.Error as exc:
        raise AudioAnalysisError("Extracted audio could not be read") from exc

    if width != 2:
        raise AudioAnalysisError("Unexpected PCM sample width")

    samples = []
    for index in range(0, len(frames), 2):
        sample = int.from_bytes(frames[index : index + 2], byteorder="little", signed=True)
        samples.append(sample / 32768.0)
    return samples


def _audio_stats(samples):
    if not samples:
        return {"energy_raw": 0.0, "peak_raw": 0.0, "change_raw": 0.0, "silence_ratio": 1.0}

    squares = [sample * sample for sample in samples]
    rms = math.sqrt(sum(squares) / len(squares))
    peak = max(abs(sample) for sample in samples)
    midpoint = max(1, len(samples) // 2)
    first = samples[:midpoint]
    second = samples[midpoint:]
    first_rms = math.sqrt(sum(sample * sample for sample in first) / len(first)) if first else 0.0
    second_rms = math.sqrt(sum(sample * sample for sample in second) / len(second)) if second else 0.0
    change = abs(second_rms - first_rms)
    silence_ratio = sum(1 for sample in samples if abs(sample) < 0.01) / len(samples)
    return {
        "energy_raw": rms,
        "peak_raw": peak,
        "change_raw": change,
        "silence_ratio": silence_ratio,
    }


def _normalize_regions(regions):
    max_energy = max((item["audio"]["energy_raw"] for item in regions), default=0.0) or 1.0
    max_peak = max((item["audio"]["peak_raw"] for item in regions), default=0.0) or 1.0
    max_change = max((item["audio"]["change_raw"] for item in regions), default=0.0) or 1.0

    for item in regions:
        audio = item["audio"]
        audio["energy"] = round(_clamp(audio.pop("energy_raw") / max_energy), 3)
        audio["peak"] = round(_clamp(audio.pop("peak_raw") / max_peak), 3)
        audio["change"] = round(_clamp(audio.pop("change_raw") / max_change), 3)
        audio["silence_before_after"] = round(_clamp(audio["silence_ratio"]), 3)
        audio["score"] = round(
            _clamp((audio["energy"] * 0.45) + (audio["peak"] * 0.35) + (audio["change"] * 0.20)),
            3,
        )
    return regions


def analyze_audio_regions(video_path, regions, output_path=None, config=None, job_id=None):
    config = config or AudioAnalysisConfig()
    started = time.perf_counter()
    selected_regions = list(regions)[: config.max_regions]
    analyzed = []
    errors = []

    for index, region in enumerate(selected_regions):
        start = _as_float(region.get("start"))
        end = _as_float(region.get("end"))
        if end <= start:
            continue
        try:
            samples = _read_region_audio(video_path, start, end, config.sample_rate)
            stats = _audio_stats(samples)
            analyzed.append(
                {
                    "index": index,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3),
                    "audio": stats,
                }
            )
        except AudioAnalysisError as exc:
            errors.append({"index": index, "start": start, "end": end, "error": str(exc)[:300]})

    result = {
        "job_id": job_id,
        "video": str(video_path),
        "region_count": len(selected_regions),
        "analyzed_count": len(analyzed),
        "failed_count": len(errors),
        "errors": errors,
        "regions": _normalize_regions(analyzed),
        "processing_time_seconds": round(time.perf_counter() - started, 3),
    }

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
