# Architecture

GameCut AI consists of a PHP web application, a MySQL-backed job queue, a
Python worker, and private media storage. `ai_jobs` is the single canonical
execution state. `ai_job_events` is append-only history for status, progress,
and operational audit data; `projects` and `videos` contain user-facing
summaries only.

## AI Processing Pipeline

1. Upload gameplay to `uploads/original/`.
2. Create a project, video metadata row, and queued `ai_jobs` record.
3. Extract audio from the uploaded gameplay.
4. Run speech recognition to produce transcript segments.
5. Detect scenes and gameplay cuts.
6. Select highlight moments from transcript, scene changes, and gameplay signals.
7. Crop/reframe clips for the selected platform.
8. Generate and style subtitles.
9. Render the final short to `uploads/processed/`.
10. Show the finished video in Preview.
11. Let the user download/export the result.

Each job claim receives an execution token, lease, heartbeat, and isolated
workspace. Any progress, retry, failure, or publication update must be guarded
by that ownership token. Regeneration creates a new job revision and cancels
the old revision; it never reuses an active job row.

Project deletion is asynchronous: the UI requests cancellation, workers lose
ownership safely, and the CLI deletion reaper removes files and database rows
only after no queued or processing job remains.
