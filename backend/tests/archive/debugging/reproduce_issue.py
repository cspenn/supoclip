
import logging
import sys
from unittest.mock import MagicMock

# Mock dependencies to avoid needing the full environment
sys.modules["moviepy.video.fx.Margin"] = MagicMock()
sys.modules["moviepy.video.VideoClip"] = MagicMock()
sys.modules["moviepy.editor"] = MagicMock()

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Copying the relevant classes from video_utils.py (simplified for testing)
class TranscriptLineBreaker:
    MAX_WORDS_PER_LINE = 50
    BREAK_PUNCTUATION = {".", "!", "?"}

    @staticmethod
    def should_break_line(word_text: str, word_count: int) -> bool:
        # Punctuation check (Testing if the fix works)
        clean_text = word_text.strip()
        if clean_text and any(
            clean_text.endswith(punct)
            for punct in TranscriptLineBreaker.BREAK_PUNCTUATION
        ):
            return True
        
        # Commas
        if clean_text and clean_text.endswith(",") and word_count > 15:
            return True

        # Hard limit
        if word_count >= TranscriptLineBreaker.MAX_WORDS_PER_LINE:
            return True

        return False

def test_line_breaker():
    print("Testing TranscriptLineBreaker...")
    # Case 1: "word." -> Should break
    assert TranscriptLineBreaker.should_break_line("word.", 5) == True, "Failed to break on clean period"
    
    # Case 2: "word. " -> Should break (The previously failing case)
    assert TranscriptLineBreaker.should_break_line("word. ", 5) == True, "Failed to break on period with space"
    
    print("TranscriptLineBreaker tests passed.")

if __name__ == "__main__":
    try:
        test_line_breaker()
    except AssertionError as e:
        print(f"ASSERTION FAILED: {e}")
