# VLM Enhancement Plan — Vision-Aware Clipping

**Status:** Draft / planning (not yet scheduled)
**Date:** 2026-06-29
**Author:** initial draft for review
**Context:** The local LLM endpoint now serves a multimodal model
(`gemma-4-26B-A4B-MLX-4-8`, type `vlm`, OpenAI-compatible at
`http://127.0.0.1:8998/v1`). SupoClip's pipeline today is **transcript-only** —
it never looks at a single pixel when deciding what to clip or how to frame it.
This document maps how to use the VLM for greater impact, ranked by value, with a
concrete phased roadmap and the open decisions that gate it.

---

## 1. The core thesis

SupoClip selects clips from **what was said**. The most viral short-form moments
are often about **what was shown**: a reaction, a demo, a reveal, on-screen text,
a gesture, a scene change. A VLM lets the pipeline see the video, so selection,
framing, and packaging can be driven by visual signal — not just the transcript.

The backbone stays deterministic and offline (parakeet transcript + text LLM);
the VLM is layered in as an **additive, gracefully-degrading** signal, matching
the project's existing "detect → fall back cleanly" patterns (e.g.
`face_detect.detect_face_center` returning `None` → center crop).

---

## 2. Where the codebase plugs in (today's reality)

| Concern | Current code | VLM opportunity |
|---|---|---|
| Clip selection | `src/pipeline/analyze.py` `analyze_transcript()` → `TranscriptSegment[]` (transcript text only, via `OpenAIModel(base_url=local_llm_base_url)`) | Re-rank / propose segments using sampled frames |
| 9:16 framing | `src/pipeline/face_detect.py` `detect_face_center` / `detect_face_center_multi` → `calculate_crop_box` | Salient-subject framing beyond faces (product, slide, on-screen text) |
| Frame access | `src/pipeline/face_detect.py` `get_representative_frame` (already extracts frames) | Reuse for VLM frame sampling |
| Orchestration | `src/services/video_service.py` `_run_analysis`, `_run_clip_generation` | Insert an optional vision stage between analysis and clip-gen |
| Config | `src/config.py` `local_llm_base_url/model/api_key`, `max_workers` | Add VLM toggle, sampling density, frame budget |

The VLM endpoint is **OpenAI-compatible with vision**: images are passed as
`{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}` entries
in the message `content` array — the same `OpenAIModel`/`OpenAIProvider` wiring
already used in `analyze.py`, just with image parts added. (Gemma-4 chat-template
and image-token handling is done server-side by the omlx endpoint; see the
model-card / prompt-formatting docs. Verify the endpoint accepts OpenAI vision
message shape during Phase 0.)

---

## 3. Opportunity map (ranked by impact ÷ effort)

### A. Visual engagement re-ranking of candidate clips — **HIGHEST ROI**
Keep transcript-based candidate generation; add a VLM pass that scores each
candidate segment's sampled frames for visual interest (motion/scene change,
on-screen text, facial expression/reaction, demonstration) and **fuses** that
with the transcript relevance score. Net effect: better picks, minimal
architectural risk, fully additive.

### B. Salient-subject reframing for the 9:16 crop — **HIGH**
Today the crop centers on a detected face or the frame center. A VLM can name the
moment's salient region (active speaker among several, the slide, the product,
the on-screen caption) to drive `calculate_crop_box`. Fixes the "talking head is
off to one side / b-roll gets center-cropped badly" failure mode.

### C. Auto thumbnail + hook-frame selection — **HIGH, low effort**
Pick the single most arresting frame per clip (clear face, peak expression, text
on screen) for a cover image / hook. Cheap: one VLM call over a handful of
candidate frames per clip.

### D. Auto metadata: titles, hooks, hashtags — **MEDIUM**
Combine the clip's transcript with 1–2 representative frames so the VLM writes a
platform-native title/hook/hashtags grounded in what's visually happening.

### E. Visual scene/shot-boundary detection — **MEDIUM**
Detect hard cuts / scene changes to align clip boundaries to visual structure
(complements transcript sentence boundaries; avoids starting a clip mid-cut).

### F. Quality / safety filtering — **LOW–MEDIUM**
Drop or down-rank segments that are blurry, dark, frozen, or off-topic before
spending an encode on them.

---

## 4. Recommended architecture

A new module `src/pipeline/vision.py` owning frame sampling + VLM calls, returning
typed results; `video_service` calls it as an **optional stage**; `analyze.py`
consumes a vision score to fuse with the transcript score. Mirrors the existing
module boundaries and the `# start <path>` / structlog / `get_config()` / typed
conventions.

```
download ─► transcribe ─► analyze (transcript) ─┐
                                                ├─► [VLM vision stage] ─► fuse ─► generate clips
        frame sampling (ffmpeg select / fps) ───┘     (optional, graceful)
```

Design rules (consistent with the audited codebase):
- **Additive & graceful**: if the VLM is disabled/unreachable, the pipeline behaves
  exactly as today (deterministic transcript path). No hard dependency.
- **Frugal sampling**: VLM inference on a 16 GB model is seconds per image. Sample
  sparsely — e.g. 1 frame / N seconds or scene-keyframes — with a hard per-video
  frame budget; run within the existing `max_workers` concurrency bound and the
  `ffmpeg_timeout`/`transcription_timeout` style timeouts.
- **Cache**: key VLM results by (video hash, timestamp) so re-runs are cheap
  (mirrors the existing transcript cache).
- **Offline-first preserved**: VLM stays the local endpoint; no new cloud
  dependency unless explicitly opted in.
- **Real-output tested**: like the audit's `tests/integration/test_pipeline_real_output.py`,
  prove the vision stage on a real fixture (assert it scores/labels a real frame),
  not mocks-only.

---

## 5. Phased roadmap

**Phase 0 — Spike (½–1 day).** Stand up `vision.py` with a single function: sample
K frames from a clip and get a structured VLM judgment (engagement score + 1-line
reason) via the OpenAI vision message format against the gemma endpoint. Confirm
the endpoint accepts base64 image parts and returns parseable structured output.
Output: a go/no-go on latency and format.

**Phase 1 — Visual re-ranking (Opportunity A).** Add an optional vision pass that
scores each transcript-selected candidate and fuses scores (e.g.
`final = w_t·transcript + w_v·visual`). Config flags: `VLM_ENABLED`,
`VLM_FRAMES_PER_CLIP`, fusion weights. Graceful no-op when disabled. Real-output
test. **This is the recommended first ship — highest impact, lowest risk.**

**Phase 2 — Salient-subject framing (Opportunity B).** VLM proposes a crop focus
region per segment; feed into `calculate_crop_box` as a higher-priority signal than
face detection, with face/center as fallback.

**Phase 3 — Thumbnails + metadata (C, D).** Hook-frame selection and
vision-grounded titles/hooks/hashtags; surface in the task page.

**Phase 4 — Scene detection + quality filtering (E, F).** Visual boundaries and
pre-encode quality gating for longer / lower-quality sources.

---

## 6. Risks & constraints

- **Latency/cost.** VLM per-frame is the dominant new cost. Mitigate with sparse
  sampling, a per-video frame budget, batching, concurrency caps, and caching.
- **Non-determinism.** VLM scores vary run-to-run. Keep the transcript path as the
  deterministic backbone; treat VLM as a re-ranker/advisor, not the sole selector,
  so output stays stable and explainable.
- **Endpoint format drift.** Gemma-4 vision via the omlx OpenAI shim must accept
  base64 image parts and return usable structured output — validate in Phase 0.
- **Scope discipline.** Each phase is independently shippable and gate-green
  (`./checkpython.sh`); no phase should regress the now-working transcript pipeline.

---

## 7. Open decisions (need your input to prioritize)

1. **Primary goal first?** Better **selection** (A), better **framing** (B), or
   richer **packaging/metadata** (C/D)? (Recommendation: A — biggest viral-quality
   lever, lowest risk.)
2. **Latency budget.** How much extra time per video is acceptable for the vision
   pass? (Sets sampling density and frame budget.)
3. **Offline-only?** Keep VLM strictly local (gemma endpoint), or allow a cloud VLM
   fallback for speed/quality?
4. **Determinism tolerance.** OK with VLM as a re-ranker on top of deterministic
   selection (recommended), or do you want VLM to propose segments directly?

---

*Next step after sign-off: implement Phase 0 spike, then a brainstorming pass to
lock Phase 1 scope and the fusion/scoring design before building.*
