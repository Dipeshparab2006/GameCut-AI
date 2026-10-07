# GameCut AI Python Service

The Python service runs the GameCut AI analysis and Basic Auto Editor pipeline. The worker reads the uploaded video path from MySQL, scores highlights, builds a deterministic edit plan, renders a plain source-resolution MP4, validates it with ffprobe, and updates the existing PHP/MySQL records.

Supported game-event profiles include Free Fire, Free Fire MAX, Valorant, PUBG/BGMI, Fortnite, CS2, and Apex Legends. Free Fire uses a game-specific HUD/kill-feed OCR profile when optional Tesseract OCR is installed; otherwise it falls back to the game-agnostic audio/visual montage detector.

The current agent provider is deterministic/mock by default. It does not call an external LLM unless a future provider is configured.

## Setup

```powershell
cd "C:\xampp\htdocs\AI Video Editor\GameCut-AI"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r python\requirements.txt
```

## Environment Variables

```powershell
$env:GAMECUT_AI_API_TOKEN="change-this-local-token"
$env:GAMECUT_DB_HOST="127.0.0.1"
$env:GAMECUT_DB_PORT="3306"
$env:GAMECUT_DB_NAME="gamecut_ai"
$env:GAMECUT_DB_USER="root"
$env:GAMECUT_DB_PASS=""
$env:GAMECUT_FFMPEG_DIR="C:\xampp\htdocs\AI Video Editor\GameCut-AI\bin"
$env:GAMECUT_SCORE_WEIGHT_SPEECH="0.25"
$env:GAMECUT_SCORE_WEIGHT_AUDIO="0.20"
$env:GAMECUT_SCORE_WEIGHT_VISUAL="0.20"
$env:GAMECUT_SCORE_WEIGHT_SCENE="0.10"
$env:GAMECUT_SCORE_WEIGHT_DURATION="0.10"
$env:GAMECUT_SCORE_WEIGHT_CONTEXT="0.15"
$env:GAMECUT_HIGHLIGHT_KEYWORDS="let's go,no way,what,wow,nice,oh my god,clutch"
$env:GAMECUT_MIN_HIGHLIGHT_DURATION="5"
$env:GAMECUT_MAX_HIGHLIGHT_DURATION="30"
$env:GAMECUT_HIGHLIGHT_PADDING_BEFORE="3"
$env:GAMECUT_HIGHLIGHT_PADDING_AFTER="5"
$env:GAMECUT_HIGHLIGHT_OVERLAP_THRESHOLD="0.50"
$env:GAMECUT_AUDIO_MAX_REGIONS="80"
$env:GAMECUT_VISUAL_MAX_REGIONS="80"
$env:GAMECUT_VISUAL_SAMPLES_PER_REGION="8"
$env:GAMECUT_AGENT_PROVIDER="deterministic"
$env:GAMECUT_JOB_LEASE_SECONDS="3600"
$env:GAMECUT_JOB_HEARTBEAT_SECONDS="30"
$env:WHISPER_MODEL_SIZE="tiny"
$env:WHISPER_DEVICE="cpu"
```

`GAMECUT_FFMPEG_DIR` is optional when `ffmpeg` and `ffprobe` are already on PATH or available in the project `bin` folder.

## Start FastAPI

```powershell
cd "C:\xampp\htdocs\AI Video Editor\GameCut-AI"
.\.venv\Scripts\Activate.ps1
cd python
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

## Start The Worker

Process one queued job:

```powershell
cd "C:\xampp\htdocs\AI Video Editor\GameCut-AI\python"
..\.venv\Scripts\python.exe jobs\worker.py --once
```

Run continuously:

```powershell
cd "C:\xampp\htdocs\AI Video Editor\GameCut-AI\python"
..\.venv\Scripts\python.exe jobs\worker.py
```

Simulate a failure for one job:

```powershell
..\.venv\Scripts\python.exe jobs\worker.py --once --fail-job-id 123
```

## API Endpoints

```powershell
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/jobs/123 -H "X-GameCut-Token: change-this-local-token"
curl http://127.0.0.1:8000/jobs/123/status -H "X-GameCut-Token: change-this-local-token"
```

## Job Lifecycle

1. PHP upload creates a project, video, and queued `ai_jobs` row.
2. The worker claims one queued job inside a MySQL transaction using `SELECT ... FOR UPDATE`.
3. The worker updates `current_step = analyzing`, `progress = 5`.
4. The worker fetches `videos.file_path` and resolves it under the project directory.
5. The worker validates the video with file checks and ffprobe.
6. The worker reuses `uploads/temp/<job_id>/scene_analysis.json` when present, otherwise runs PySceneDetect.
7. The worker reads `uploads/temp/<job_id>/transcript.json` when present, otherwise attempts faster-whisper transcription.
8. The worker analyzes scene regions for audio energy, peaks, and sudden changes.
9. The worker analyzes scene regions for visual activity, transitions, and brightness changes.
10. The worker updates `current_step = highlight_scoring`, `progress = 58`.
11. Deterministic V1 scoring creates `uploads/temp/<job_id>/highlight_candidates.json`.
12. The planner creates and validates `uploads/temp/<job_id>/editing_plan.json`.
13. FFmpeg renders the selected clips to `uploads/processed/`.
14. ffprobe validates the output, FFmpeg creates a thumbnail, and MySQL is updated.
15. The job is marked `completed`, `progress = 100`.

Each worker claim receives an opaque execution token stored in the job payload.
Progress, failure, and final publication writes are conditional on that token;
an execution that is cancelled, regenerated, deleted, or reclaimed cannot
publish after it loses ownership. The worker heartbeats the job every
`GAMECUT_JOB_HEARTBEAT_SECONDS` (30 seconds by default). Jobs with no heartbeat
for `GAMECUT_JOB_LEASE_SECONDS` (one hour by default) are safely requeued with a
new token and an isolated work directory. An expired job that has exhausted its
configured attempts is marked failed rather than remaining indefinitely in
`processing`.

Regenerating from the PHP UI creates a new `ai_jobs` record and cancels queued
or active predecessors. It never resets an active job row in place. Per-run
artifacts live under `uploads/temp/<job-id>/<execution-token>/`, and generated
output names include the execution token to prevent write collisions.

Operational failures (for example, a transient FFmpeg or model-service error)
are retried while `attempts < max_attempts`, with exponential backoff capped at
15 minutes. Invalid input, invalid plans, and exhausted attempts are terminal.

If no candidates pass the configured threshold, the worker fails cleanly with a useful error. It does not invent or duplicate highlights.

## Audio Analysis

`python/detection/audio_analyzer.py` uses FFmpeg to decode only candidate scene regions to temporary in-memory PCM. It writes:

```txt
uploads/temp/<job_id>/audio_analysis.json
```

Signals are normalized per job:

- `energy`: RMS loudness.
- `peak`: strongest sample peak.
- `change`: rough first-half vs second-half volume change.
- `silence_before_after`: low-amplitude sample ratio.

Missing audio or per-region FFmpeg failures are recorded in the JSON and do not fail the whole job.

## Visual Analysis

`python/detection/visual_analyzer.py` uses OpenCV to sample frames inside candidate scene regions. It writes:

```txt
uploads/temp/<job_id>/visual_analysis.json
```

Signals are normalized per job:

- `activity`: average frame-to-frame difference.
- `transition`: strongest sampled frame difference.
- `brightness_change`: brightness range across sampled frames.

This is only a visual-interest heuristic. It does not detect kills, enemies, game events, or objects.

## Rendering

`python/processing/basic_editor.py` uses FFmpeg to:

- trim selected clips
- normalize to MP4/H.264
- preserve AAC audio when available
- normalize to source resolution and 30 FPS
- concatenate normalized clips
- keep subtitles disabled by default
- generate a thumbnail
- validate the final file with ffprobe

Generated outputs are stored under:

```text
uploads/processed/
```

The PHP preview page reads the relative `videos.output_path`.

## Agent Planning

`python/agents/` contains a constrained editing planner:

- `editing_agent.py`: provider abstraction and orchestration.
- `agent_tools.py`: safe deterministic tools.
- `validator.py`: strict plan validation.
- `schemas.py`: simple preferences/schema helpers.
- `prompts.py`: future LLM system prompt.

The default provider is deterministic, so no API key is needed. Invalid plans are rejected before rendering.

## Scoring Signals

The V1 scorer is not a machine-learning classifier. It is an explainable heuristic scorer using normalized `0.0` to `1.0` signals:

- `speech`: speech overlap, confidence where available, and configurable excitement keywords.
- `audio`: optional energy, peak, and change analysis.
- `visual`: optional activity, transition, and brightness-change analysis.
- `scene`: local scene-boundary density from scene detection.
- `duration`: preference for clips within the configured min/max range.
- `context`: speech and keyword signals in a padded context window around the scene.

Default combined score:

```text
final_score =
  0.25 * speech +
  0.20 * audio +
  0.20 * visual +
  0.10 * scene +
  0.10 * duration +
  0.15 * context
```

These weights are V1 heuristics, not scientifically optimal.

## Example Output

```json
{
  "job_id": 123,
  "video_duration": 1046.3,
  "weights": {
    "speech": 0.25,
    "audio": 0.2,
    "visual": 0.2,
    "scene": 0.1,
    "duration": 0.1,
    "context": 0.15
  },
  "candidate_count": 1,
  "highest_score": 0.826,
  "candidates": [
    {
      "start": 8.0,
      "end": 21.5,
      "duration": 13.5,
      "score": 0.824,
      "signals": {
        "speech": 0.749,
        "audio": 0.796,
        "visual": 0.407,
        "scene": 1.0,
        "duration": 0.821,
        "context": 0.733
      },
      "reason": [
        "high speech activity",
        "gaming excitement keyword signal",
        "strong audio peak",
        "high visual activity",
        "nearby scene changes",
        "strong contextual signal",
        "good highlight duration"
      ]
    }
  ]
}
```

Reasons are generated only from actual scoring signals. Keyword matches are treated as one weak signal, not proof of a highlight.

## Limitations

- No game-specific kill-feed/object detection yet.
- No LLM or agent review yet.
- Quiet but visually important moments can still be under-scored because V1 visual analysis measures motion/change, not game semantics.
- Missing transcripts are allowed, but the scorer becomes scene/duration/context-only and marks `transcript_missing = true`.
- Missing or failed audio/visual analysis is allowed. The scorer marks `audio_analysis_missing` or `visual_analysis_missing` and falls back to the available signals.
- This phase selects candidate ranges only. It does not render or concatenate clips.

## Tests

Run API tests:

```powershell
cd "C:\xampp\htdocs\AI Video Editor\GameCut-AI\python"
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

Run the real-MySQL concurrency suite only against a disposable database whose
name ends in `_test`:

```powershell
$env:GAMECUT_DB_NAME="gamecut_ai_test"
$env:GAMECUT_RUN_DB_INTEGRATION="1"
..\.venv\Scripts\python.exe -m unittest tests.test_live_queue_concurrency -v
```

Manual queue test:

```sql
INSERT INTO ai_jobs (project_id, video_id, user_id, job_type, status, priority, payload, available_at, created_at)
VALUES (1, 1, 1, 'video_processing', 'queued', 5, JSON_OBJECT('test', true), NOW(), NOW());
```

Only use IDs that already exist in `projects`, `videos`, and `users`.
