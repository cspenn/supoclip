# Testing Infrastructure Audit — SupoClip

**Audit date:** 2026-06-29
**Auditor:** Claude Sonnet 4.6 (read-only)

---

## Ground-Truth Numbers (authoritative — do not re-derive)

| Metric | Value |
|--------|-------|
| Tests collected | 466 |
| Tests passed | 466 |
| Tests failed | 0 |
| Exit code | 0 |
| Runtime | ~23 s |
| Line coverage | 100.00% (1434 statements, 0 missed) |
| Branch coverage | **not measured** (see Finding 1) |
| mypy issues | 0 across 19 source files |
| ruff issues | 0 |
| radon C violations | 3 functions |

---

## Test Structure

```
tests/
  conftest.py                      — empty (3 lines)
  unit/
    conftest.py                    — NiceGUI stub + MagicMock widget factory
    test_analyze.py
    test_clip.py
    test_config.py
    test_database.py
    test_download.py
    test_face_detect.py
    test_history.py
    test_home.py
    test_main.py
    test_models.py
    test_settings.py
    test_subtitles.py
    test_task_page.py
    test_transcribe.py
    test_video_service.py
  integration/
    conftest.py                    — real in-memory aiosqlite DB + mock fixtures
    test_pipeline_e2e.py           — 2 tests; all pipeline calls are mocked
    test_pipeline_failures.py      — 4 failure mode tests; some real, some mocked
    test_settings_persistence.py   — 3 real DB round-trip tests
  fixtures/
    sample_video.mp4               — 5441-byte real MP4; NEVER used in any test
    sample_logo.png                — real PNG; NEVER used in any test
  verify_subtitle_renderer.py      — dead orphan script from old architecture
  output/
    logo_test.mp4                  — binary artifact from manual testing
```

---

## Finding 1 — No Branch Coverage (HIGH, test-gap)

**Location:** `pyproject.toml:54`

The `addopts` line is:
```
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=100"
```

`--cov-branch` is absent. Only LINE coverage is enforced. 100% line coverage means every source line is executed at least once — it does not mean every conditional branch is exercised. For every `if/elif/else`, `try/except`, short-circuit `and`/`or`, and comprehension filter, at least one arm may be permanently untested without this being visible in the coverage report.

**Impact:** The 100% line figure is misleading. In `src/pipeline/subtitles.py:162–170`, the `if duration_ms < _MIN_WORD_DURATION_MS: continue` path IS tested (test_short_words_skipped), but subtler conditional chains in `face_detect.py`, `transcribe.py` (grade-C function `_tokens_from_result`), and `video_service.py` (grade-C `process_video`) have internal branches that may only be covered on the "happy" side.

**Remediation:** Add `--cov-branch` to `addopts` and set a target (≥85% branch coverage is a reasonable starting floor). Expect 10–25 new uncovered branches to emerge.

---

## Finding 2 — E2E "Integration" Tests Are Fully Mocked (HIGH, test-gap)

**Location:** `tests/integration/test_pipeline_e2e.py:70–98`

The file is named "end-to-end" but both tests mock every IO boundary:

```python
patch("src.services.video_service.asyncio.to_thread", new=AsyncMock(return_value=word_list)),
patch("src.pipeline.clip.generate_clip", new=AsyncMock(return_value=None)),
patch("src.services.video_service._generate_clips_concurrently",
      new=AsyncMock(return_value=[(tmp_path / "...", mock_analyze.return_value[0])])),
```

`_generate_clips_concurrently` — the function that actually calls ffmpeg — is replaced entirely. No real ffmpeg subprocess runs. No real video file is produced or inspected. The tests verify only DB state and progress callback milestones.

`tests/fixtures/sample_video.mp4` (a genuine 5441-byte ISO MP4 file) is committed but referenced by **zero** test files. It was presumably intended for real E2E tests that were never written.

**Impact:** Runtime output bugs — wrong crop box causing portrait clipping, subtitle text invisible, ASS file encoding errors, wrong ffmpeg filtergraph syntax — are completely invisible to the test suite. The four recent runtime-fix commits (a3af789, 92dfc0f, 529be05, 4a851dc) were all discovered at runtime, not by tests.

**Remediation:** Add at least one real integration test using `tests/fixtures/sample_video.mp4` that:
1. Runs the real transcribe → analyze (mocked LLM) → clip pipeline
2. Calls actual ffmpeg via `subprocess.run`
3. Verifies the output `.mp4` file exists, is non-zero bytes, and passes `ffprobe` checks for dimensions (1080×1920) and codec (H.264/AAC)

---

## Finding 3 — ASS Special Character Escaping Not Tested (HIGH, test-gap)

**Location:** `tests/unit/test_subtitles.py`, `src/pipeline/subtitles.py:178`

The subtitle source at line 178–179 writes text directly to the ASS event:
```python
event.text = text  # text is str(word_data["text"]) possibly .upper()
```

The ASS format uses `{...}` for inline override blocks (e.g. `{\an8}` for alignment). A word containing a curly brace — e.g. `{hello}` or even `\N` (ASS newline) — will be parsed as a style tag by ffmpeg's ASS filter, causing that word's text to be silently hidden or misrendered.

All test words in `_SAMPLE_WORDS` are clean alphanumeric: `"Hello"`, `"world"`, `"foo"`, `"bar"`. No test exercises:
- Words with `{`, `}` characters
- Words with `\N`, `\n`, `\h` (ASS special sequences)
- Words with backslash

This directly relates to the "subtitle text clipped/invisible" runtime bug fixed in commit `92dfc0f`.

**Remediation:** Add tests to `TestGenerateAssSubtitles` for words containing `{`, `}`, `\N`. Decide and document the escaping policy (pysubs2 may or may not escape these automatically — test both paths).

---

## Finding 4 — tests/verify_subtitle_renderer.py Is Dead Orphan Code (MEDIUM, broken)

**Location:** `tests/verify_subtitle_renderer.py:9`

```python
from src.subtitle_renderer import BrowserSubtitleRenderer
```

`src.subtitle_renderer` and `BrowserSubtitleRenderer` do not exist in the current codebase. This module was part of the old React + Playwright architecture deleted in the March 2026 redesign (documented in `docs/` and `.serena/project.yml`). The file is not collected by pytest (it uses `if __name__ == "__main__"` instead of test functions), but it:

1. Cannot be imported or run — it would immediately raise `ModuleNotFoundError`
2. References architecture concepts (`BrowserSubtitleRenderer`, `stroke_width`, `shadow_color`, `text_transform`, `font_weight`) that are conceptually replaced by `SubtitleStyle` and `generate_ass_subtitles`
3. Generates output PNG files via a Chrome headless browser — a mechanism the project no longer has

**Impact:** Any developer who attempts to run or extend this file will be confused. The graphify knowledge graph may index it and create misleading edges to non-existent `src.subtitle_renderer`.

**Remediation:** Delete `tests/verify_subtitle_renderer.py` and `tests/output/logo_test.mp4`. If visual subtitle verification is needed, write a new script using the actual `write_ass_file` API and ffmpeg to render a test frame.

---

## Finding 5 — Fixture Files Are Never Used (MEDIUM, unnecessary)

**Location:** `tests/fixtures/sample_video.mp4`, `tests/fixtures/sample_logo.png`

Both files are committed to the repository but referenced by no test. Confirmation:
```
grep -rn "sample_video\|sample_logo\|fixtures" tests/ | grep -v "__pycache__\|conftest"
# (no output)
```

`tests/fixtures/sample_video.mp4` is a real ISO MP4 (5441 bytes, `file` command confirmed). It is suitable for a real transcription or clip-generation integration test. Its presence in the repo with no associated test suggests a real E2E test was planned but not written.

**Remediation:** Either write the integration test that uses `sample_video.mp4`, or explicitly document these as reserved for future tests with a `README` or inline comment in `conftest.py`.

---

## Finding 6 — NiceGUI Page Tests Are Smoke Tests Only (MEDIUM, test-gap)

**Location:** `tests/unit/conftest.py:16–37`, all `test_home.py`, `test_task_page.py`, `test_history.py`, `test_settings.py` render tests

The NiceGUI stub in `conftest.py` makes every widget (`ui.label`, `ui.button`, `ui.video`, etc.) return a `MagicMock` that supports fluent chaining but records nothing meaningful. Every `render()` test in the page test files follows the same pattern:

```python
await render()
assert True  # or assert that notify was called
```

These tests verify:
- Page modules can be imported without error
- `render()` coroutines complete without raising

These tests do NOT verify:
- Widget hierarchy, text labels, CSS classes
- Phone-frame preview content or positioning
- Whether the progress bar is actually wired to the correct data source
- Whether video elements have the correct `src` attribute

The "subtitle text clipped/invisible in phone-frame preview" bug (commits `92dfc0f`, `529be05`) and "HTML sanitization disabled" bug exist at the NiceGUI layer where actual HTML is generated. These are architecturally impossible to catch with the current stub approach.

**Remediation (pragmatic):** For the phone-frame preview specifically, add a Playwright/browser-based smoke test using `claude-in-chrome` or a headless browser fixture that loads the actual NiceGUI app and screenshots the preview element. For unit tests, consider threading the rendered HTML through the NiceGUI `TestClient` if the library supports it.

---

## Finding 7 — ClipOptions/Subtitle Style Never Tested End-to-End Through video_service (MEDIUM, test-gap)

**Location:** `tests/unit/test_video_service.py:422`, all `TestProcessVideo` tests

In every `TestProcessVideo` test, `ClipOptions` is mocked:
```python
mock_clip_module.ClipOptions = MagicMock(return_value=None)
```

This means the actual flow:
1. User settings → `UserPreferences` DB row
2. `video_service.py` reads prefs and constructs `SubtitleStyle`
3. `SubtitleStyle` → `ClipOptions(subtitle_style=style)`
4. `ClipOptions` → `write_ass_file` → `generate_ass_subtitles`
5. ffmpeg ASS burn-in

...is never exercised as a whole unit in any test. Individual steps are tested in isolation (`test_subtitles.py`, `test_clip.py`), but the wiring between `video_service` and `subtitles` with real UserPreferences data is a test gap.

**Remediation:** Add a `TestProcessVideo` variant that passes a real `SubtitleStyle` through the pipeline (keeping ffmpeg mocked at `_run_ffmpeg`) and asserts that `write_ass_file` was called with the expected style parameters.

---

## Finding 8 — Crop Math Not Tested With Non-Ideal Dimensions (LOW, test-gap)

**Location:** `tests/unit/test_face_detect.py:49–147`

`calculate_crop_box` is well-tested for clean cases: 1920×1080, 1280×720, and portrait 1080×1920. Missing:
- A landscape source with odd dimensions (e.g. 1919×1079) where even-rounding interacts with face centering
- A face positioned such that both x-clamp AND y-clamp are triggered simultaneously
- A very small source (e.g. 320×240) where the crop box collapses to minimum dimensions

These are edge cases but the "all dimensions are even" contract (for H.264 macroblock compliance) could fail in subtle combinations.

**Remediation:** Add three parameterized cases covering the above inputs. Verify `w % 2 == 0` and `h % 2 == 0` in each.

---

## Finding 9 — Recent Runtime Bugs Are Now Tested Post-Fix (INFO, good)

The four recent fix commits introduced test coverage for their specific behaviors:

| Commit | Bug | Test Added |
|--------|-----|------------|
| a3af789 | YouTube Live URL not recognized | `test_download.py:105–107` (`test_extract_video_id_live_url`) and `test_valid_youtube_urls` parametrize includes `youtube.com/live/...` |
| a3af789 | Local LLM `base_url` not passed to `OpenAIProvider` | `test_analyze.py:774` (`test_local_llm_constructs_openai_model_with_base_url`) |
| 92dfc0f, 529be05 | Subtitle text clipped/invisible in preview | **No corresponding test added** — this was a NiceGUI HTML rendering issue, not testable by current unit test approach |

**Conclusion:** The fix-then-test pattern was partially followed. The NiceGUI rendering bugs remain untested.

---

## Finding 10 — Integration DB Tests Are Genuine (INFO, good)

**Location:** `tests/integration/test_settings_persistence.py`, `tests/integration/test_pipeline_failures.py`

These tests use the `test_db` fixture which creates a real aiosqlite in-memory engine, calls `init_db()` to create schema, and runs real `async with get_session()` sessions. The ORM models, session lifecycle, and SQLAlchemy `add`/`get`/`flush`/`commit` paths are genuinely exercised. This is a solid validation of `src/database.py` and `src/models.py`.

---

## Summary

The test suite achieves 100% line coverage with 466 passing tests, which is a substantial quantity of tests. Quality gaps fall into three tiers:

**Critical quality gap:** No branch coverage and no real ffmpeg execution in any test. A 100% line coverage number with zero branch coverage can be achieved even when half the conditional arms are never exercised. Combined with the full mock-out of ffmpeg, the test suite provides no defense against runtime output bugs.

**Structural gap:** `tests/verify_subtitle_renderer.py` is a dead file from the deleted React architecture that imports non-existent modules. `tests/fixtures/sample_video.mp4` is committed but unused. The `tests/output/` directory contains a committed binary artifact.

**Known unexercised scenarios:** ASS special character handling, full subtitle-style pipeline from user preferences to ffmpeg command, NiceGUI widget rendering and HTML output.
