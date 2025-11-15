# Video Processing & Transcription Pipeline Analysis

## Executive Summary
The SupoClip backend has successfully migrated from AssemblyAI cloud API to parakeet-mlx local transcription. The pipeline is well-architected with proper separation of concerns, but there are outdated log messages and function naming conventions that reference AssemblyAI, which could be confusing during maintenance.

---

## Complete Transcript Pipeline Flow

### 1. ENTRY POINTS
There are two entry points for video processing:

#### Entry Point A: `/start` endpoint (main.py:97-298)
- Synchronous processing (returns results immediately)
- Calls `get_video_transcript()` at line 211
- Full pipeline: download → transcribe → AI analyze → create clips → save to DB

#### Entry Point B: `/start-with-progress` endpoint (main.py:400+)
- Async processing with progress tracking via SSE
- Same pipeline but with progress callbacks
- Calls `get_video_transcript()` at line 446

#### Entry Point C: Background job queue (workers/tasks.py:15-75)
- Called via `process_video_task()`
- Eventually calls TaskService.process_task() which orchestrates via VideoService

### 2. TRANSCRIPTION GENERATION

**File**: `backend/src/transcription_mlx.py`

**Primary Function**: `transcribe_video_mlx(video_path, model_id="mlx-community/parakeet-tdt-0.6b-v2")`
- Line 22-109: Main transcription function
- Uses parakeet-mlx model from HuggingFace MLX Community
- Returns dict with keys:
  - `text`: Full transcript text
  - `segments`: List of segment dicts with timing
  - `words`: List of word-level timestamps (AssemblyAI-compatible format)
  - `language`: Language code (currently hardcoded to "en")

**Key Formatting Functions** (lines 112-259):
1. `_extract_text_from_result()` (line 112-133): Extracts full text from parakeet sentences
2. `_extract_segments_from_result()` (line 136-178): Converts parakeet sentences to AssemblyAI-compatible segment format
3. `_extract_words_from_result()` (line 181-220): Extracts word-level timestamps with start/end in milliseconds
4. `_get_token_start_time()` (line 223-239): Converts token.start_ts to milliseconds
5. `_get_token_end_time()` (line 242-258): Converts token.end_ts to milliseconds

**Cache Mechanism** (line 59-70, 94-100):
- Path format: `{video_filename}.transcript_cache.json`
- Stored alongside video file in same directory
- Loads from cache if exists, avoids re-transcribing
- Saves to cache after new transcription

**Output Format Example**:
```json
{
  "text": "Full transcript text here...",
  "segments": [
    {
      "id": 0,
      "start": 1250,
      "end": 3500,
      "text": "Segment text",
      "tokens": [...],
      ...
    }
  ],
  "words": [
    {"text": "Word", "start": 1250, "end": 1350, "confidence": 1.0},
    ...
  ],
  "language": "en"
}
```

### 3. TRANSCRIPT FORMATTING FOR AI

**File**: `backend/src/video_utils.py`

**Function**: `get_video_transcript(video_path)` (lines 85-151)

**Flow**:
1. Calls `transcribe_video_mlx()` to get raw result dict
2. Extracts `words` array from result
3. Groups words into segments (max 8 words per segment = ~3-4 seconds)
4. Segments end at natural breaks (`.`, `!`, `?`) or word limit
5. Formats each segment as: `[MM:SS - MM:SS] Text content`
6. Returns newline-separated string of formatted segments

**Timestamp Conversion** (lines 196-201):
- Input: milliseconds (from parakeet)
- Output: MM:SS format for AI analysis
- Function: `format_ms_to_timestamp(ms: int)` → formats to `{minutes:02d}:{seconds:02d}`

**Example Output**:
```
[00:01 - 00:05] Welcome to the video today we're going to talk about something
[00:05 - 00:10] really important that will help you understand the basics
[00:10 - 00:14] of this technology and how it works in practice
```

### 4. LLM INTEGRATION & SEGMENT SELECTION

**File**: `backend/src/ai.py`

**Main Function**: `get_most_relevant_parts_by_transcript(transcript: str)` (line 119-215)

**Flow**:
1. Takes formatted transcript string (with [MM:SS - MM:SS] timestamps)
2. Creates Pydantic AI agent with simplified_system_prompt
3. Sends to configured LLM (local or cloud)
4. LLM returns TranscriptAnalysis with:
   - `most_relevant_segments`: List[TranscriptSegment]
   - `summary`: str
   - `key_topics`: List[str]

**LLM Configuration** (config.py:73-91):
- **Default (Local-First)**: OpenAI-compatible endpoint
  - `LOCAL_LLM_ENABLED=true` (default)
  - `LOCAL_LLM_BASE_URL=http://localhost:6969/v1` (default)
  - Uses KoboldCPP or similar compatible server
- **Fallback (Cloud)**: 
  - Requires `LLM_MODEL` and API key (OpenAI, Anthropic, Google)

**Validation Logic** (lines 140-190):
1. Checks segment text has ≥3 words
2. CRITICAL: Validates `start_time ≠ end_time` (line 153)
3. Parses MM:SS timestamps to validate duration
4. Enforces minimum duration ≥5 seconds (line 175)
5. Logs warnings for skipped segments
6. Sorts by relevance_score descending

**TranscriptSegment Model** (lines 20-29):
```python
start_time: str  # MM:SS format
end_time: str    # MM:SS format
text: str        # Segment text
relevance_score: float  # 0.0-1.0
reasoning: str   # Why it's relevant
```

### 5. CLIP GENERATION FROM SEGMENTS

**File**: `backend/src/video_utils.py`

**Main Function**: `create_clips_with_transitions()` (lines 937-1008)

**Flow**:
1. Takes segments list with start_time/end_time in MM:SS format
2. Calls `create_clips_from_segments()` to create individual clips
3. Applies transition effects between clips
4. Returns list of clip info dicts

**Segment Format Conversion**:
- Input: `{"start_time": "00:25", "end_time": "00:45", ...}`
- Used directly as MM:SS strings for video clipping

**Subtitle Generation** (lines 587-698):
- Function: `create_assemblyai_subtitles()`
- Loads cached transcript from `.transcript_cache.json`
- Extracts words overlapping with clip time range
- Groups words into 3-word subtitle segments
- Generates text clips with custom font at 75% down video

### 6. DATABASE STORAGE

**File**: `backend/src/services/task_service.py` (lines 115-135)

**Clip Storage**:
```python
clip_id = await clip_repo.create_clip(
    task_id=task_id,
    filename=clip_info["filename"],
    file_path=clip_info["path"],
    start_time=clip_info["start_time"],  # Float seconds
    end_time=clip_info["end_time"],      # Float seconds
    duration=clip_info["duration"],      # Float seconds
    text=clip_info["text"],              # AI-selected text
    relevance_score=clip_info["relevance_score"],
    reasoning=clip_info["reasoning"],
    clip_order=i + 1
)
```

---

## Transcript Data Flow Diagram

```
Video File (MP4/etc)
    ↓
transcribe_video_mlx() 
  ├─ Loads parakeet-mlx model
  ├─ Checks/loads .transcript_cache.json
  ├─ Extracts: sentences → words/tokens
  └─ Returns: {text, segments[], words[], language}
    ↓
Cache: {video_name}.transcript_cache.json
    ↓
get_video_transcript()
  ├─ Gets transcribe_video_mlx() result
  ├─ Extracts words[] array
  ├─ Groups into ~8-word segments
  ├─ Formats as "[MM:SS - MM:SS] text"
  └─ Returns: formatted_string (newline-separated)
    ↓
get_most_relevant_parts_by_transcript()
  ├─ Sends formatted_string to LLM
  ├─ LLM returns segments with MM:SS times
  ├─ Validates duration & timing
  └─ Returns: TranscriptAnalysis{segments[], summary, topics[]}
    ↓
create_clips_with_transitions()
  ├─ Takes segments with MM:SS times
  ├─ Converts to float seconds for video clipping
  ├─ Creates individual clips
  ├─ Generates subtitles from .transcript_cache.json words[]
  ├─ Applies transitions
  └─ Saves to {TEMP_DIR}/clips/
    ↓
Database
  ├─ Tasks table (one per processing job)
  ├─ GeneratedClips table (one per clip)
  └─ Stores: filename, path, start_time, end_time, text, scores
```

---

## Data Format Conversions

| Stage | Format | Example | Precision |
|-------|--------|---------|-----------|
| Parakeet raw | `start_ts` (float seconds) | 12.345 | ~10ms |
| parakeet-mlx words dict | Milliseconds int | 1234 | 1ms |
| AI transcript input | MM:SS string | "[01:23 - 01:45]" | 1 second |
| AI segment output | MM:SS string | "01:23" | 1 second |
| Video clip times | Float seconds | 12.345 | Precise |
| Subtitles timing | Float seconds | 12.345 | Precise |
| Database storage | Float seconds | 12.345 | Precise |

---

## Current Caching Strategy

### Transcript Cache Location
- Filename: `{video_stem}.transcript_cache.json`
- Location: Same directory as video file
- Created by: `transcribe_video_mlx()` line 94-100
- Format: Full parakeet result dict (text, segments, words, language)

### Cache Loading
1. `transcribe_video_mlx()` checks cache first (line 63)
2. `load_cached_transcript_mlx()` utility for manual cache loading
3. Cache reused for:
   - Subtitle generation in `create_assemblyai_subtitles()`
   - Future transcription requests on same video

### Cache Invalidation
- No automatic invalidation
- Manual deletion required to re-transcribe
- WARNING: If cache is corrupted, continues with fresh transcription (line 68-70)

---

## Issues & Observations

### 1. **Outdated Log Messages** (MINOR)
- `main.py:209, 213`: References "AssemblyAI + SRT equalization"
- `main.py:445`: References "AssemblyAI" in progress log
- `services/video_service.py:74`: Docstring says "Generate transcript from video using AssemblyAI"
- `ai.py:40`: System prompt comment "trusts AssemblyAI timing"

These are misleading but NOT functional issues. Code actually uses parakeet-mlx.

### 2. **No Legacy AssemblyAI Code Found** ✓
- No actual AssemblyAI API calls detected
- No credentials for AssemblyAI in config
- Backward compatibility functions properly redirect to parakeet-mlx:
  - `get_video_transcript_with_assemblyai()` → calls `get_video_transcript()`
  - `create_assemblyai_subtitles()` → uses cached parakeet data

### 3. **Function Naming Inconsistencies** (MINOR)
- `create_assemblyai_subtitles()` uses parakeet data (confusing name)
- `load_cached_transcript_data()` generic name but loads parakeet cache
- `cache_transcript_data()` (line 154) is never called (dead code?)

### 4. **Timestamp Precision Considerations**
- Parakeet provides millisecond precision (tokens)
- AI receives/outputs 1-second precision (MM:SS)
- Video clipping uses float seconds (precise)
- Minimal precision loss: AI rounds to 1s, video clip time is then precise

### 5. **Cache Format Compatibility**
- Cache stores full parakeet result (dict)
- Functions expect specific keys: "words", "segments", "text"
- If cache structure changes, subtitles may fail silently

### 6. **Word-Level Timing Accuracy**
- Parakeet extracts from tokens: `start_ts`, `end_ts` (seconds, float)
- Conversion to milliseconds at line 204-205, 235, 254
- Handles fallback attribute names: `stime`, `etime`
- Default to 0 if timing attributes missing (line 239, 258)

---

## Flow Completeness Check

| Stage | Status | Location | Notes |
|-------|--------|----------|-------|
| Video Input | ✓ | services/video_service.py:39-53 | YouTube or upload |
| Transcription | ✓ | transcription_mlx.py:22-109 | parakeet-mlx with cache |
| Formatting | ✓ | video_utils.py:85-151 | MM:SS format for AI |
| LLM Analysis | ✓ | ai.py:119-215 | Local or cloud LLM |
| Validation | ✓ | ai.py:140-190 | Duration, timing, content checks |
| Clip Creation | ✓ | video_utils.py:937-1008 | From segments to video files |
| Subtitles | ✓ | video_utils.py:587-698 | Word-level from cache |
| Database Save | ✓ | task_service.py:115-135 | All metadata stored |

---

## Configuration Environment Variables

```bash
# Transcription
PARAKEET_MODEL=mlx-community/parakeet-tdt-0.6b-v2

# LLM (local-first)
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:6969/v1
LOCAL_LLM_MODEL=local-model
LOCAL_LLM_API_KEY=not-needed

# LLM (cloud fallback)
LLM_MODEL=openai:gpt-4  # or anthropic:claude-3-5-sonnet
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...

# Storage
TEMP_DIR=temp
TRANSCRIPT_CACHE_DIR={TEMP_DIR}  # implicit

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_RETENTION_DAYS=30

# Database
DATABASE_URL=sqlite+aiosqlite:///./supoclip.db
```

---

## Key Takeaways

1. **Pipeline is properly implemented**: parakeet-mlx → formatted text → LLM → validated segments → clips
2. **No AssemblyAI code execution**: All references are outdated logging/comments
3. **Caching works well**: Transcript cache prevents re-transcribing same video
4. **Format compatibility**: MM:SS format bridges parakeet precision with LLM understanding
5. **Validation is thorough**: Multiple checks prevent invalid segments from creating clips
6. **Subtitle sync**: Word-level timing from cache ensures lip-sync accuracy

