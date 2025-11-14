# Cloud API Removal - Complete Local-First Migration Plan

**Date:** November 14, 2025
**Branch:** `feature/mlx-no-docker-migration`
**Status:** Investigation Complete - Ready for VUW Implementation
**Methodology:** Verifiable Units of Work (VUWs)

---

## Executive Summary

This plan addresses the remaining cloud API dependency in SupoClip: **Pydantic AI's LLM usage for transcript analysis**. While the previous migration successfully removed AssemblyAI (transcription), Redis (job queue), and PostgreSQL (database), the application still requires cloud LLM APIs (OpenAI/Google/Anthropic) for AI-powered clip segment selection.

### Current State Analysis

**Already Migrated (Phases 1-8):**
- ✅ AssemblyAI → MLX Whisper (offline transcription with word-level timestamps)
- ✅ PostgreSQL → SQLite (local database)
- ✅ Redis/arq → Local asyncio queue (in-process job queue)
- ✅ Docker removed (native macOS execution)
- ✅ 146 tests passing with 65% core coverage

**Still Requires Cloud:**
- ❌ Pydantic AI transcript analysis (requires OpenAI/Google/Anthropic API keys)
- File: `backend/src/ai.py` uses `Agent(model=config.llm)` where `config.llm` defaults to `"google:gemini-2.5-flash-lite"`

### User Context

- User has **koboldcpp running on localhost:6969** (OpenAI-compatible API)
- User wants **local-first operation** with cloud as optional fallback
- User experienced error: missing `.env` file with cloud API keys
- Goal: Run entirely offline with local LLM by default

---

## Technical Analysis

### 1. What Pydantic AI Does

**Purpose:** Analyzes video transcripts to select 3-7 compelling segments for short-form clips

**Input:** Full video transcript with word-level timestamps (from MLX Whisper)

**Output:** `TranscriptAnalysis` Pydantic model containing:
- `most_relevant_segments`: List of segments with start/end times, relevance scores
- `summary`: Video content summary
- `key_topics`: List of main topics

**Current Implementation:**
```python
# backend/src/ai.py (line 67-71)
transcript_agent = Agent(
    model=config.llm,  # "google:gemini-2.5-flash-lite"
    result_type=TranscriptAnalysis,
    system_prompt=simplified_system_prompt
)
```

**Model String Format:** Pydantic AI uses `"<provider>:<model>"` format:
- `"openai:gpt-4o"` - Cloud OpenAI
- `"google:gemini-2.5-flash"` - Cloud Google
- `"anthropic:claude-3-5-sonnet"` - Cloud Anthropic
- Custom format needed for local LLM

### 2. Pydantic AI + OpenAI-Compatible Endpoints

**Key Finding:** Pydantic AI's `OpenAIProvider` supports custom `base_url` configuration

**Configuration Pattern:**
```python
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# Option 1: Custom provider with base_url
model = OpenAIChatModel(
    'model_name',
    provider=OpenAIProvider(
        base_url='http://localhost:6969/v1',  # KoboldCPP endpoint
        api_key='dummy-key-not-required'      # Some servers need placeholder
    ),
)

# Option 2: Custom AsyncOpenAI client
client = AsyncOpenAI(
    base_url='http://localhost:6969/v1',
    api_key='dummy-key-not-required',
    max_retries=3
)
model = OpenAIChatModel('model_name', provider=OpenAIProvider(openai_client=client))

agent = Agent(model)
```

**KoboldCPP Compatibility:**
- KoboldCPP provides OpenAI-compatible API at `/v1` route (e.g., `http://localhost:5001/v1`)
- User's instance runs on `localhost:6969`, so endpoint is `http://localhost:6969/v1`
- No actual API key required for local instances (use placeholder)

### 3. MLX Whisper Status

**CONFIRMED:** Already fully implemented and tested
- ✅ Word-level timestamps working (critical for subtitle sync)
- ✅ Transcript caching (`.transcript_cache.json`)
- ✅ AssemblyAI-compatible output format
- ✅ Tests passing (test_offline_capability.py)
- ✅ File: `backend/src/transcription_mlx.py` complete

**Evidence from code:**
```python
# backend/src/transcription_mlx.py (line 71-78)
result = mlx_whisper.transcribe(
    str(video_path),
    path_or_hf_repo=f"mlx-community/whisper-{model_size}",
    word_level_timings=True,  # ✅ CONFIRMED: Word-level timestamps enabled
    language="en",
    fp16=False,
)
```

No changes needed to transcription - this is working correctly.

---

## Cloud API Dependencies - Complete Audit

### Dependencies in Code

| File | Line(s) | Dependency | Status | Action Needed |
|------|---------|------------|--------|---------------|
| `backend/src/ai.py` | 67-71 | Pydantic AI agent using cloud LLM | Active | Replace with local LLM config |
| `backend/src/config.py` | 23-29 | LLM API key configuration | Active | Add local LLM config options |
| `backend/.env.example` | 20-29 | Cloud API keys required | Active | Make optional, add local defaults |
| `backend/src/transcription_mlx.py` | All | MLX Whisper (local) | ✅ Done | None - already local |
| `backend/src/video_utils.py` | 22-24 | Uses MLX Whisper | ✅ Done | None - already local |

### Dependencies NOT in Code (Already Removed)

- ✅ AssemblyAI - Completely removed in Phase 4
- ✅ Redis - Completely removed in Phase 3
- ✅ PostgreSQL - Completely removed in Phase 2
- ✅ Docker - Completely removed in Phase 8

### Configuration Files Audit

**Current `.env.example` Issues:**
```bash
# backend/.env.example (lines 20-29)
OPENAI_API_KEY=          # ❌ Shows as required
GOOGLE_API_KEY=          # ❌ Shows as required
ANTHROPIC_API_KEY=       # ❌ Shows as required
LLM_MODEL=google:gemini-2.5-flash  # ❌ Defaults to cloud
```

**Needs to change to:**
```bash
# Local LLM (default - no API key required)
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:6969/v1
LOCAL_LLM_MODEL=local-model  # Model name from koboldcpp

# Cloud LLM (optional fallback)
OPENAI_API_KEY=          # Optional - only if using OpenAI
GOOGLE_API_KEY=          # Optional - only if using Google
ANTHROPIC_API_KEY=       # Optional - only if using Anthropic
LLM_MODEL=openai:gpt-4o  # Optional - used only if LOCAL_LLM_ENABLED=false
```

---

## Migration Strategy: Local-First with Cloud Fallback

### Design Principles

1. **Local by Default** - No cloud APIs required for basic operation
2. **Cloud as Optional Override** - User can enable cloud if desired
3. **Backward Compatibility** - Existing cloud configurations still work
4. **Clear Configuration** - Obvious which mode is active
5. **Fail Gracefully** - Clear error messages when local LLM unavailable

### Configuration Hierarchy (Priority Order)

```
1. Local LLM (if LOCAL_LLM_ENABLED=true and endpoint reachable)
   ↓ Falls back to ↓
2. Cloud LLM (if LLM_MODEL set and API key available)
   ↓ Falls back to ↓
3. Error with clear instructions
```

### Proposed Configuration Model

**New Config Class Structure:**
```python
# backend/src/config.py
class Config:
    def __init__(self) -> None:
        # Local LLM configuration (default)
        self.local_llm_enabled = os.getenv("LOCAL_LLM_ENABLED", "true").lower() == "true"
        self.local_llm_base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:6969/v1")
        self.local_llm_model = os.getenv("LOCAL_LLM_MODEL", "local-model")
        self.local_llm_api_key = os.getenv("LOCAL_LLM_API_KEY", "not-needed")  # Placeholder

        # Cloud LLM configuration (optional fallback)
        self.llm = os.getenv("LLM_MODEL", "")  # Empty default = not configured
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")

    def get_llm_model(self):
        """Get configured LLM model (local-first, cloud fallback)."""
        if self.local_llm_enabled:
            return self._create_local_llm_model()
        elif self.llm and self._has_cloud_api_key():
            return self.llm  # Use cloud model string
        else:
            raise ValueError(
                "No LLM configured. Either:\n"
                "1. Enable local LLM: LOCAL_LLM_ENABLED=true and start koboldcpp\n"
                "2. Configure cloud LLM: Set LLM_MODEL and appropriate API key"
            )

    def _create_local_llm_model(self):
        """Create OpenAI-compatible model for local LLM."""
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        client = AsyncOpenAI(
            base_url=self.local_llm_base_url,
            api_key=self.local_llm_api_key,
            max_retries=3,
            timeout=120.0,
        )

        return OpenAIChatModel(
            self.local_llm_model,
            provider=OpenAIProvider(openai_client=client)
        )

    def _has_cloud_api_key(self) -> bool:
        """Check if any cloud API key is configured."""
        return bool(
            self.openai_api_key or
            self.anthropic_api_key or
            self.google_api_key
        )
```

### Updated Agent Initialization

**Current (backend/src/ai.py line 67-71):**
```python
transcript_agent = Agent(
    model=config.llm,  # String like "google:gemini-2.5-flash"
    result_type=TranscriptAnalysis,
    system_prompt=simplified_system_prompt
)
```

**New (with local-first support):**
```python
# Get model based on configuration (local-first, cloud fallback)
llm_model = config.get_llm_model()

transcript_agent = Agent(
    model=llm_model,  # Either OpenAIChatModel (local) or string (cloud)
    result_type=TranscriptAnalysis,
    system_prompt=simplified_system_prompt
)
```

---

## Verifiable Units of Work (VUWs)

### Campaign Structure

This migration follows VUW methodology with mandatory verification after each unit.

**Campaign:** Cloud API Removal - Local LLM Integration
**Priority:** Campaign 1 (Application Stability)
**Git Strategy:** Checkpoint before/after each VUW

---

### VUW-1: Add Local LLM Configuration to Config Class

**Objective:** Extend `backend/src/config.py` to support local LLM configuration

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-1 - Add local LLM config"
```

**Changes:**
1. Add local LLM environment variables to `Config.__init__()`:
   - `local_llm_enabled`
   - `local_llm_base_url`
   - `local_llm_model`
   - `local_llm_api_key`

2. Add method `get_llm_model()` that returns appropriate model configuration

3. Add helper methods:
   - `_create_local_llm_model()` - Creates OpenAIChatModel for local endpoint
   - `_has_cloud_api_key()` - Checks if cloud API key configured

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Run `pytest tests/test_configuration.py -v` - Must pass **100%**
- [ ] Manually verify: Import config and call `config.get_llm_model()` with local endpoint
- [ ] Self-attestation: Changes work as expected

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-1 COMPLETE: Add local LLM configuration to Config class"
```

**Files Modified:**
- `backend/src/config.py`

**Expected Diff:**
- Add ~50 lines for local LLM configuration
- Add imports: `AsyncOpenAI`, `OpenAIChatModel`, `OpenAIProvider`
- Maintain all existing functionality

---

### VUW-2: Update AI Module to Use Config-Based Model Selection

**Objective:** Modify `backend/src/ai.py` to use `config.get_llm_model()` instead of hardcoded `config.llm`

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-2 - Update AI module model selection"
```

**Changes:**
1. Replace line 68 in `backend/src/ai.py`:
   ```python
   # Before
   transcript_agent = Agent(
       model=config.llm,  # String format
       result_type=TranscriptAnalysis,
       system_prompt=simplified_system_prompt
   )

   # After
   transcript_agent = Agent(
       model=config.get_llm_model(),  # Dynamic model selection
       result_type=TranscriptAnalysis,
       system_prompt=simplified_system_prompt
   )
   ```

2. Add logging to show which LLM mode is active:
   ```python
   if config.local_llm_enabled:
       logger.info(f"🤖 Using local LLM: {config.local_llm_base_url}")
   else:
       logger.info(f"☁️ Using cloud LLM: {config.llm}")
   ```

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Run `pytest tests/ -v -k ai` - All AI-related tests pass
- [ ] Manually test: Start koboldcpp, run transcript analysis, verify it uses local endpoint
- [ ] Manually test: Disable local LLM, set cloud API key, verify it uses cloud
- [ ] Self-attestation: Both local and cloud modes work

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-2 COMPLETE: Update AI module to use config-based model selection"
```

**Files Modified:**
- `backend/src/ai.py`

**Expected Diff:**
- Change 1 line (model assignment)
- Add 3-5 lines (logging)

---

### VUW-3: Update Environment Configuration Examples

**Objective:** Update `.env.example` files to show local-first configuration

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-3 - Update environment examples"
```

**Changes:**

1. Update `backend/.env.example`:
   ```bash
   # ==============================================
   # LLM Configuration (Local-First)
   # ==============================================

   # Local LLM (Default - No API Key Required)
   # Recommended: Run koboldcpp locally for offline operation
   LOCAL_LLM_ENABLED=true
   LOCAL_LLM_BASE_URL=http://localhost:6969/v1
   LOCAL_LLM_MODEL=local-model
   LOCAL_LLM_API_KEY=not-needed

   # Cloud LLM (Optional Fallback)
   # Set LOCAL_LLM_ENABLED=false to use cloud APIs
   # Choose one provider and set corresponding API key:
   OPENAI_API_KEY=
   GOOGLE_API_KEY=
   ANTHROPIC_API_KEY=

   # Cloud LLM model (only used if LOCAL_LLM_ENABLED=false)
   # Format: "provider:model-name"
   # Examples:
   #   - openai:gpt-4o
   #   - anthropic:claude-3-5-sonnet
   #   - google:gemini-2.5-flash
   LLM_MODEL=google:gemini-2.5-flash
   ```

2. Update root `.env.example` (if exists) with same pattern

3. Add comments explaining local-first design

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Verify format matches existing `.env.example` style
- [ ] Test: Copy to `.env`, verify config loads correctly
- [ ] Self-attestation: Configuration is clear and user-friendly

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-3 COMPLETE: Update environment configuration for local-first LLM"
```

**Files Modified:**
- `backend/.env.example`
- `.env.example` (if exists in root)

**Expected Diff:**
- Reorder LLM configuration section (~30 lines modified)
- Add explanatory comments (~10 lines)

---

### VUW-4: Create Tests for Local LLM Configuration

**Objective:** Add comprehensive tests for local LLM configuration and fallback logic

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-4 - Add local LLM tests"
```

**Changes:**

1. Create new test file: `backend/tests/test_local_llm_config.py`

2. Test cases to implement:
   ```python
   class TestLocalLLMConfiguration:
       def test_local_llm_enabled_default(self):
           """Local LLM should be enabled by default"""

       def test_local_llm_base_url_default(self):
           """Default base URL should be localhost:6969"""

       def test_local_llm_model_configurable(self):
           """Local LLM model name should be configurable"""

       def test_get_llm_model_returns_openai_chat_model(self):
           """get_llm_model() should return OpenAIChatModel for local"""

       def test_cloud_fallback_when_local_disabled(self):
           """Should fall back to cloud when LOCAL_LLM_ENABLED=false"""

       def test_error_when_no_llm_configured(self):
           """Should raise ValueError when neither local nor cloud configured"""

       def test_cloud_requires_api_key(self):
           """Cloud mode should require at least one API key"""

       def test_local_mode_logging(self):
           """Should log which LLM mode is active"""
   ```

3. Add integration test:
   ```python
   class TestLLMIntegration:
       async def test_local_llm_agent_creation(self):
           """Agent should be created successfully with local LLM"""

       async def test_cloud_llm_agent_creation(self):
           """Agent should be created successfully with cloud LLM"""
   ```

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Run `pytest tests/test_local_llm_config.py -v` - All tests pass
- [ ] Run `pytest tests/ -v` - All existing tests still pass
- [ ] Coverage report shows new code is tested
- [ ] Self-attestation: All scenarios covered by tests

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-4 COMPLETE: Add comprehensive local LLM configuration tests"
```

**Files Created:**
- `backend/tests/test_local_llm_config.py`

**Expected Additions:**
- ~200-300 lines of test code
- 8+ test functions

---

### VUW-5: Update CLAUDE.md Documentation

**Objective:** Document the local-first LLM configuration in project documentation

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-5 - Update CLAUDE.md documentation"
```

**Changes:**

1. Update `CLAUDE.md` section on "Environment variables (backend/.env)":
   ```markdown
   **Environment variables (backend/.env):**

   **Local LLM (Default - No API Key Required):**
   - `LOCAL_LLM_ENABLED` - Enable local LLM (default: true)
   - `LOCAL_LLM_BASE_URL` - Local LLM endpoint (default: http://localhost:6969/v1)
   - `LOCAL_LLM_MODEL` - Model name for local LLM (default: local-model)

   **Cloud LLM (Optional Fallback):**
   - `LLM_MODEL` - AI model identifier (e.g., "openai:gpt-4", "anthropic:claude-3-5-sonnet")
   - `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY` - Depending on LLM choice

   **Other Configuration:**
   - `DATABASE_URL` - SQLite connection string (default: sqlite+aiosqlite:///./supoclip.db)
   - `TEMP_DIR` - Directory for temporary files (defaults to ./temp)
   ```

2. Update "Video Processing Pipeline" section:
   ```markdown
   1. **Video Input** → YouTube URL (via yt-dlp) or uploaded file
   2. **Transcription** → MLX Whisper generates word-level timestamps (offline)
   3. **AI Analysis** → Local LLM or cloud LLM analyzes transcript for viral segments (10-45s clips)
   4. **Clip Generation** → MoviePy creates 9:16 clips...
   ```

3. Update "Offline Capability" section to clarify what's now fully offline

4. Update "Project-Specific Deviations" table:
   ```markdown
   | LLM Analysis | Cloud APIs (OpenAI/Google/Anthropic) | Local LLM via koboldcpp (optional cloud fallback) |
   ```

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Read through CLAUDE.md to ensure clarity and accuracy
- [ ] Verify all references to LLM are updated
- [ ] Check markdown formatting is correct
- [ ] Self-attestation: Documentation is clear and complete

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-5 COMPLETE: Update CLAUDE.md with local-first LLM documentation"
```

**Files Modified:**
- `CLAUDE.md`

**Expected Diff:**
- ~20-30 lines modified
- Updated 3-4 sections

---

### VUW-6: Update QUICKSTART.md with Local LLM Setup

**Objective:** Add instructions for setting up koboldcpp for local LLM operation

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-6 - Update QUICKSTART.md"
```

**Changes:**

1. Add new section: "Local LLM Setup (Recommended)"
   ```markdown
   ## Local LLM Setup (Recommended)

   For fully offline operation, run a local LLM using koboldcpp:

   ### Install KoboldCPP

   ```bash
   # macOS (Apple Silicon)
   brew install koboldcpp

   # Or download from: https://github.com/LostRuins/koboldcpp/releases
   ```

   ### Download a Model

   Download a GGUF model file (recommended: 7B-13B parameter models):

   - [Mistral-7B-Instruct](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF)
   - [Llama-2-13B-Chat](https://huggingface.co/TheBloke/Llama-2-13B-chat-GGUF)
   - [OpenHermes-2.5-Mistral-7B](https://huggingface.co/TheBloke/OpenHermes-2.5-Mistral-7B-GGUF)

   ### Start KoboldCPP

   ```bash
   koboldcpp --port 6969 --model /path/to/your-model.gguf --contextsize 4096
   ```

   ### Configure SupoClip

   The default configuration (`backend/.env.example`) is already set for local LLM.
   Just copy it:

   ```bash
   cp backend/.env.example backend/.env
   ```

   ### Cloud LLM Alternative (Optional)

   If you prefer cloud LLMs, edit `backend/.env`:

   ```bash
   LOCAL_LLM_ENABLED=false
   LLM_MODEL=openai:gpt-4o  # or google:gemini-2.5-flash
   OPENAI_API_KEY=your-key-here
   ```
   ```

2. Update "Prerequisites" section to include koboldcpp as optional

3. Update "Quick Start" section to reference local LLM setup

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Test instructions by following them manually
- [ ] Verify links to koboldcpp and models are valid
- [ ] Check markdown formatting
- [ ] Self-attestation: Instructions are clear and complete

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-6 COMPLETE: Update QUICKSTART.md with local LLM setup instructions"
```

**Files Modified:**
- `QUICKSTART.md`

**Expected Diff:**
- Add ~60-80 lines (new section)
- Modify ~10 lines (prerequisites, quick start)

---

### VUW-7: Create Integration Test for Full Local Pipeline

**Objective:** Create end-to-end test proving full offline operation

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-7 - Add full local pipeline test"
```

**Changes:**

1. Add test to `backend/tests/test_offline_capability.py`:
   ```python
   class TestFullyOfflineOperation:
       async def test_complete_offline_pipeline(self):
           """Test entire video processing pipeline works offline"""
           # This test proves:
           # 1. SQLite database works (no PostgreSQL)
           # 2. MLX Whisper works (no AssemblyAI)
           # 3. Local LLM works (no cloud APIs)
           # 4. Local job queue works (no Redis)
           # 5. Video processing works (all local)

       async def test_offline_with_local_llm_configured(self):
           """Config with LOCAL_LLM_ENABLED=true should not require API keys"""

       async def test_local_llm_endpoint_validation(self):
           """Should validate local LLM endpoint is reachable before use"""

       async def test_graceful_fallback_to_cloud(self):
           """Should gracefully fall back to cloud if local LLM unreachable"""
   ```

2. Add fixture for mock local LLM responses

3. Add test for error handling when neither local nor cloud configured

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] Run `pytest tests/test_offline_capability.py -v` - All tests pass
- [ ] Run `pytest tests/ -v` - All tests pass (must maintain 146+ passing)
- [ ] Coverage report confirms offline path is fully tested
- [ ] Self-attestation: Full offline operation is proven by tests

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-7 COMPLETE: Add integration test for full local pipeline"
```

**Files Modified:**
- `backend/tests/test_offline_capability.py`

**Expected Diff:**
- Add ~100-150 lines of test code
- Add 4+ test functions

---

### VUW-8: Update Migration Summary Documentation

**Objective:** Document the completion of cloud API removal in migration summary

**Git Checkpoint Before:**
```bash
git add -A
git commit -m "CHECKPOINT: Before VUW-8 - Update migration summary"
```

**Changes:**

1. Update `docs/MIGRATION_SUMMARY.md`:
   - Add new section: "Phase 9: Remove Cloud LLM Dependency"
   - Update "Offline Capability" section to show LLM is now local
   - Update "Architecture Changes" table
   - Update success metrics

2. Create `docs/progress/fixes/cloud-removal-2025-11-14-COMPLETE.md`:
   - Copy this VUW plan
   - Add completion status for each VUW
   - Document test results
   - Add final verification checklist

**Content for Phase 9:**
```markdown
### Phase 9: Remove Cloud LLM Dependency ✅

- Created local LLM configuration in `backend/src/config.py`
- Updated AI module to support local-first LLM selection
- Integrated KoboldCPP (OpenAI-compatible local LLM)
- Made cloud APIs optional fallback instead of required
- Updated all documentation for local-first design

**Key Changes:**
- Added: `LOCAL_LLM_ENABLED`, `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL` config
- Modified: `backend/src/ai.py` to use `config.get_llm_model()`
- Updated: Environment examples to show local-first defaults
- Created: Comprehensive tests for local LLM configuration

**Files Modified:**
- `backend/src/config.py`
- `backend/src/ai.py`
- `backend/.env.example`
- `CLAUDE.md`
- `QUICKSTART.md`
- `backend/tests/test_local_llm_config.py`
- `backend/tests/test_offline_capability.py`
```

**Verification Checklist:**
- [ ] Run `./checkpython.sh` - Must report **zero errors**
- [ ] All VUWs documented with completion status
- [ ] Migration summary reflects current state
- [ ] Test results documented
- [ ] Self-attestation: Documentation is complete and accurate

**Git Checkpoint After:**
```bash
git add -A
git commit -m "VUW-8 COMPLETE: Update migration documentation for cloud API removal"
```

**Files Modified:**
- `docs/MIGRATION_SUMMARY.md`

**Files Created:**
- `docs/progress/fixes/cloud-removal-2025-11-14-COMPLETE.md`

**Expected Diff:**
- Add ~100-150 lines to migration summary
- Create new completion document (~200 lines)

---

## Post-VUW Validation

After completing all VUWs, perform final validation:

### Final Verification Checklist

- [ ] **Run `./checkpython.sh`** - Must report **zero errors with 100% tests passing**
- [ ] **Run full test suite** - `pytest tests/ -v --cov=src`
  - All 146+ tests passing
  - Coverage maintained or improved
  - No regressions introduced
- [ ] **Manual testing - Local LLM mode:**
  - Start koboldcpp on localhost:6969
  - Process test video end-to-end
  - Verify clips generated successfully
  - Confirm no cloud API calls made
- [ ] **Manual testing - Cloud LLM mode:**
  - Set `LOCAL_LLM_ENABLED=false`
  - Set cloud API key
  - Process test video end-to-end
  - Verify clips generated successfully
- [ ] **Manual testing - Error handling:**
  - Disable both local and cloud
  - Verify clear error message shown
  - Confirm application doesn't crash
- [ ] **Documentation review:**
  - CLAUDE.md updated and accurate
  - QUICKSTART.md has clear setup instructions
  - Migration summary complete
  - All references to cloud-only operation removed
- [ ] **Self-attestation:** All VUWs complete and verified

### Final Git Commit

```bash
git add -A
git commit -m "🎉 CLOUD API REMOVAL COMPLETE: Full local-first operation with optional cloud fallback

Phase 9 Complete:
- Local LLM support via KoboldCPP (OpenAI-compatible)
- Cloud APIs now optional instead of required
- Full offline operation verified by tests
- Documentation updated for local-first design

VUWs Completed: 8/8
Tests Passing: 146+ (maintained)
Coverage: 65%+ core modules (maintained or improved)

Files Modified: 8
Files Created: 2
Lines Added: ~500-700
Test Coverage: New code 100% tested
"
```

---

## Success Metrics

### Before This Migration

| Metric | Value |
|--------|-------|
| **Cloud Dependencies** | 1 (Pydantic AI LLM) |
| **Required API Keys** | 1+ (OpenAI/Google/Anthropic) |
| **Offline Capability** | Partial (transcription only) |
| **Cost for Local Use** | $0.01-$0.10 per video (LLM API calls) |
| **Internet Required** | Yes (for LLM analysis) |

### After This Migration

| Metric | Value |
|--------|-------|
| **Cloud Dependencies** | 0 (all optional) |
| **Required API Keys** | 0 (local-first) |
| **Offline Capability** | Complete (100% offline) |
| **Cost for Local Use** | $0.00 (fully free) |
| **Internet Required** | No (optional for cloud fallback) |

### Quality Metrics

- **Test Coverage:** 65%+ core modules (maintained)
- **Tests Passing:** 146+ tests (maintained or increased)
- **Documentation:** 100% updated
- **Type Safety:** 100% type hints maintained
- **Code Quality:** Zero ruff/mypy errors
- **VUW Completion:** 8/8 (100%)

---

## Risk Mitigation

### Identified Risks

1. **Local LLM Quality:** Local models may produce lower-quality segment selection than GPT-4
   - **Mitigation:** Keep cloud fallback option; recommend 7B+ parameter models
   - **Testing:** Compare segment quality between local and cloud in manual testing

2. **Performance:** Local LLM may be slower than cloud APIs
   - **Mitigation:** Document expected performance; recommend GPU acceleration
   - **Testing:** Benchmark processing time in integration tests

3. **Configuration Complexity:** More configuration options could confuse users
   - **Mitigation:** Clear defaults (local-first); excellent documentation
   - **Testing:** User-friendly error messages; validate configuration at startup

4. **Breaking Changes:** Existing users with cloud configs might break
   - **Mitigation:** Backward compatibility maintained; cloud configs still work
   - **Testing:** Test both local and cloud modes thoroughly

5. **Local LLM Setup:** Users may struggle to set up koboldcpp
   - **Mitigation:** Detailed QUICKSTART.md instructions; links to resources
   - **Testing:** Follow instructions on clean system to verify completeness

### Rollback Plan

If any VUW fails verification:

1. **Stop immediately** - Do not proceed to next VUW
2. **Review test failures** - Understand what broke
3. **Fix the issue** - Make necessary corrections
4. **Re-run verification** - Must pass before continuing
5. **If unfixable** - Rollback to previous git checkpoint:
   ```bash
   git reset --hard HEAD~1  # Rollback last commit
   ```

### Complete Rollback (if needed)

```bash
# Rollback entire migration
git reset --hard <commit-before-VUW-1>

# Or revert all commits
git revert <vuw-8-commit>..<vuw-1-commit>
```

---

## Dependencies

### New Dependencies Required

**Python packages (already in pyproject.toml):**
- None - `pydantic-ai` already installed and supports OpenAI-compatible endpoints

**Optional external software (for local LLM):**
- KoboldCPP (optional but recommended)
- GGUF model file (user's choice, 7B-13B recommended)

### No Dependencies to Remove

All cloud dependencies are made **optional**, not removed:
- Pydantic AI still supports cloud models
- API key config still exists
- Users can still choose cloud if preferred

---

## Configuration Strategy: Config File vs Environment Variables

### Decision: Stick with Environment Variables (.env)

**Rationale:**
1. **Consistency:** Project already uses `.env` files throughout
2. **Better Auth:** Frontend uses `.env` for Better Auth configuration
3. **Docker/Deployment:** `.env` files are standard for Docker/cloud deployment
4. **Twelve-Factor App:** Environment variables are best practice for config
5. **Security:** Secrets (API keys) should never be in YAML files
6. **Simplicity:** No need to introduce new config format

**Current Pattern (Keep):**
```
.env.example → Copy to .env → Load via python-dotenv → Validate with Pydantic
```

**NOT Migrating to YAML because:**
- Adds unnecessary complexity
- Requires new dependency (PyYAML)
- Contradicts project's current pattern
- Environment variables are more flexible for deployment

---

## References

### Documentation

- **Pydantic AI OpenAI Provider:** https://ai.pydantic.dev/models/openai/
- **KoboldCPP GitHub:** https://github.com/LostRuins/koboldcpp
- **MLX Whisper (already integrated):** https://github.com/ml-explore/mlx-examples/tree/main/whisper
- **VUW Methodology:** CLAUDE.md Section "Debugging Methodology"

### Internal Documentation

- **Migration Summary:** `docs/MIGRATION_SUMMARY.md`
- **Testing Report:** `backend/TESTING_REPORT.md`
- **Project Standards:** `docs/standards.md`
- **Code Guidelines:** `CLAUDE.md`

### Code Files Referenced

- `backend/src/config.py` - Configuration management
- `backend/src/ai.py` - Pydantic AI agent initialization
- `backend/src/transcription_mlx.py` - MLX Whisper integration (complete)
- `backend/.env.example` - Environment configuration template
- `backend/tests/test_offline_capability.py` - Offline operation tests

---

## Next Steps After Completion

### Immediate (Post-VUW)

1. **Merge to main** - After all VUWs verified
2. **Update README.md** - Add local LLM setup section
3. **Create release notes** - Document v2.1 changes
4. **Test on fresh macOS** - Verify installation instructions work

### Future Enhancements (Optional)

1. **MLX LM Integration** - Replace KoboldCPP with native MLX LM for even better performance
2. **Model Management UI** - Web interface for downloading/managing local models
3. **Benchmark Suite** - Compare local vs cloud quality/performance
4. **Prompt Optimization** - Fine-tune prompts for smaller local models
5. **Hybrid Mode** - Use local for fast preview, cloud for final quality

---

## Conclusion

This VUW plan provides a systematic, verifiable path to complete local-first operation for SupoClip. By following the 8 VUWs in sequence with mandatory verification after each step, we ensure:

1. **No Cloud APIs Required** - Full offline operation by default
2. **Cloud as Optional Fallback** - Users can still choose cloud if desired
3. **Backward Compatibility** - Existing cloud configurations still work
4. **Quality Maintained** - All tests pass, code quality preserved
5. **Well Documented** - Clear instructions for setup and use

**Total Effort Estimate:** 4-6 hours for all VUWs + verification

**Ready to Begin:** Yes - All research complete, plan verified

---

**Plan Created By:** Claude Code Agent
**Date:** November 14, 2025
**Status:** Ready for Implementation
