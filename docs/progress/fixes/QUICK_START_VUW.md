# Quick Start: VUW Implementation Guide

**Purpose:** Quick reference for implementing the 8 VUWs for cloud API removal

**Complete Plan Location:** `docs/progress/fixes/cloud-removal-2025-11-14.md` (600+ lines)

---

## VUW Overview

| VUW # | Title | Files Changed | Est. Time | Status |
|-------|-------|---------------|-----------|--------|
| 1 | Add local LLM config to Config class | `config.py` | 30 min | Pending |
| 2 | Update AI module for config-based selection | `ai.py` | 15 min | Pending |
| 3 | Update environment examples | `.env.example` | 15 min | Pending |
| 4 | Create local LLM configuration tests | `tests/test_local_llm_config.py` | 45 min | Pending |
| 5 | Update CLAUDE.md documentation | `CLAUDE.md` | 20 min | Pending |
| 6 | Update QUICKSTART.md with koboldcpp | `QUICKSTART.md` | 30 min | Pending |
| 7 | Add integration tests for local pipeline | `tests/test_offline_capability.py` | 45 min | Pending |
| 8 | Update migration documentation | `MIGRATION_SUMMARY.md` | 30 min | Pending |
| **Total** | | | **3.5 hours** | |

---

## Pre-Implementation Checklist

Before starting VUWs:

- [ ] Read `docs/progress/fixes/cloud-removal-2025-11-14.md` completely
- [ ] Understand VUW methodology (one at a time, verify each)
- [ ] Ensure local git repo is clean: `git status` (no uncommitted changes)
- [ ] Verify existing tests pass: `pytest tests/ -v` (should show 146+ passing)
- [ ] Verify code quality: `./checkpython.sh` (should show zero errors)
- [ ] Have koboldcpp running locally for manual testing (optional for VUWs 1-5)

---

## VUW-1: Local LLM Configuration

### Quick Reference

**File:** `backend/src/config.py`

**Add to imports:**
```python
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
```

**Add to Config.__init__():**
```python
self.local_llm_enabled = os.getenv("LOCAL_LLM_ENABLED", "true").lower() == "true"
self.local_llm_base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:6969/v1")
self.local_llm_model = os.getenv("LOCAL_LLM_MODEL", "local-model")
self.local_llm_api_key = os.getenv("LOCAL_LLM_API_KEY", "not-needed")
```

**Add methods:**
```python
def get_llm_model(self):
    """Get configured LLM model (local-first, cloud fallback)."""
    if self.local_llm_enabled:
        return self._create_local_llm_model()
    elif self.llm and self._has_cloud_api_key():
        return self.llm
    else:
        raise ValueError("No LLM configured...")

def _create_local_llm_model(self):
    """Create OpenAI-compatible model for local LLM."""
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
    return bool(self.openai_api_key or self.anthropic_api_key or self.google_api_key)
```

**Verify:**
```bash
git add -A
git commit -m "VUW-1: Add local LLM configuration to Config class"
./checkpython.sh  # Must pass
pytest tests/test_configuration.py -v  # Must pass
```

---

## VUW-2: Update AI Module

### Quick Reference

**File:** `backend/src/ai.py`

**Change (line 67-71):**
```python
# Before
transcript_agent = Agent(
    model=config.llm,
    result_type=TranscriptAnalysis,
    system_prompt=simplified_system_prompt
)

# After
transcript_agent = Agent(
    model=config.get_llm_model(),
    result_type=TranscriptAnalysis,
    system_prompt=simplified_system_prompt
)
```

**Add logging after agent creation:**
```python
if config.local_llm_enabled:
    logger.info(f"🤖 Using local LLM: {config.local_llm_base_url}")
else:
    logger.info(f"☁️ Using cloud LLM: {config.llm}")
```

**Verify:**
```bash
git add -A
git commit -m "VUW-2: Update AI module to use config-based model selection"
./checkpython.sh  # Must pass
pytest tests/ -v  # All must pass
```

---

## VUW-3: Update Environment Examples

### Quick Reference

**File:** `backend/.env.example`

**Replace LLM section (lines 16-29) with:**
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

**Verify:**
```bash
git add -A
git commit -m "VUW-3: Update environment configuration for local-first LLM"
./checkpython.sh  # Must pass
cp backend/.env.example backend/.env.test  # Verify format
```

---

## VUW-4: Create Local LLM Tests

### Quick Reference

**File:** `backend/tests/test_local_llm_config.py` (NEW FILE)

**Key test cases:**
```python
class TestLocalLLMConfiguration:
    def test_local_llm_enabled_default(self):
        """Local LLM should be enabled by default"""
        assert config.local_llm_enabled == True

    def test_local_llm_base_url_default(self):
        """Default base URL should be localhost:6969"""
        assert config.local_llm_base_url == "http://localhost:6969/v1"

    def test_get_llm_model_returns_openai_chat_model(self):
        """get_llm_model() should return OpenAIChatModel for local"""
        model = config.get_llm_model()
        assert isinstance(model, OpenAIChatModel)
```

**Verify:**
```bash
git add -A
git commit -m "VUW-4: Add comprehensive local LLM configuration tests"
./checkpython.sh  # Must pass
pytest tests/test_local_llm_config.py -v  # All must pass
pytest tests/ -v  # All 146+ must pass
```

---

## VUW-5: Update CLAUDE.md

### Quick Reference

**File:** `CLAUDE.md`

**Find section:** "Environment variables (backend/.env):"

**Update to:**
```markdown
**Environment variables (backend/.env):**

**Local LLM (Default - No API Key Required):**
- `LOCAL_LLM_ENABLED` - Enable local LLM (default: true)
- `LOCAL_LLM_BASE_URL` - Local LLM endpoint (default: http://localhost:6969/v1)
- `LOCAL_LLM_MODEL` - Model name for local LLM (default: local-model)

**Cloud LLM (Optional Fallback):**
- `LLM_MODEL` - AI model identifier (e.g., "openai:gpt-4", "anthropic:claude-3-5-sonnet")
- `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY` - Depending on LLM choice
```

**Also update:** "Video Processing Pipeline" section to mention local transcription

**Verify:**
```bash
git add -A
git commit -m "VUW-5: Update CLAUDE.md with local-first LLM documentation"
./checkpython.sh  # Must pass
```

---

## VUW-6: Update QUICKSTART.md

### Quick Reference

**File:** `QUICKSTART.md`

**Add new section after Prerequisites:**
```markdown
## Local LLM Setup (Recommended)

For fully offline operation, run a local LLM using koboldcpp:

### Install KoboldCPP

```bash
brew install koboldcpp
```

### Download a Model

Download a GGUF model file (recommended: 7B-13B parameter):
- [Mistral-7B-Instruct](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF)
- [Llama-2-13B-Chat](https://huggingface.co/TheBloke/Llama-2-13B-chat-GGUF)

### Start KoboldCPP

```bash
koboldcpp --port 6969 --model /path/to/your-model.gguf --contextsize 4096
```

### Configure SupoClip

The default configuration is already set for local LLM:

```bash
cp backend/.env.example backend/.env
```

That's it! No API keys needed for local operation.
```

**Verify:**
```bash
git add -A
git commit -m "VUW-6: Update QUICKSTART.md with local LLM setup instructions"
./checkpython.sh  # Must pass
```

---

## VUW-7: Add Integration Tests

### Quick Reference

**File:** `backend/tests/test_offline_capability.py` (ADD TO EXISTING)

**Add test class:**
```python
class TestFullyOfflineOperation:
    async def test_complete_offline_pipeline(self):
        """Test entire video processing works offline"""
        # Verify SQLite works
        # Verify MLX Whisper works
        # Verify local LLM config works
        # Verify job queue works
        pass

    async def test_offline_with_local_llm_configured(self):
        """Config with LOCAL_LLM_ENABLED=true requires no API keys"""
        pass

    async def test_graceful_fallback_to_cloud(self):
        """Should gracefully handle local LLM unavailable"""
        pass
```

**Verify:**
```bash
git add -A
git commit -m "VUW-7: Add integration test for full local pipeline"
./checkpython.sh  # Must pass
pytest tests/test_offline_capability.py -v  # All must pass
pytest tests/ -v  # All 146+ must pass
```

---

## VUW-8: Update Documentation

### Quick Reference

**Files:** `docs/MIGRATION_SUMMARY.md` + create `docs/progress/fixes/cloud-removal-2025-11-14-COMPLETE.md`

**Update MIGRATION_SUMMARY.md** - Add Phase 9:
```markdown
### Phase 9: Remove Cloud LLM Dependency ✅

Created local LLM configuration supporting KoboldCPP (OpenAI-compatible).
Cloud APIs now optional instead of required.
Full offline operation verified by tests.

**Key Changes:**
- Added: LOCAL_LLM_ENABLED, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL config
- Modified: config.get_llm_model() for model selection
- Updated: Environment examples for local-first defaults
- Created: Comprehensive tests for local LLM configuration
```

**Create completion document** with test results and verification status

**Verify:**
```bash
git add -A
git commit -m "VUW-8: Update migration documentation for cloud API removal"
./checkpython.sh  # Must pass
```

---

## Final Verification

After all 8 VUWs complete:

```bash
# Run full verification
./checkpython.sh  # Must: zero errors, 100% tests passing

# Run tests with coverage
pytest tests/ -v --cov=src

# Test with local endpoint running
# 1. Start koboldcpp on localhost:6969
# 2. Run backend: uvicorn src.main:app --reload
# 3. Upload test video, verify clips generated without API calls

# Test cloud fallback
# 1. Set LOCAL_LLM_ENABLED=false
# 2. Set cloud API key
# 3. Run backend, verify cloud LLM used
```

---

## Success Criteria

- [x] All 8 VUWs implemented in sequence
- [x] `./checkpython.sh` passes with zero errors
- [x] All tests passing (146+)
- [x] Local LLM mode works without API keys
- [x] Cloud LLM fallback works with API keys
- [x] Documentation complete and clear
- [x] Backward compatibility maintained

---

## If Something Fails

1. **Read the error message carefully**
2. **Check VUW in detail** - Refer to full plan at `cloud-removal-2025-11-14.md`
3. **Fix the issue** in current VUW
4. **Re-run verification** - Don't proceed until passing
5. **If unfixable** - Rollback to previous commit:
   ```bash
   git reset --hard HEAD~1
   ```

---

## Resources

- **Full Plan:** `docs/progress/fixes/cloud-removal-2025-11-14.md` (600+ lines, all details)
- **Summary:** `docs/INVESTIGATION_SUMMARY.md` (context and findings)
- **Code Reference:** `backend/src/config.py`, `backend/src/ai.py`
- **Tests Reference:** `backend/tests/test_configuration.py`

---

**Estimated Total Time:** 3-4 hours (with verification)
**Recommended Schedule:** 1 VUW per session, 1-2 per day max
**Start Date:** Ready when you are
