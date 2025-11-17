"""
Investigate the actual structure of parakeet-mlx result object.
"""
from pathlib import Path
from parakeet_mlx.utils import from_pretrained
from mlx.core import bfloat16

# Load model
print("Loading parakeet-mlx model...")
model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2", dtype=bfloat16)

# Find a test video
video_path = Path("temp/uploads").glob("*.mp4")
video_file = next(video_path, None)

if not video_file:
    print("No video file found in temp/uploads/")
    exit(1)

print(f"Transcribing: {video_file}")

# Transcribe
result = model.transcribe(
    str(video_file),
    chunk_duration=30.0,  # Short duration for testing
    overlap_duration=5.0,
)

print("\n" + "=" * 80)
print("RESULT OBJECT STRUCTURE:")
print("=" * 80)
print(f"Type: {type(result)}")
print(f"Dir: {[attr for attr in dir(result) if not attr.startswith('_')]}")

# Check for common attributes
print("\n" + "=" * 80)
print("ATTRIBUTES:")
print("=" * 80)
for attr in ["text", "segments", "words", "sentences", "tokens", "language"]:
    if hasattr(result, attr):
        val = getattr(result, attr)
        print(f"✓ result.{attr} exists (type: {type(val).__name__})")
        if isinstance(val, list) and len(val) > 0:
            print(f"  First item type: {type(val[0])}")
            print(
                f"  First item attributes: {[a for a in dir(val[0]) if not a.startswith('_')][:10]}"
            )
    else:
        print(f"✗ result.{attr} NOT FOUND")

# If it has sentences, examine the structure
if hasattr(result, "sentences"):
    sentences = result.sentences
    print("\n" + "=" * 80)
    print(f"SENTENCES ({len(sentences)} total):")
    print("=" * 80)
    if len(sentences) > 0:
        first_sentence = sentences[0]
        print(f"First sentence type: {type(first_sentence)}")
        print(
            f"First sentence attributes: {[a for a in dir(first_sentence) if not a.startswith('_')]}"
        )

        if hasattr(first_sentence, "tokens"):
            tokens = first_sentence.tokens
            print(f"\nTokens ({len(tokens)} total):")
            if len(tokens) > 0:
                first_token = tokens[0]
                print(f"  First token type: {type(first_token)}")
                print(
                    f"  First token attributes: {[a for a in dir(first_token) if not a.startswith('_')]}"
                )

                # Try to get actual values
                print("\n  First token values:")
                for attr in dir(first_token):
                    if not attr.startswith("_"):
                        try:
                            val = getattr(first_token, attr)
                            if not callable(val):
                                print(f"    {attr} = {val}")
                        except:
                            pass

# Print actual result structure
print("\n" + "=" * 80)
print("FULL RESULT DUMP (first 500 chars):")
print("=" * 80)
print(str(result)[:500])
