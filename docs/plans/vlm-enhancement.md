# VLM Enhancement Plan — Vision-Aware Clipping

**Status:** Draft / planning (not yet scheduled) — revised after review
**Date:** 2026-06-29
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
a gesture, a cut. A VLM lets the pipeline see the video, so selection, framing,
and packaging can be driven by visual signal — not just the transcript. The
backbone stays deterministic and offline (parakeet transcript + text LLM); the
VLM is layered in as an **additive, gracefully-degrading** signal.

---

## 2. NON-NEGOTIABLE design constraint — the coverage/determinism boundary

**This is the one thing that decides whether VLM work regresses the pipeline the
2026-06-29 audit just stabilized. Read it before writing any code.**

The project's hard-won invariant is **100% line+branch coverage over *real-output*
tests, with no mock-to-pass** (the exact disease the audit cured; see
`output/review/fixes-2026-06-29.md`). A VLM call is **non-deterministic** and
depends on the gemma endpoint being up, so it **cannot** be real-output-tested
inside `./checkpython.sh` — which is precisely why the e2e smoke runner
(`tests/e2e/smoke_pipeline.py`) is *excluded* from the gate.

The first VLM PR therefore hits a fork: break the gate, or mock the VLM to hit
100% — which silently reintroduces mock-coverage. Resolve it by design, up front:

- **Split the seam.** The **deterministic core** — frame sampling (ffmpeg), the
  fusion math, and every disabled/error/timeout/fallback branch — is ordinary code
  and **must be 100% unit-tested inside the gate**.
- **Isolate the model call.** The actual VLM request/parse is a **thin seam** that
  lives in the **e2e tier** (excluded from the gate, like `smoke_pipeline.py`),
  exercised by a real-endpoint smoke runner, never by mocked gate tests.
- **Default OFF.** The fusion weight / `VLM_ENABLED` defaults to **off**, so the
  gate exercises the deterministic path and the disabled branch; "VLM-on" is opt-in
  and proven only in the e2e tier.
- **Graceful degradation is a *tested* branch.** VLM unreachable/timeout/garbage →
  fall back to today's behavior, and that fallback is unit-tested in the gate
  (mirrors `face_detect.detect_face_center` → `None` → center crop).

If a phase can't be built within this boundary, it isn't ready.

---

## 3. Where the codebase plugs in (today's reality)

| Concern | Current code | VLM opportunity |
|---|---|---|
| Clip selection | `src/pipeline/analyze.py` `analyze_transcript()` → `TranscriptSegment[]` (transcript only, via `OpenAIModel(base_url=local_llm_base_url)`) | Re-rank candidates by visual signal |
| 9:16 framing | `src/pipeline/face_detect.py` `detect_face_center` / `_multi` → `calculate_crop_box` | Salient-subject framing beyond faces |
| Frame access | `src/pipeline/face_detect.py` `get_representative_frame` | Reuse for VLM frame sampling |
| Orchestration | `src/services/video_service.py` `_run_analysis`, `_run_clip_generation` | Optional vision stage between analysis and clip-gen |
| Config | `src/config.py` `local_llm_*`, `max_workers` | VLM toggle (default off), frame budget, fusion weight |

The endpoint is **OpenAI-compatible with vision**: images are `image_url` parts
(base64 data URLs) in the message `content` array — the same `OpenAIModel`/
`OpenAIProvider` wiring as `analyze.py`, plus image parts. Validate the gemma/omlx
endpoint accepts this shape and returns parseable structured output in Phase 0.

---

## 4. Opportunity map (re-ranked; **ordering is content-dependent — see §8.1**)

> The smoke-test sample (a person talking in a kitchen) is the dominant OpusClip
> case: talking-head / podcast / educational, with near-zero visual variance.
> For *that* content, frame-level "engagement" re-ranking adds little, and
> **active-speaker / salient framing is the bigger lever**. For multi-speaker or
> cut-heavy footage the ranking flips. So the A-vs-B order below is provisional
> until the user confirms their dominant content type.

### B. Salient-subject / active-speaker reframing — **likely highest value**
Today the crop centers on a detected face or the frame center. A VLM names the
moment's salient region (which speaker is talking, the slide, the product, the
on-screen caption) to drive `calculate_crop_box`. Fixes "subject is off to one
side / b-roll center-cropped badly" — the real differentiator for multi-person
and cut-heavy video.

### A. Visual engagement re-ranking of candidates — **high, but content-dependent**
Keep transcript-based candidate generation; add a VLM pass that scores each
candidate's sampled frames (motion/scene change, on-screen text, reaction,
demonstration) and **fuses** with the transcript score. Big lever for visually
dynamic content; marginal for static talking-head.

### C. Auto thumbnail / hook-frame selection — **high, low effort**
Pick the single most arresting frame per clip (clear face, peak expression,
on-screen text) for a cover image / hook. Cheap: one VLM call over a few frames.

### D. Auto titles/hooks/hashtags from frames — **LOW priority**
The text LLM already writes titles from the transcript; a frame rarely improves
the title materially. Defer.

### NOT VLM work (do with deterministic ffmpeg instead — respects P12 "never reinvent")
- **Scene/shot-boundary detection** → ffmpeg `select='gt(scene,<thresh>)'`. Cheap,
  deterministic, gate-testable. Do **not** spend a 16 GB VLM on cut detection.
- **Quality/safety filtering** (blurry/dark/frozen) → ffmpeg signal stats
  (brightness/variance/freeze detect). Deterministic and cheap.
- Re-scoped as small ffmpeg utilities, these *help* the determinism story and can
  ship inside the gate without the VLM boundary above.

---

## 5. Recommended architecture

New module `src/pipeline/vision.py` owning frame sampling + the VLM seam, returning
typed results; `video_service` calls it as an **optional, default-off** stage;
`analyze.py` / `face_detect` consume its output. Mirrors existing module
boundaries and the `# start <path>` / structlog / `get_config()` / typed
conventions.

```
download ─► transcribe ─► analyze (transcript) ─┐
                                                ├─► [VLM vision stage, default OFF] ─► fuse ─► clips
        frame sampling (ffmpeg) ────────────────┘     deterministic core in-gate;
                                                       VLM call in e2e tier only
```

Design rules: additive & graceful (disabled == today's behavior); **frugal
sampling** (seconds/image on a 16 GB model → sparse sampling, hard per-video frame
budget, run within `max_workers`, timeouts like `ffmpeg_timeout`); **cache** VLM
results by (video hash, timestamp) like the transcript cache; **offline-first**
preserved (local endpoint, no new cloud dep unless opted in).

---

## 6. Phased roadmap

**Phase 0 — Spike (½–1 day).** `vision.py` with one function: sample K frames and
get a structured VLM judgment via the OpenAI vision message format against the
gemma endpoint. Output: go/no-go on latency and message-format compatibility.
Lives in the e2e tier from day one.

**Phase 1 — first real feature: A *or* B depending on §8.1.** Default-off, fusion
weight 0, deterministic core 100% unit-tested in the gate, VLM call e2e-only.
- If content is multi-speaker/cut-heavy → **B (framing)** first.
- If content is visually dynamic single-stream → **A (re-ranking)** first.

**Phase 2 — the other of A/B.** **Regression callout:** changing
`calculate_crop_box`'s input priority (VLM subject over face) risks the
face-centered crop the smoke test just validated. Keep face/center as the
*gate-tested* fallback behind the graceful boundary; verify the VLM-framing path in
the e2e tier only.

**Phase 3 — thumbnails/hook frames (C).** Surface in the task page.

**Parallel, non-VLM track:** ship scene-boundary + quality-filter as deterministic
ffmpeg utilities whenever convenient (independent of the VLM boundary, fully
in-gate).

---

## 7. Risks & constraints (ordered by real danger)

1. **Gate/coverage/determinism collision (the real one).** Resolved only by §2's
   boundary. The failure mode is silent: someone mocks the VLM to keep 100%,
   re-importing mock-coverage. Bank §2 before the first PR.
2. **Phase-2 crop regression.** VLM framing must not displace the tested
   face/center crop as the default-on path; it's an opt-in override with the
   tested fallback intact.
3. **Latency/cost.** VLM per-frame dominates. Sparse sampling, frame budget,
   batching, concurrency caps, caching.
4. **Endpoint format drift.** Validate gemma/omlx vision message shape + structured
   output in Phase 0.
5. **Non-determinism.** VLM is a re-ranker/advisor over the deterministic backbone,
   not the sole selector — keeps output stable and explainable.

---

## 8. Open decisions (need your input)

1. **Dominant content type? (gates Phase-1 A-vs-B order — answer this first.)**
   Mostly single-speaker talking-head/podcast/educational → **B (framing)** first.
   Multi-speaker / cut-heavy / visually dynamic → **A (re-ranking)** first.
2. **Latency budget** per video for the vision pass (sets sampling density / frame
   budget).
3. **Offline-only** local VLM, or allow a cloud VLM fallback for speed/quality?
4. **Determinism:** VLM as a re-ranker over deterministic selection
   (recommended), or proposing segments directly?

---

*Next step after sign-off: Phase 0 spike (e2e-tier) to de-risk latency/format,
then a brainstorming pass to lock Phase-1 scope, the deterministic/VLM test split,
and the fusion design — before building.*
