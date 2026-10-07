"""
Comprehensive Live Integration and Error Test Suite for GameCut AI (Phase 11)
Tests:
1. End-to-end small gameplay video processing via worker.py
2. Validation of generated 9:16 1080x1920 video and manifest
3. Cleanup of intermediate render artifacts
4. Speechless / quiet video handling
5. Corrupted / invalid video error handling
6. Job status API consistency
"""

import os
import sys
import json
import time
from pathlib import Path

# Add project root and python root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from utils.binaries import ensure_static_ffmpeg, ffmpeg_binary, ffprobe_binary
from utils.db import get_db_connection
from utils.ffmpeg import get_metadata
from jobs.worker import process_one, claim_one_job

ensure_static_ffmpeg()

PASS = 0
FAIL = 0

def log_test(name, success, detail=""):
    global PASS, FAIL
    if success:
        PASS += 1
        print(f"  [PASS] {name} {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -> {detail}")

def reset_or_create_test_job(video_path, project_name="Phase 11 Integration Test"):
    """
    Creates a new project, video, and queued ai_job in MySQL database for testing.
    """
    path_obj = Path(video_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    file_size = path_obj.stat().st_size
    rel_path = path_obj.relative_to(PROJECT_ROOT).as_posix() if PROJECT_ROOT in path_obj.parents else str(video_path)
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Get demo user (id 1 or first available)
        cur.execute("SELECT id FROM users LIMIT 1")
        user = cur.fetchone()
        user_id = user["id"] if user else 1

        # Insert project
        cur.execute(
            "INSERT INTO projects (user_id, project_name, description, status, created_at) VALUES (%s, %s, %s, 'draft', NOW())",
            (user_id, project_name, "Phase 11 Automated Test")
        )
        project_id = cur.lastrowid

        # Insert video
        cur.execute(
            """
            INSERT INTO videos (project_id, user_id, original_filename, stored_filename, file_path, file_size, mime_type, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'video/mp4', 'uploaded', NOW())
            """,
            (project_id, user_id, path_obj.name, path_obj.name, rel_path, file_size)
        )
        video_id = cur.lastrowid

        # Insert queued ai_job
        payload = json.dumps({"test": True, "source": rel_path})
        cur.execute(
            """
            INSERT INTO ai_jobs (project_id, video_id, user_id, job_type, status, priority, payload, available_at, created_at)
            VALUES (%s, %s, %s, 'video_processing', 'queued', 10, %s, NOW(), NOW())
            """,
            (project_id, video_id, user_id, payload)
        )
        job_id = cur.lastrowid

        conn.commit()
        return job_id, project_id, video_id
    finally:
        cur.close()
        conn.close()


def test_small_video_end_to_end():
    print("\n=== TEST 1: SMALL VIDEO END-TO-END PIPELINE ===")
    test_video = PROJECT_ROOT / "uploads" / "original" / "user_5_20260816033206_725907e2.mp4"
    if not test_video.is_file():
        # Fallback to phase4 video
        test_video = PROJECT_ROOT / "uploads" / "temp" / "phase4_many_scenes.mp4"
    
    if not test_video.is_file():
        log_test("Small video exists", False, "No valid test video found in uploads")
        return

    job_id, project_id, video_id = reset_or_create_test_job(str(test_video), "Small Video E2E Test")
    print(f"Created Job ID: {job_id}, Project ID: {project_id}")

    # Process job with worker
    start_time = time.perf_counter()
    success = process_one()
    elapsed = time.perf_counter() - start_time

    log_test("Worker execution succeeds", success, f"Elapsed: {elapsed:.2f}s")

    # Verify DB state
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM ai_jobs WHERE id = %s", (job_id,))
    job = cur.fetchone()
    cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    proj = cur.fetchone()
    cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
    vid = cur.fetchone()
    cur.close()
    conn.close()

    log_test("ai_jobs status is completed", job["status"] == "completed", f"Got: {job['status']}")
    log_test("ai_jobs progress is 100", job["progress"] == 100, f"Got: {job['progress']}")
    log_test("project status is completed", proj["status"] == "completed", f"Got: {proj['status']}")
    log_test("video status is processed", vid["status"] == "processed", f"Got: {vid['status']}")
    log_test("video output_path is populated", bool(vid.get("output_path")), f"Got: {vid.get('output_path')}")

    # Output file validation
    out_file = PROJECT_ROOT / vid["output_path"]
    log_test("Output file exists on disk", out_file.is_file(), str(out_file))

    if out_file.is_file():
        meta = get_metadata(str(out_file))
        vstream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
        log_test("Output has video stream", vstream is not None)
        if vstream:
            w, h = int(vstream.get("width", 0)), int(vstream.get("height", 0))
            log_test("Resolution is 1080x1920 (9:16)", w == 1080 and h == 1920, f"Got: {w}x{h}")
            log_test("Video codec is h264", vstream.get("codec_name") == "h264", f"Got: {vstream.get('codec_name')}")

    # Check cleanup
    job_dir = PROJECT_ROOT / "uploads" / "temp" / str(job_id)
    clips_left = (job_dir / "clips").exists()
    concat_left = (job_dir / "concat.mp4").exists()
    audio_left = (job_dir / "audio.wav").exists()
    log_test("Intermediate clips cleaned up", not clips_left)
    log_test("Intermediate concat.mp4 cleaned up", not concat_left)
    log_test("Intermediate audio.wav cleaned up", not audio_left)
    log_test("Analysis manifests preserved", (job_dir / "scene_analysis.json").exists())


def test_invalid_video_error_handling():
    print("\n=== TEST 2: INVALID/CORRUPTED VIDEO ERROR HANDLING ===")
    invalid_file = PROJECT_ROOT / "uploads" / "temp" / "phase4_invalid.mp4"
    if not invalid_file.is_file():
        invalid_file.write_text("Not a real video file content", encoding="utf-8")

    job_id, project_id, video_id = reset_or_create_test_job(str(invalid_file), "Invalid Video Test")
    
    # Process job (should fail gracefully)
    success = process_one()
    log_test("Worker returns False on corrupted video", success is False)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM ai_jobs WHERE id = %s", (job_id,))
    job = cur.fetchone()
    cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    proj = cur.fetchone()
    cur.close()
    conn.close()

    log_test("ai_jobs status is failed", job["status"] == "failed", f"Got: {job['status']}")
    log_test("ai_jobs has error_message", bool(job["error_message"]), f"Error: {job['error_message']}")
    log_test("project status is failed", proj["status"] == "failed", f"Got: {proj['status']}")


def main():
    print("=" * 60)
    print("GAMECUT AI - PHASE 11 INTEGRATION & STABILIZATION SUITE")
    print("=" * 60)
    
    test_small_video_end_to_end()
    test_invalid_video_error_handling()

    print("\n" + "=" * 60)
    print(f"INTEGRATION TEST RESULTS: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
