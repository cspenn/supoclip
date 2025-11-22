"""
Test script to verify parakeet-mlx token extraction fix.
"""
import sys
from pathlib import Path

from src.transcription_mlx import transcribe_video_mlx


# Find a test video
video_path = list(Path("temp/uploads").glob("*.mp4"))
if not video_path:
    print("❌ No video file found in temp/uploads/")
    sys.exit(1)

video_file = video_path[0]
print(f"📹 Testing transcription on: {video_file}")

# Transcribe
result = transcribe_video_mlx(video_file)

# Verify results
print("\n" + "=" * 80)
print("VERIFICATION RESULTS:")
print("=" * 80)

success = True

# Check 1: Text is not empty
if result["text"] and len(result["text"]) > 0:
    print(f"✅ Text extracted: {len(result['text'])} characters")
    print(f"   First 100 chars: {result['text'][:100]}...")
else:
    print("❌ Text is EMPTY")
    success = False

# Check 2: Words are extracted
if result["words"] and len(result["words"]) > 0:
    print(f"✅ Words extracted: {len(result['words'])} words")
    print(f"   First word: {result['words'][0]}")
    print(f"   Last word: {result['words'][-1]}")
else:
    print("❌ Words are EMPTY")
    success = False

# Check 3: Segments are extracted
if result["segments"] and len(result["segments"]) > 0:
    print(f"✅ Segments extracted: {len(result['segments'])} segments")
    print(
        f"   First segment: start={result['segments'][0]['start']}ms, end={result['segments'][0]['end']}ms"
    )
    print(f"   First segment text: {result['segments'][0]['text'][:80]}...")
else:
    print("❌ Segments are EMPTY")
    success = False

# Check 4: Word timing is valid
if result["words"]:
    first_word = result["words"][0]
    if first_word["start"] < first_word["end"]:
        print("✅ Word timing is valid: start < end")
    else:
        print(
            f"❌ Word timing is INVALID: start={first_word['start']}, end={first_word['end']}"
        )
        success = False

# Check 5: Segment timing is valid
if result["segments"]:
    first_segment = result["segments"][0]
    if first_segment["start"] < first_segment["end"]:
        print("✅ Segment timing is valid: start < end")
    else:
        print(
            f"❌ Segment timing is INVALID: start={first_segment['start']}, end={first_segment['end']}"
        )
        success = False

print("\n" + "=" * 80)
if success:
    print("🎉 ALL CHECKS PASSED - Parakeet-MLX extraction is working correctly!")
    print("=" * 80)
    sys.exit(0)
else:
    print("❌ SOME CHECKS FAILED - Parakeet-MLX extraction needs more fixes")
    print("=" * 80)
    sys.exit(1)
