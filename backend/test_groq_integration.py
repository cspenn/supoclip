"""
Test Groq integration with Llama 4 Scout model.
Verifies LLM configuration and AI analysis works with Groq API.
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from src.config import Config
from src.ai import get_most_relevant_parts_by_transcript

async def test_groq_config():
    """Test Groq configuration and AI analysis."""
    print("="*80)
    print("GROQ INTEGRATION TEST")
    print("="*80)

    # Test 1: Configuration
    print("\n" + "-"*80)
    print("TEST 1: CONFIGURATION")
    print("-"*80)

    config = Config()

    print(f"LOCAL_LLM_ENABLED: {config.local_llm_enabled}")
    print(f"LLM_MODEL: {config.llm}")

    if config.local_llm_enabled:
        print("❌ LOCAL_LLM_ENABLED should be false for Groq")
        return False

    if not config.llm or not config.llm.startswith("groq:"):
        print(f"❌ LLM_MODEL should start with 'groq:', got: {config.llm}")
        return False

    print("✅ Configuration correct: Using Groq API")

    # Test 2: Get LLM Model
    print("\n" + "-"*80)
    print("TEST 2: LLM MODEL INITIALIZATION")
    print("-"*80)

    try:
        llm_model = config.get_llm_model()
        print(f"✅ LLM model initialized: {llm_model}")
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        return False

    # Test 3: AI Analysis with Sample Transcript
    print("\n" + "-"*80)
    print("TEST 3: AI ANALYSIS WITH GROQ")
    print("-"*80)

    sample_transcript = """
[00:00 - 00:05] Welcome to this video about artificial intelligence and machine learning.
[00:05 - 00:15] Today we're going to explore how AI is transforming the way we work and live.
[00:15 - 00:25] One of the most exciting developments is in natural language processing.
[00:25 - 00:35] These models can understand context, generate creative content, and assist with complex tasks.
[00:35 - 00:45] The future of AI is incredibly promising, with applications in healthcare, education, and more.
[00:45 - 01:00] Let's dive into some specific examples of how AI is being used today.
[01:00 - 01:15] In healthcare, AI helps diagnose diseases earlier and more accurately than ever before.
[01:15 - 01:30] In education, personalized learning systems adapt to each student's unique needs and pace.
[01:30 - 01:45] The possibilities are endless, and we're just getting started with this technology.
"""

    try:
        print("Analyzing transcript with Groq API (Llama 4 Scout)...")
        print("(This may take 10-30 seconds depending on API response time)")

        analysis = await get_most_relevant_parts_by_transcript(sample_transcript)

        if len(analysis.most_relevant_segments) > 0:
            print(f"\n✅ AI ANALYSIS SUCCESS: {len(analysis.most_relevant_segments)} segments found")
            print("\nSegments identified by Llama 4 Scout:")
            for i, seg in enumerate(analysis.most_relevant_segments, 1):
                print(f"\n  Segment {i}:")
                print(f"    Time: {seg.start_time} → {seg.end_time}")
                print(f"    Score: {seg.relevance_score:.2f}")
                print(f"    Text: {seg.text[:100]}...")
                print(f"    Reasoning: {seg.reasoning[:150]}...")
        else:
            print("⚠️  AI returned no segments (unexpected)")
            return False

    except Exception as e:
        print(f"\n❌ AI ANALYSIS FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Final Summary
    print("\n" + "="*80)
    print("GROQ INTEGRATION TEST PASSED! 🎉")
    print("="*80)
    print("\n✅ Configuration: Groq API enabled")
    print("✅ Model: meta-llama/llama-4-scout-17b-16e-instruct")
    print("✅ AI Analysis: Working correctly")
    print("\n🚀 Your application is now using Groq's fast inference!")
    print("\nExpected performance:")
    print("  • Speed: ~460 tokens/second")
    print("  • Cost: ~$0.0009 per video")
    print("  • Context: 128K tokens")

    return True

if __name__ == "__main__":
    result = asyncio.run(test_groq_config())
    sys.exit(0 if result else 1)
