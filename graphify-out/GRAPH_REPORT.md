# Graph Report - /Users/cspenn/Documents/github/supoclip  (2026-06-29)

## Corpus Check
- 68 files · ~190,032 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2056 nodes · 9716 edges · 56 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 2216 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]

## God Nodes (most connected - your core abstractions)
1. `TranscriptSegment` - 222 edges
2. `AnalysisError` - 153 edges
3. `UserPreferences` - 136 edges
4. `Base` - 117 edges
5. `SubtitleStyle` - 115 edges
6. `DownloadError` - 112 edges
7. `addErrorMessage()` - 96 edges
8. `slice()` - 91 edges
9. `ProcessingRequest` - 80 edges
10. `Config` - 78 edges

## Surprising Connections (you probably didn't know these)
- `test_creates_task_and_returns_id()` --calls--> `_create_task()`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/tests/integration/test_pipeline_failures.py
- `test_creates_upload_task()` --calls--> `_create_task()`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/tests/integration/test_pipeline_failures.py
- `Tests for validate_youtube_url.` --uses--> `DownloadError`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_download.py → /Users/cspenn/Documents/github/supoclip/src/pipeline/download.py
- `Returns False when a non-string is passed.` --uses--> `DownloadError`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_download.py → /Users/cspenn/Documents/github/supoclip/src/pipeline/download.py
- `Tests for _extract_video_id (internal helper).` --uses--> `DownloadError`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_download.py → /Users/cspenn/Documents/github/supoclip/src/pipeline/download.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (373): AnalysisError, analyze_transcript(), _analyze_with_groq_structured(), _analyze_with_pydantic_ai(), build_system_prompt(), _build_user_prompt(), _parse_timestamp(), Convert string timestamps to float seconds.      Args:         raw: A raw segmen (+365 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (323): Base, Base class for all ORM models., DeclarativeBase, Exception, delete_task(), _format_date(), _load_tasks(), Render a single task row inside a card.      Args:         task: The Task ORM ob (+315 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (368): ao(), ap(), as(), Ci(), cr(), cs(), ac(), At() (+360 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (231): be(), bi(), bo(), br(), bs(), Ei(), an(), ar() (+223 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (73): append(), Tests for load_cached_transcript., Returns None when no cache file exists., Returns None when the cache has a wrong version number., Returns None when the cache file contains invalid JSON., Returns word list for a valid, current-version cache., Round-trip tests for save_transcript_cache and load_cached_transcript., Saved cache is loadable and contains the original words. (+65 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (90): _build_ui_module(), _make_widget(), mock_ffmpeg(), mock_transcribe(), mock_yt_dlp(), Provide a fresh in-memory SQLite database for each test., Return a MagicMock that supports the most common NiceGUI widget fluent API., Mock ffmpeg subprocess calls to avoid real video processing. (+82 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (42): _build_style(), calculate_margin_v(), generate_ass_subtitles(), hex_to_bgr_color(), Construct a pysubs2 SSAStyle from a SubtitleStyle dataclass.      Args:, Generate ASS subtitle file content with per-word timing.      Creates one SSAEve, Write an .ass subtitle file to disk.      Generates the ASS subtitle content via, Convert a #RRGGBB hex string to a pysubs2 Color.      pysubs2's Color constructo (+34 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (45): _build_ydl_opts(), download_youtube_video(), _extract_video_id(), find_downloaded_file(), get_video_info(), Check if a URL is a valid YouTube video URL.      Args:         url: URL string, Find the most recently modified video file in the output directory.      yt-dlp, Download a YouTube video to the output directory.      Downloads the best availa (+37 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (27): calculate_crop_box(), detect_face_center(), get_representative_frame(), Calculate the crop box for 9:16 vertical format.      Centers the crop on the de, Extract a single frame from a video file for face detection.      Attempts to us, Round n down to the nearest even integer (required by H.264 encoding).      Args, Detect the center (x, y) of the most prominent face in the frame.      Uses Medi, round_to_even() (+19 more)

### Community 9 - "Community 9"
Cohesion: 0.13
Nodes (17): PrismaClient, AnyNull, DbNull, JsonNull, DataLoader, Decimal, MergedExtensionsList, MetricsClient (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.18
Nodes (11): Verify that BrowserSubtitleRenderer accepts new style arguments., verify_styling(), destroy(), digest(), digestInto(), finish(), keccak(), update() (+3 more)

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (0): 

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): A polling timer must not be created when the task is already done.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): ui.video must be called once for each clip returned by the DB.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): set_visibility is called at least once on a column widget.          The progress

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): A ui.timer(1.0, ...) is created when status is 'processing'.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): A ui.timer is also created when status is 'pending'.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): No polling timer is created for a task that has already failed.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): set_visibility is called on at least one card widget for a failed task.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): render() must not raise for a missing task_id.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): No polling timer is created when the task does not exist.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): At least one ui.card is rendered for the not-found warning.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches completed status.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches failed status.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Fallback error message is used when error_message is None.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Timer deactivates when the task record disappears mid-poll.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Timer stays active when the task is still processing.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): _show_clips calls ui.video once per clip from the DB.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): _show_clips sets status label text containing the word clip.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): _show_clips uses clips plural when count is not 1.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): YouTube and youtu.be URLs must return True.          Args:             url: URL

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Non-YouTube strings and local paths must return False.          Args:

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): _create_task must persist a Task and return the UUID string.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): _create_task must work for upload source_type as well.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): _start_processing must build ProcessingRequest and call process_video.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): _start_processing must forward a local file path as the source.          Args: (

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): render() must complete without raising when NiceGUI is mocked.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): handle_upload must call ui.notify with color=negative when content is None.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): handle_upload must write readable content to disk and notify on success.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): handle_upload must write raw bytes content (no .read()) directly.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): on_start must notify with negative color when no URL or file is given.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): on_start must notify when min clip length >= max clip length.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): on_start must show error notification when _create_task raises.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): on_start must create task, fire background job, and navigate to task page.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): on_start must use the uploaded local path when URL input is empty.

## Knowledge Gaps
- **224 isolated node(s):** `DataLoader`, `MergedExtensionsList`, `MetricsClient`, `PrismaClientInitializationError`, `PrismaClientKnownRequestError` (+219 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (1 nodes): `next-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `wasm-edge-light-loader.mjs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (1 nodes): `client.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `edge.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `wasm.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `wasm-worker-loader.mjs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `index.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `wasm.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `default.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `default.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `client.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `A polling timer must not be created when the task is already done.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `ui.video must be called once for each clip returned by the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `set_visibility is called at least once on a column widget.          The progress`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `A ui.timer(1.0, ...) is created when status is 'processing'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `A ui.timer is also created when status is 'pending'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `No polling timer is created for a task that has already failed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `set_visibility is called on at least one card widget for a failed task.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `render() must not raise for a missing task_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `No polling timer is created when the task does not exist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `At least one ui.card is rendered for the not-found warning.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Timer deactivates when DB task reaches completed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Timer deactivates when DB task reaches failed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Fallback error message is used when error_message is None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Timer deactivates when the task record disappears mid-poll.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Timer stays active when the task is still processing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `_show_clips calls ui.video once per clip from the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `_show_clips sets status label text containing the word clip.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `_show_clips uses clips plural when count is not 1.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `YouTube and youtu.be URLs must return True.          Args:             url: URL`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Non-YouTube strings and local paths must return False.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `_create_task must persist a Task and return the UUID string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `_create_task must work for upload source_type as well.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `_start_processing must build ProcessingRequest and call process_video.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `_start_processing must forward a local file path as the source.          Args: (`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `render() must complete without raising when NiceGUI is mocked.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `handle_upload must call ui.notify with color=negative when content is None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `handle_upload must write readable content to disk and notify on success.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `handle_upload must write raw bytes content (no .read()) directly.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `on_start must notify with negative color when no URL or file is given.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `on_start must notify when min clip length >= max clip length.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `on_start must show error notification when _create_task raises.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `on_start must create task, fire background job, and navigate to task page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `on_start must use the uploaded local path when URL input is empty.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.207) - this node is a cross-community bridge._
- **Why does `render()` connect `Community 1` to `Community 0`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Why does `Config` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Are the 216 inferred relationships involving `TranscriptSegment` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`TranscriptSegment` has 216 INFERRED edges - model-reasoned connections that need verification._
- **Are the 148 inferred relationships involving `AnalysisError` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`AnalysisError` has 148 INFERRED edges - model-reasoned connections that need verification._
- **Are the 134 inferred relationships involving `UserPreferences` (e.g. with `TestTask` and `TestGeneratedClip`) actually correct?**
  _`UserPreferences` has 134 INFERRED edges - model-reasoned connections that need verification._
- **Are the 114 inferred relationships involving `Base` (e.g. with `TestTask` and `TestGeneratedClip`) actually correct?**
  _`Base` has 114 INFERRED edges - model-reasoned connections that need verification._