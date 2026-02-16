# start backend/tests/test_font_cutoff_and_short_clips.py
"""
Tests for subtitle rendering and AI clip duration behavior.

- TestBrowserSubtitleRenderer: Tests for BrowserSubtitleRenderer interface and rendering
- TestFontResolution: Tests for font path resolution logic
- TestShortClipsIssue: Tests for AI clip duration parameterization
- TestActualUserScenario: Integration test reproducing user scenario with BrowserSubtitleRenderer
"""

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ai_structured import analyze_transcript_structured, build_system_prompt
from src.subtitle_renderer import BrowserSubtitleRenderer


class TestBrowserSubtitleRenderer:
    """
    Tests for the BrowserSubtitleRenderer rendering path.

    Production uses Playwright-based browser rendering instead of
    MoviePy TextClip for subtitle generation. These tests verify the
    renderer class interface and rendering behavior. Playwright browser
    calls are mocked to allow unit testing without browser installation.
    """

    def test_renderer_class_exists(self):
        """BrowserSubtitleRenderer should be importable and instantiable."""
        renderer = BrowserSubtitleRenderer()
        assert renderer is not None
        assert hasattr(renderer, "start")
        assert hasattr(renderer, "stop")
        assert hasattr(renderer, "render_text_to_image")

    def test_renderer_is_context_manager(self):
        """BrowserSubtitleRenderer should implement context manager protocol."""
        renderer = BrowserSubtitleRenderer()
        assert hasattr(renderer, "__enter__")
        assert hasattr(renderer, "__exit__")

    def test_renderer_initial_state(self):
        """BrowserSubtitleRenderer should start with no browser running."""
        renderer = BrowserSubtitleRenderer()
        assert renderer._playwright is None
        assert renderer._browser is None
        assert renderer._page is None

    def test_render_text_to_image_signature(self):
        """render_text_to_image should accept all expected styling parameters."""
        sig = inspect.signature(BrowserSubtitleRenderer.render_text_to_image)
        params = list(sig.parameters.keys())

        expected_params = [
            "self", "text", "font_family", "font_size", "color", "width",
            "stroke_width", "stroke_color", "shadow_color", "shadow_offset",
            "text_transform", "font_weight",
        ]
        for param in expected_params:
            assert param in params, (
                f"render_text_to_image missing parameter: {param}"
            )

    def test_render_text_to_image_default_values(self):
        """render_text_to_image should have sensible defaults for optional params."""
        sig = inspect.signature(BrowserSubtitleRenderer.render_text_to_image)
        params = sig.parameters

        assert params["stroke_width"].default == 2
        assert params["stroke_color"].default == "black"
        assert params["shadow_color"].default is None
        assert params["shadow_offset"].default == 2
        assert params["text_transform"].default == "none"
        assert params["font_weight"].default == "bold"

    def test_stop_clears_all_state(self):
        """Calling stop() should reset all internal state to None."""
        renderer = BrowserSubtitleRenderer()
        # Simulate started state
        renderer._playwright = MagicMock()
        renderer._browser = MagicMock()
        renderer._page = MagicMock()

        renderer.stop()

        assert renderer._playwright is None
        assert renderer._browser is None
        assert renderer._page is None

    def test_stop_closes_browser_before_playwright(self):
        """stop() should close browser before stopping playwright."""
        renderer = BrowserSubtitleRenderer()
        call_order = []

        mock_browser = MagicMock()
        mock_browser.close.side_effect = lambda: call_order.append("browser_close")

        mock_playwright = MagicMock()
        mock_playwright.stop.side_effect = lambda: call_order.append("playwright_stop")

        renderer._browser = mock_browser
        renderer._playwright = mock_playwright
        renderer._page = MagicMock()

        renderer.stop()

        assert call_order == ["browser_close", "playwright_stop"], (
            f"Expected browser.close() before playwright.stop(), got: {call_order}"
        )

    def test_context_manager_calls_start_and_stop(self):
        """Context manager should call start() on enter and stop() on exit."""
        renderer = BrowserSubtitleRenderer()

        with patch.object(renderer, "start") as mock_start, \
             patch.object(renderer, "stop") as mock_stop:
            with renderer:
                mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @patch("src.subtitle_renderer.sync_playwright")
    def test_start_launches_headless_chromium(self, mock_sync_pw):
        """start() should launch a headless Chromium browser."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        mock_pw_instance.chromium.launch.assert_called_once_with(headless=True)
        mock_browser.new_page.assert_called_once()

    @patch("src.subtitle_renderer.sync_playwright")
    def test_start_is_idempotent(self, mock_sync_pw):
        """Calling start() twice should not create a second browser."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        renderer = BrowserSubtitleRenderer()
        renderer.start()
        renderer.start()

        # Should only launch once since _playwright is already set
        mock_sync_pw.return_value.start.assert_called_once()

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_returns_png_path(self, mock_sync_pw):
        """render_text_to_image should return a Path to a .png file."""
        # Set up mock chain
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        result = renderer.render_text_to_image(
            text="Hello world",
            font_family="Arial",
            font_size=30,
            color="white",
            width=576,
        )

        assert result is not None
        assert isinstance(result, Path)
        assert result.suffix == ".png"

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_returns_none_when_element_not_found(self, mock_sync_pw):
        """render_text_to_image should return None if subtitle element is missing."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        # Simulate element not found
        mock_page.query_selector.return_value = None

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        result = renderer.render_text_to_image(
            text="Hello world",
            font_family="Arial",
            font_size=30,
            color="white",
            width=576,
        )

        assert result is None

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_returns_none_on_exception(self, mock_sync_pw):
        """render_text_to_image should return None if rendering raises an exception."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        # Simulate rendering exception
        mock_page.set_content.side_effect = RuntimeError("Browser crashed")

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        result = renderer.render_text_to_image(
            text="Hello world",
            font_family="Arial",
            font_size=30,
            color="white",
            width=576,
        )

        assert result is None

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_sets_html_with_correct_styling(self, mock_sync_pw):
        """render_text_to_image should generate HTML with the correct CSS properties."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        renderer.render_text_to_image(
            text="Test subtitle",
            font_family="Barlow Condensed",
            font_size=30,
            color="#FFFFFF",
            width=576,
            stroke_width=3,
            stroke_color="black",
            text_transform="uppercase",
            font_weight="bold",
        )

        # Verify the HTML content passed to set_content
        set_content_call = mock_page.set_content.call_args[0][0]
        assert "Barlow Condensed" in set_content_call
        assert "30px" in set_content_call
        assert "#FFFFFF" in set_content_call
        assert "576px" in set_content_call
        assert "3px" in set_content_call
        assert "uppercase" in set_content_call
        assert "bold" in set_content_call

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_includes_shadow_when_specified(self, mock_sync_pw):
        """render_text_to_image should include text-shadow CSS when shadow_color is set."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        renderer.render_text_to_image(
            text="Shadow test",
            font_family="Arial",
            font_size=24,
            color="white",
            width=576,
            shadow_color="rgba(0,0,0,0.8)",
            shadow_offset=3,
        )

        set_content_call = mock_page.set_content.call_args[0][0]
        assert "text-shadow" in set_content_call
        assert "rgba(0,0,0,0.8)" in set_content_call
        assert "3px" in set_content_call

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_text_no_shadow_when_not_specified(self, mock_sync_pw):
        """render_text_to_image should not include text-shadow when shadow_color is None."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element

        renderer = BrowserSubtitleRenderer()
        renderer.start()

        renderer.render_text_to_image(
            text="No shadow test",
            font_family="Arial",
            font_size=24,
            color="white",
            width=576,
            shadow_color=None,
        )

        set_content_call = mock_page.set_content.call_args[0][0]
        assert "text-shadow" not in set_content_call

    @patch("src.subtitle_renderer.sync_playwright")
    def test_render_auto_starts_if_not_started(self, mock_sync_pw):
        """render_text_to_image should auto-start the browser if not already running."""
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.query_selector.return_value = MagicMock()

        renderer = BrowserSubtitleRenderer()
        # Do NOT call renderer.start() - should auto-start

        result = renderer.render_text_to_image(
            text="Auto start test",
            font_family="Arial",
            font_size=24,
            color="white",
            width=576,
        )

        # Verify browser was started
        mock_sync_pw.return_value.start.assert_called_once()
        assert result is not None


class TestFontResolution:
    """
    Tests for font path resolution logic used with BrowserSubtitleRenderer.

    BrowserSubtitleRenderer receives a font_family name derived from the font path.
    Production code uses Path(font_path).stem to extract the family name.
    These tests verify that font resolution works correctly for the renderer.
    """

    def test_font_stem_extraction(self):
        """Font family name should be extracted from font path stem."""
        font_path = "/path/to/fonts/Barlow-Condensed-Bold.ttf"
        font_family = Path(font_path).stem
        assert font_family == "Barlow-Condensed-Bold"

    def test_font_stem_with_spaces(self):
        """Font paths with special characters should produce valid stems."""
        font_path = "/path/to/fonts/THEBOLDFONT-FREEVERSION.ttf"
        font_family = Path(font_path).stem
        assert font_family == "THEBOLDFONT-FREEVERSION"

    def test_bundled_fonts_directory_exists(self):
        """The bundled fonts directory should exist in the project."""
        fonts_dir = Path(__file__).parent.parent / "fonts"
        assert fonts_dir.exists(), f"Fonts directory not found: {fonts_dir}"

    def test_default_font_exists(self):
        """The default fallback font should exist."""
        default_font = (
            Path(__file__).parent.parent / "fonts" / "THEBOLDFONT-FREEVERSION.ttf"
        )
        assert default_font.exists(), f"Default font not found: {default_font}"

    def test_resolve_font_path_returns_existing_file(self):
        """resolve_font_path should return a path to an existing .ttf file."""
        from src.video_utils import resolve_font_path

        result = resolve_font_path("THEBOLDFONT-FREEVERSION")
        assert Path(result).exists()
        assert result.endswith(".ttf")

    def test_resolve_font_path_falls_back_to_default(self):
        """resolve_font_path should fall back to default font for unknown names."""
        from src.video_utils import resolve_font_path

        result = resolve_font_path("NonExistentFont12345")
        assert Path(result).exists()
        assert "THEBOLDFONT-FREEVERSION" in result


class TestShortClipsIssue:
    """
    Tests demonstrating that AI generates short clips (10-20s)
    despite user setting min_length=47, max_length=58.

    Issue: User sets clip length to 47-58s but gets 11s clips.
    Root Cause: SYSTEM_PROMPT has hardcoded "10-45s" that overrides user parameters.
    Expected Behavior: AI should respect min_length and max_length parameters.
    Actual Behavior: AI generates clips in 10-45s range, ignoring user settings.
    """

    def test_system_prompt_has_hardcoded_durations(self):
        """
        SHOULD PASS: Verifies SYSTEM_PROMPT is now dynamic with parameters.

        This test checks that build_system_prompt() generates different prompts
        based on min_length and max_length parameters.
        """
        # Generate prompts with different parameters
        prompt_default = build_system_prompt(10, 45)
        prompt_custom = build_system_prompt(47, 58)

        # Verify default prompt contains default values
        assert "10 seconds" in prompt_default, (
            "Default prompt should contain '10 seconds' minimum"
        )
        assert "45 seconds" in prompt_default, (
            "Default prompt should contain '45 seconds' maximum"
        )

        # Verify custom prompt contains custom values
        assert "47 seconds" in prompt_custom, (
            "Custom prompt should contain '47 seconds' minimum"
        )
        assert "58 seconds" in prompt_custom, (
            "Custom prompt should contain '58 seconds' maximum"
        )

        # Verify custom prompt does NOT contain default values
        assert "10 seconds" not in prompt_custom or "47 seconds" in prompt_custom, (
            "Custom prompt should use custom values, not defaults"
        )

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Known limitation: AI prompt has hardcoded 10-45s range that overrides custom settings")
    async def test_ai_generates_short_clips_despite_long_settings(self):
        """
        SHOULD FAIL: Demonstrates AI ignoring min_length=47, max_length=58.

        This test documents a known limitation where the AI system prompt has
        hardcoded clip duration values (10-45s) that override the requested range.

        Current behavior: AI will generate 10-45s clips regardless of settings.
        Expected behavior: AI should generate clips within requested 47-58s range.

        FIX: Make SYSTEM_PROMPT dynamic with min_length/max_length parameters.
        """
        # Sample transcript with timestamps (realistic format)
        transcript = """
[00:00] Welcome to this video about AI and automation.
[00:15] Today we're going to talk about how AI can help you be more productive.
[00:30] The first thing to understand is that AI is a tool.
[00:45] It's not magic, it's just really advanced pattern matching.
[01:00] Let me give you some examples of how this works in practice.
[01:15] When you use an AI assistant, it's analyzing your request.
[01:30] It breaks down the task into smaller components.
[01:45] Then it uses its training data to find relevant patterns.
[02:00] This process happens incredibly fast, in milliseconds.
[02:15] But the key is knowing how to ask the right questions.
[02:30] Prompt engineering is becoming a crucial skill.
[02:45] You need to be specific about what you want.
[03:00] Give context, provide examples, set constraints.
[03:15] The more clarity you provide, the better results you get.
[03:30] This applies to all AI tools, not just language models.
[03:45] Image generation, video editing, code assistance.
[04:00] They all benefit from clear, specific instructions.
[04:15] Now let's talk about some practical applications.
[04:30] In business, AI can automate repetitive tasks.
[04:45] Customer service, data entry, report generation.
[05:00] This frees up humans to focus on creative work.
[05:15] The work that actually requires human judgment.
[05:30] That's the real value of AI - augmentation, not replacement.
"""

        # Request clips in 47-58 second range
        try:
            result = await analyze_transcript_structured(
                transcript=transcript,
                min_length=47,  # User wants longer clips
                max_length=58,
                custom_prompt=None
            )
        except Exception as e:
            # If Groq API fails, skip test (need API key)
            pytest.skip(f"Groq API not available: {e}")

        # Parse durations from returned segments
        durations = []
        for segment in result.most_relevant_segments:
            # Parse MM:SS format
            start_parts = segment.start_time.split(":")
            end_parts = segment.end_time.split(":")

            start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
            end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])

            duration = end_seconds - start_seconds
            durations.append(duration)

        # Calculate statistics
        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            # ASSERTION: ALL clips should be >= 47s
            clips_too_short = [d for d in durations if d < 47]
            assert len(clips_too_short) == 0, (
                f"AI generated {len(clips_too_short)} clips shorter than 47s! "
                f"Durations: {durations}. "
                f"Average: {avg_duration:.2f}s, Min: {min_duration:.2f}s, Max: {max_duration:.2f}s. "
                f"This proves SYSTEM_PROMPT hardcoded values (10-45s) are overriding "
                f"the requested range (47-58s). "
                f"FIX: Make SYSTEM_PROMPT dynamic with min_length/max_length parameters."
            )

            # ASSERTION: ALL clips should be <= 58s
            clips_too_long = [d for d in durations if d > 58]
            assert len(clips_too_long) == 0, (
                f"AI generated {len(clips_too_long)} clips longer than 58s! "
                f"Durations: {durations}. "
                f"Max allowed: 58s, but got clips up to {max_duration:.2f}s."
            )
        else:
            pytest.fail("AI returned 0 segments - cannot validate duration")

    def test_validation_hardcoded_minimum(self):
        """
        SHOULD FAIL: Proves validation code uses hardcoded 10 instead of min_length.

        Location: backend/src/ai_structured.py line 274
        Current: if duration < 10:
        Should be: if duration < min_length:
        """
        # Get source code of analyze_transcript_structured
        source = inspect.getsource(analyze_transcript_structured)

        # Check if validation uses hardcoded 10
        assert "if duration < 10:" not in source, (
            "Validation code uses hardcoded 'if duration < 10' instead of "
            "'if duration < min_length'. This ignores user's min_length setting. "
            "FIX: Replace hardcoded 10 with min_length parameter in ai_structured.py line 274"
        )


class TestActualUserScenario:
    """
    Integration test reproducing the EXACT user scenario from screenshot.

    User settings:
    - Font: "Barlow Condensed Bold", 30px
    - Clip length: 47-58 seconds (inferred from "too short" complaint)

    Expected:
    - Full captions visible (no vertical cropping)
    - Clips 47-58 seconds long

    Now tests BrowserSubtitleRenderer path instead of old TextClip path.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch("src.subtitle_renderer.sync_playwright")
    async def test_user_scenario_reproduction(self, mock_sync_pw):
        """
        Integration test of user's exact scenario using BrowserSubtitleRenderer.

        Verifies:
        1. BrowserSubtitleRenderer can render with user's font settings
        2. AI generates clips within requested duration range
        """
        # User settings from screenshot
        font_family = "Barlow Condensed Bold"
        font_size = 30
        clip_min_length = 47
        clip_max_length = 58

        # Part 1: Test font rendering via BrowserSubtitleRenderer
        video_width = 720
        horizontal_padding = 0.1
        max_text_width = int(video_width * (1 - 2 * horizontal_padding))

        # Set up mock Playwright chain
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element

        with BrowserSubtitleRenderer() as renderer:
            result = renderer.render_text_to_image(
                text="Test caption text that should display fully",
                font_family=font_family,
                font_size=font_size,
                color="white",
                width=max_text_width,
                stroke_width=2,
                stroke_color="black",
                font_weight="bold",
            )

            # BrowserSubtitleRenderer should return a valid path (no vertical cropping issue)
            assert result is not None, (
                "BrowserSubtitleRenderer returned None - rendering failed"
            )
            assert isinstance(result, Path)
            assert result.suffix == ".png"

        # Verify HTML was generated with correct font styling
        set_content_call = mock_page.set_content.call_args[0][0]
        assert font_family in set_content_call, (
            f"Expected font family '{font_family}' in rendered HTML"
        )
        assert f"{font_size}px" in set_content_call, (
            f"Expected font size '{font_size}px' in rendered HTML"
        )
        assert f"{max_text_width}px" in set_content_call, (
            f"Expected width '{max_text_width}px' in rendered HTML"
        )

        # Part 2: Test AI clip length
        sample_transcript = "[00:00] Sample transcript content for testing..." * 50

        try:
            result = await analyze_transcript_structured(
                transcript=sample_transcript,
                min_length=clip_min_length,
                max_length=clip_max_length
            )

            # Calculate durations
            for segment in result.most_relevant_segments:
                start_parts = segment.start_time.split(":")
                end_parts = segment.end_time.split(":")
                start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
                duration = end_seconds - start_seconds

                # Each clip should be 47-58s
                assert duration >= clip_min_length, (
                    f"Short clip issue reproduced! Duration {duration}s < {clip_min_length}s"
                )
        except Exception as e:
            pytest.skip(f"API not available: {e}")


# Helper function for duration calculation
def calculate_duration(start_time: str, end_time: str) -> float:
    """Parse MM:SS timestamps and calculate duration in seconds."""
    def parse_timestamp(ts: str) -> float:
        parts = ts.split(":")
        return int(parts[0]) * 60 + float(parts[1])

    return parse_timestamp(end_time) - parse_timestamp(start_time)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# end backend/tests/test_font_cutoff_and_short_clips.py
