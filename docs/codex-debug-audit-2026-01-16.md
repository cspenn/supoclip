# Codex Debug Audit — 2026-01-16

## Scope & Method

Focused on the caption/transcript/clip pipeline and UI presentation paths for the reported A/V/text mismatch. Sources include code inspection plus targeted tooling.

Tools used:
- `radon cc` for complexity (backend/src/video_utils.py, backend/src/services/video_service.py, backend/src/ai.py, backend/src/transcription_mlx.py)
- `wc -l` for module size (backend/src/video_utils.py)

## Pipeline Summary (Current Behavior)

1. Transcribe video with parakeet-mlx and cache word-level timings.
2. Format transcript into “SRT-style” line ranges and send to LLM for segment selection.
3. Snap segment start to a sentence boundary, then extract verbatim text from cached words.
4. Create clips; add 150ms buffer and render word-by-word subtitle overlays using cached word timings.
5. Store clip metadata (start/end strings + extracted text) and display in UI.

Key locations: `backend/src/video_utils.py:161`, `backend/src/video_utils.py:376`, `backend/src/video_utils.py:463`, `backend/src/services/video_service.py:248`, `backend/src/video_utils.py:1483`.

## Findings: Likely Root Causes of A/V/Text Mismatch

1. Verbatim transcript replacement silently falls back to AI text when cache lookup fails.
   - If `extract_text_from_cache` returns None, the code keeps the AI-generated summary text, which can diverge from the actual audio/video.
   - Evidence: `backend/src/services/video_service.py:248`, `backend/src/services/video_service_async.py:121`, `backend/src/video_utils.py:235`.
   - Failure modes include cache missing/unwritable paths or stale caches (see next finding).

2. Transcript cache is keyed only by file stem and has no version/metadata validation in the loader used for captions.
   - `load_cached_transcript_data` does not check `_cache_version`, mtime, or video hash, so stale caches can be read even after transcription changes.
   - Evidence: `backend/src/video_utils.py:220`. The cache writer adds `_cache_version` in `backend/src/transcription_mlx.py:95`, but the reader ignores it.

3. Clip timing is altered after AI selection (snap + buffer), but stored timestamps and UI transcript are not updated to match the final clip boundaries.
   - Start time can be moved earlier and an additional 0.15s buffer is added during clip creation, while `clip_info` keeps the original string timestamps.
   - Result: displayed transcript timing doesn’t reflect what the clip actually contains, and edge words can look “wrong.”
   - Evidence: `backend/src/services/video_service.py:248`, `backend/src/video_utils.py:1524`, `backend/src/video_utils.py:1643`, `backend/src/video_utils.py:1687`.

4. Transcript text extraction and subtitle word selection use different boundary rules.
   - Transcript extraction only includes words that start inside the range, while subtitle generation includes any word that overlaps the range.
   - This creates predictable mismatches at clip boundaries (first/last words missing in transcript but shown in subtitles, or vice versa).
   - Evidence: `backend/src/video_utils.py:235` vs `backend/src/video_utils.py:923`.

5. The “SRT-style” transcript used for AI is line-based, not word-based.
   - Each line can contain up to 20 words with a single start/end time, reducing boundary precision and conflicting with the intended “granular SRT” flow.
   - Evidence: `backend/src/video_utils.py:376`, `backend/src/video_utils.py:413`, `backend/src/video_utils.py:463`.

6. Word reconstruction timing can drift due to heuristic realignment.
   - `_align_reconstructed_words` uses an 80% length heuristic; complex tokenization can shift word boundaries and timing.
   - This directly impacts word-level subtitles and text extraction.
   - Evidence: `backend/src/transcription_mlx.py:425`.

7. Short-word filtering in subtitle generation can drop legitimate words.
   - Any word < 50ms is skipped; fast speech often produces short real words (“a”, “I”).
   - That yields captions that omit spoken words and appear misaligned.
   - Evidence: `backend/src/video_utils.py:1309`.

## Caption Clipping (Visual Cutoff)

- The renderer still depends on a tight screenshot bounding box; margins are applied after rasterization.
- Even with a larger dynamic margin, the bounding box can undercount descenders or strokes, so text may still clip.
- Evidence: `backend/src/video_utils.py:1023`, `backend/src/subtitle_renderer.py:52` and prior fix notes in `docs/progress/fixes/2025-11-19-root-causes.md`.

## Defaults & Settings Drift

- Frontend submits `subtitle_style`, `subtitle_position`, and `output_resolution`, but the `/tasks` pipeline drops these fields; the worker signature doesn’t accept them and the task service doesn’t pass them.
- This explains “defaults not honored” and inconsistent subtitle placement/style.
- Evidence: `frontend/src/app/page.tsx:156`, `backend/src/api/routes/tasks.py:50`, `backend/src/workers/tasks.py:20`, `backend/src/services/task_service.py:34`.

## Complexity & Technical Debt Signals

- `backend/src/video_utils.py` is 1894 lines and mixes transcription formatting, face detection, subtitle rendering, and encoding. This increases the risk of subtle timing regressions.
- Radon shows multiple B-complexity blocks in critical sections (e.g., `create_optimized_clip`, `format_transcript_for_ai`).
- Evidence: `backend/src/video_utils.py` size and `radon` results from this audit.

## Suggested Verification Steps (No Code Changes)

1. Cache integrity check: log presence and `_cache_version` for each clip to confirm the same transcript cache is used for AI selection and subtitle generation.
2. Boundary audit: for a short clip, compare `clip.text` words vs subtitle word list at start/end; verify whether mismatch is due to overlap rules.
3. Controlled sync test: use a 10–15s reference video with known transcript and timestamps; measure word onset vs subtitle overlay to quantify drift.
4. Settings path audit: confirm whether `/tasks` or `/start-with-progress` is used in production; only the async endpoint accepts subtitle style/position and output resolution today.
