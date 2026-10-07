import argparse
import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from mysql.connector import Error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection.audio_analyzer import analyze_audio_regions, config_from_env as audio_config_from_env
from detection.highlight_scorer import generate_highlight_candidates, config_from_env
from detection.editing_profiles import config_for_style
from detection.montage_detector import detect_montage_events
from detection.game_event_detector import detect_game_events
from detection.scene_detector import analyze_video_scenes
from detection.speech_analyzer import transcribe_audio
from detection.visual_analyzer import analyze_visual_regions, config_from_env as visual_config_from_env
from agents.editing_agent import generate_validated_plan
from agents.schemas import AgentPreferences
from processing.basic_editor import build_basic_plan, motion_settings
from processing.clip_renderer import render_highlight_video, write_render_manifest
from utils.db import get_db_connection
from utils.ffmpeg import extract_audio, get_metadata
from utils.logging import configure_logging, log_extra
from jobs.execution import (
    JobOwnershipLostError,
    attach_execution_token,
    execution_token_for,
    execution_work_directory,
    payload_as_dict,
)


configure_logging()
logger = logging.getLogger("gamecut.worker")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = PROJECT_ROOT / "uploads" / "temp"
PROCESSED_ROOT = PROJECT_ROOT / "uploads" / "processed"


def _execution_token_sql_guard():
    """SQL predicate used by every worker-side state transition.

    `payload` is a JSON column.  The token is assigned atomically when a
    worker claims the job and invalidated whenever the job is regenerated or
    reclaimed.  This prevents stale workers from publishing their result.
    """
    return (
        "id = %s AND status = 'processing' "
        "AND delete_requested_at IS NULL "
        "AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$._gamecut_runtime.execution_token')) = %s"
    )


def _lease_seconds():
    """Return the stale-worker recovery threshold with safe operational bounds."""
    try:
        value = int(os.getenv("GAMECUT_JOB_LEASE_SECONDS", "3600"))
    except ValueError:
        value = 3600
    return min(86400, max(300, value))


def _heartbeat_seconds():
    """Return a heartbeat interval that always remains below the lease timeout."""
    try:
        value = int(os.getenv("GAMECUT_JOB_HEARTBEAT_SECONDS", "30"))
    except ValueError:
        value = 30
    return min(max(10, value), max(10, _lease_seconds() // 3))


def _set_related_processing(cursor, project_id, video_id):
    cursor.execute("UPDATE projects SET status = 'processing' WHERE id = %s", (project_id,))
    cursor.execute(
        """
        UPDATE videos
        SET status = 'processing',
            processing_started_at = COALESCE(processing_started_at, NOW())
        WHERE id = %s
        """,
        (video_id,),
    )


def _set_related_failed(cursor, project_id, video_id):
    cursor.execute("UPDATE projects SET status = 'failed' WHERE id = %s", (project_id,))
    cursor.execute("UPDATE videos SET status = 'failed' WHERE id = %s", (video_id,))


def _set_related_completed(cursor, project_id, video_id, output_path, duration):
    cursor.execute(
        "UPDATE projects SET status = 'completed', completed_at = NOW() WHERE id = %s",
        (project_id,),
    )
    cursor.execute(
        """
        UPDATE videos
        SET status = 'processed',
            output_path = %s,
            duration = %s,
            processing_completed_at = NOW()
        WHERE id = %s
        """,
        (output_path, int(round(duration)), video_id),
    )


def resolve_project_path(relative_path):
    if not relative_path:
        raise ValueError("Video path is empty")

    path = Path(relative_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    resolved = path.resolve()
    if PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT:
        raise ValueError("Video path is outside the project directory")
    return resolved


def recover_stale_jobs():
    """Make abandoned executions available to another worker.

    The heartbeat updates `updated_at` while an execution is alive.  Once that
    heartbeat expires, the next claim receives a new execution token and an
    isolated workspace; an old process that later wakes up therefore loses all
    guarded writes and cannot publish an obsolete edit.
    """
    lease_seconds = _lease_seconds()
    with get_db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                f"""
                UPDATE ai_jobs
                SET status = 'queued',
                    progress = 0,
                    current_step = 'recovered_after_lease_expiry',
                    error_message = 'Previous worker lease expired; retrying.',
                    available_at = NOW(),
                    started_at = NULL
                WHERE status = 'processing'
                  AND attempts < max_attempts
                  AND updated_at < (NOW() - INTERVAL {lease_seconds} SECOND)
                """
            )
            recovered = cursor.rowcount

            # A lease expiry after the final allowed attempt is terminal. Do
            # not let it remain forever in `processing`; only mark the shared
            # project/video failed when no newer job is still active.
            cursor.execute(
                f"""
                SELECT id, project_id, video_id
                FROM ai_jobs
                WHERE status = 'processing'
                  AND attempts >= max_attempts
                  AND updated_at < (NOW() - INTERVAL {lease_seconds} SECOND)
                FOR UPDATE
                """
            )
            exhausted_jobs = cursor.fetchall()
            exhausted = 0
            for stale_job in exhausted_jobs:
                cursor.execute(
                    """
                    UPDATE ai_jobs
                    SET status = 'failed',
                        current_step = 'failed',
                        error_message = 'Worker lease expired after maximum attempts.',
                        completed_at = NOW()
                    WHERE id = %s AND status = 'processing'
                    """,
                    (stale_job["id"],),
                )
                if cursor.rowcount != 1:
                    continue

                exhausted += 1
                cursor.execute(
                    """
                    SELECT COUNT(*) AS active_jobs
                    FROM ai_jobs
                    WHERE project_id = %s
                      AND video_id = %s
                      AND id <> %s
                      AND status IN ('queued', 'processing')
                    """,
                    (stale_job["project_id"], stale_job["video_id"], stale_job["id"]),
                )
                active = cursor.fetchone()
                if not active or int(active["active_jobs"] or 0) == 0:
                    _set_related_failed(cursor, stale_job["project_id"], stale_job["video_id"])

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    if recovered or exhausted:
        logger.warning(
            "Recovered stale job executions",
            **log_extra(
                recovered_count=recovered,
                exhausted_count=exhausted,
                lease_seconds=lease_seconds,
            ),
        )
    return recovered


def heartbeat_job(job):
    """Touch a job only while this worker still owns its execution token."""
    token = execution_token_for(job)
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"UPDATE ai_jobs SET updated_at = NOW() WHERE {_execution_token_sql_guard()}",
                (job["id"], token),
            )
            owned = cursor.rowcount == 1
            if owned:
                connection.commit()
            else:
                connection.rollback()
            return owned
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def finalize_deleted_job(job):
    """Release a deleted project's worker lease after ownership is lost."""
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE ai_jobs
                SET status = 'cancelled',
                    current_step = 'cancelled_for_project_deletion',
                    completed_at = NOW(),
                    execution_token = NULL
                WHERE id = %s
                  AND status = 'processing'
                  AND delete_requested_at IS NOT NULL
                """,
                (job["id"],),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


class JobHeartbeat:
    """Keeps a long FFmpeg/ML execution recoverable without duplicate publish."""

    def __init__(self, job):
        self.job = job
        self._stop = threading.Event()
        self._ownership_lost = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"gamecut-heartbeat-{job['id']}",
            daemon=True,
        )

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(2, _heartbeat_seconds() + 1))

    def ensure_owned(self):
        if self._ownership_lost.is_set():
            raise JobOwnershipLostError("Job execution was cancelled, regenerated, or reclaimed")

    def _run(self):
        while not self._stop.wait(_heartbeat_seconds()):
            try:
                if not heartbeat_job(self.job):
                    self._ownership_lost.set()
                    logger.info("Worker lost job ownership", **log_extra(job_id=self.job["id"]))
                    return
            except Exception as exc:
                # A transient DB outage must not immediately kill rendering. If
                # it persists, the lease mechanism safely reclaims the job.
                logger.warning(
                    "Job heartbeat failed",
                    **log_extra(job_id=self.job["id"], error=str(exc)[:500]),
                )


def claim_one_job():
    recover_stale_jobs()
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """
            SELECT *
            FROM ai_jobs
            WHERE status = 'queued'
              AND available_at <= NOW()
              AND attempts < max_attempts
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            FOR UPDATE
            """
        )
        job = cursor.fetchone()
        if not job:
            connection.rollback()
            logger.info("No queued jobs found")
            return None

        claimed_payload = attach_execution_token(job.get("payload"))
        execution_token = claimed_payload["_gamecut_runtime"]["execution_token"]
        cursor.execute(
            """
            UPDATE ai_jobs
            SET status = 'processing',
                progress = 0,
                current_step = 'queued',
                attempts = attempts + 1,
                error_message = NULL,
                started_at = NOW(),
                payload = %s
            WHERE id = %s AND status = 'queued'
            """,
            (json.dumps(claimed_payload, ensure_ascii=False, separators=(",", ":")), job["id"]),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            logger.info("Queued job was already claimed", **log_extra(job_id=job["id"]))
            return None

        _set_related_processing(cursor, job["project_id"], job["video_id"])
        connection.commit()
        job["payload"] = claimed_payload
        job["execution_token"] = execution_token
        logger.info(
            "Job claimed",
            **log_extra(
                job_id=job["id"],
                project_id=job["project_id"],
                video_id=job["video_id"],
                execution_token=execution_token[:8],
            ),
        )
        return job
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def update_job(job, progress, current_step):
    """Persist progress only if this execution still owns the job."""
    token = execution_token_for(job)
    progress = max(0, min(100, int(progress)))
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                UPDATE ai_jobs
                SET progress = %s, current_step = %s
                WHERE {_execution_token_sql_guard()}
                """,
                (progress, current_step, job["id"], token),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise JobOwnershipLostError("Job ownership was lost before progress could be saved")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    logger.info(
        "Job status changed",
        **log_extra(job_id=job["id"], progress=progress, current_step=current_step),
    )


def load_scene_regions(scene_analysis_path):
    data = json.loads(Path(scene_analysis_path).read_text(encoding="utf-8"))
    regions = data.get("scenes", [])
    if not isinstance(regions, list):
        raise ValueError("Scene analysis does not contain regions")
    return regions


def load_transcript_segments(transcript_path):
    """Read the optional speech analysis in the renderer's stable shape."""
    data = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        segments = data
    elif isinstance(data, dict):
        segments = data.get("segments", [])
    else:
        segments = []
    return [segment for segment in segments if isinstance(segment, dict)]


def requested_target_duration(payload):
    """Normalize both upload and regeneration duration payload formats."""
    requested_length = payload.get("target_duration")
    if requested_length is None:
        try:
            requested_length = float(str(payload.get("output_length", "45")).split()[0])
        except (TypeError, ValueError):
            requested_length = 45
    try:
        duration = float(requested_length)
    except (TypeError, ValueError) as exc:
        raise ValueError("Requested output duration must be numeric") from exc
    if duration <= 0:
        raise ValueError("Requested output duration must be greater than zero")
    return duration


def build_production_plan(job_dir, candidates, video_duration, payload):
    """Create a validated vertical-edit plan without losing current controls.

    The basic planner keeps the existing score ordering, context padding, and
    speed-aware source-duration selection.  Its safe candidate set is then fed
    through the agent-plan validator, which provides the canonical plan used
    by the 9:16 renderer.
    """
    target_duration = requested_target_duration(payload)
    preselected = build_basic_plan(
        candidates,
        video_duration,
        target_duration=target_duration,
        padding_before=float(payload.get("padding_before", os.getenv("GAMECUT_BASIC_PADDING_BEFORE", "2"))),
        padding_after=float(payload.get("padding_after", os.getenv("GAMECUT_BASIC_PADDING_AFTER", "3"))),
        style=payload.get("style", "Esports"),
        speed=payload.get("playback_speed"),
    )
    if not preselected["clips"]:
        raise RuntimeError("No suitable highlights were found")

    # The agent reads its context from disk.  Persist only the preselected,
    # non-overlapping candidates so every provider receives exactly the ranges
    # that the deterministic fallback and FFmpeg renderer can safely process.
    candidates_path = Path(job_dir) / "highlight_candidates.json"
    candidates_path.write_text(
        json.dumps(
            {
                "video_duration": float(video_duration),
                "candidates": preselected["clips"],
                "selection_source": "score_padding_preselection",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    source_selection_duration = sum(
        float(clip["end"]) - float(clip["start"])
        for clip in preselected["clips"]
    )
    preferences = AgentPreferences(
        target_duration=target_duration,
        source_selection_duration=source_selection_duration,
        aspect_ratio="9:16",
        # Captions are a product guarantee when the transcript contains text;
        # the renderer only omits burning when no usable segment maps to a clip.
        subtitles=True,
        thumbnail=True,
        style=str(preselected["style"]),
        motion_mode=str(preselected["motion_mode"]),
        speed=float(preselected["speed"]),
    )
    plan = generate_validated_plan(job_dir, preferences=preferences)
    if not plan["clips"]:
        raise RuntimeError("No suitable highlights were found")
    if plan.get("aspect_ratio") != "9:16":
        raise RuntimeError("Production highlight plans must use a 9:16 aspect ratio")
    return plan


def fetch_video_for_job(job):
    with get_db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, file_path, original_filename, stored_filename, file_size, mime_type
                FROM videos
                WHERE id = %s AND project_id = %s AND user_id = %s
                """,
                (job["video_id"], job["project_id"], job["user_id"]),
            )
            video = cursor.fetchone()
        finally:
            cursor.close()

    if not video:
        raise ValueError("Video record not found for job")
    return video


def cleanup_job_temp_files(job_dir):
    """
    Removes intermediate render files (extracted audio, individual trimmed clips,
    intermediate concat/subtitled videos) while preserving JSON manifests and subtitles.srt.
    """
    try:
        job_dir = Path(job_dir)
        if not job_dir.is_dir():
            return

        # Remove clips directory
        clips_dir = job_dir / "clips"
        if clips_dir.is_dir():
            import shutil
            shutil.rmtree(clips_dir, ignore_errors=True)

        # Remove intermediate render binaries
        intermediate_files = ["audio.wav", "concat.mp4", "concat_list.txt", "subtitled.mp4"]
        for fname in intermediate_files:
            target = job_dir / fname
            if target.is_file():
                try:
                    target.unlink()
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Temp cleanup warning", **log_extra(error=str(exc)[:200]))


def cleanup_unpublished_output(output_path):
    """Remove a run-specific output that failed ownership checks before publish."""
    if not output_path:
        return

    try:
        output = Path(output_path).resolve()
        processed_root = PROCESSED_ROOT.resolve()
        if processed_root not in output.parents:
            raise ValueError("Refusing to clean an output outside the processed root")

        thumbnail = output.with_name(output.stem + "_thumbnail.jpg")
        for path in (output, thumbnail):
            if path.is_file():
                path.unlink()
    except Exception as exc:
        logger.warning(
            "Unpublished output cleanup warning",
            **log_extra(output_path=str(output_path), error=str(exc)[:200]),
        )


def cleanup_failed_execution(job_dir, output_path, published):
    """Remove only artifacts that were never committed as the current output."""
    if not published:
        cleanup_unpublished_output(output_path)
    if job_dir:
        cleanup_job_temp_files(job_dir)


def _active_sibling_job_exists(cursor, job):
    """Return whether a newer execution still owns this video's visible state."""
    cursor.execute(
        """
        SELECT COUNT(*) AS active_jobs
        FROM ai_jobs
        WHERE project_id = %s
          AND video_id = %s
          AND id <> %s
          AND status IN ('queued', 'processing')
        """,
        (job["project_id"], job["video_id"], job["id"]),
    )
    result = cursor.fetchone()
    if isinstance(result, dict):
        return int(result.get("active_jobs") or 0) > 0
    return bool(result and result[0])


def retry_delay_seconds(attempts):
    """Use bounded exponential backoff so transient failures do not hammer dependencies."""
    try:
        attempt_number = max(1, int(attempts))
    except (TypeError, ValueError):
        attempt_number = 1
    return min(900, 15 * (2 ** min(6, attempt_number - 1)))


def is_retryable_error(error):
    """Separate deterministic input/plan failures from operational failures."""
    if isinstance(error, (ValueError, KeyError, TypeError, JobOwnershipLostError)):
        return False

    message = str(error).lower()
    permanent_markers = (
        "no suitable highlights",
        "unsupported video",
        "does not contain a video stream",
        "video file does not exist",
        "video metadata could not be read",
        "video duration must be greater than zero",
        "outside the project directory",
        "editing plan",
    )
    return not any(marker in message for marker in permanent_markers)


def retry_job(job, error_message):
    """Requeue an owned execution with a new future availability time."""
    token = execution_token_for(job)
    delay = retry_delay_seconds(job.get("attempts"))
    clean_message = str(error_message)[:1000]
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                UPDATE ai_jobs
                SET status = 'queued',
                    progress = 0,
                    current_step = 'retry_scheduled',
                    error_message = %s,
                    available_at = DATE_ADD(NOW(), INTERVAL %s SECOND),
                    started_at = NULL
                WHERE {_execution_token_sql_guard()}
                """,
                (clean_message, delay, job["id"], token),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                logger.info(
                    "Skipping retry for an obsolete job execution",
                    **log_extra(job_id=job["id"]),
                )
                return False
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    logger.warning(
        "Job retry scheduled",
        **log_extra(job_id=job["id"], delay_seconds=delay, error_message=clean_message),
    )
    return True


def complete_rendering(job, relative_output_path, output_duration):
    """Atomically publish an output only while its execution remains current."""
    token = execution_token_for(job)
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                UPDATE ai_jobs
                SET status = 'completed',
                    progress = 100,
                    current_step = 'completed',
                    completed_at = NOW()
                WHERE {_execution_token_sql_guard()}
                """,
                (job["id"], token),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise JobOwnershipLostError("Job ownership was lost before output publication")
            _set_related_completed(cursor, job["project_id"], job["video_id"], relative_output_path, output_duration)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    logger.info("Job completed", **log_extra(job_id=job["id"], output_path=relative_output_path))


def fail_job(job, error_message):
    """Fail only the current execution; a newer execution must stay untouched."""
    clean_message = str(error_message)[:1000]
    token = execution_token_for(job)
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    UPDATE ai_jobs
                    SET status = 'failed',
                        error_message = %s,
                        current_step = 'failed',
                        completed_at = NOW()
                    WHERE {_execution_token_sql_guard()}
                    """,
                    (clean_message, job["id"], token),
                )
                if cursor.rowcount != 1:
                    connection.rollback()
                    logger.info(
                        "Skipping failure update for an obsolete job execution",
                        **log_extra(job_id=job["id"]),
                    )
                    return False
                if not _active_sibling_job_exists(cursor, job):
                    _set_related_failed(cursor, job["project_id"], job["video_id"])
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
    except Exception:
        logger.exception("Could not record job failure", **log_extra(job_id=job["id"]))
        return False

    logger.error("Job failed", **log_extra(job_id=job["id"], error_message=clean_message))
    return True


def retry_or_fail_job(job, error):
    """Honor the queue's retry contract while keeping deterministic failures terminal."""
    try:
        attempts = int(job.get("attempts") or 0)
        max_attempts = int(job.get("max_attempts") or 1)
    except (TypeError, ValueError):
        attempts, max_attempts = 1, 1

    if attempts < max_attempts and is_retryable_error(error):
        try:
            return retry_job(job, error)
        except Exception:
            logger.exception("Could not schedule job retry", **log_extra(job_id=job["id"]))
            # The still-processing job is recoverable by the lease reaper.
            return False
    return fail_job(job, error)


def process_job(job, fail_job_id=None):
    started = datetime.now(timezone.utc)
    execution_token = execution_token_for(job)
    heartbeat = JobHeartbeat(job)
    job_dir = None
    output_path = None
    published = False
    logger.info(
        "Job started",
        **log_extra(job_id=job["id"], execution_token=execution_token[:8]),
    )

    try:
        heartbeat.start()
        heartbeat.ensure_owned()
        if fail_job_id is not None and int(job["id"]) == int(fail_job_id):
            raise RuntimeError("Simulated scene detection failure requested")

        update_job(job, 5, "analyzing")
        video = fetch_video_for_job(job)
        video_path = resolve_project_path(video["file_path"])
        job_dir = execution_work_directory(ANALYSIS_ROOT, job["id"], execution_token)
        job_dir.mkdir(parents=True, exist_ok=True)
        analysis_path = job_dir / "scene_analysis.json"
        transcript_path = job_dir / "transcript.json"
        audio_path = job_dir / "audio.wav"
        audio_analysis_path = job_dir / "audio_analysis.json"
        visual_analysis_path = job_dir / "visual_analysis.json"
        candidates_path = job_dir / "highlight_candidates.json"
        payload_for_style = payload_as_dict(job.get("payload"))
        motion_mode = motion_settings(
            payload_for_style.get("style"), payload_for_style.get("playback_speed")
        )["mode"] != "normal"

        # Motion modes are whole-video timeline effects. They do not need the
        # expensive highlight-analysis pipeline; analyzing a 15-minute upload
        # before applying a simple speed change made the job appear stuck.
        if motion_mode and not analysis_path.is_file():
            metadata = get_metadata(str(video_path))
            duration = float((metadata.get("format") or {}).get("duration") or 0)
            if duration <= 0:
                raise RuntimeError("Video duration could not be read")
            analysis_path.write_text(json.dumps({
                "video": str(video_path), "duration": duration,
                "scene_count": 1,
                "scenes": [{"start": 0.0, "end": duration, "duration": duration}],
                "metadata": {"format_name": (metadata.get("format") or {}).get("format_name")},
            }, indent=2), encoding="utf-8")
            transcript_path.write_text(json.dumps({"language": None, "segments": [], "missing": True}, indent=2), encoding="utf-8")

        logger.info(
            "Starting scene detection",
            **log_extra(
                job_id=job["id"],
                video_id=job["video_id"],
                video_path=str(video_path),
                mime_type=video.get("mime_type"),
                file_size=video.get("file_size"),
            ),
        )

        if analysis_path.is_file():
            update_job(job, 40, "scene_detection_completed")
            logger.info(
                "Using existing scene analysis",
                **log_extra(job_id=job["id"], analysis_path=str(analysis_path)),
            )
        else:
            update_job(job, 20, "scene_detection")
            analysis = analyze_video_scenes(str(video_path), analysis_path)

            logger.info(
                "Scene detection result",
                **log_extra(
                    job_id=job["id"],
                    video_duration=analysis["duration"],
                    scene_count=analysis["scene_count"],
                    analysis_path=str(analysis_path),
                ),
            )

            update_job(job, 40, "scene_detection_completed")

        update_job(job, 45, "speech_analysis")
        if transcript_path.is_file():
            logger.info("Using existing transcript", **log_extra(job_id=job["id"], transcript_path=str(transcript_path)))
        else:
            try:
                ok, error = extract_audio(str(video_path), str(audio_path))
                if ok:
                    transcript = transcribe_audio(audio_path, output_path=transcript_path)
                    logger.info(
                        "Speech analysis result",
                        **log_extra(
                            job_id=job["id"],
                            segment_count=len(transcript.get("segments", [])),
                            language=transcript.get("language"),
                            device=transcript.get("device"),
                        ),
                    )
                else:
                    logger.warning("Audio extraction failed; continuing without transcript", **log_extra(job_id=job["id"], error=str(error)[:500]))
            except Exception as exc:
                logger.warning("Speech analysis failed; continuing without transcript", **log_extra(job_id=job["id"], error=str(exc)[:500]))
        if not transcript_path.is_file():
            transcript_path.write_text(json.dumps({"language": None, "segments": [], "missing": True}, indent=2), encoding="utf-8")
        update_job(job, 46, "speech_analysis_completed")

        regions = [] if motion_mode else load_scene_regions(analysis_path)

        update_job(job, 48, "audio_analysis")
        try:
            audio_result = analyze_audio_regions(
                str(video_path),
                regions,
                output_path=audio_analysis_path,
                config=audio_config_from_env(),
                job_id=job["id"],
            )
            logger.info(
                "Audio analysis result",
                **log_extra(
                    job_id=job["id"],
                    analyzed_count=audio_result["analyzed_count"],
                    failed_count=audio_result["failed_count"],
                    analysis_path=str(audio_analysis_path),
                ),
            )
        except Exception as exc:
            logger.warning(
                "Audio analysis failed; continuing without audio signals",
                **log_extra(job_id=job["id"], error=str(exc)[:500]),
            )

        update_job(job, 52, "visual_analysis")
        try:
            visual_result = analyze_visual_regions(
                str(video_path),
                regions,
                output_path=visual_analysis_path,
                config=visual_config_from_env(),
                job_id=job["id"],
            )
            logger.info(
                "Visual analysis result",
                **log_extra(
                    job_id=job["id"],
                    analyzed_count=visual_result["analyzed_count"],
                    failed_count=visual_result["failed_count"],
                    analysis_path=str(visual_analysis_path),
                ),
            )
        except Exception as exc:
            logger.warning(
                "Visual analysis failed; continuing without visual signals",
                **log_extra(job_id=job["id"], error=str(exc)[:500]),
            )

        update_job(job, 58, "highlight_scoring")
        scoring = generate_highlight_candidates(
            analysis_path,
            transcript_path,
            candidates_path,
            job_id=job["id"],
            audio_analysis_path=audio_analysis_path if audio_analysis_path.is_file() else None,
            visual_analysis_path=visual_analysis_path if visual_analysis_path.is_file() else None,
            config=config_for_style(payload_for_style.get("style"), config_from_env()),
        )

        logger.info(
            "Highlight scoring result",
            **log_extra(
                job_id=job["id"],
                scene_count=scoring["scene_count"],
                candidate_count=scoring["candidate_count"],
                overlap_removed_count=scoring["overlap_removed_count"],
                highest_score=scoring["highest_score"],
                total_selected_duration=scoring["total_selected_duration"],
                transcript_missing=scoring["transcript_missing"],
                audio_analysis_missing=scoring["audio_analysis_missing"],
                visual_analysis_missing=scoring["visual_analysis_missing"],
                candidates_path=str(candidates_path),
            ),
        )

        if scoring["candidate_count"] == 0:
            logger.warning("No highlight candidates found", **log_extra(job_id=job["id"]))

        update_job(job, 72, "clip_selection")
        candidates_data = json.loads(candidates_path.read_text(encoding="utf-8"))
        game_payload = payload_for_style
        kill_events = detect_game_events(
            str(video_path), game_payload.get("game", ""),
            output_path=job_dir / "game_events.json",
            before=float(game_payload.get("padding_before", 3)),
            after=float(game_payload.get("padding_after", 5)),
        )
        if kill_events.get("events"):
            candidates_data["game_events"] = kill_events["events"]
            candidates_data["event_detection"] = "game_hud_ocr"
            candidates_data["candidates"] = [dict(event, score=1.0, signals={"game_event": 1.0}) for event in kill_events["events"]]
        montage_candidates = detect_montage_events(
            candidates_data.get("candidates", []),
            candidates_data.get("video_duration", 0),
            max_events=int(os.getenv("GAMECUT_MONTAGE_MAX_EVENTS", "12")),
            minimum_gap=float(os.getenv("GAMECUT_MONTAGE_MIN_GAP", "1")),
        )
        job_payload = payload_for_style
        plan = build_production_plan(
            job_dir,
            montage_candidates or candidates_data.get("candidates", []),
            candidates_data.get("video_duration", 0),
            job_payload,
        )

        update_job(job, 78, "plan_validation")
        output_filename = (
            f"project_{job['project_id']}_job_{job['id']}_"
            f"{execution_token[:16]}_ai_highlight.mp4"
        )
        output_path = PROCESSED_ROOT / output_filename

        update_job(job, 85, "rendering")
        transcript_segments = load_transcript_segments(transcript_path)
        render_result = render_highlight_video(
            str(video_path),
            plan["clips"],
            transcript_segments,
            output_path,
            job_dir,
            subtitles=bool(transcript_segments),
            playback_speed=plan.get("speed", 1.0),
        )
        write_render_manifest(render_result, job_dir / "render_result.json")

        heartbeat.ensure_owned()
        update_job(job, 98, "output_validation")
        relative_output_path = output_path.relative_to(PROJECT_ROOT).as_posix()
        complete_rendering(job, relative_output_path, render_result["metadata"]["duration"])
        published = True
        cleanup_job_temp_files(job_dir)
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "Processing duration",
            **log_extra(job_id=job["id"], duration_seconds=round(duration, 2)),
        )
        return True
    except JobOwnershipLostError as exc:
        logger.info(
            "Job execution stopped without publication",
            **log_extra(job_id=job["id"], error=str(exc)),
        )
        try:
            finalize_deleted_job(job)
        except Exception:
            logger.exception("Could not finalize deleted job", **log_extra(job_id=job["id"]))
        cleanup_unpublished_output(output_path)
        if job_dir:
            cleanup_job_temp_files(job_dir)
        return False
    except Exception as exc:
        logger.exception("Unexpected worker error", **log_extra(job_id=job["id"]))
        retry_or_fail_job(job, exc)
        cleanup_failed_execution(job_dir, output_path, published)
        return False
    finally:
        heartbeat.stop()


def process_one(fail_job_id=None):
    job = claim_one_job()
    if not job:
        return False
    return process_job(job, fail_job_id=fail_job_id)


def run_forever(poll_interval=5.0, fail_job_id=None):
    logger.info("Worker startup", **log_extra(mode="loop"))
    while True:
        try:
            processed = process_one(fail_job_id=fail_job_id)
            if not processed:
                import time

                time.sleep(poll_interval)
        except Error as exc:
            logger.error("Database unavailable", **log_extra(error=str(exc)))
            import time

            time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="GameCut AI scene detection worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--fail-job-id", type=int, default=None)
    args = parser.parse_args()

    if args.once:
        logger.info("Worker startup", **log_extra(mode="once"))
        try:
            process_one(fail_job_id=args.fail_job_id)
        except Error as exc:
            logger.error("Database unavailable", **log_extra(error=str(exc)))
        return

    run_forever(
        poll_interval=args.poll_interval,
        fail_job_id=args.fail_job_id,
    )


if __name__ == "__main__":
    main()
