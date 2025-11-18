# Video Processing Failure Flow Diagram
Date: 2025-11-18

## Visual Flow of the Failure

```
┌─────────────────────────────────────────────────────────────────┐
│ USER REQUEST                                                    │
│ min_clip_length: 49s, max_clip_length: 58s                    │
│ (Unrealistic - viral clips are typically 10-30s)              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Groq Structured Outputs API                            │
│ File: src/ai_structured.py                                     │
│ Function: analyze_transcript_structured()                       │
│                                                                 │
│ → Sends transcript to Groq Llama 4 Scout                       │
│ → Model analyzes and returns 5 segments                        │
│ → Segments: 8.96s, 12.40s, 11.84s, 12.56s, 12.40s            │
│ → Average duration: 11.63 seconds                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Validation Logic (Lines 254-313)                       │
│ File: src/ai_structured.py                                     │
│                                                                 │
│ FOR EACH SEGMENT:                                              │
│   ✓ Check text content (min 3 words)                          │
│   ✓ Check start_time ≠ end_time                               │
│   ✓ Parse timestamps, calculate duration                       │
│   ✓ Validate: duration >= min_length (49s)                    │
│   ✓ Validate: duration <= max_length (58s)                    │
│                                                                 │
│ RESULTS:                                                        │
│   ❌ Segment 1: 8.96s  < 49s → REJECTED                       │
│   ❌ Segment 2: 12.40s < 49s → REJECTED                       │
│   ❌ Segment 3: 11.84s < 49s → REJECTED                       │
│   ❌ Segment 4: 12.56s < 49s → REJECTED                       │
│   ❌ Segment 5: 12.40s < 49s → REJECTED                       │
│                                                                 │
│ validated_segments = [] (EMPTY!)                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Error Raised (Lines 320-336)                           │
│ File: src/ai_structured.py                                     │
│                                                                 │
│ if not validated_segments:                                     │
│     raise ValueError(                                           │
│         "No valid segments found. All segments rejected."      │
│     )                                                           │
│                                                                 │
│ ✅ THIS IS CORRECT BEHAVIOR                                    │
│    (Prevents processing of invalid segments)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Exception Caught in ai.py (Lines 351-358)              │
│ File: src/ai.py                                                │
│ Function: get_most_relevant_parts_by_transcript()              │
│                                                                 │
│ try:                                                            │
│     result = await analyze_transcript_structured(...)          │
│ except Exception as e:                                          │
│     logger.warning("Groq failed, falling back to Pydantic AI") │
│     # Continue to fallback below...                            │
│                                                                 │
│ ⚠️  PROBLEM: Catches ValueError and tries fallback            │
│    (Should re-raise validation errors instead)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Pydantic AI Fallback (Lines 361-362)                   │
│ File: src/ai.py                                                │
│                                                                 │
│ agent = _get_transcript_agent()                                │
│ result = await agent.run(analysis_prompt)                      │
│                                                                 │
│ Agent Configuration (Lines 119-123):                           │
│   Agent(                                                        │
│       model=groq:meta-llama/llama-4-scout-17b-16e-instruct,   │
│       output_type=TranscriptAnalysis,                          │
│       system_prompt=simplified_system_prompt,                  │
│       # NO TOOLS REGISTERED!                                   │
│   )                                                             │
│                                                                 │
│ ⚠️  CRITICAL ISSUE:                                            │
│    • Same model as primary path (Llama 4 Scout)                │
│    • Different API interface (tool calling vs structured)      │
│    • No tools registered on agent                              │
│    • Model expects to call tools                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Groq API Call via Pydantic AI                          │
│                                                                 │
│ Pydantic AI Library:                                           │
│ → Converts output_type schema to tool definitions              │
│ → Sends request to Groq without tools in request.tools[]      │
│                                                                 │
│ Llama 4 Scout Model:                                           │
│ → Attempts to analyze transcript                               │
│ → Tries to call get_transcript_segment tool                    │
│ → Generates tool call in response                              │
│                                                                 │
│ Groq API Validation:                                           │
│ → Checks: Is 'get_transcript_segment' in request.tools?       │
│ → Answer: NO (tools array is empty)                            │
│ → Result: 400 Bad Request                                      │
│                                                                 │
│ Error Message:                                                  │
│ "tool call validation failed: attempted to call tool           │
│  'get_transcript_segment' which was not in request.tools"      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Exception Propagates Up (ai.py Lines 402-409)          │
│                                                                 │
│ except Exception as e:                                          │
│     logger.error(f"Error in transcript analysis: {e}")         │
│     raise  # Re-raise to fail the task                         │
│                                                                 │
│ ✅ THIS IS CORRECT - Errors should propagate                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Task Marked as Failed (video_service.py)               │
│                                                                 │
│ try:                                                            │
│     relevant_parts = await VideoService.analyze_transcript()   │
│ except Exception as e:                                          │
│     logger.error(f"Error in video processing: {e}")            │
│     raise  # Propagates to task handler                        │
│                                                                 │
│ Task Status: FAILED                                            │
│ User sees: "Video processing failed"                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why the Fallback Never Works

### Architecture Mismatch

```
PRIMARY PATH (Groq Structured Outputs):
┌──────────────────────────────────────────────────┐
│ Client Request                                   │
│ ├─ model: llama-4-scout-17b-16e-instruct        │
│ ├─ messages: [system, user]                     │
│ └─ response_format:                              │
│    └─ type: "json_schema"                        │
│       └─ schema: TranscriptAnalysis.json_schema()│
│                                                  │
│ Groq API Response:                               │
│ └─ JSON object matching schema (NO TOOL CALLS)  │
└──────────────────────────────────────────────────┘
                     ✅ Works correctly

FALLBACK PATH (Pydantic AI with Tool Calling):
┌──────────────────────────────────────────────────┐
│ Pydantic AI Request                              │
│ ├─ model: llama-4-scout-17b-16e-instruct        │
│ ├─ messages: [system, user]                     │
│ ├─ tools: [] ← EMPTY! No tools registered       │
│ └─ Expects: Structured output via tool calling   │
│                                                  │
│ Model Behavior:                                  │
│ └─ Tries to call 'get_transcript_segment' tool  │
│                                                  │
│ Groq API Validation:                             │
│ └─ Error: Tool not in request.tools[]           │
└──────────────────────────────────────────────────┘
                     ❌ Always fails
```

### The Fundamental Problem

**Same model, two different API interfaces:**

1. **Structured Outputs API** (response_format)
   - Model constrained to return exact JSON schema
   - No tool calling involved
   - Works perfectly

2. **Chat Completions API** (with tools parameter)
   - Model can call tools to gather data
   - Requires tools to be registered in request
   - **Pydantic AI sends empty tools array**
   - Model tries to call tools anyway
   - API rejects the attempt

**This is why the fallback has NEVER worked.**

---

## The Fix: Remove the Broken Fallback

```
CURRENT (BROKEN):
┌──────────────────────────────────────┐
│ Primary: Groq Structured Outputs    │
│ ↓ (on any error)                    │
│ Fallback: Pydantic AI (broken)      │
└──────────────────────────────────────┘

FIXED:
┌──────────────────────────────────────┐
│ Primary: Groq Structured Outputs    │
│ ↓ (on ValueError - validation fail) │
│ Re-raise with helpful error message │
│                                      │
│ ↓ (on other errors - API issues)    │
│ Re-raise with API error details     │
└──────────────────────────────────────┘

BENEFIT:
• Clear error messages
• User guidance ("try shorter clips")
• No false hope of broken fallback
• Faster failure (no wasted API calls)
```

---

## Parameter Validation Flow (After Fix)

```
USER REQUEST
  ↓
┌────────────────────────────────────────┐
│ Parameter Validation (NEW)            │
│                                        │
│ min_length = 49                        │
│ ↓ if > 45: cap to 45                  │
│ min_length = 45 ✅                    │
│                                        │
│ max_length = 58                        │
│ ↓ if > 60: cap to 60                  │
│ max_length = 58 ✅                    │
│                                        │
│ Log: "Capped 49-58s to 45-58s"       │
└────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────┐
│ Groq Structured Outputs               │
│ (with capped parameters)              │
│                                        │
│ Returns: 5 segments, 8-13s each       │
└────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────┐
│ Validation                            │
│ min=45, max=58                        │
│                                        │
│ Still rejects (all < 45s)             │
└────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────┐
│ Error Message (IMPROVED)              │
│                                        │
│ "No valid segments found.             │
│  Requested: 45-58s                    │
│  AI returned avg: 11.6s               │
│  Recommendation: Try 10-30s"          │
└────────────────────────────────────────┘

USER SEES HELPFUL GUIDANCE
```

---

## Recommended Values for Viral Content

```
┌─────────────────────────────────────────────────┐
│ PLATFORM OPTIMAL DURATIONS                     │
├─────────────────────────────────────────────────┤
│ TikTok              │ 10-30 seconds            │
│ Instagram Reels     │ 15-30 seconds            │
│ YouTube Shorts      │ 15-45 seconds            │
│ Twitter/X           │ 10-45 seconds            │
├─────────────────────────────────────────────────┤
│ RECOMMENDED DEFAULT │ min=10s, max=45s         │
│ ABSOLUTE MAXIMUM    │ min=45s, max=60s         │
│ ABSOLUTE MINIMUM    │ min=10s, max=15s         │
└─────────────────────────────────────────────────┘

Note: Clips longer than 45s rarely perform well as
short-form content. They work better as highlights
or feature content, not viral clips.
```

---

## Summary

**The failure path:**
1. User requests 49-58s clips (unrealistic)
2. AI returns 11s clips (realistic)
3. Validation rejects all (correct)
4. Fallback triggers (wrong - should error)
5. Fallback fails (no tools registered)
6. Processing fails (correct, but unclear why)

**The fix:**
1. Validate parameters upfront (cap to realistic ranges)
2. Remove broken fallback (clear error instead)
3. Improve error messages (guide user to solution)

**Result:**
- Clear failures with actionable guidance
- No wasted API calls to broken fallback
- Users get helpful recommendations
- System fails fast and informatively
