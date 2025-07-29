"""
Utility functions for video-related operations.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import os
import logging
import numpy as np

import whisper
import cv2
from moviepy import VideoFileClip, CompositeVideoClip, TextClip

from .config import Config

logger = logging.getLogger(__name__)

config = Config()

def get_video_transcript(path: Path) -> str:
  """Get the transcript of a video from a path using whisper with timestamps."""
  logger.info(f"🎤 Loading Whisper model: {config.whisper_model}")
  model = whisper.load_model(config.whisper_model)

  logger.info(f"🎵 Starting transcription of: {path}")
  result = model.transcribe(str(path), word_timestamps=True)
  logger.info(f"✅ Transcription complete - found {len(result['segments'])} segments")

  # Format as subtitle-style transcript with timestamps
  transcript_lines = []
  for i, segment in enumerate(result["segments"]):
    start_time = format_timestamp(segment["start"])
    end_time = format_timestamp(segment["end"])
    text = segment["text"].strip()
    transcript_lines.append(f"[{start_time} - {end_time}] {text}")
    if i < 3:  # Log first 3 segments as examples
      logger.info(f"📝 Segment {i+1}: [{start_time} - {end_time}] {text[:50]}...")

  total_transcript = "\n".join(transcript_lines)
  logger.info(f"✅ Transcript formatted with {len(transcript_lines)} lines, {len(total_transcript)} characters")
  return total_transcript

def format_timestamp(seconds: float) -> str:
  """Format timestamp from seconds to MM:SS format."""
  minutes = int(seconds // 60)
  seconds = int(seconds % 60)
  return f"{minutes:02d}:{seconds:02d}"

def parse_timestamp(timestamp_str: str) -> float:
  """Parse timestamp string (MM:SS) back to seconds."""
  try:
    minutes, seconds = map(int, timestamp_str.split(':'))
    return minutes * 60 + seconds
  except ValueError:
    return 0.0

def detect_face_center(video_clip: VideoFileClip, start_time: float, end_time: float) -> Optional[Tuple[int, int]]:
  """Detect the center of the most prominent face in a video segment."""
  try:
    logger.info("👤 Starting face detection analysis")

    # Load OpenCV's face detection model
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # Sample frames at different points in the segment
    sample_times = []
    duration = end_time - start_time
    if duration > 3:
      # Sample at start, middle, and end for longer clips
      sample_times = [start_time + 0.5, start_time + duration/2, end_time - 0.5]
    else:
      # Sample at middle for shorter clips
      sample_times = [start_time + duration/2]

    face_centers = []
    largest_face_area = 0
    best_face_center = None

    for sample_time in sample_times:
      try:
        # Extract frame at sample time
        frame = video_clip.get_frame(sample_time)

        # Convert RGB to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = face_cascade.detectMultiScale(
          gray,
          scaleFactor=1.1,
          minNeighbors=5,
          minSize=(50, 50)  # Minimum face size
        )

        if len(faces) > 0:
          logger.info(f"😊 Found {len(faces)} face(s) at time {sample_time:.1f}s")

          # Find the largest face (most prominent)
          for (x, y, w, h) in faces:
            face_area = w * h
            face_center_x = x + w // 2
            face_center_y = y + h // 2

            face_centers.append((face_center_x, face_center_y, face_area))

            # Track the largest face
            if face_area > largest_face_area:
              largest_face_area = face_area
              best_face_center = (face_center_x, face_center_y)

      except Exception as e:
        logger.warning(f"⚠️ Error processing frame at {sample_time:.1f}s: {e}")
        continue

    if best_face_center:
      logger.info(f"✅ Face detection successful - center at ({best_face_center[0]}, {best_face_center[1]})")
      return best_face_center
    else:
      logger.info("😐 No faces detected, will use center crop")
      return None

  except Exception as e:
    logger.error(f"❌ Face detection failed: {e}")
    return None

def create_9_16_clip(video_path: Path, start_time: float, end_time: float, output_path: Path, subtitle_text: str = "") -> bool:
  """Create a 9:16 aspect ratio clip from a video segment using MoviePy v2 (TikTok format) with face-focused cropping and subtitles."""
  try:
    logger.info(f"🎞️ Loading video file: {video_path}")
    # Load the video
    video = VideoFileClip(str(video_path))
    logger.info(f"📐 Original video size: {video.size[0]}x{video.size[1]}, duration: {video.duration:.1f}s")

    # Extract the segment
    logger.info(f"✂️ Extracting segment: {start_time:.1f}s to {end_time:.1f}s")
    clip = video.subclipped(start_time, end_time)
    logger.info(f"✅ Segment extracted, duration: {clip.duration:.1f}s")

    # Calculate 9:16 dimensions based on video size
    original_width, original_height = clip.size
    target_ratio = 9/16  # Portrait ratio for TikTok
    current_ratio = original_width / original_height

    logger.info(f"📏 Original ratio: {current_ratio:.2f}, target ratio: {target_ratio:.2f}")

    # Determine crop dimensions
    if current_ratio > target_ratio:
      # Video is wider than 9:16, crop width
      new_width = int(original_height * target_ratio)
      new_height = original_height
      logger.info(f"📐 Cropping width: {original_width}x{original_height} → {new_width}x{new_height}")
    else:
      # Video is taller than 9:16, crop height
      new_width = original_width
      new_height = int(original_width / target_ratio)
      logger.info(f"📐 Cropping height: {original_width}x{original_height} → {new_width}x{new_height}")

    # Try to detect faces and center crop around them
    face_center = detect_face_center(clip, 0, clip.duration)

    if face_center:
      face_x, face_y = face_center
      logger.info(f"🎯 Centering crop around detected face at ({face_x}, {face_y})")

      # Center the crop around the face
      x_offset = max(0, min(face_x - new_width // 2, original_width - new_width))
      y_offset = max(0, min(face_y - new_height // 2, original_height - new_height))

      # Ensure we don't go outside video boundaries
      if x_offset + new_width > original_width:
        x_offset = original_width - new_width
      if y_offset + new_height > original_height:
        y_offset = original_height - new_height

      logger.info(f"👤 Face-centered crop: x={x_offset}, y={y_offset}, w={new_width}, h={new_height}")
    else:
      # Fall back to center crop
      x_offset = (original_width - new_width) // 2 if current_ratio > target_ratio else 0
      y_offset = (original_height - new_height) // 2 if current_ratio <= target_ratio else 0
      logger.info(f"📐 Center crop (no face): x={x_offset}, y={y_offset}, w={new_width}, h={new_height}")

    # Crop to 9:16 using MoviePy v2 syntax
    logger.info(f"✂️ Applying crop: x={x_offset}, y={y_offset}, w={new_width}, h={new_height}")
    cropped_clip = clip.cropped(x1=x_offset, y1=y_offset,
                               x2=x_offset + new_width, y2=y_offset + new_height)

    # Add subtitles if text is provided
    if subtitle_text and subtitle_text.strip():
      logger.info("📝 Adding subtitles to clip")
      font_path = str(Path(__file__).parent.parent / "fonts" / "THEBOLDFONT-FREEVERSION.ttf")

      # Create subtitle clip with styling for TikTok format
      subtitle_clip = TextClip(
        txt=subtitle_text.strip(),
        font=font_path,
        font_size=45,
        color='white',
        stroke_color='black',
        stroke_width=3,
        method='caption',
        size=(new_width - 40, None),  # Fit within video width with padding
        align='center'
      ).with_duration(cropped_clip.duration)

      # Position subtitles at bottom with padding
      subtitle_clip = subtitle_clip.with_position(('center', new_height - subtitle_clip.size[1] - 60))

      # Composite the video with subtitles
      final_clip = CompositeVideoClip([cropped_clip, subtitle_clip])
      logger.info("✅ Subtitles added successfully")
    else:
      final_clip = cropped_clip
      logger.info("ℹ️ No subtitle text provided, creating clip without subtitles")

    # Write the final clip using MoviePy v2 parameters
    logger.info(f"💾 Writing clip to: {output_path}")
    final_clip.write_videofile(
      str(output_path),
      codec='libx264',
      audio_codec='aac',
      temp_audiofile='temp-audio.m4a',
      remove_temp=True,
      logger=None  # MoviePy v2 uses logger=None instead of verbose=False
    )

    # Clean up
    logger.info("🧹 Cleaning up video objects")
    final_clip.close()
    if subtitle_text and subtitle_text.strip():
      # cropped_clip and subtitle_clip are cleaned up when final_clip is closed
      pass
    clip.close()
    video.close()

    logger.info(f"✅ TikTok format clip with face detection created successfully: {output_path}")
    return True

  except Exception as e:
    logger.error(f"❌ Error creating clip: {str(e)}")
    logger.error(f"❌ Failed parameters - video: {video_path}, start: {start_time}, end: {end_time}, output: {output_path}")
    return False

def create_clips_from_segments(video_path: Path, segments: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
  """Create video clips from relevant segments in 9:16 TikTok format with burned-in subtitles and face-focused cropping."""
  logger.info(f"🎬 Starting clip creation for {len(segments)} segments with face detection and subtitles")
  logger.info(f"📁 Input video: {video_path}")
  logger.info(f"📁 Output directory: {output_dir}")

  clips_info = []

  # Ensure output directory exists
  output_dir.mkdir(parents=True, exist_ok=True)
  logger.info(f"✅ Output directory ready: {output_dir}")

  for i, segment in enumerate(segments):
    logger.info(f"🎥 Processing clip {i+1}/{len(segments)}")
    start_seconds = parse_timestamp(segment['start_time'])
    end_seconds = parse_timestamp(segment['end_time'])
    logger.info(f"⏱️ Clip timing: {start_seconds}s - {end_seconds}s ({end_seconds - start_seconds:.1f}s duration)")

    # Generate clip filename
    clip_filename = f"clip_{i+1}_{segment['start_time'].replace(':', '')}-{segment['end_time'].replace(':', '')}.mp4"
    clip_path = output_dir / clip_filename
    logger.info(f"📄 Creating: {clip_filename}")

    # Create the clip with subtitles
    success = create_9_16_clip(video_path, start_seconds, end_seconds, clip_path, segment['text'])

    if success:
      logger.info(f"✅ Clip {i+1} created successfully")
      clip_info = {
        "clip_id": i + 1,
        "filename": clip_filename,
        "path": str(clip_path),
        "start_time": segment['start_time'],
        "end_time": segment['end_time'],
        "duration": end_seconds - start_seconds,
        "text": segment['text'],
        "relevance_score": segment['relevance_score'],
        "reasoning": segment['reasoning']
      }
      clips_info.append(clip_info)
    else:
      logger.error(f"❌ Failed to create clip {i+1}")

  logger.info(f"🎉 Clip creation complete! Successfully created {len(clips_info)}/{len(segments)} clips")
  return clips_info
