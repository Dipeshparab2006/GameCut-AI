import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


class HighlightScoringError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreWeights:
    speech: float = 0.25
    audio: float = 0.20
    visual: float = 0.20
    scene: float = 0.10
    duration: float = 0.10
    context: float = 0.15


@dataclass(frozen=True)
class HighlightScoringConfig:
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    keywords: tuple[str, ...] = (
        "let's go",
        "lets go",
        "no way",
        "what",
        "wow",
        "nice",
        "oh my god",
        "omg",
        "insane",
        "crazy",
        "clutch",
    )
    min_highlight_duration: float = 5.0
    max_highlight_duration: float = 30.0
    padding_before: float = 3.0
    padding_after: float = 5.0
    overlap_threshold: float = 0.50
    max_candidates: int = 12
    minimum_score: float = 0.12
    ideal_duration: float = 16.0


def config_from_env():
    keywords = os.getenv("GAMECUT_HIGHLIGHT_KEYWORDS", "")
    keyword_list = tuple(k.strip().lower() for k in keywords.split(",") if k.strip())

    return HighlightScoringConfig(
        weights=ScoreWeights(
            speech=float(os.getenv("GAMECUT_SCORE_WEIGHT_SPEECH", "0.25")),
            audio=float(os.getenv("GAMECUT_SCORE_WEIGHT_AUDIO", "0.20")),
            visual=float(os.getenv("GAMECUT_SCORE_WEIGHT_VISUAL", "0.20")),
            scene=float(os.getenv("GAMECUT_SCORE_WEIGHT_SCENE", "0.10")),
            duration=float(os.getenv("GAMECUT_SCORE_WEIGHT_DURATION", "0.10")),
            context=float(os.getenv("GAMECUT_SCORE_WEIGHT_CONTEXT", "0.15")),
        ),
        keywords=keyword_list or HighlightScoringConfig().keywords,
        min_highlight_duration=float(os.getenv("GAMECUT_MIN_HIGHLIGHT_DURATION", "5")),
        max_highlight_duration=float(os.getenv("GAMECUT_MAX_HIGHLIGHT_DURATION", "30")),
        padding_before=float(os.getenv("GAMECUT_HIGHLIGHT_PADDING_BEFORE", "3")),
        padding_after=float(os.getenv("GAMECUT_HIGHLIGHT_PADDING_AFTER", "5")),
        overlap_threshold=float(os.getenv("GAMECUT_HIGHLIGHT_OVERLAP_THRESHOLD", "0.50")),
        max_candidates=int(os.getenv("GAMECUT_MAX_HIGHLIGHT_CANDIDATES", "12")),
        minimum_score=float(os.getenv("GAMECUT_MIN_HIGHLIGHT_SCORE", "0.12")),
    )


def load_json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HighlightScoringError(f"Required analysis file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HighlightScoringError(f"Malformed analysis JSON: {path}") from exc


def load_optional_analysis(path, key):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"regions": [], "missing": True}
    except json.JSONDecodeError as exc:
        raise HighlightScoringError(f"Malformed {key} analysis JSON: {path}") from exc

    if not isinstance(data, dict):
        raise HighlightScoringError(f"{key} analysis JSON must be an object")
    regions = data.get("regions", [])
    if not isinstance(regions, list):
        raise HighlightScoringError(f"{key} analysis regions must be a list")
    data["missing"] = False
    return data


def load_transcript(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"language": None, "segments": [], "missing": True}
    except json.JSONDecodeError as exc:
        raise HighlightScoringError(f"Malformed transcript JSON: {path}") from exc

    if isinstance(data, list):
        return {"language": None, "segments": data, "missing": False}
    if isinstance(data, dict):
        segments = data.get("segments", [])
        if not isinstance(segments, list):
            raise HighlightScoringError("Transcript segments must be a list")
        return {"language": data.get("language"), "segments": segments, "missing": False}
    raise HighlightScoringError("Transcript JSON must be an object or list")


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _validate_scene(scene, video_duration):
    start = _as_float(scene.get("start"))
    end = _as_float(scene.get("end"))
    if start < 0 or end <= start:
        return None
    if video_duration > 0:
        start = min(start, video_duration)
        end = min(end, video_duration)
    if end <= start:
        return None
    return {"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)}


def _normalize_segments(transcript_segments, video_duration):
    normalized = []
    for segment in transcript_segments:
        if not isinstance(segment, dict):
            continue
        start = _as_float(segment.get("start"))
        end = _as_float(segment.get("end"))
        text = str(segment.get("text") or "").strip()
        if start < 0 or end <= start:
            continue
        if video_duration > 0:
            start = min(start, video_duration)
            end = min(end, video_duration)
        if end <= start:
            continue
        normalized.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "text": text,
                "confidence": _as_float(segment.get("confidence"), 0.0),
            }
        )
    return sorted(normalized, key=lambda item: (item["start"], item["end"]))


def _overlap_seconds(start_a, end_a, start_b, end_b):
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def _duration_score(duration, config):
    if duration <= 0:
        return 0.0
    if config.min_highlight_duration <= duration <= config.max_highlight_duration:
        distance = abs(duration - config.ideal_duration)
        span = max(config.ideal_duration - config.min_highlight_duration, config.max_highlight_duration - config.ideal_duration)
        return max(0.35, 1.0 - (distance / span))
    if duration < config.min_highlight_duration:
        return max(0.0, duration / config.min_highlight_duration * 0.35)
    overflow = duration - config.max_highlight_duration
    return max(0.0, 0.35 - min(0.35, overflow / config.max_highlight_duration))


def _speech_signal(scene, segments, keywords):
    duration = max(scene["duration"], 0.001)
    speech_seconds = 0.0
    keyword_hits = 0
    confidence_values = []
    reason_parts = []

    for segment in segments:
        overlap = _overlap_seconds(scene["start"], scene["end"], segment["start"], segment["end"])
        if overlap <= 0:
            continue
        speech_seconds += overlap
        confidence_values.append(segment["confidence"])
        text = _clean_text(segment["text"])
        keyword_hits += sum(1 for keyword in keywords if keyword in text)

    activity = min(1.0, speech_seconds / duration)
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    confidence = max(0.0, min(1.0, (confidence + 1.0) / 2.0 if confidence < 0 else confidence))
    keyword_score = min(1.0, keyword_hits / 3.0)
    score = min(1.0, (activity * 0.55) + (confidence * 0.20 if confidence_values else 0) + (keyword_score * 0.25))

    if activity >= 0.35:
        reason_parts.append("high speech activity")
    elif activity > 0:
        reason_parts.append("some speech activity")
    if keyword_hits:
        reason_parts.append("gaming excitement keyword signal")

    return score, reason_parts


def _scene_signal(scene, all_scenes):
    if len(all_scenes) <= 1:
        return 0.45, ["single-scene fallback"]

    nearby = 0
    center = (scene["start"] + scene["end"]) / 2.0
    for other in all_scenes:
        if other is scene:
            continue
        other_center = (other["start"] + other["end"]) / 2.0
        if abs(center - other_center) <= 20:
            nearby += 1

    density_score = min(1.0, nearby / 4.0)
    boundary_score = 0.35 + (0.65 * density_score)
    reasons = ["nearby scene changes"] if density_score >= 0.5 else []
    return boundary_score, reasons


def _context_signal(scene, segments, keywords, config, video_duration):
    context_start = max(0.0, scene["start"] - config.padding_before)
    context_end = min(video_duration, scene["end"] + config.padding_after) if video_duration > 0 else scene["end"] + config.padding_after
    context_hits = 0
    context_speech = 0.0

    for segment in segments:
        overlap = _overlap_seconds(context_start, context_end, segment["start"], segment["end"])
        if overlap <= 0:
            continue
        context_speech += overlap
        text = _clean_text(segment["text"])
        context_hits += sum(1 for keyword in keywords if keyword in text)

    window = max(context_end - context_start, 0.001)
    speech_ratio = min(1.0, context_speech / window)
    keyword_score = min(1.0, context_hits / 2.0)
    score = min(1.0, (speech_ratio * 0.45) + (keyword_score * 0.55))
    reasons = []
    if score >= 0.65:
        reasons.append("strong contextual signal")
    elif score >= 0.25:
        reasons.append("moderate contextual signal")
    return score, reasons


def _region_signal(scene, analysis, signal_name):
    best_score = 0.0
    best_payload = None
    for region in analysis.get("regions", []):
        if not isinstance(region, dict):
            continue
        start = _as_float(region.get("start"))
        end = _as_float(region.get("end"))
        overlap = _overlap_seconds(scene["start"], scene["end"], start, end)
        if overlap <= 0:
            continue
        payload = region.get(signal_name, {})
        if not isinstance(payload, dict):
            continue
        score = _as_float(payload.get("score"))
        weighted = score * min(1.0, overlap / max(scene["duration"], 0.001))
        if weighted > best_score:
            best_score = weighted
            best_payload = payload

    reasons = []
    if signal_name == "audio" and best_payload:
        if _as_float(best_payload.get("peak")) >= 0.75:
            reasons.append("strong audio peak")
        if _as_float(best_payload.get("change")) >= 0.70:
            reasons.append("sudden audio change")
        if _as_float(best_payload.get("energy")) >= 0.75:
            reasons.append("high audio energy")
    if signal_name == "visual" and best_payload:
        if _as_float(best_payload.get("activity")) >= 0.70:
            reasons.append("high visual activity")
        if _as_float(best_payload.get("transition")) >= 0.70:
            reasons.append("strong visual transition")
        if _as_float(best_payload.get("brightness_change")) >= 0.70:
            reasons.append("noticeable brightness change")
    return min(1.0, best_score), reasons


def _apply_padding(scene, config, video_duration):
    start = max(0.0, scene["start"] - config.padding_before)
    end = scene["end"] + config.padding_after
    if video_duration > 0:
        end = min(video_duration, end)

    duration = end - start
    if duration > config.max_highlight_duration:
        center = (scene["start"] + scene["end"]) / 2.0
        start = max(0.0, center - (config.max_highlight_duration / 2.0))
        end = start + config.max_highlight_duration
        if video_duration > 0 and end > video_duration:
            end = video_duration
            start = max(0.0, end - config.max_highlight_duration)

    return round(start, 3), round(end, 3), round(max(0.0, end - start), 3)


def _candidate_overlap_ratio(a, b):
    overlap = _overlap_seconds(a["start"], a["end"], b["start"], b["end"])
    shorter = max(0.001, min(a["duration"], b["duration"]))
    return overlap / shorter


def remove_overlapping_candidates(candidates, overlap_threshold=0.50):
    selected = []
    removed = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        if any(_candidate_overlap_ratio(candidate, kept) >= overlap_threshold for kept in selected):
            removed.append(candidate)
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: item["start"]), removed


def score_candidates(scene_analysis, transcript=None, audio_analysis=None, visual_analysis=None, config=None, job_id=None):
    config = config or HighlightScoringConfig()
    transcript = transcript or {"segments": []}
    audio_analysis = audio_analysis or {"regions": [], "missing": True}
    visual_analysis = visual_analysis or {"regions": [], "missing": True}
    video_duration = _as_float(scene_analysis.get("duration"))
    if video_duration <= 0:
        raise HighlightScoringError("Video duration unavailable")

    raw_scenes = scene_analysis.get("scenes")
    if not isinstance(raw_scenes, list):
        raise HighlightScoringError("Scene analysis does not contain a scenes list")

    scenes = [scene for scene in (_validate_scene(item, video_duration) for item in raw_scenes if isinstance(item, dict)) if scene]
    if not scenes:
        raise HighlightScoringError("No valid scenes available for scoring")

    segments = _normalize_segments(transcript.get("segments", []), video_duration)
    effective_min_duration = min(config.min_highlight_duration, video_duration)
    candidates = []
    for index, scene in enumerate(scenes):
        padded_start, padded_end, padded_duration = _apply_padding(scene, config, video_duration)
        if padded_duration < effective_min_duration:
            continue

        speech_score, speech_reasons = _speech_signal(scene, segments, config.keywords)
        audio_score, audio_reasons = _region_signal(scene, audio_analysis, "audio")
        visual_score, visual_reasons = _region_signal(scene, visual_analysis, "visual")
        scene_score, scene_reasons = _scene_signal(scene, scenes)
        duration_score = _duration_score(padded_duration, config)
        context_score, context_reasons = _context_signal(scene, segments, config.keywords, config, video_duration)
        final_score = (
            (config.weights.speech * speech_score)
            + (config.weights.audio * audio_score)
            + (config.weights.visual * visual_score)
            + (config.weights.scene * scene_score)
            + (config.weights.duration * duration_score)
            + (config.weights.context * context_score)
        )

        reasons = speech_reasons + audio_reasons + visual_reasons + scene_reasons + context_reasons
        if duration_score >= 0.75:
            reasons.append("good highlight duration")
        if not reasons:
            reasons.append("baseline scene candidate")

        candidate = {
            "start": padded_start,
            "end": padded_end,
            "duration": padded_duration,
            "score": round(min(1.0, max(0.0, final_score)), 3),
            "source_scene": {
                "index": index,
                "start": scene["start"],
                "end": scene["end"],
                "duration": scene["duration"],
            },
            "signals": {
                "speech": round(speech_score, 3),
                "audio": round(audio_score, 3),
                "visual": round(visual_score, 3),
                "scene": round(scene_score, 3),
                "duration": round(duration_score, 3),
                "context": round(context_score, 3),
            },
            "reason": reasons,
        }
        if candidate["score"] >= config.minimum_score:
            candidates.append(candidate)

    selected, removed = remove_overlapping_candidates(candidates, config.overlap_threshold)
    selected = sorted(selected, key=lambda item: item["score"], reverse=True)[: config.max_candidates]
    selected = sorted(selected, key=lambda item: item["start"])

    return {
        "job_id": job_id,
        "video_duration": round(video_duration, 3),
        "weights": {
            "speech": config.weights.speech,
            "audio": config.weights.audio,
            "visual": config.weights.visual,
            "scene": config.weights.scene,
            "duration": config.weights.duration,
            "context": config.weights.context,
        },
        "thresholds": {
            "min_highlight_duration": config.min_highlight_duration,
            "max_highlight_duration": config.max_highlight_duration,
            "padding_before": config.padding_before,
            "padding_after": config.padding_after,
            "overlap_threshold": config.overlap_threshold,
            "minimum_score": config.minimum_score,
        },
        "transcript_missing": bool(transcript.get("missing")),
        "audio_analysis_missing": bool(audio_analysis.get("missing")),
        "visual_analysis_missing": bool(visual_analysis.get("missing")),
        "scene_count": len(scenes),
        "raw_candidate_count": len(candidates),
        "overlap_removed_count": len(removed),
        "candidate_count": len(selected),
        "total_selected_duration": round(sum(item["duration"] for item in selected), 3),
        "highest_score": round(max((item["score"] for item in selected), default=0.0), 3),
        "candidates": selected,
    }


def generate_highlight_candidates(
    scene_analysis_path,
    transcript_path,
    output_path,
    job_id=None,
    config=None,
    audio_analysis_path=None,
    visual_analysis_path=None,
):
    started = time.perf_counter()
    scene_analysis = load_json_file(scene_analysis_path)
    transcript = load_transcript(transcript_path)
    audio_analysis = load_optional_analysis(audio_analysis_path, "audio") if audio_analysis_path else {"regions": [], "missing": True}
    visual_analysis = load_optional_analysis(visual_analysis_path, "visual") if visual_analysis_path else {"regions": [], "missing": True}
    result = score_candidates(
        scene_analysis,
        transcript=transcript,
        audio_analysis=audio_analysis,
        visual_analysis=visual_analysis,
        config=config,
        job_id=job_id,
    )
    result["processing_time_seconds"] = round(time.perf_counter() - started, 3)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
