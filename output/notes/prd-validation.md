# PRD / Spec → Implementation Validation

Audit-only. Every claim cites `file:line`. Ground truth: docs/prd.md, docs/spec.md, and src/ as of branch `main` (commit a3af789).

Legend: FULLY = implemented & wired into the live run path; PARTIAL = code exists but incomplete or not wired; MISSING = absent.

---

## THE HEADLINE FINDING (read first)

**Subtitles, fonts, and ALL subtitle-style customization are NEVER applied to generated clips in the real run path.** The Settings page persists font/size/color/stroke/shadow/position to `UserPreferences`, but no code outside `settings.py`/`models.py` ever reads `UserPreferences`, and `home.py` builds the `ProcessingRequest` with `subtitle_style=None`. Therefore every clip produced from the UI is rendered with NO burned-in subtitles at all.

Evidence chain:
- `src/pages/home.py:91-97` — `ProcessingRequest(source, task_id, min_clip_length, max_clip_length, output_resolution)`. No `subtitle_style`, no `custom_prompt`, no `logo_path`. Defaults apply.
- `src/services/video_service.py:70-72` — `ProcessingRequest.subtitle_style` defaults to `None`.
- `src/services/video_service.py:384-392` — `ClipOptions(output_resolution=..., subtitle_style=request.subtitle_style, logo_path=...)` → `subtitle_style=None`.
- `src/pipeline/clip.py:310` — `if opts.subtitle_style is not None:` guards ALL subtitle generation. With `None`, no `.ass` file is written and no `ass=` filter is added → clips have no captions.
- Grep confirmation: `SubtitleStyle(` is constructed only in a docstring example (`clip.py:14`) and a default fallback (`subtitles.py:153`). `UserPreferences` is referenced only in `settings.py` and `models.py` — never in `home.py` or `video_service.py`.

This is the most likely root of the user's "formatting and output issues" complaint: the entire subtitle feature (PRD Core Feature 4 & 6) is dead code in production. The recent "phone-frame preview" fix commits touched only the *Settings preview*, not the actual render path.

**Why 100% coverage + green tests missed it (the test-gap):** The test suite covers BOTH branches of the `if opts.subtitle_style is not None` guard in isolation, and actually *codifies the broken behavior as expected*:
- `tests/unit/test_clip.py:342` — explicit test "write_ass_file is NOT called when subtitle_style is None" (passes `ClipOptions(subtitle_style=None)`).
- `tests/unit/test_video_service.py:138-140` — asserts `req.subtitle_style is None` is the correct default.
- `tests/unit/test_home.py:144-148` — tests `_start_processing` builds a `ProcessingRequest`, but `home._start_processing` (`home.py:72-98`) has no `subtitle_style` parameter at all, so the test cannot detect the missing wiring.

No test exercises the real home→service→clip path asserting a non-None subtitle style reaches `generate_clip`. The unit tests pin the dead wiring in place. This is exactly why 100% line coverage and 466 green tests coexist with broken output.

---

## Requirement-by-Requirement Table

### Core Feature 1 — Video Input

| Requirement (PRD/spec) | Status | Evidence |
|---|---|---|
| YouTube download via yt-dlp | FULLY | `src/pipeline/download.py:216` `download_youtube_video`; URL ID extraction incl. Live/shorts `download.py:36-45` |
| Best video+audio up to 1080p | FULLY | `download.py:63` format string `bv*[height<=1080]+ba/...` |
| File upload via web UI | PARTIAL | `home.py:137-159` upload handler works BUT writes to hardcoded `/tmp` (`home.py:150`), not `temp/{task_id}/` per spec 5.2; also violates project rule "no /tmp". Uploaded file never moved into TEMP_DIR. |
| `source_type IN ('youtube','upload','url')` | PARTIAL | Model docstring `models.py:42` only lists youtube/upload; `'url'` never produced. A non-YouTube URL typed in the URL box is tagged `source_type='upload'` (`home.py:219`) and later treated as a local path → `FileNotFoundError` (`video_service.py:330-334`). Direct (non-YouTube) URL input is effectively broken. |
| Reject videos > MAX_VIDEO_DURATION | MISSING | No duration check anywhere; `MAX_VIDEO_DURATION` config var absent (see Config table). |

### Core Feature 2 — Transcription

| Requirement | Status | Evidence |
|---|---|---|
| parakeet-mlx offline transcription | FULLY | `src/pipeline/transcribe.py:281-288` `from_pretrained(...).transcribe(...)` |
| Word-level timestamps | FULLY | `transcribe.py:43-111` `merge_bpe_tokens` → `start_ms/end_ms` per word |
| Transcript cache | FULLY | `transcribe.py:125-188` load/save `.transcript_cache.json` |
| `PARAKEET_MODEL` configurable (spec 8.2) | MISSING | Model hardcoded `transcribe.py:25` `_DEFAULT_MODEL_ID`; no env override. |
| `RECONSTRUCT_WORDS_WITH_LLM` (spec 4.10, 8.2, default true) | MISSING | Path deliberately removed; `transcribe.py:6-8` docstring. Config var absent. Replaced by local BPE merge. (Documented as intentional in transcribe docstring, but contradicts spec 8.2 which still lists it.) |

### Core Feature 3 — Intelligent Clip Selection

| Requirement | Status | Evidence |
|---|---|---|
| LLM analysis, local + cloud routing | FULLY | `src/pipeline/analyze.py:494` `analyze_transcript`; routing `analyze.py:326-338`, `_analyze_with_pydantic_ai` / `_analyze_with_groq_structured` |
| 3–7 segments | PARTIAL | Prompt requests "3-7" (`analyze.py:206`) but NO hard cap/count enforcement in code. LLM could return more/fewer; no `target_clip_count` plumbed; `MAX_CLIPS` ceiling absent. |
| 10–45s duration | PARTIAL | Enforced via `validate_segments` (`analyze.py:286-302`) using min/max, but default min is 15s (`analyze.py:497`, `home.py:28`), not the PRD's 10. UI slider floor is 10 so 10–45 reachable. |
| Validation: start != end | FULLY | `analyze.py:276-284` rejects duration <= 0 |
| Validation: min/max duration | FULLY | `analyze.py:286-302` |
| Clean Start Rule (drop filler-word starts) | FULLY | Prompt `analyze.py:170-173` + post-filter `analyze.py:304-314` against `_FILLER_STARTS` |
| Verbatim text | FULLY (prompt-enforced only) | `analyze.py:175-177`; not verifiable in code |
| `@stamina.retry` on selection + re-attempt loop (spec 11.5) | MISSING | `analyze_transcript` has no retry decorator and no inner re-attempt loop. Spec'd `select_segments` signature/name does not exist. |
| `InsufficientSegmentsError` raised (spec 11.3) | PARTIAL | Raises generic `AnalysisError` instead (`analyze.py:563-569`). Named exception absent. |
| `ClipSegment` fields incl. `reasoning` | PARTIAL | Public model is `TranscriptSegment` (`analyze.py:48`) with `title` but NO `reasoning` field; `_RawSegment` parses `reasoning` (`analyze.py:78`) then discards it (`analyze.py:471-479`). Reasoning never persisted. |

### Core Feature 4 — Video Generation

| Requirement | Status | Evidence |
|---|---|---|
| 9:16 vertical output | FULLY | `clip.py:44-48` RESOLUTIONS all 9:16; crop `face_detect.py:97-151` |
| Smart crop face-centered | PARTIAL | `face_detect.detect_face_center` MediaPipe (`face_detect.py:35-94`); center fallback `face_detect.py:140-142`. BUT single representative frame only (`clip.py:286-288`), NOT spec 4.14's "up to 10 evenly spaced frames + median x-center". And face detect silently disabled if cv2 absent (see contradiction note). |
| MediaPipe primary + OpenCV DNN + Haar fallbacks (PRD line 37) | CONTRADICTED / MISSING | **PRD vs CLAUDE.md/spec contradiction.** PRD claims 3-tier fallback. CLAUDE.md + spec 4.14 say MediaPipe-only, center fallback, opencv-python removed. CODE matches CLAUDE.md/spec: detection is MediaPipe-only with center fallback (`face_detect.py:6-7` docstring). No DNN/Haar. **However spec's "opencv-python removed" is itself contradicted**: cv2 IS imported for frame extraction (`face_detect.py:171`) and dimension probing (`clip.py:393`). If cv2 is not installed, `get_representative_frame` returns None → face detection never runs → every clip is center-cropped. So "smart crop" depends on an undeclared/"removed" opencv dependency. |
| Word-level subtitles burned in | MISSING (in live path) | See HEADLINE. Code path exists (`subtitles.py`, `clip.py:308-320`) but never invoked because `subtitle_style=None` from UI. |
| Subtitle context-line / karaoke highlight (spec 9.2: active word primary, ≤6 context words dimmed, inline override tags) | MISSING | `subtitles.py:158-180` emits ONE isolated word per event, no grouping, no secondary color, no active-word highlight. `SubtitleStyle` (`subtitles.py:24-48`) lacks `secondary_color`, `shadow_color`, `bold` fields named in spec 9.3. |
| Customizable font/size/color/stroke/shadow/position | PARTIAL | Fields exist on `SubtitleStyle` (`subtitles.py:40-48`) and Settings UI (`settings.py:295-335`), but never reach a clip (HEADLINE). So customization is non-functional end-to-end. |
| Transitions (intro/outro MP4 templates; CLAUDE.md says round-robin) | MISSING | `ClipOptions.add_transitions`/`transitions_dir` "Reserved for future" (`clip.py:88-96`). `TRANSITIONS_DIR` config exists (`config.py:74`) but is never read. No transition logic in `build_ffmpeg_command`. |
| Logo overlay (spec 10.5) | MISSING | `clip.py:87` "not yet implemented"; `build_ffmpeg_command` (`clip.py:161-233`) has no `overlay`/`filter_complex`. `logo_path` threaded through but ignored. |
| H.264 + even dimensions | FULLY | `clip.py:226-228` libx264; `round_to_even` `face_detect.py:23-32` |
| Resolution targets match spec 10.1 (720p=1080×1920, 1080p=2160×3840) | DEVIATES (code labeling is arguably more correct than spec) | Code: `clip.py:44-48` 720p=(720,1280), 1080p=(1080,1920). The spec's own labels are odd (1080×1920 is literally a 1080p frame); the code's labels are conventionally correct and produce valid 9:16 output. Not broken — just mislabeled relative to spec. Default also differs: code default 1080p (`clip.py:50`, `home.py:27`) vs spec home default 720p. |
| `FFMPEG_PRESET` / `FFMPEG_CRF` configurable (spec 8.3) | MISSING | Hardcoded `"fast"` / `"23"` (`clip.py:227,229`); magic numbers, config vars absent (violates "no magic numbers"). |

### Core Feature 5 — Real-Time Progress

| Requirement | Status | Evidence |
|---|---|---|
| Live progress during pipeline | PARTIAL | Progress IS shown, but spec 6.2 explicitly says "via WebSocket... No polling." Implementation polls the DB every 1s with `ui.timer(1.0, _refresh)` (`task.py:230-262`). Functionally works; architecturally contradicts spec. |
| `progress_callback` WebSocket push (spec 4.15) | MISSING (as designed) | `home._start_processing` calls `process_video(request)` with NO `progress_callback` (`home.py:98`), so the callback path is unused in production; UI relies solely on DB polling. |
| Per-clip progress 60→95 / "Rendering clip N of M" | PARTIAL | Service emits "Generated clip d/total" at 50→100 (`video_service.py:235-237`), different ranges/wording than spec 4.15 table; only via callback which UI doesn't pass. |
| Task-based tracking + history | FULLY | Task model + history page (below) |

### Core Feature 6 — Font & Style Customization

| Requirement | Status | Evidence |
|---|---|---|
| Custom TTF fonts from fonts/ | PARTIAL | Discovery works (`settings.py:46-91` via fontTools); `fontsdir` wired in filter (`clip.py:212-214`, `_find_fonts_dir` `clip.py:413-429`). But because subtitles never render in live path, fonts never used. |
| Per-request font/size/color/stroke/shadow/position | PARTIAL | Persisted in `UserPreferences` (`models.py:155-186`) but not consumed by pipeline (HEADLINE). |
| System font discovery | PARTIAL | Only scans project `fonts/` dir (`settings.py:65`), not system fonts; PRD says "System font discovery". |

### Core Feature 7 — Settings Persistence

| Requirement | Status | Evidence |
|---|---|---|
| Persist prefs across sessions | FULLY (storage only) | `settings.py:239-265` upserts singleton row id=1 |
| Logo upload pref | PARTIAL | Upload saved (`settings.py:390-409`) and `logo_path` persisted, but logo never used in render (logo overlay MISSING). |
| `logo_position` corner select (spec 6.4, 7.3) | MISSING | No corner selector in Settings UI; `UserPreferences` has no `logo_position` column (`models.py:129-189`). |
| `clip_target_s` / `target_clip_count` prefs (spec 7.3) | MISSING | Model has `min_clip_length`/`max_clip_length` only; no target length, no target count. |
| Field naming matches spec 7.3 | DEVIATES | Spec: `clip_min_s`,`clip_target_s`,`clip_max_s`,`custom_ai_prompt`. Code: `min_clip_length`,`max_clip_length`,`ai_prompt`. Also adds `font_stroke_*`,`font_shadow_offset`,`subtitle_position_y` not in spec. |

### Core Feature 8 — Task History & Clip Management

| Requirement | Status | Evidence |
|---|---|---|
| View past tasks w/ status, clip count, date | FULLY | `history.py:143-176`, `_load_tasks` `history.py:54-75` |
| Row navigation to task | FULLY | `history.py:119` link to `/task/{id}` |
| Delete task + clips | PARTIAL | `history.py:78-94` hard-deletes via `session.delete` (cascade). Spec 6.3 says "soft-deletes"; this is a hard delete. |
| Download / delete individual clips | PARTIAL | Download per clip `task.py:103-107`. Per-clip delete: MISSING (only whole-task delete). PRD says "Download or delete individual clips". |
| Clip viewer / playback | FULLY | `task.py:68-114` video player + transcript expansion |
| Status badge color coding | FULLY | `history.py:19-24`, `task.py:50-65` |

---

## Data Model Conformance (spec §7)

| Spec requirement | Status | Evidence |
|---|---|---|
| 3 tables: tasks, generated_clips, user_preferences | FULLY | `models.py:33,86,129` |
| Task.status values | DEVIATES | Spec: `'done'`. Code: `'completed'` (`models.py:43`, used consistently `video_service.py:432`). Internally consistent but off-spec. |
| Task.settings_json snapshot on submit | MISSING | `home._create_task` (`home.py:52-69`) never sets `settings_json`; column exists (`models.py:71`) but always NULL. |
| Error stored in `settings_json["error"]` (spec 5.3) | DEVIATES | Stored in dedicated `error_message` column instead (`models.py:72`, `video_service.py:124`). Acceptable but off-spec. |
| GeneratedClip.start_time/end_time as `MM:SS.mmm` VARCHAR | DEVIATES | Stored as Float seconds (`models.py:115-116`). |
| GeneratedClip.reasoning column | MISSING | Not in model (`models.py:106-126`). |
| GeneratedClip.clip_order column | MISSING | `clip_order` is a param of `_save_generated_clip` (`video_service.py:139`) but NEVER persisted — no column. Display order relies on `created_at` (`task.py:165`). |
| GeneratedClip.updated_at | MISSING | Only `created_at` (`models.py:121`). |
| UserPreferences constraints (logo_position, output_resolution CHECK) | MISSING | No CHECK constraints; no logo_position column. |

---

## Configuration Conformance (spec §8)

| Spec env var | Status | Evidence |
|---|---|---|
| `PORT` (default 8008) | DEVIATES | Aliased `BACKEND_PORT` not `PORT` (`config.py:30`). `main.py:60` hardcodes `port=8008` and ignores `cfg.app_port` entirely. |
| `HOST` | MISSING | Not in Config; `ui.run` has no host arg (`main.py:60`). |
| `MAX_VIDEO_DURATION` | MISSING | Absent; not enforced. |
| `MAX_CLIPS` | MISSING | Absent; clip count never capped. |
| `FFMPEG_PRESET`, `FFMPEG_CRF` | MISSING | Absent; hardcoded in clip.py. |
| `MAX_WORKERS` (parallel clip cap, spec 4.15) | MISSING | Absent. `_generate_clips_concurrently` spawns ALL clips at once via unbounded `TaskGroup` (`video_service.py:252-254`); no concurrency limit. |
| `LOG_DIR` | MISSING | Absent. |
| `PARAKEET_MODEL`, `RECONSTRUCT_WORDS_WITH_LLM` | MISSING | Absent (see Transcription). |
| LLM keys, LOCAL_LLM_* , DATABASE_URL, LOG_LEVEL, TEMP_DIR | FULLY | `config.py:30-69` |
| `get_llm_model()` returns OpenAIModel for local (spec 11.4) | DEVIATES | Returns a string `f"openai:{model}"` (`config.py:85-87`); actual local model object is built inline in analyze.py (`analyze.py:428-435`). Functional, different shape. |

---

## Cross-Cutting / Standards Gaps (spec §12)

| Requirement | Status | Evidence |
|---|---|---|
| Custom exception hierarchy `src/exceptions.py` (SupoClipError base) | MISSING | File absent. Exceptions defined ad hoc per module: `DownloadError`, `TranscriptionError`, `AnalysisError`, `ClipGenerationError`. No common base, no `RenderError`/`InsufficientSegmentsError`. |
| structlog only; stdlib `logging` banned (CLAUDE.md, spec 12.2/12.4) | VIOLATED | `import logging` in `video_service.py`, `analyze.py`, `download.py`. Others use structlog. Mixed logging stacks. |
| `checkpython.sh` quality gate exists (CLAUDE.md, spec 13.5, qa.md) | MISSING | Phantom: not in working tree nor git history (orchestrator-confirmed). The mandated gate cannot be run. |
| No magic numbers | VIOLATED | ffmpeg `"fast"`/`"23"` (`clip.py:227-229`), face-detect offset 1.0s (`clip.py:53`), chunk_duration 120/overlap 15 (`transcribe.py:286-287`) are inline constants/magic numbers that spec says belong in config. |

---

## Items That ARE Fully Correct (no action)

- yt-dlp download incl. YouTube Live/shorts URL recognition (`download.py:36-45`).
- parakeet-mlx transcription + word timing + cache (`transcribe.py`).
- LLM routing local/Groq/cloud + Clean Start Rule + duration validation (`analyze.py`).
- 3-table schema, async SQLAlchemy, cascade delete (`models.py`).
- History list, status badges, task navigation, clip playback/download UI.
- pysubs2 ASS generation logic itself is correct (just never invoked live).
- `subprocess.run` uses list form, `shell=False` (`clip.py:371-376`) — spec 10.6 satisfied.

---

## Summary of FUNCTIONAL gaps (prd-gap), ranked

1. CRITICAL: Subtitles + all font/style customization never applied to clips (Settings is dead end-to-end). [HEADLINE]
2. HIGH: Logo overlay not implemented (PRD Feature 4 / spec 10.5).
3. HIGH: Transitions not implemented (PRD Feature 4; CLAUDE.md round-robin claim).
4. HIGH: `MAX_WORKERS` / concurrency cap absent — unbounded parallel ffmpeg (resource risk).
5. MEDIUM: Smart crop is single-frame, not multi-frame median; and silently disabled when cv2 missing.
6. MEDIUM: Real-time progress is 1s DB polling, not WebSocket push (contradicts spec 6.2); callback path unused.
7. MEDIUM: Non-YouTube direct URL input broken (treated as local path → FileNotFoundError).
8. MEDIUM: Resolution dimensions disagree with spec (720p/1080p both wrong).
9. MEDIUM: Per-clip delete missing; whole-task delete is hard not soft.
10. LOW: Upload saved to hardcoded `/tmp` (rule + spec violation).
11. LOW: Many spec config vars missing (MAX_VIDEO_DURATION, MAX_CLIPS, FFMPEG_*, HOST, PORT alias, LOG_DIR, PARAKEET_MODEL).
12. LOW: Model gaps (reasoning, clip_order, updated_at not persisted; status 'completed' vs 'done').
