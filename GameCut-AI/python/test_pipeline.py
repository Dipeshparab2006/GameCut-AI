"""
GameCut AI Pipeline — Comprehensive Test Script
Tests every module for import errors, logic issues, and integration gaps.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.binaries import ensure_static_ffmpeg, ffmpeg_binary, ffprobe_binary
ensure_static_ffmpeg()

PASS = 0
FAIL = 0
WARN = 0

def test(name, func):
    global PASS, FAIL, WARN
    try:
        result = func()
        if result == "WARN":
            WARN += 1
            print(f"  ⚠  WARN: {name}")
        else:
            PASS += 1
            print(f"  ✓  PASS: {name}")
    except Exception as e:
        FAIL += 1
        print(f"  ✗  FAIL: {name} → {e}")

# === 1. IMPORTS ===
print("\n=== MODULE IMPORTS ===")

def test_import_fastapi():
    from fastapi import FastAPI
test("Import FastAPI", test_import_fastapi)

def test_import_uvicorn():
    import uvicorn
test("Import uvicorn", test_import_uvicorn)

def test_import_mysql():
    import mysql.connector
test("Import mysql-connector", test_import_mysql)

def test_import_cv2():
    import cv2
test("Import opencv-python", test_import_cv2)

def test_import_scenedetect():
    from scenedetect import detect, ContentDetector
test("Import scenedetect", test_import_scenedetect)

def test_import_whisper():
    from faster_whisper import WhisperModel
test("Import faster-whisper", test_import_whisper)

def test_import_numpy():
    import numpy
test("Import numpy", test_import_numpy)

def test_import_scipy():
    from scipy.io import wavfile
test("Import scipy", test_import_scipy)

def test_import_requests():
    import requests
test("Import requests", test_import_requests)

# === 2. OUR MODULES ===
print("\n=== OUR MODULES ===")

def test_import_db():
    from utils.db import get_db_connection
test("Import utils.db", test_import_db)

def test_import_ffmpeg_utils():
    from utils.ffmpeg import get_metadata, extract_audio, generate_proxy, trim_clip, create_concat_file, concat_clips, generate_srt, render_final_video
test("Import utils.ffmpeg (all functions)", test_import_ffmpeg_utils)

def test_import_preprocess():
    from processing.preprocess import preprocess_video
test("Import processing.preprocess", test_import_preprocess)

def test_import_scoring():
    from processing.scoring import score_candidates, remove_overlapping_clips
test("Import processing.scoring", test_import_scoring)

def test_import_plan():
    from processing.plan_generator import select_final_highlights, generate_editing_plan
test("Import processing.plan_generator", test_import_plan)

def test_import_render():
    from processing.render import process_editing_plan
test("Import processing.render", test_import_render)

def test_import_scene():
    from detection.scene_detector import detect_scenes
test("Import detection.scene_detector", test_import_scene)

def test_import_speech():
    from detection.speech_detector import transcribe_audio
test("Import detection.speech_detector", test_import_speech)

def test_import_audio():
    from detection.audio_detector import analyze_audio_excitement
test("Import detection.audio_detector", test_import_audio)

def test_import_visual():
    from detection.visual_analyzer import analyze_visual_activity
test("Import detection.visual_analyzer", test_import_visual)

def test_import_agent():
    from agents.highlight_agent import agent_select_highlights, build_agent_prompt, parse_agent_response
test("Import agents.highlight_agent", test_import_agent)

# === 3. LOGIC TESTS ===
print("\n=== SCORING LOGIC ===")

def test_scoring_basic():
    from processing.scoring import score_candidates
    scenes = [(0, 10), (15, 25), (40, 55)]
    audio = [{"start_time": i, "end_time": i+1, "energy": 0.5} for i in range(60)]
    visual = [{"time": i, "activity": 0.5} for i in range(60)]
    transcript = [{"start": 2, "end": 5, "text": "let's go!", "confidence": 0.9}]
    result = score_candidates(scenes, audio, visual, transcript)
    assert len(result) >= 1, f"Expected at least 1 scored clip, got {len(result)}"
    for clip in result:
        assert "start" in clip and "end" in clip and "score" in clip
        assert 0 <= clip["score"] <= 1, f"Score {clip['score']} out of range"
test("Scoring produces valid clips with scores 0-1", test_scoring_basic)

def test_scoring_filters_short():
    from processing.scoring import score_candidates
    scenes = [(0, 1)]  # Too short (< 3 sec)
    result = score_candidates(scenes, [], [], [])
    assert len(result) == 0, f"Should filter clips < 3s, got {len(result)}"
test("Scoring filters clips shorter than 3 seconds", test_scoring_filters_short)

def test_scoring_filters_long():
    from processing.scoring import score_candidates
    scenes = [(0, 35)]  # Too long (> 30 sec)
    result = score_candidates(scenes, [], [], [])
    assert len(result) == 0, f"Should filter clips > 30s, got {len(result)}"
test("Scoring filters clips longer than 30 seconds", test_scoring_filters_long)

def test_hype_words_boost():
    from processing.scoring import score_candidates
    scenes = [(0, 10)]
    audio = [{"start_time": i, "end_time": i+1, "energy": 0.5} for i in range(10)]
    visual = [{"time": i, "activity": 0.5} for i in range(10)]
    transcript_hype = [{"start": 2, "end": 5, "text": "NO WAY! LET'S GO!", "confidence": 0.9}]
    transcript_calm = [{"start": 2, "end": 5, "text": "moving to the next area", "confidence": 0.9}]
    score_hype = score_candidates(scenes, audio, visual, transcript_hype)[0]['score']
    score_calm = score_candidates(scenes, audio, visual, transcript_calm)[0]['score']
    assert score_hype > score_calm, f"Hype score {score_hype} should be > calm score {score_calm}"
test("Hype words boost score above calm speech", test_hype_words_boost)

print("\n=== OVERLAP PREVENTION ===")

def test_overlap_removal():
    from processing.scoring import remove_overlapping_clips
    clips = [
        {"start": 0, "end": 15, "score": 0.9},
        {"start": 10, "end": 25, "score": 0.7},  # Overlaps with first
        {"start": 30, "end": 45, "score": 0.8},
    ]
    result = remove_overlapping_clips(clips, overlap_threshold=2.0)
    assert len(result) == 2, f"Expected 2 non-overlapping clips, got {len(result)}"
    starts = [c['start'] for c in result]
    assert 10 not in starts, "Lower-scored overlapping clip should be removed"
test("Overlap removal keeps highest-scored, discards overlapping", test_overlap_removal)

print("\n=== PLAN GENERATION ===")

def test_plan_selection():
    from processing.plan_generator import select_final_highlights
    clips = [
        {"start": 0, "end": 10, "score": 0.9},
        {"start": 20, "end": 35, "score": 0.85},
        {"start": 50, "end": 65, "score": 0.8},
        {"start": 80, "end": 100, "score": 0.7},
    ]
    result = select_final_highlights(clips, [], 120, target_duration=30, use_agent=False)
    total_dur = sum(c['end'] - c['start'] for c in result)
    assert total_dur <= 35, f"Total duration {total_dur}s should be ~30s"
    assert result == sorted(result, key=lambda x: x['start']), "Clips should be in timeline order"
test("Select highlights respects target duration and timeline order", test_plan_selection)

def test_plan_json_output():
    from processing.plan_generator import generate_editing_plan
    import json, tempfile
    clips = [{"start": 10, "end": 25, "score": 0.9}]
    path = os.path.join(tempfile.gettempdir(), "test_plan.json")
    plan = generate_editing_plan(clips, path)
    assert plan["target_duration"] == 45
    assert plan["aspect_ratio"] == "9:16"
    assert plan["subtitles"] == True
    assert len(plan["clips"]) == 1
    with open(path, 'r') as f:
        loaded = json.load(f)
    assert loaded == plan
    os.remove(path)
test("JSON plan writes valid file with correct structure", test_plan_json_output)

print("\n=== AGENT LOGIC ===")

def test_agent_prompt_format():
    from agents.highlight_agent import build_agent_prompt
    import json
    candidates = [{"start": 10, "end": 25, "score": 0.91}]
    transcript = [{"start": 12, "end": 15, "text": "NO WAY!"}]
    prompt = build_agent_prompt(candidates, transcript, 1800, 45)
    assert "1800" in prompt
    assert "NO WAY!" in prompt
test("Agent prompt includes video duration and speech text", test_agent_prompt_format)

def test_agent_parse_valid():
    from agents.highlight_agent import parse_agent_response
    valid_json = '{"selected_clips": [{"start": 10, "end": 25, "reason": "test"}], "reasoning": "ok"}'
    result = parse_agent_response(valid_json)
    assert result is not None
    assert len(result) == 1
    assert result[0]["start"] == 10
test("Agent parses valid JSON response", test_agent_parse_valid)

def test_agent_parse_markdown_wrapped():
    from agents.highlight_agent import parse_agent_response
    wrapped = '```json\n{"selected_clips": [{"start": 5, "end": 15, "reason": "good"}], "reasoning": "ok"}\n```'
    result = parse_agent_response(wrapped)
    assert result is not None
    assert len(result) == 1
test("Agent handles markdown-wrapped JSON from LLMs", test_agent_parse_markdown_wrapped)

def test_agent_parse_bad_json():
    from agents.highlight_agent import parse_agent_response
    result = parse_agent_response("This is not JSON at all")
    assert result is None
test("Agent gracefully returns None for invalid JSON", test_agent_parse_bad_json)

def test_agent_validator():
    from agents.validator import validate_and_constrain_agent_clips
    candidates = [{"start": 10.0, "end": 20.0, "score": 0.9}]
    video_duration = 100.0
    
    # Valid
    agent_clips = [{"start": 10.1, "end": 19.9, "reason": "test"}]
    result = validate_and_constrain_agent_clips(agent_clips, candidates, video_duration)
    assert len(result) == 1
    assert result[0]['start'] == 10.0 # Constrained to candidate start

    # Invalid (start > end)
    agent_clips = [{"start": 25.0, "end": 15.0}]
    result = validate_and_constrain_agent_clips(agent_clips, candidates, video_duration)
    assert len(result) == 0

    # Invalid (out of bounds)
    agent_clips = [{"start": 90.0, "end": 110.0}]
    result = validate_and_constrain_agent_clips(agent_clips, candidates, video_duration)
    assert len(result) == 0

    # Invalid (hallucinated clip, no matching candidate)
    agent_clips = [{"start": 50.0, "end": 60.0}]
    result = validate_and_constrain_agent_clips(agent_clips, candidates, video_duration)
    assert len(result) == 0
test("Agent validator rejects invalid and hallucinated clips", test_agent_validator)

def test_agent_fallback():
    from agents.highlight_agent import agent_select_highlights
    candidates = [
        {"start": 0, "end": 10, "score": 0.9},
        {"start": 20, "end": 30, "score": 0.8},
    ]
    # Forcing no agent should return None to trigger fallback in plan_generator
    os.environ["LLM_PROVIDER"] = "deterministic"
    result = agent_select_highlights(candidates, [], video_duration=120, target_duration=15)
    assert result is None, "Agent should return None to trigger fallback"
test("Agent falls back to deterministic when Ollama unavailable", test_agent_fallback)

print("\n=== SRT SUBTITLE GENERATION ===")

def test_srt_generation():
    from utils.ffmpeg import generate_srt
    import tempfile
    transcript = [
        {"start": 1.5, "end": 3.2, "text": "Hello world"},
        {"start": 5.0, "end": 7.8, "text": "Let's go!"},
    ]
    path = os.path.join(tempfile.gettempdir(), "test.srt")
    generate_srt(transcript, path)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "1\n" in content
    assert "Hello world" in content
    assert "-->" in content
    os.remove(path)
test("SRT generation produces valid subtitle file", test_srt_generation)

# === 4. SYSTEM CHECKS ===
print("\n=== SYSTEM CHECKS ===")

def test_ffmpeg():
    import subprocess
    subprocess.run([ffmpeg_binary(), "-version"], check=True, capture_output=True)
test("FFmpeg available in PATH", test_ffmpeg)

def test_ffprobe():
    import subprocess
    subprocess.run([ffprobe_binary(), "-version"], check=True, capture_output=True)
test("FFprobe available in PATH", test_ffprobe)

def test_db_connection():
    from utils.db import get_db_connection
    conn = get_db_connection()
    assert conn is not None, "Could not connect to MySQL"
    conn.close()
test("MySQL database connection (gamecut_ai)", test_db_connection)

def test_ai_jobs_columns():
    from utils.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DESCRIBE ai_jobs")
    columns = [row[0] for row in cursor.fetchall()]
    assert "progress" in columns, f"'progress' column missing. Columns: {columns}"
    assert "current_step" in columns, f"'current_step' column missing. Columns: {columns}"
    cursor.close()
    conn.close()
test("ai_jobs table has progress and current_step columns", test_ai_jobs_columns)

# === SUMMARY ===
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed, {WARN} warnings")
print(f"{'='*50}")

if FAIL:
    raise SystemExit(1)
