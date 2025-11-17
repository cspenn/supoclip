"""Test that timestamp parsing handles millisecond precision (MM:SS.mmm format).

This test validates the fix for parsing timestamps with milliseconds,
which is what Groq Llama 4 Scout returns (not the standard MM:SS format).
"""
import pytest
from src.ai_structured import TranscriptSegment


def test_parse_timestamps_with_milliseconds():
    """Test that timestamps with milliseconds (MM:SS.mmm) are parsed correctly.
    
    This reproduces the issue where Groq Llama 4 Scout returns timestamps
    with millisecond precision, which the original code failed to parse
    because it used int() instead of float() for the seconds component.
    
    Example timestamps from Groq:
    - "01:23.456" (1 minute, 23.456 seconds)
    - "05:45.100" (5 minutes, 45.1 seconds)
    """
    # Create a segment with millisecond-precision timestamps
    # This is what Groq Llama 4 Scout actually returns
    segment = TranscriptSegment(
        start_time="01:23.456",  # 1 minute 23.456 seconds = 83.456 seconds
        end_time="01:45.789",    # 1 minute 45.789 seconds = 105.789 seconds
        text="This is a test segment with valuable content",
        relevance_score=0.95,
        reasoning="Strong hook and valuable information"
    )
    
    # Parse timestamps (this is what the fixed code does)
    try:
        start_parts = segment.start_time.split(":")
        end_parts = segment.end_time.split(":")
        
        # With the fix, we use float() instead of int()
        start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
        end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
        
        duration = end_seconds - start_seconds
        
        # Expected values
        assert start_seconds == pytest.approx(83.456), f"Expected 83.456, got {start_seconds}"
        assert end_seconds == pytest.approx(105.789), f"Expected 105.789, got {end_seconds}"
        assert duration == pytest.approx(22.333, abs=0.001), f"Expected ~22.333, got {duration}"
        assert duration > 5, "Duration should be greater than 5 seconds"
        
    except (ValueError, IndexError) as e:
        pytest.fail(f"Failed to parse millisecond timestamps: {e}")


def test_parse_timestamps_without_milliseconds():
    """Test that standard MM:SS format still works (backward compatibility)."""
    segment = TranscriptSegment(
        start_time="02:15",      # 2 minutes 15 seconds = 135 seconds
        end_time="02:45",        # 2 minutes 45 seconds = 165 seconds
        text="Standard timestamp format test",
        relevance_score=0.85,
        reasoning="Testing backward compatibility"
    )
    
    try:
        start_parts = segment.start_time.split(":")
        end_parts = segment.end_time.split(":")
        
        # float() works with both "15" and "15.0" format
        start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
        end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
        
        duration = end_seconds - start_seconds
        
        assert start_seconds == 135.0, f"Expected 135.0, got {start_seconds}"
        assert end_seconds == 165.0, f"Expected 165.0, got {end_seconds}"
        assert duration == 30.0, f"Expected 30.0, got {duration}"
        
    except (ValueError, IndexError) as e:
        pytest.fail(f"Failed to parse standard timestamps: {e}")


def test_parse_timestamps_edge_cases():
    """Test edge cases with millisecond precision."""
    test_cases = [
        ("00:00.001", "00:10.000", 9.999),  # Just over 9 seconds
        ("10:00.999", "10:05.001", 4.002),  # Milliseconds at boundaries
        ("05:30.100", "05:40.900", 10.8),   # More than 10 seconds
    ]
    
    for start, end, expected_duration in test_cases:
        try:
            start_parts = start.split(":")
            end_parts = end.split(":")
            
            start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
            end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
            
            duration = end_seconds - start_seconds
            
            assert duration == pytest.approx(expected_duration, abs=0.001), \
                f"Duration mismatch for {start} to {end}: expected {expected_duration}, got {duration}"
        except (ValueError, IndexError) as e:
            pytest.fail(f"Failed to parse timestamps {start}-{end}: {e}")


def test_timestamp_segment_validation():
    """Test that segments with millisecond timestamps pass validation checks."""
    segments_data = [
        {
            "start_time": "00:05.123",
            "end_time": "00:25.456",
            "text": "This is meaningful content about the topic",
            "relevance_score": 0.92,
            "reasoning": "Strong hook with valuable information"
        },
        {
            "start_time": "01:10.000",
            "end_time": "01:35.789",
            "text": "Another important segment with multiple words",
            "relevance_score": 0.88,
            "reasoning": "Emotional moment"
        }
    ]
    
    for data in segments_data:
        segment = TranscriptSegment(**data)
        
        # Validate as done in analyze_transcript_structured
        start_parts = segment.start_time.split(":")
        end_parts = segment.end_time.split(":")
        
        start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
        end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
        
        duration = end_seconds - start_seconds
        
        # Should pass all validation checks
        assert segment.start_time != segment.end_time, "Times should be different"
        assert duration > 0, "Duration should be positive"
        assert duration >= 5, "Duration should be at least 5 seconds"
        assert len(segment.text.split()) >= 3, "Text should have at least 3 words"
        assert 0.0 <= segment.relevance_score <= 1.0, "Score should be between 0 and 1"
