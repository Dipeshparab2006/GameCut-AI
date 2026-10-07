"""Optional game-specific kill/event detection.

OCR is deliberately optional. When pytesseract/Tesseract is installed, known
kill-feed terms are read from game-specific HUD regions; otherwise callers can
use the existing game-agnostic montage detector safely.
"""
import json
import os
from pathlib import Path

PROFILES = {
    "free fire": {"terms": ("killed", "eliminated", "headshot", "knocked", "booyah"), "roi": (0.55, 0.0, 1.0, 0.38)},
    "free fire max": {"terms": ("killed", "eliminated", "headshot", "knocked", "booyah"), "roi": (0.55, 0.0, 1.0, 0.38)},
    "valorant": {"terms": ("killed", "headshot", "eliminated", "assist"), "roi": (0.62, 0.0, 1.0, 0.32)},
    "pubg / bgmi": {"terms": ("killed", "knocked", "eliminated", "finish"), "roi": (0.55, 0.0, 1.0, 0.35)},
    "fortnite": {"terms": ("eliminated", "knocked", "headshot"), "roi": (0.55, 0.0, 1.0, 0.35)},
    "cs2": {"terms": ("killed", "headshot", "assist"), "roi": (0.62, 0.0, 1.0, 0.30)},
    "apex legends": {"terms": ("knocked", "eliminated", "assist"), "roi": (0.55, 0.0, 1.0, 0.38)},
}

def profile_for_game(game):
    key = str(game or "").strip().lower()
    return PROFILES.get(key)

def detect_game_events(video_path, game, output_path=None, before=3.0, after=5.0, sample_every=0.5):
    profile = profile_for_game(game)
    result = {"game": game, "ocr_available": False, "events": [], "profile": profile}
    if not profile:
        return result
    try:
        import cv2
        import pytesseract
    except ImportError:
        return result
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened(): return result
    result["ocr_available"] = True
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frames / fps if fps else 0
    last_text = ""
    timestamp = 0.0
    try:
        while timestamp < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = cap.read()
            if ok:
                h, w = frame.shape[:2]; x1, y1, x2, y2 = profile["roi"]
                crop = frame[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]
                text = pytesseract.image_to_string(crop, config="--psm 6").lower()
                if text != last_text and any(term in text for term in profile["terms"]):
                    result["events"].append({"timestamp": round(timestamp, 3), "text": text[:240], "start": round(max(0, timestamp-before), 3), "end": round(min(duration, timestamp+after), 3), "reason": "game HUD kill/event OCR"})
                last_text = text
            timestamp += max(0.25, float(sample_every))
    finally: cap.release()
    if output_path: Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
