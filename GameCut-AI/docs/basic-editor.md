# Basic Auto Editor V1

Phase 13 is a deterministic pipeline: existing analysis produces scored candidates, candidates are padded and de-duplicated, clips are rendered to compatible MP4/H.264/AAC files, then concatenated and validated with ffprobe. The original upload is never modified.

The default context is 2 seconds before and 3 seconds after each candidate. Values are bounded by the source duration. Candidates with at least 50% overlap are reduced to the stronger candidate, and the final list is chronological.

FFmpeg normalizes each clip to source resolution, 30 FPS, yuv420p, H.264, and AAC when audio exists. Subtitles, effects, music, cropping, and agent-controlled ordering are not part of V1. Invalid timestamps, missing sources, no candidates, FFmpeg errors, and invalid output metadata fail the job cleanly.

V1 uses the existing heuristic scorer and does not identify game-specific events. It intentionally produces a plain source-resolution highlight video.
