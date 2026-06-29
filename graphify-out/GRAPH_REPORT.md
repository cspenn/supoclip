# Graph Report - /Users/cspenn/Documents/github/supoclip  (2026-06-29)

## Corpus Check
- 47 files · ~394,674 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1428 nodes · 3527 edges · 35 communities detected
- Extraction: 47% EXTRACTED · 53% INFERRED · 0% AMBIGUOUS · INFERRED: 1880 edges (avg confidence: 0.59)
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

## God Nodes (most connected - your core abstractions)
1. `TranscriptSegment` - 234 edges
2. `UserPreferences` - 174 edges
3. `AnalysisError` - 157 edges
4. `SubtitleStyle` - 138 edges
5. `Base` - 117 edges
6. `DownloadError` - 115 edges
7. `ClipOptions` - 83 edges
8. `ProcessingRequest` - 82 edges
9. `ClipGenerationError` - 80 edges
10. `Task` - 77 edges

## Surprising Connections (you probably didn't know these)
- `test_creates_task_and_returns_id()` --calls--> `_create_task()`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/tests/integration/test_pipeline_failures.py
- `test_creates_upload_task()` --calls--> `_create_task()`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/tests/integration/test_pipeline_failures.py
- `test_render_does_not_raise()` --calls--> `render()`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/pages/history.py
- `Tests for the YouTube URL detection helper.` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py
- `Tests for the Task DB creation helper.` --uses--> `UserPreferences`  [INFERRED]
  /Users/cspenn/Documents/github/supoclip/tests/unit/test_home.py → /Users/cspenn/Documents/github/supoclip/src/models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (167): Base, Base class for all ORM models., DeclarativeBase, Render a single task row inside a card.      Args:         task: The Task ORM ob, Render the empty-state message when no tasks exist., Render the history page.      Queries all tasks from the database and displays t, Format a UTC datetime for display.      Args:         dt: The datetime to format, Truncate a string to *max_len* characters, appending ``…`` if cut.      Args: (+159 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (145): build_ffmpeg_command(), ClipGenerationError, ClipOptions, _escape_filter_path(), filter_words_for_segment(), _find_fonts_dir(), generate_clip(), _get_video_dimensions() (+137 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (171): AnalysisError, build_system_prompt(), _build_user_prompt(), _parse_timestamp(), Check if the model supports Groq structured outputs.      Groq structured output, Convert raw LLM string-timestamp segments to float-second TranscriptSegments., Parse a ``MM:SS`` or ``MM:SS.mmm`` timestamp to seconds.      Args:         time, _raw_segment_to_float_times() (+163 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (110): delete_task(), _format_date(), _load_tasks(), render(), _render_empty_state(), _render_navigation(), _render_task_row(), _truncate() (+102 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (80): Exception, ConfigurationError, InsufficientSegmentsError, Base class for every error raised by SupoClip's own code., Raised when audio transcription fails., Raised when analysis yields fewer than one usable clip segment., Raised when required configuration is missing or invalid., SupoClipError (+72 more)

### Community 5 - "Community 5"
Cohesion: 0.03
Nodes (61): _build_ydl_opts(), download_youtube_video(), _extract_video_id(), find_downloaded_file(), get_video_info(), Check if a URL is a valid YouTube video URL.      Args:         url: URL string, Find the most recently modified video file in the output directory.      yt-dlp, Execute yt-dlp download synchronously.      Args:         url: YouTube URL to do (+53 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (60): analyze_transcript(), _analyze_with_groq_structured(), _analyze_with_pydantic_ai(), Convert string timestamps to float seconds.      Args:         raw: A raw segmen, Build the LLM system prompt for clip selection.      Args:         min_length_s:, Build the user-turn prompt for the LLM.      Args:         transcript_text: Full, Call Groq API with structured JSON output.      Args:         user_prompt: User-, Call LLM via Pydantic AI agent.      Args:         user_prompt: User-turn prompt (+52 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (51): Filter and validate LLM-returned segments.      Removes segments that:     - Hav, validate_segments(), get_session(), Provide an async database session as a context manager.      Yields:         An, Persist a new Task row and return its UUID.      Args:         source_url: YouTu, _make_segment(), TestValidateSegments, _make_task_row() (+43 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (45): _build_ui_module(), _make_widget(), mock_analyze(), mock_ffmpeg(), mock_transcribe(), mock_yt_dlp(), Provide a fresh in-memory SQLite database for each test., Return a MagicMock that supports the most common NiceGUI widget fluent API. (+37 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (27): calculate_crop_box(), detect_face_center(), get_representative_frame(), Calculate the crop box for 9:16 vertical format.      Centers the crop on the de, Extract a single frame from a video file for face detection.      Attempts to us, Round n down to the nearest even integer (required by H.264 encoding).      Args, Detect the center (x, y) of the most prominent face in the frame.      Uses Medi, round_to_even() (+19 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (44): build_processing_request(), _is_youtube_url(), Run the full video processing pipeline for one task.      Intended to be execute, Return True if *text* looks like a YouTube URL.      Args:         text: Raw str, Construct a ProcessingRequest with saved style/prompt preferences wired in., _start_processing(), Map persisted ``UserPreferences`` onto a pipeline ``SubtitleStyle``.      This i, subtitle_style_from_prefs() (+36 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (39): history_page(), home_page(), main(), Render the home page., Render the task detail page., Render the task history page., Render the settings page., Close the database on application shutdown. (+31 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (15): _format_seconds(), _render_clip_card(), _score_color(), Tests for the _format_seconds helper., Zero seconds formats as '00:00'., 45 seconds formats as '00:45'., 67 seconds formats as '01:07'., Fractional seconds are truncated to whole seconds. (+7 more)

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): A polling timer must not be created when the task is already done.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): ui.video must be called once for each clip returned by the DB.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): set_visibility is called at least once on a column widget.          The progress

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): A ui.timer(1.0, ...) is created when status is 'processing'.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): A ui.timer is also created when status is 'pending'.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): No polling timer is created for a task that has already failed.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): set_visibility is called on at least one card widget for a failed task.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): render() must not raise for a missing task_id.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): No polling timer is created when the task does not exist.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): At least one ui.card is rendered for the not-found warning.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches completed status.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Timer deactivates when DB task reaches failed status.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Fallback error message is used when error_message is None.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Timer deactivates when the task record disappears mid-poll.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Timer stays active when the task is still processing.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): _show_clips calls ui.video once per clip from the DB.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): _show_clips sets status label text containing the word clip.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): _show_clips uses clips plural when count is not 1.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Verify that BrowserSubtitleRenderer accepts new style arguments.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): _start_processing must forward a local file path as the source.          Args: (

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): on_start must notify with negative color when no URL or file is given.

## Knowledge Gaps
- **212 isolated node(s):** `TestRefreshCallback`, `TestShowClips`, `Build a MagicMock that behaves like a Task ORM instance.      Using ``MagicMock``, `Build a MagicMock that behaves like a GeneratedClip ORM instance.      Using ``M`, `Return an async context-manager mock that yields a DB session stub.      The yie` (+207 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 13`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `A polling timer must not be created when the task is already done.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `ui.video must be called once for each clip returned by the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `set_visibility is called at least once on a column widget.          The progress`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `A ui.timer(1.0, ...) is created when status is 'processing'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `A ui.timer is also created when status is 'pending'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `No polling timer is created for a task that has already failed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `set_visibility is called on at least one card widget for a failed task.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `render() must not raise for a missing task_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `No polling timer is created when the task does not exist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `At least one ui.card is rendered for the not-found warning.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Timer deactivates when DB task reaches completed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Timer deactivates when DB task reaches failed status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Fallback error message is used when error_message is None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Timer deactivates when the task record disappears mid-poll.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Timer stays active when the task is still processing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `_show_clips calls ui.video once per clip from the DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `_show_clips sets status label text containing the word clip.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `_show_clips uses clips plural when count is not 1.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Verify that BrowserSubtitleRenderer accepts new style arguments.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `_start_processing must forward a local file path as the source.          Args: (`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `on_start must notify with negative color when no URL or file is given.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `render()` connect `Community 3` to `Community 0`, `Community 6`, `Community 7`, `Community 10`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._
- **Why does `TranscriptSegment` connect `Community 2` to `Community 8`, `Community 1`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.169) - this node is a cross-community bridge._
- **Why does `SubtitleStyle` connect `Community 1` to `Community 0`, `Community 3`, `Community 2`, `Community 10`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Are the 228 inferred relationships involving `TranscriptSegment` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`TranscriptSegment` has 228 INFERRED edges - model-reasoned connections that need verification._
- **Are the 172 inferred relationships involving `UserPreferences` (e.g. with `TestIsYoutubeUrl` and `TestCreateTask`) actually correct?**
  _`UserPreferences` has 172 INFERRED edges - model-reasoned connections that need verification._
- **Are the 148 inferred relationships involving `AnalysisError` (e.g. with `TestProcessingRequest` and `TestProcessingResult`) actually correct?**
  _`AnalysisError` has 148 INFERRED edges - model-reasoned connections that need verification._
- **Are the 135 inferred relationships involving `SubtitleStyle` (e.g. with `TestHexToBgrColor` and `TestCalculateMarginV`) actually correct?**
  _`SubtitleStyle` has 135 INFERRED edges - model-reasoned connections that need verification._