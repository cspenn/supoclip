"""
Utility functions for video-related operations.
Optimized for MoviePy v2, AssemblyAI integration, and high-quality output.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import os
import logging
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import json

import cv2
from moviepy import VideoFileClip, CompositeVideoClip, TextClip, ColorClip

import assemblyai as aai
import srt
from datetime import timedelta

from .config import Config

logger = logging.getLogger(__name__)
config = Config()

class VideoProcessor:
    """Handles video processing operations with optimized settings."""

    def __init__(self):
        self.font_path = str(Path(__file__).parent.parent / "fonts" / "THEBOLDFONT-FREEVERSION.ttf")

    def get_optimal_encoding_settings(self, target_quality: str = "high") -> Dict[str, Any]:
        """Get optimal encoding settings for different quality levels."""
        settings = {
            "high": {
                "codec": "libx264",
                "audio_codec": "aac",
                "bitrate": "8000k",
                "audio_bitrate": "256k",
                "preset": "medium",
                "ffmpeg_params": ["-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "main", "-level", "4.1"]
            },
            "medium": {
                "codec": "libx264",
                "audio_codec": "aac",
                "bitrate": "4000k",
                "audio_bitrate": "192k",
                "preset": "fast",
                "ffmpeg_params": ["-crf", "23", "-pix_fmt", "yuv420p"]
            }
        }
        return settings.get(target_quality, settings["high"])

def get_video_transcript(video_path: Path) -> str:
    """Get transcript using AssemblyAI with word-level timing for precise subtitles."""
    logger.info(f"Getting transcript for: {video_path}")

    # Configure AssemblyAI
    aai.settings.api_key = config.assembly_ai_api_key
    transcriber = aai.Transcriber()

    # Request word-level timestamps for precise subtitle sync
    config_obj = aai.TranscriptionConfig(
        speaker_labels=False,
        punctuate=True,
        format_text=True,
        speech_model=aai.SpeechModel.best
    )

    try:
        logger.info("Starting AssemblyAI transcription")
        transcript = transcriber.transcribe(str(video_path), config=config_obj)

        if transcript.status == aai.TranscriptStatus.error:
            logger.error(f"AssemblyAI transcription failed: {transcript.error}")
            raise Exception(f"Transcription failed: {transcript.error}")

        # Format transcript with timestamps for AI analysis
        formatted_lines = []
        if transcript.words:
            logger.info(f"Processing {len(transcript.words)} words with precise timing")

            # Group words into logical segments for readability
            current_segment = []
            current_start = None
            segment_word_count = 0
            max_words_per_segment = 8  # ~3-4 seconds of speech

            for word in transcript.words:
                if current_start is None:
                    current_start = word.start

                current_segment.append(word.text)
                segment_word_count += 1

                # End segment at natural breaks or word limit
                if (segment_word_count >= max_words_per_segment or
                    word.text.endswith('.') or word.text.endswith('!') or word.text.endswith('?')):

                    if current_segment:
                        start_time = format_ms_to_timestamp(current_start)
                        end_time = format_ms_to_timestamp(word.end)
                        text = ' '.join(current_segment)
                        formatted_lines.append(f"[{start_time} - {end_time}] {text}")

                    current_segment = []
                    current_start = None
                    segment_word_count = 0

            # Handle any remaining words
            if current_segment and current_start is not None:
                start_time = format_ms_to_timestamp(current_start)
                end_time = format_ms_to_timestamp(transcript.words[-1].end)
                text = ' '.join(current_segment)
                formatted_lines.append(f"[{start_time} - {end_time}] {text}")

        # Cache the raw transcript for subtitle generation
        cache_transcript_data(video_path, transcript)

        result = '\n'.join(formatted_lines)
        logger.info(f"Transcript formatted: {len(formatted_lines)} segments, {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        raise

def cache_transcript_data(video_path: Path, transcript) -> None:
    """Cache AssemblyAI transcript data for subtitle generation."""
    cache_path = video_path.with_suffix('.transcript_cache.json')

    # Store word-level data
    words_data = []
    if transcript.words:
        for word in transcript.words:
            words_data.append({
                'text': word.text,
                'start': word.start,
                'end': word.end,
                'confidence': word.confidence if hasattr(word, 'confidence') else 1.0
            })

    cache_data = {
        'words': words_data,
        'text': transcript.text
    }

    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

    logger.info(f"Cached {len(words_data)} words to {cache_path}")

def load_cached_transcript_data(video_path: Path) -> Optional[Dict]:
    """Load cached AssemblyAI transcript data."""
    cache_path = video_path.with_suffix('.transcript_cache.json')

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load transcript cache: {e}")
        return None

def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds to MM:SS format."""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def round_to_even(value: int) -> int:
    """Round integer to nearest even number for H.264 compatibility."""
    return value - (value % 2)

def detect_optimal_crop_region(video_clip: VideoFileClip, start_time: float, end_time: float, target_ratio: float = 9/16) -> Tuple[int, int, int, int]:
    """Detect optimal crop region using face detection."""
    try:
        original_width, original_height = video_clip.size

        # Calculate target dimensions and ensure they're even
        if original_width / original_height > target_ratio:
            new_width = round_to_even(int(original_height * target_ratio))
            new_height = round_to_even(original_height)
        else:
            new_width = round_to_even(original_width)
            new_height = round_to_even(int(original_width / target_ratio))

        # Try face detection for better cropping
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # Sample a few frames
        duration = end_time - start_time
        sample_times = [start_time + duration * 0.2, start_time + duration * 0.5, start_time + duration * 0.8]
        sample_times = [t for t in sample_times if t < end_time]

        face_centers = []

        for sample_time in sample_times:
            try:
                frame = video_clip.get_frame(sample_time)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

                for (x, y, w, h) in faces:
                    face_center_x = x + w // 2
                    face_center_y = y + h // 2
                    face_area = w * h
                    face_centers.append((face_center_x, face_center_y, face_area))

            except Exception:
                continue

        # Calculate crop position
        if face_centers:
            # Use weighted average of face centers
            total_weight = sum(area for _, _, area in face_centers)
            if total_weight > 0:
                weighted_x = sum(x * area for x, y, area in face_centers) / total_weight
                weighted_y = sum(y * area for x, y, area in face_centers) / total_weight

                x_offset = max(0, min(int(weighted_x - new_width // 2), original_width - new_width))
                y_offset = max(0, min(int(weighted_y - new_height // 2), original_height - new_height))

                logger.info(f"Face-centered crop: {len(face_centers)} faces detected")
            else:
                # Center crop
                x_offset = (original_width - new_width) // 2 if original_width > new_width else 0
                y_offset = (original_height - new_height) // 2 if original_height > new_height else 0
        else:
            # Center crop
            x_offset = (original_width - new_width) // 2 if original_width > new_width else 0
            y_offset = (original_height - new_height) // 2 if original_height > new_height else 0
            logger.info("Using center crop (no faces detected)")

        # Ensure offsets are even too
        x_offset = round_to_even(x_offset)
        y_offset = round_to_even(y_offset)

        logger.info(f"Crop dimensions: {new_width}x{new_height} at offset ({x_offset}, {y_offset})")
        return (x_offset, y_offset, new_width, new_height)

    except Exception as e:
        logger.error(f"Error in crop detection: {e}")
        # Fallback to center crop
        original_width, original_height = video_clip.size
        if original_width / original_height > target_ratio:
            new_width = round_to_even(int(original_height * target_ratio))
            new_height = round_to_even(original_height)
        else:
            new_width = round_to_even(original_width)
            new_height = round_to_even(int(original_width / target_ratio))

        x_offset = round_to_even((original_width - new_width) // 2) if original_width > new_width else 0
        y_offset = round_to_even((original_height - new_height) // 2) if original_height > new_height else 0

        return (x_offset, y_offset, new_width, new_height)

def parse_timestamp_to_seconds(timestamp_str: str) -> float:
    """Parse timestamp string to seconds."""
    try:
        timestamp_str = timestamp_str.strip()
        logger.info(f"Parsing timestamp: '{timestamp_str}'")  # Debug logging

        if ':' in timestamp_str:
            parts = timestamp_str.split(':')
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                result = minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result
            elif len(parts) == 3:  # HH:MM:SS format
                hours, minutes, seconds = map(int, parts)
                result = hours * 3600 + minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result

        # Try parsing as pure seconds
        result = float(timestamp_str)
        logger.info(f"Parsed '{timestamp_str}' as seconds -> {result}s")
        return result

    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return 0.0

def create_assemblyai_subtitles(video_path: Path, clip_start: float, clip_end: float, video_width: int, video_height: int) -> List[TextClip]:
    """Create subtitles using AssemblyAI's precise word timing."""
    transcript_data = load_cached_transcript_data(video_path)

    if not transcript_data or not transcript_data.get('words'):
        logger.warning("No cached transcript data available for subtitles")
        return []

    # Convert clip timing to milliseconds
    clip_start_ms = int(clip_start * 1000)
    clip_end_ms = int(clip_end * 1000)

    # Find words that fall within our clip timerange
    relevant_words = []
    for word_data in transcript_data['words']:
        word_start = word_data['start']
        word_end = word_data['end']

        # Check if word overlaps with clip
        if word_start < clip_end_ms and word_end > clip_start_ms:
            # Adjust timing relative to clip start
            relative_start = max(0, (word_start - clip_start_ms) / 1000.0)
            relative_end = min((clip_end_ms - clip_start_ms) / 1000.0, (word_end - clip_start_ms) / 1000.0)

            if relative_end > relative_start:
                relevant_words.append({
                    'text': word_data['text'],
                    'start': relative_start,
                    'end': relative_end,
                    'confidence': word_data.get('confidence', 1.0)
                })

    if not relevant_words:
        logger.warning("No words found in clip timerange")
        return []

    # Group words into subtitle segments (3-4 words per subtitle for readability)
    subtitle_clips = []
    processor = VideoProcessor()

    # Smaller font size calculation - reduced from 45 to 28 base size
    base_font_size = 28
    font_size = max(20, min(40, int(base_font_size * (video_width / 720))))

    words_per_subtitle = 3
    for i in range(0, len(relevant_words), words_per_subtitle):
        word_group = relevant_words[i:i + words_per_subtitle]

        if not word_group:
            continue

        # Calculate segment timing
        segment_start = word_group[0]['start']
        segment_end = word_group[-1]['end']
        segment_duration = segment_end - segment_start

        if segment_duration < 0.1:  # Skip very short segments
            continue

        # Create text
        text = ' '.join(word['text'] for word in word_group)

        try:
            # Create high-quality text clip
            text_clip = TextClip(
                text=text,
                font=processor.font_path,
                font_size=font_size,
                color='white',
                stroke_color='black',
                stroke_width=1,  # Reduced from max(2, int(font_size / 15)) for cleaner look
                method='label',  # Changed from 'caption' to 'label' for better quality
                text_align='center'
            ).with_duration(segment_duration).with_start(segment_start)

            # Position at bottom with more padding
            text_height = text_clip.size[1] if text_clip.size else 40
            vertical_position = video_height - text_height - 80  # Increased padding from 60 to 80
            text_clip = text_clip.with_position(('center', vertical_position))

            # Subtle background for better readability - reduced opacity and padding
            bg_clip = ColorClip(
                size=(text_clip.size[0] + 16, text_height + 12),  # Reduced padding
                color=(0, 0, 0),
                duration=segment_duration
            ).with_opacity(0.3).with_position(('center', vertical_position - 6)).with_start(segment_start)  # Reduced opacity

            subtitle_clips.extend([bg_clip, text_clip])

        except Exception as e:
            logger.warning(f"Failed to create subtitle for '{text}': {e}")
            continue

    logger.info(f"Created {len(subtitle_clips)} subtitle elements from AssemblyAI data")
    return subtitle_clips

def create_optimized_clip(video_path: Path, start_time: float, end_time: float, output_path: Path, add_subtitles: bool = True) -> bool:
    """Create optimized 9:16 clip with AssemblyAI subtitles."""
    try:
        duration = end_time - start_time
        if duration <= 0:
            logger.error(f"Invalid clip duration: {duration:.1f}s")
            return False

        logger.info(f"Creating clip: {start_time:.1f}s - {end_time:.1f}s ({duration:.1f}s)")

        # Load and process video
        video = VideoFileClip(str(video_path))

        if start_time >= video.duration:
            logger.error(f"Start time {start_time}s exceeds video duration {video.duration:.1f}s")
            video.close()
            return False

        end_time = min(end_time, video.duration)
        clip = video.subclipped(start_time, end_time)

        # Get optimal crop
        x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
            video, start_time, end_time, target_ratio=9/16
        )

        cropped_clip = clip.cropped(
            x1=x_offset, y1=y_offset,
            x2=x_offset + new_width, y2=y_offset + new_height
        )

        # Add AssemblyAI subtitles
        final_clips = [cropped_clip]

        if add_subtitles:
            subtitle_clips = create_assemblyai_subtitles(
                video_path, start_time, end_time, new_width, new_height
            )
            final_clips.extend(subtitle_clips)

        # Compose and encode
        final_clip = CompositeVideoClip(final_clips) if len(final_clips) > 1 else cropped_clip

        processor = VideoProcessor()
        encoding_settings = processor.get_optimal_encoding_settings("high")

        final_clip.write_videofile(
            str(output_path),
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            logger=None,
            **encoding_settings
        )

        # Cleanup
        final_clip.close()
        clip.close()
        video.close()

        logger.info(f"Successfully created clip: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create clip: {e}")
        return False

def create_clips_from_segments(video_path: Path, segments: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
    """Create optimized video clips from segments."""
    logger.info(f"Creating {len(segments)} clips")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_info = []

    for i, segment in enumerate(segments):
        try:
            # Debug log the segment data
            logger.info(f"Processing segment {i+1}: start='{segment.get('start_time')}', end='{segment.get('end_time')}'")

            start_seconds = parse_timestamp_to_seconds(segment['start_time'])
            end_seconds = parse_timestamp_to_seconds(segment['end_time'])

            duration = end_seconds - start_seconds
            logger.info(f"Segment {i+1} duration: {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)")

            if duration <= 0:
                logger.warning(f"Skipping clip {i+1}: invalid duration {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)")
                continue

            clip_filename = f"clip_{i+1}_{segment['start_time'].replace(':', '')}-{segment['end_time'].replace(':', '')}.mp4"
            clip_path = output_dir / clip_filename

            success = create_optimized_clip(video_path, start_seconds, end_seconds, clip_path)

            if success:
                clip_info = {
                    "clip_id": i + 1,
                    "filename": clip_filename,
                    "path": str(clip_path),
                    "start_time": segment['start_time'],
                    "end_time": segment['end_time'],
                    "duration": duration,
                    "text": segment['text'],
                    "relevance_score": segment['relevance_score'],
                    "reasoning": segment['reasoning']
                }
                clips_info.append(clip_info)
                logger.info(f"Created clip {i+1}: {duration:.1f}s")
            else:
                logger.error(f"Failed to create clip {i+1}")

        except Exception as e:
            logger.error(f"Error processing clip {i+1}: {e}")

    logger.info(f"Successfully created {len(clips_info)}/{len(segments)} clips")
    return clips_info

# Backward compatibility functions
def get_video_transcript_with_assemblyai(path: Path) -> str:
    """Backward compatibility wrapper."""
    return get_video_transcript(path)

def create_9_16_clip(video_path: Path, start_time: float, end_time: float, output_path: Path, subtitle_text: str = "") -> bool:
    """Backward compatibility wrapper."""
    return create_optimized_clip(video_path, start_time, end_time, output_path, add_subtitles=bool(subtitle_text))
