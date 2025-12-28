"""Integration test for timestamp parsing through the entire video processing pipeline.

This test simulates the complete flow:
1. AI analysis (ai_structured.py) returns segments with millisecond timestamps
2. Segments are validated with millisecond timestamp precision
3. Timestamp parser (video_utils.py) converts to seconds
4. Clip duration validation succeeds
5. All clips are marked as valid for generation

This demonstrates that the fix is complete and functional across the entire pipeline.
"""
import pytest
from src.ai_structured import TranscriptSegment
from src.video_utils import parse_timestamp_to_seconds


class TestTimestampPipelineIntegration:
    """Test the full pipeline from AI analysis to clip validation."""

    def test_ai_segments_to_video_parser_flow(self):
        """Test complete flow: AI analysis -> validation -> video parser."""
        # Step 1: Simulate AI analysis with millisecond timestamps (from Groq Llama 4 Scout)
        # Note: Groq returns MM:SS.mmm format, not HH:MM:SS.mmm
        segments_from_ai = [
            TranscriptSegment(
                start_time="03:08.120",
                end_time="03:28.450",
                text="First engaging segment with strong hooks and valuable content",
                relevance_score=0.95,
                reasoning="Strong opening hook with immediate value"
            ),
            TranscriptSegment(
                start_time="05:15.300",
                end_time="05:40.750",
                text="Second important segment showing interesting technique step by step",
                relevance_score=0.92,
                reasoning="Educational content with practical value"
            ),
            TranscriptSegment(
                start_time="12:30.100",
                end_time="12:55.890",
                text="Third powerful segment with emotional connection and memorable takeaway",
                relevance_score=0.88,
                reasoning="Emotional impact with memorable conclusion"
            ),
        ]

        # Step 2: Validate segments (as done in analyze_transcript_structured)
        validated_segments = []
        for segment in segments_from_ai:
            # Validate text content
            if not segment.text.strip() or len(segment.text.split()) < 3:
                continue

            # Validate timestamps - this is where millisecond parsing happens
            try:
                start_parts = segment.start_time.split(":")
                end_parts = segment.end_time.split(":")

                # This is the validation logic from ai_structured.py (lines 213-214)
                start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])

                duration = end_seconds - start_seconds

                if duration <= 0:
                    continue

                if duration < 5:
                    continue

                validated_segments.append({
                    "segment": segment,
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "duration": duration
                })

            except (ValueError, IndexError):
                continue

        # Should have 3 valid segments
        assert len(validated_segments) == 3, f"Expected 3 validated segments, got {len(validated_segments)}"

        # Step 3: Parse timestamps through video_utils parser
        clips_info = []
        for i, validated in enumerate(validated_segments):
            segment = validated["segment"]

            # This is what happens in create_clips_from_segments
            start_seconds_from_parser = parse_timestamp_to_seconds(segment.start_time)
            end_seconds_from_parser = parse_timestamp_to_seconds(segment.end_time)

            # Verify parser produces same results as AI validation
            assert start_seconds_from_parser == pytest.approx(validated["start_seconds"], abs=0.001), \
                f"Clip {i+1}: Parser start time mismatch"
            assert end_seconds_from_parser == pytest.approx(validated["end_seconds"], abs=0.001), \
                f"Clip {i+1}: Parser end time mismatch"

            duration = end_seconds_from_parser - start_seconds_from_parser

            # Validate clip can be created (duration > 5 seconds for valid clip)
            assert duration > 5.0, f"Clip {i+1}: Duration {duration}s is invalid"

            clips_info.append({
                "clip_id": i + 1,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "start_seconds": start_seconds_from_parser,
                "end_seconds": end_seconds_from_parser,
                "duration": duration,
                "text": segment.text[:50] + "...",
                "relevance_score": segment.relevance_score,
            })

        # Step 4: Verify all clips are ready for generation
        assert len(clips_info) == 3, f"Expected 3 clips ready for generation, got {len(clips_info)}"

        # Verify each clip has valid metadata
        for i, clip in enumerate(clips_info):
            assert clip["duration"] > 5.0, f"Clip {clip['clip_id']}: Invalid duration {clip['duration']}s"
            assert clip["start_seconds"] >= 0, f"Clip {clip['clip_id']}: Invalid start time"
            assert clip["end_seconds"] > clip["start_seconds"], f"Clip {clip['clip_id']}: Invalid time range"
            assert clip["relevance_score"] > 0.5, f"Clip {clip['clip_id']}: Low relevance score"

        # Print clip details for debugging
        for clip in clips_info:
            print(f"\nClip {clip['clip_id']}: {clip['start_time']} -> {clip['end_time']}")
            print(f"  Parsed: {clip['start_seconds']:.3f}s -> {clip['end_seconds']:.3f}s")
            print(f"  Duration: {clip['duration']:.3f}s")

    def test_3_clips_generation_simulation(self):
        """Simulate generating 3 clips from AI segments with millisecond timestamps."""
        # Represent segments as they come from Groq Llama 4 Scout
        ai_segments = [
            {"start": "00:10.500", "end": "00:30.750", "text": "First clip content"},
            {"start": "00:45.000", "end": "01:05.200", "text": "Second clip content"},
            {"start": "02:00.100", "end": "02:25.800", "text": "Third clip content"},
        ]

        successful_clips = []

        for i, segment in enumerate(ai_segments):
            # Parse timestamps
            start = parse_timestamp_to_seconds(segment["start"])
            end = parse_timestamp_to_seconds(segment["end"])
            duration = end - start

            # Clip generation criteria
            if duration > 5:
                successful_clips.append({
                    "clip_num": i + 1,
                    "start_time": segment["start"],
                    "end_time": segment["end"],
                    "parsed_start": start,
                    "parsed_end": end,
                    "duration": duration,
                    "status": "GENERATED"
                })

        # Result: 3/3 clips successfully generated
        assert len(successful_clips) == 3, f"Expected 3/3 clips, got {len(successful_clips)}/3"

        # Verify clip details
        expected_durations = [20.25, 20.2, 25.7]
        for i, clip in enumerate(successful_clips):
            assert clip["duration"] == pytest.approx(expected_durations[i], abs=0.01), \
                f"Clip {clip['clip_num']}: Unexpected duration"
            assert clip["status"] == "GENERATED", f"Clip {clip['clip_num']}: Not generated"

    def test_millisecond_precision_preserved_through_pipeline(self):
        """Verify millisecond precision is preserved from AI to video parser."""
        # Test cases: (timestamp, expected_seconds)
        test_cases = [
            ("00:03:08.120", 188.120),
            ("00:05:15.300", 315.300),
            ("00:12:30.100", 750.100),
            ("01:23:45.678", 5025.678),
            ("00:00:00.001", 0.001),
        ]

        for timestamp, expected in test_cases:
            # Parse through video_utils parser
            parsed = parse_timestamp_to_seconds(timestamp)

            # Verify millisecond precision is preserved
            assert parsed == pytest.approx(expected, abs=0.001), \
                f"Timestamp {timestamp}: Expected {expected}, got {parsed}"

    def test_backward_compatibility_with_legacy_timestamps(self):
        """Ensure old segments with integer-only timestamps still work."""
        # Old segments without millisecond precision
        legacy_segments = [
            {"start": "00:05", "end": "00:25", "duration": 20.0},
            {"start": "01:00", "end": "01:30", "duration": 30.0},
            {"start": "02:15", "end": "02:50", "duration": 35.0},
        ]

        for segment in legacy_segments:
            start = parse_timestamp_to_seconds(segment["start"])
            end = parse_timestamp_to_seconds(segment["end"])
            duration = end - start

            assert duration == pytest.approx(segment["duration"]), \
                f"Duration mismatch for {segment['start']}-{segment['end']}"

    def test_mixed_timestamp_formats_in_same_batch(self):
        """Test handling both new and legacy timestamp formats in same request."""
        # Simulated batch: some clips with milliseconds, some without
        mixed_segments = [
            ("00:05:30.123", "00:05:45.678", True),   # With milliseconds
            ("00:10:00", "00:10:20", False),            # Without milliseconds
            ("01:15:30.500", "01:15:55.800", True),   # With milliseconds
            ("02:00", "02:30", False),                  # Without milliseconds
        ]

        parsed_clips = []
        for start, end, has_ms in mixed_segments:
            start_sec = parse_timestamp_to_seconds(start)
            end_sec = parse_timestamp_to_seconds(end)
            duration = end_sec - start_sec

            if duration > 0:
                parsed_clips.append({
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "has_milliseconds": has_ms
                })

        # All clips should parse successfully
        assert len(parsed_clips) == 4, f"Expected 4 clips parsed, got {len(parsed_clips)}"

        # Verify both formats work
        ms_clips = [c for c in parsed_clips if c["has_milliseconds"]]
        no_ms_clips = [c for c in parsed_clips if not c["has_milliseconds"]]

        assert len(ms_clips) == 2, "Should have 2 clips with milliseconds"
        assert len(no_ms_clips) == 2, "Should have 2 clips without milliseconds"

    def test_segment_duration_range_validation(self):
        """Test that parsed timestamps enable proper duration validation."""
        # From Groq Llama 4 Scout output
        segments = [
            {
                "start": "00:05:10.100",
                "end": "00:05:45.950",
                "expected_duration": 35.85,
                "valid": True
            },
            {
                "start": "00:20:00.500",
                "end": "00:20:02.000",
                "expected_duration": 1.5,
                "valid": False  # Too short (< 5 seconds)
            },
            {
                "start": "01:30:15.200",
                "end": "01:30:45.800",
                "expected_duration": 30.6,
                "valid": True
            },
        ]

        valid_count = 0
        for segment in segments:
            start = parse_timestamp_to_seconds(segment["start"])
            end = parse_timestamp_to_seconds(segment["end"])
            duration = end - start

            # Verify duration calculation
            assert duration == pytest.approx(segment["expected_duration"], abs=0.01), \
                f"Duration mismatch for {segment['start']}-{segment['end']}"

            # Check if valid for clip generation (minimum 5 seconds)
            is_valid = duration > 5
            assert is_valid == segment["valid"], \
                f"Validity check failed for segment {segment['start']}-{segment['end']}"

            if is_valid:
                valid_count += 1

        # Should have 2 valid clips out of 3
        assert valid_count == 2, f"Expected 2 valid clips, got {valid_count}"


class TestEndToEndClipGeneration:
    """Test complete end-to-end clip generation flow."""

    def test_generate_3_clips_from_groq_timestamps(self):
        """Simulate complete pipeline: Groq output -> Parse -> Generate 3 clips."""
        # Simulated Groq Llama 4 Scout response with millisecond timestamps (MM:SS.mmm format)
        groq_analysis = {
            "most_relevant_segments": [
                {
                    "start_time": "03:08.120",
                    "end_time": "03:28.450",
                    "text": "First segment with strong hooks and compelling information",
                    "relevance_score": 0.95,
                    "reasoning": "Excellent opening hook"
                },
                {
                    "start_time": "05:15.300",
                    "end_time": "05:40.750",
                    "text": "Second segment with practical tips and actionable insights",
                    "relevance_score": 0.92,
                    "reasoning": "High value educational content"
                },
                {
                    "start_time": "12:30.100",
                    "end_time": "12:55.890",
                    "text": "Third segment with emotional impact and memorable takeaway",
                    "relevance_score": 0.88,
                    "reasoning": "Strong emotional moment"
                },
            ]
        }

        # Process segments through pipeline
        generated_clips = []

        for segment_data in groq_analysis["most_relevant_segments"]:
            # Step 1: Validate segment (as in ai_structured.py)
            if not segment_data["text"].strip() or len(segment_data["text"].split()) < 3:
                continue

            # Step 2: Parse timestamps (as in video_utils.py)
            try:
                start = parse_timestamp_to_seconds(segment_data["start_time"])
                end = parse_timestamp_to_seconds(segment_data["end_time"])
                duration = end - start

                # Step 3: Validate duration
                if duration <= 0 or duration < 5:
                    continue

                # Step 4: Mark as ready for generation
                generated_clips.append({
                    "clip_id": len(generated_clips) + 1,
                    "start_time": segment_data["start_time"],
                    "end_time": segment_data["end_time"],
                    "start_seconds": start,
                    "end_seconds": end,
                    "duration": duration,
                    "text": segment_data["text"],
                    "relevance_score": segment_data["relevance_score"],
                    "status": "READY_FOR_GENERATION"
                })

            except (ValueError, IndexError):
                continue

        # Verify: 3/3 clips generated
        assert len(generated_clips) == 3, f"Expected 3/3 clips, got {len(generated_clips)}/3"

        # Verify clip details (MM:SS.mmm format)
        # 03:08.120 = 3*60 + 8.120 = 188.120
        # 03:28.450 = 3*60 + 28.450 = 208.450
        # 05:15.300 = 5*60 + 15.300 = 315.300
        # 05:40.750 = 5*60 + 40.750 = 340.750
        # 12:30.100 = 12*60 + 30.100 = 750.100
        # 12:55.890 = 12*60 + 55.890 = 775.890
        expected_clips = [
            {
                "start": 188.120,
                "end": 208.450,
                "duration": 20.330,
            },
            {
                "start": 315.300,
                "end": 340.750,
                "duration": 25.450,
            },
            {
                "start": 750.100,
                "end": 775.890,
                "duration": 25.790,
            },
        ]

        for i, (clip, expected) in enumerate(zip(generated_clips, expected_clips)):
            assert clip["start_seconds"] == pytest.approx(expected["start"], abs=0.001), \
                f"Clip {i+1}: Start time mismatch"
            assert clip["end_seconds"] == pytest.approx(expected["end"], abs=0.001), \
                f"Clip {i+1}: End time mismatch"
            assert clip["duration"] == pytest.approx(expected["duration"], abs=0.001), \
                f"Clip {i+1}: Duration mismatch"
            assert clip["status"] == "READY_FOR_GENERATION", \
                f"Clip {i+1}: Not ready for generation"

        # All clips have valid metadata
        for clip in generated_clips:
            assert clip["clip_id"] > 0, "Clip ID must be positive"
            assert clip["duration"] > 5.0, "Duration must be > 5 seconds"
            assert 0.0 <= clip["relevance_score"] <= 1.0, "Relevance score must be 0-1"
            assert clip["text"], "Text must not be empty"
