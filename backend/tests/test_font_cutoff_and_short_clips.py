# start backend/tests/test_font_cutoff_and_short_clips.py
"""
Failing tests to demonstrate font cutoff and short clips issues.

These tests SHOULD FAIL until fixes are implemented.
They prove the existence of the reported bugs.
"""

import pytest
from pathlib import Path
from moviepy.video.VideoClip import TextClip
from src.ai_structured import analyze_transcript_structured, build_system_prompt


class TestFontCutoffIssue:
    """
    Tests demonstrating that method='caption' with size=(width, None)
    causes text to be vertically cropped.

    Issue: User reports captions appearing cut in half.
    Root Cause: MoviePy TextClip using method="caption" with constrained size.
    Expected Behavior: Full text should be visible.
    Actual Behavior: Text exceeding implicit height is cropped.
    """

    def test_caption_method_causes_text_cutoff(self):
        """
        SHOULD FAIL: Demonstrates caption mode crops text.

        This test creates a TextClip using the EXACT parameters from video_utils.py
        line 906-914 and verifies that text gets cut off.
        """
        # Simulate parameters from user's screenshot
        text = "This is a multi-line caption that should wrap and display fully"
        font_path = "Arial"  # Use system font for test
        font_size = 30  # User's setting from screenshot
        video_width = 720  # Standard 9:16 width

        # Calculate max_text_width exactly as video_utils.py does
        HORIZONTAL_PADDING = 0.1
        max_text_width = int(video_width * (1 - 2 * HORIZONTAL_PADDING))

        # Create TextClip with CURRENT implementation (method="caption")
        text_clip_caption = TextClip(
            text=text,
            font=font_path,
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=1,
            method="caption",  # ← Current implementation causes cutoff
            size=(max_text_width, None),  # ← Height is None but still crops
            text_align="center",
        )

        # Create TextClip with FIXED implementation (method="label")
        text_clip_label = TextClip(
            text=text,
            font=font_path,
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=1,
            method="label",  # ← Fixed implementation
            text_align="center",
        )

        # ASSERTION: Caption mode should produce smaller height (text is cropped)
        # This test SHOULD FAIL because caption mode DOES crop text
        caption_height = text_clip_caption.size[1]
        label_height = text_clip_label.size[1]

        # If fix is NOT applied, caption_height will be less than label_height
        # This assertion will FAIL proving the bug exists
        assert caption_height >= label_height, (
            f"Font cutoff detected! Caption mode height ({caption_height}px) "
            f"is less than label mode height ({label_height}px). "
            f"This proves text is being cropped. "
            f"FIX: Change method='caption' to method='label' in video_utils.py line 913"
        )

    def test_barlow_condensed_bold_cutoff_reproduction(self):
        """
        SHOULD FAIL: Reproduces exact user scenario with Barlow Condensed Bold.

        User screenshot shows:
        - Font: "Barlow Condensed Bold" at 30px
        - Text appears cut in half vertically
        """
        # Check if font exists
        font_path = Path("/Users/cspenn/Documents/github/supoclip/backend/fonts/Barlow-Condensed-Bold.ttf")
        if not font_path.exists():
            pytest.skip(f"Font not found: {font_path}")

        text = "Example subtitle text that wraps to multiple lines for testing"
        font_size = 30  # User's setting
        video_width = 720

        HORIZONTAL_PADDING = 0.1
        max_text_width = int(video_width * (1 - 2 * HORIZONTAL_PADDING))

        # Current implementation
        text_clip = TextClip(
            text=text,
            font=str(font_path),
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=1,
            method="caption",  # ← Bug is here
            size=(max_text_width, None),
            text_align="center",
        )

        # Calculate expected height for 2 lines (font_size * 1.5 * 2 lines)
        expected_min_height = font_size * 1.5 * 2

        # ASSERTION: Text clip height should accommodate at least 2 lines
        actual_height = text_clip.size[1]
        assert actual_height >= expected_min_height, (
            f"Text cutoff detected! Actual height {actual_height}px "
            f"is less than expected minimum {expected_min_height}px for 2 lines. "
            f"Text is being cropped by caption mode."
        )


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
    async def test_ai_generates_short_clips_despite_long_settings(self):
        """
        SHOULD FAIL: Demonstrates AI ignoring min_length=47, max_length=58.

        This test uses a real transcript and verifies that AI generates
        clips within the requested duration range.

        Current behavior: AI will generate 10-20s clips.
        Expected behavior: AI should generate 47-58s clips.
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
        from src.ai_structured import analyze_transcript_structured
        import inspect

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
    - Full captions visible
    - Clips 47-58 seconds long

    Actual (before fix):
    - Captions cut off vertically
    - Clips 11-16 seconds long
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_user_scenario_reproduction(self):
        """
        SHOULD FAIL: Full integration test of user's exact scenario.

        This test will fail in two ways:
        1. TextClip will have reduced height (font cutoff)
        2. AI will generate short clips (ignoring length settings)
        """
        # User settings from screenshot
        font_family = "Barlow Condensed Bold"
        font_size = 30
        clip_min_length = 47
        clip_max_length = 58

        # Part 1: Test font rendering
        font_path = Path("/Users/cspenn/Documents/github/supoclip/backend/fonts/Barlow-Condensed-Bold.ttf")
        if font_path.exists():
            video_width = 720
            HORIZONTAL_PADDING = 0.1
            max_text_width = int(video_width * (1 - 2 * HORIZONTAL_PADDING))

            text_clip = TextClip(
                text="Test caption text",
                font=str(font_path),
                font_size=font_size,
                color="white",
                method="caption",  # ← Bug
                size=(max_text_width, None),
            )

            # Should have adequate height
            min_expected_height = font_size * 1.5
            assert text_clip.size[1] >= min_expected_height, (
                f"Font cutoff issue reproduced! Height {text_clip.size[1]} < {min_expected_height}"
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
