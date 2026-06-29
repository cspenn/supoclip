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

## 4. Opportunity map — organized by **content mode**

### 4.0 `content_mode`: single / duo / multi — the organizing axis (decided)

Content type varies per video, so it is a **configured setting**, not a global
assumption. A `content_mode` with three built-in options selects the
framing/selection strategy per run:

| Mode | Meaning | Framing strategy | Visual lever |
|---|---|---|---|
| `single` | one speaker / talking-head | existing face-centered crop (`detect_face_center_multi`) is sufficient — **skip the VLM framing call** (save latency) | engagement re-ranking (A) is the visual win, since framing is already solved |
| `duo` | two speakers / interview | **active-speaker framing** — pick the currently-speaking person each moment; optionally alternate | who-is-talking (B) is the dominant lever |
| `multi` | 3+ speakers / panel / cut-heavy | salient/active-subject tracking across many subjects; denser frame sampling | salient framing (B) + scene awareness |

This dissolves the old "A-vs-B first" question: **the mode picks the strategy.**
`single` leans on A, `duo`/`multi` lean on B. The deterministic default
(`content_mode` unset / VLM off) is exactly today's behavior.

**Config mechanism (small open decision — see §8.1):** the project standard
(CLAUDE.md, `docs/spec.md`) is `.env` + Pydantic `BaseSettings` in
`src/config.py`. Recommended: add `content_mode: Literal["single","duo","multi"]`
(default `"single"`) to `Config` — consistent, validated at startup, and gate-
friendly. The request for a `config.yml` would introduce a *new* config pattern;
if richer per-profile YAML config is genuinely wanted, that's a separate,
deliberate migration of the whole config layer, not a one-off file.

**Active-speaker, build-vs-borrow (P12 check for `duo`/`multi`):** identifying the
talking person is not necessarily a VLM job. Proven, cheaper, more deterministic
options exist — audio **diarization** (who speaks when; Pyannote is already on the
FOSS-borrow roadmap) fused with **face positions** (`face_detect`), or an
audio-visual active-speaker model (TalkNet-style). Per-frame VLM is the expensive
fallback. Phase 0 should compare "diarization + faces" against "VLM points at the
active face" on a real `duo` clip before committing — the cheaper deterministic
path may win and would live entirely inside the gate.

### 4.1 Opportunities (mode-aware)

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

**No magic numbers — every VLM tunable lives in `Config` (first-principles, P-config).**
The audit's M-7 just moved hardcoded constants into config; VLM work must not
reintroduce them. Each of these is a named, defaulted, env-overridable
`Config` field, never a literal buried in code: `content_mode`, `VLM_ENABLED`,
frames-per-clip / sampling FPS, per-video frame budget, fusion weights
(transcript vs visual), score/threshold cutoffs, scene-detection threshold, VLM
request timeout, max image dimension/quality, and the active-speaker approach
toggle. Code review and `checkpython.sh` (radon/ruff) treat any bare numeric
literal in the vision path as a defect, exactly as elsewhere in the codebase.

---

## 6. Phased roadmap

**Phase 0 — Spike (½–1 day).** `vision.py` with one function: sample K frames and
get a structured VLM judgment via the OpenAI vision message format against the
gemma endpoint. Output: go/no-go on latency and message-format compatibility.
Lives in the e2e tier from day one.

*Reference smoke sources:*
- **single** — `https://www.youtube.com/watch?v=wkPL4QNlNV4` ("LLM Context Window
  Decay", talking-head; already validated end-to-end by `tests/e2e/smoke_pipeline.py`).
- **duo** — `https://www.youtube.com/watch?v=kssjy4RCKgU` ("What is Agentic SEO?",
  split-screen two-speaker; the active-speaker / `duo` framing + diarization-vs-VLM
  comparison target).
- *(add a `multi` source when that mode is scheduled.)*

### Phase 0 spike RESULT (2026-06-29) — vision is MODEL-DEPENDENT; **Qwen works**, gemma is broken

Ran `tests/e2e/vision_spike.py` against `http://127.0.0.1:8998/v1`. Both models
accept the OpenAI vision format and consume ~290 image tokens, but perception
differs sharply:

- **`gemma-4-26B-A4B-MLX-4-8` — vision BROKEN.** Synthetic solid-RED → *"Gray"*;
  real duo frame → *"solid gray, no people."* Token count fixed regardless of
  source size (32 KB JPEG vs 425 KB PNG). The pixels do not reach the model.
  **NO-GO on this model.** (Likely the 4-8 quant's vision tower or the omlx
  image-preprocessing for this build.)
- **`Qwen3.6-35B-A3B-Mixed-4-8` — vision WORKS. ✅** Solid-RED → *"...clearly a
  shade of red. FINAL: Red"*; real duo frame → *"Two people ... split-screen video
  conference"*; and a structured-output prompt returned clean JSON:
  `{"people": 2, "active_speaker": "left", "engagement": 0.85}`. Accurate
  perception **and** parseable structured output — exactly what the vision stage
  needs.

**Caveats for Qwen (these shape the design):**
- **Reasoning model.** It emits chain-of-thought, so it needs a generous output-
  token budget (CoT precedes the answer) and the parser must extract the final
  JSON/answer (it fences with ```json). Check whether the endpoint supports
  disabling thinking (Qwen `enable_thinking=false` / `/no_think`) to cut latency
  and tokens.
- **Latency.** ~3–16 s/call warm, ~79 s cold-start (one-time load). Fine for
  **sparse** sampling within a frame budget; not for dense per-frame analysis.
- **Config implication.** The VLM model is **distinct** from the text-analysis
  model → add `vlm_model` (+ `vlm_max_tokens`, `vlm_enabled`) as their own `Config`
  fields, not reusing `local_llm_model`. (No magic numbers — see §5.)

**Roadmap impact:** VLM-vision features are **UNBLOCKED** on `Qwen3.6-35B-A3B`. For
`duo`/`multi` active-speaker framing both paths are now viable — it's a
cost/quality choice, not a blocker:
- **VLM path (Qwen):** one call per sampled moment returns `active_speaker` +
  `engagement` directly. Simplest; ~seconds/call, non-deterministic → e2e-tier.
- **Deterministic path (diarization + faces):** cheaper, audio-grounded, fully
  gate-testable.

Use `tests/e2e/vision_spike.py` (`VLM_MODEL=…`) as the **entry gate** before any
VLM-vision build, and pin the chosen `vlm_model` in config.

**Phase 1 — `content_mode` config + mode-aware framing.** Add
`content_mode: Literal["single","duo","multi"]` (default `single`) to `Config`,
plus a strategy selector. `single` = today's face-centered crop (no VLM, cheap).
`duo` = active-speaker framing — built per the Phase-0 build-vs-borrow result
(diarization+faces vs VLM). Default-off for any VLM/active-speaker path;
deterministic core (mode selection, frame sampling, fallback) 100% unit-tested in
the gate; any VLM call e2e-only. **Regression callout:** changing
`calculate_crop_box`'s input priority risks the face-centered crop the smoke test
just validated — keep face/center as the *gate-tested* fallback behind the
graceful boundary.

**Phase 2 — `multi` framing + engagement re-ranking (A).** Salient/active-subject
tracking for `multi`; engagement re-ranking as the visual lever for `single`
dynamic content. Same default-off / in-gate-core / e2e-VLM boundary.

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

## 8. Decisions

**Resolved**
- **Content type → `content_mode` (single/duo/multi) config setting** that selects
  the per-video strategy (§4.0). Dissolves the A-vs-B ordering question.

**Open (need your input)**
1. **Config mechanism.** Recommended: `content_mode` (and all VLM tunables) as
   `.env` + Pydantic `BaseSettings` fields in `src/config.py` — the project
   standard. You mentioned `config.yml`; adopting YAML would be a deliberate
   migration of the whole config layer (new pattern vs the audited standard). Keep
   `.env`/`BaseSettings`, or commit to a YAML config layer?
2. **Active-speaker approach (`duo`/`multi`).** Cheaper/deterministic
   diarization+faces (or audio-visual model) vs per-frame VLM — Phase 0 compares
   both on a real `duo` clip; do you have a preference or constraint (e.g. must
   stay fully local)?
3. **Latency budget** per video for the vision pass (sets sampling density / frame
   budget — all config fields, no magic numbers).
4. **Offline-only** local VLM, or allow a cloud VLM fallback for speed/quality?
5. **Determinism:** VLM as a re-ranker over deterministic selection
   (recommended), or proposing segments directly?

---

*Next step after sign-off: Phase 0 spike (e2e-tier) to de-risk latency/format,
then a brainstorming pass to lock Phase-1 scope, the deterministic/VLM test split,
and the fusion design — before building.*
