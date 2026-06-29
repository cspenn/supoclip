# Graph Report - /Users/cspenn/Documents/github/supoclip  (2026-06-29)

## Corpus Check
- 48 files · ~264,113 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1569 nodes · 3887 edges · 57 communities detected
- Extraction: 46% EXTRACTED · 54% INFERRED · 0% AMBIGUOUS · INFERRED: 2101 edges (avg confidence: 0.59)
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
- [[_COMMUNITY_Community 56|Community 56]]

## God Nodes (most connected - your core abstractions)
1. `TranscriptSegment` - 274 edges
2. `UserPreferences` - 182 edges
3. `SubtitleStyle` - 159 edges
4. `Task` - 136 edges
5. `DownloadError` - 135 edges
6. `GeneratedClip` - 119 edges
7. `InsufficientSegmentsError` - 108 edges
8. `ClipOptions` - 104 edges
9. `ProcessingRequest` - 90 edges
10. `ClipGenerationError` - 80 edges

## Surprising Connections (you probably didn't know these)
- `_RESOLUTIONS must contain both 720p and 1080p.` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py
- `Return a self-chaining NiceGUI element stub.      Returns:         A MagicMock w` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py
- `Return a context-manager NiceGUI element stub.      Returns:         A MagicMock` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py
- `Build a ui mock capturing on_upload and on_click callbacks from render().      A` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py
- `Tests for validate_youtube_url.` --uses--> `DownloadError`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_download.py → /Users/cspenn/Documents/github/supoclip/src/pipeline/download.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (157): Base, Base class for all ORM models., DeclarativeBase, Exception, build_processing_request(), _start_processing(), _new_uuid(), Singleton row storing the user's global application preferences.      There is a (+149 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (141): analyze_transcript(), _analyze_with_groq_structured(), _analyze_with_pydantic_ai(), build_system_prompt(), _build_user_prompt(), _derive_transcript_bound(), _exceeds_bounds(), _parse_timestamp() (+133 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (150): BaseDownloadError, DownloadError, Execute yt-dlp download synchronously.      Args:         url: YouTube URL to do, Raised when video download fails., _run_ydl_download(), Raised when video acquisition (yt-dlp / upload) fails., Render a single task row inside a card.      Args:         task: The Task ORM ob, Render the empty-state message when no tasks exist. (+142 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (128): TranscriptSegment, build_ffmpeg_command(), ClipOptions, _escape_filter_path(), filter_words_for_segment(), _find_fonts_dir(), generate_clip(), _get_video_dimensions() (+120 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (126): delete_task(), _format_date(), _load_tasks(), render(), _render_empty_state(), _render_navigation(), _render_task_row(), _truncate() (+118 more)

### Community 5 - "Community 5"
Cohesion: 0.03
Nodes (82): BaseTranscriptionError, Raised when audio transcription fails., An ``except src.exceptions.DownloadError`` catches the local subclass., start_ms and end_ms are integer milliseconds., Tests for the centralized exception inheritance of TranscriptionError., transcribe.TranscriptionError subclasses the centralized one., An ``except src.exceptions.TranscriptionError`` catches the local subclass., Tests for load_cached_transcript. (+74 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (48): calculate_crop_box(), detect_face_center(), _detect_raw(), _face_model_cache_path(), _get_face_detector(), get_representative_frame(), Return a cached MediaPipe Tasks FaceDetector, or ``None`` if unavailable.      T, Run MediaPipe face detection on a BGR frame.      Converts the frame BGR->RGB (c (+40 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (43): _build_style(), calculate_margin_v(), generate_ass_subtitles(), hex_to_bgr_color(), Construct a pysubs2 SSAStyle from a SubtitleStyle dataclass.      Args:, Generate ASS subtitle file content with per-word timing.      Creates one SSAEve, Write an .ass subtitle file to disk.      Generates the ASS subtitle content via, Convert a #RRGGBB hex string to a pysubs2 Color.      pysubs2's Color constructo (+35 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (42): _build_ydl_opts(), download_youtube_video(), _extract_video_id(), find_downloaded_file(), Check if a URL is a valid YouTube video URL.      Args:         url: URL string, Find the most recently modified video file in the output directory.      yt-dlp, Download a YouTube video to the output directory.      Downloads the best availa, Build yt-dlp options for a single download.      Args:         output_dir: Direc (+34 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (57): get_session(), Provide an async database session as a context manager.      Yields:         An, _make_segment(), test_creates_task_and_returns_id(), test_creates_upload_task(), _make_task_row(), test_local_file_pipeline_happy_path(), test_progress_callback_milestones() (+49 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (44): _build_ui_module(), _make_widget(), mock_analyze(), mock_ffmpeg(), mock_transcribe(), mock_yt_dlp(), Return a MagicMock that supports the most common NiceGUI widget fluent API., Mock ffmpeg subprocess calls to avoid real video processing. (+36 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (39): Raised when transcript analysis fails., Raw segment returned by LLM before float conversion., BaseSettings, Config, get_config(), Create temp directory structure if it doesn't exist.          Creates: temp/, te, Return the cached application config singleton.      Returns:         The applic, SupoClip application configuration.      All values are loaded from environment (+31 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (32): history_page(), home_page(), main(), Render the home page., Render the task detail page., Render the task history page., Render the settings page., Close the database on application shutdown. (+24 more)

### Community 13 - "Community 13"
Cohesion: 0.13
Nodes (13): _format_seconds(), _render_clip_card(), _score_color(), Tests for the _format_seconds helper., Zero seconds formats as '00:00'., 45 seconds formats as '00:45'., 67 seconds formats as '01:07'., Score in [0.6, 0.8) returns a yellow class. (+5 more)

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): A clip with no transcript_text renders without the transcript expansion.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): A ui.timer is also created when status is 'pending'.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): A polling timer must not be created when the task is already done.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): ui.video must be called once for each clip returned by the DB.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): set_visibility is called at least once on a column widget.          The progress

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): A ui.timer(1.0, ...) is created when status is 'processing'.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): render() with a failed task shows the error banner.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): No polling timer is created for a task that has already failed.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): render() must not raise for a missing task_id.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): No polling timer is created when the task does not exist.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): At least one ui.card is rendered for the not-found warning.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Fractional seconds are truncated to whole seconds.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Tests for the _score_color helper.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches completed status.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches failed status.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Fallback error message is used when error_message is None.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Timer deactivates when the task record disappears mid-poll.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Timer stays active when the task is still processing.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): _show_clips calls ui.video once per clip from the DB.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): _show_clips sets status label text containing the word clip.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): _show_clips uses clips plural when count is not 1.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): init_db() completes without error when src.models cannot be imported.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Output dimensions must satisfy 9:16 aspect ratio (within rounding).

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Build a minimal mock that looks like a MediaPipe detection.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Return a mock mediapipe module with the given detections.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): A 30%-wide face centred at 50% should yield ~(100, 100) on a 200×200 frame.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Faces smaller than 30 px should be filtered out.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): When multiple faces qualify, the one with the highest score wins.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): A face larger than _MAX_RELATIVE_AREA (0.3) of the frame is filtered out.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): If MediaPipe raises an exception, return None gracefully.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Tests for home_page().

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Tests for task_page().

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Tests for history_page().

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Tests for settings_page().

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Tests for _startup().

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Initialize the database on application startup.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Fetch video metadata synchronously via yt-dlp.      Args:         url: YouTube U

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Fetch YouTube video metadata without downloading.      Args:         url: YouTub

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Detect the center (x, y) of the most prominent face in the frame.      Uses Medi

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Verify that BrowserSubtitleRenderer accepts new style arguments.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): _start_processing must forward a local file path as the source.          Args: (

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): on_start must notify with negative color when no URL or file is given.

## Knowledge Gaps
- **233 isolated node(s):** `TestRefreshCallback`, `TestShowClips`, `Build a MagicMock that behaves like a Task ORM instance.      Using ``MagicMock``, `Build a MagicMock that behaves like a GeneratedClip ORM instance.      Using ``M`, `Return an async context-manager mock that yields a DB session stub.      The yie` (+228 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `A clip with no transcript_text renders without the transcript expansion.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `A ui.timer is also created when status is 'pending'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `A polling timer must not be created when the task is already done.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `ui.video must be called once for each clip returned by the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `set_visibility is called at least once on a column widget.          The progress`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `A ui.timer(1.0, ...) is created when status is 'processing'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `render() with a failed task shows the error banner.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `No polling timer is created for a task that has already failed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `render() must not raise for a missing task_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `No polling timer is created when the task does not exist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `At least one ui.card is rendered for the not-found warning.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Fractional seconds are truncated to whole seconds.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Tests for the _score_color helper.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Timer deactivates when DB task reaches completed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Timer deactivates when DB task reaches failed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Fallback error message is used when error_message is None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Timer deactivates when the task record disappears mid-poll.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Timer stays active when the task is still processing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `_show_clips calls ui.video once per clip from the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `_show_clips sets status label text containing the word clip.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `_show_clips uses clips plural when count is not 1.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `init_db() completes without error when src.models cannot be imported.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Output dimensions must satisfy 9:16 aspect ratio (within rounding).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Build a minimal mock that looks like a MediaPipe detection.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Return a mock mediapipe module with the given detections.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `A 30%-wide face centred at 50% should yield ~(100, 100) on a 200×200 frame.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Faces smaller than 30 px should be filtered out.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `When multiple faces qualify, the one with the highest score wins.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `A face larger than _MAX_RELATIVE_AREA (0.3) of the frame is filtered out.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `If MediaPipe raises an exception, return None gracefully.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Tests for home_page().`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Tests for task_page().`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Tests for history_page().`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Tests for settings_page().`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Tests for _startup().`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Initialize the database on application startup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Fetch video metadata synchronously via yt-dlp.      Args:         url: YouTube U`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Fetch YouTube video metadata without downloading.      Args:         url: YouTub`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Detect the center (x, y) of the most prominent face in the frame.      Uses Medi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Verify that BrowserSubtitleRenderer accepts new style arguments.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `_start_processing must forward a local file path as the source.          Args: (`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `on_start must notify with negative color when no URL or file is given.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `UserPreferences` connect `Community 0` to `Community 2`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.198) - this node is a cross-community bridge._
- **Why does `TranscriptSegment` connect `Community 3` to `Community 1`, `Community 2`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.195) - this node is a cross-community bridge._
- **Why does `Task` connect `Community 2` to `Community 0`, `Community 9`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Are the 268 inferred relationships involving `TranscriptSegment` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`TranscriptSegment` has 268 INFERRED edges - model-reasoned connections that need verification._
- **Are the 180 inferred relationships involving `UserPreferences` (e.g. with `TestIsYoutubeUrl` and `TestCreateTask`) actually correct?**
  _`UserPreferences` has 180 INFERRED edges - model-reasoned connections that need verification._
- **Are the 156 inferred relationships involving `SubtitleStyle` (e.g. with `TestHexToBgrColor` and `TestCalculateMarginV`) actually correct?**
  _`SubtitleStyle` has 156 INFERRED edges - model-reasoned connections that need verification._
- **Are the 134 inferred relationships involving `Task` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`Task` has 134 INFERRED edges - model-reasoned connections that need verification._