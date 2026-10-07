# GameCut AI Pipeline

GameCut AI uses a deterministic analysis and rendering pipeline with a constrained editing-planner layer.

## Deterministic Analysis Layer

The worker reads queued jobs from `ai_jobs` and uses the existing `videos.file_path` value. The original uploaded video is never modified.

Generated analysis files live under:

```text
uploads/temp/<job_id>/
```

Current files:

- `scene_analysis.json`: PySceneDetect scene boundaries.
- `transcript.json`: faster-whisper speech segments when available.
- `audio_analysis.json`: optional audio energy, peak, and change signals.
- `visual_analysis.json`: optional OpenCV frame-change signals.
- `highlight_candidates.json`: deterministic candidate scores and reasons.

## Agent Layer

The V1 agent is an editing planner, not a video-processing engine. It receives structured summaries and candidate data, then returns an editing-plan JSON object.

The default provider is deterministic/mock:

```text
GAMECUT_AGENT_PROVIDER=deterministic
```

No LLM API key is required. No shell commands, SQL, or arbitrary filesystem paths are exposed to the agent.

## Editing Plan

The plan schema is:

```json
{
  "target_duration": 45,
  "aspect_ratio": "9:16",
  "clips": [
    {
      "start": 12.3,
      "end": 24.8,
      "reason": "high combined highlight score"
    }
  ],
  "subtitles": true,
  "thumbnail": true,
  "provider": "deterministic"
}
```

## Validation

Before rendering, `agents/validator.py` rejects:

- non-object plans
- invalid target durations
- unsupported aspect ratios
- empty clips
- non-numeric timestamps
- `start >= end`
- negative timestamps
- timestamps beyond video duration
- clips longer than the configured maximum
- total duration above 60 seconds
- overlapping clips

Invalid agent plans do not execute FFmpeg.

## Tool Layer

Allowed tools are regular Python functions:

- load highlight candidates
- load transcript data
- select clips deterministically
- create editing plans
- validate plans
- render video with FFmpeg
- validate final output with ffprobe

The agent never directly executes FFmpeg or shell commands.

## Rendering

`processing/clip_renderer.py`:

1. trims selected clips with FFmpeg
2. normalizes clips to MP4/H.264/AAC when audio exists
3. converts to vertical `1080x1920` with center crop
4. concatenates normalized clips
5. maps transcript timestamps into the final timeline
6. burns SRT subtitles when transcript data exists
7. generates a thumbnail
8. validates output with ffprobe

Final files live under:

```text
uploads/processed/
```

The database stores the relative output path in `videos.output_path`.

## Fallback

If an external agent provider is unavailable, malformed, times out, or returns an invalid plan, the system falls back to the deterministic provider. If no valid candidates exist, the job fails cleanly with a useful error instead of executing an unsafe plan.

## Limitations

- No game-specific kill detection.
- No custom model training.
- No cloud storage.
- No long-term memory.
- No automatic publishing.
- V1 smart editing depends on deterministic candidate quality.
