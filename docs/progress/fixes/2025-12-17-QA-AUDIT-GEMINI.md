# QA Audit Report - 2025-12-17 (GEMINI)

## Executive Summary

The codebase is currently in a **hybrid transitional state** that differs from the documentation in `CLAUDE.md`. While `CLAUDE.md` describes a clean separation between an "old" `main.py` and a "new" `main_refactored.py`, the reality is that `main.py` has been updated to include modern features (async workers, job queues) while still retaining legacy blocking endpoints.

The "Verifiable Unit of Work" (VUW) methodology seen in recent git history is a **strong positive**, leading to stabilized features (captions, text handling). However, architectural technical debt remains high due to the coexistence of two entry points and two video processing paths (sync vs async).

---

## ✅ What's Good

1.  **Evolving `main.py`**: Contrary to being a "legacy-only" file, `main.py` *has* incorporated the new `AsyncVideoProcessingService` and `JobQueue` initialization in its lifecycle management. It is not stagnant.
2.  **VUW Workflow**: The recent git history (Nov 21-22) demonstrates a disciplined approach to fixes ("VUW_LOGO", "VUW_TEXT") with rigid "CHECKPOINT" commits. This has likely reduced regression risk.
3.  **Explicit Verification**: The codebase shows evidence of "verifiable" steps, such as `workers/tasks.py` logging explicit "WORKER RECEIVED" values to aid in debugging specific field overrides.
4.  **Type Safety Improvements**: Recent commits show attention to typing (e.g., changing `int` to `float` for millisecond precision).

## ❌ What's Bad

1.  **Architectural Confusion**: `backend/src/main_refactored.py` exists as a "clean" implementation but appears to be dead code in production. This creates a "split brain" where documentation points to one file, but reality happens in another.
2.  **Feature Duplication**: `main.py` initializes *both* `LegacySyncVideoService` (for `/start`) and `AsyncVideoProcessingService` (for `/start-with-progress`). Maintaining two parallel processing pipelines is a recipe for divergent behavior and bugs.
3.  **Inconsistent Imports**: `workers/tasks.py` uses in-function imports (`from ..database import ...`) likely to hack around circular dependency issues, indicating a structural smell in the module dependencies.
4.  **Mixed Concerns**: `main.py` acts as both a router, an app factory, and a service definitions file. It is too large (600+ lines) and does too much.

## ❓ What's Missing

1.  **Deprecation Strategy**: There is no clear path documented (or implemented) to remove the `/start` synchronous endpoint and the `LegacySyncVideoService`.
2.  **Unified Entry Point**: A decision needs to be made to either fully cut over to `main_refactored.py` structure (renaming it to `main.py`) or to refactor `main.py` to match the layered architecture in situ.
3.  **Test Coverage for Legacy**: While VUW added tests for new fixes, the legacy sync pipeline likely lacks the same level of rigorous testing as the new async pipeline.

## 🗑️ What's Unnecessary

1.  **`backend/src/main_refactored.py`**: If `main.py` is the chosen path forward (which it seems to be), this file and its associated "ideal state" fiction should be removed or merged.
2.  **`LegacySyncVideoService`**: The synchronous processing path should be obsoleted in favor of the async path, with the `/start` endpoint either removed or wrapped to wait for the async result (bad practice, but better than dual pipelines).

## 🛠️ What's Fixed

1.  **Caption Rendering**: Recent VUW commits addressed stroke width and positioning.
2.  **Text Extraction**: Fixes for verbatim text and timestamp parsing are present and verified.
3.  **Worker Integration**: `main.py` *does* now start workers, addressing a previous audit finding that claimed it didn't.

## 💥 What's Newly Broken

-   Nothing "newly" broken detected in this static analysis, but the divergence between `CLAUDE.md` documentation and the actual `main.py` reality is a "broken documentation" issue that is critical for team knowledge transfer.

## 🤫 Silent Errors

-   **Background Font Detection**: `_detect_system_fonts_background` in `main.py` catches broad `Exception` and logs it. If this fails, the app continues without system fonts, likely defaulting effectively, but potentially confusing users who expect their system fonts to appear.
-   **Worker Stop Failures**: The `lifespan` context manager catches exceptions during `queue.stop_workers()` and just logs them. This could lead to orphaned worker processes in development or unstable restarts.

## 🐷 What's Overengineered

-   **Dual processing pipelines**: Maintaining both a synchronous and an asynchronous video processing service is the definition of overengineering (or rather, incomplete migration). It requires double the maintenance for the same core business logic (processing a video).

---

## Remediation Plan

### Phase 1: Clean Up Artifacts (Immediate)
1.  **Delete `backend/src/main_refactored.py`**: It is misleading. Extract any useful router configuration if valid, but remove the file to stop the confusion.
2.  **Update `CLAUDE.md`**: Rewrite the architecture section to reflect the *actual* `main.py` hybrid state. Document that `main.py` *is* the entry point and it *does* use workers.

### Phase 2: Unify Pipelines (Short Term)
1.  **Deprecate `/start`**: distinct API endpoint for synchronous processing should be marked deprecated.
2.  **Migrate Logic**: Ensure `AsyncVideoProcessingService` has 100% feature parity with `LegacySyncVideoService`.
3.  **Kill Legacy Service**: Remove `LegacySyncVideoService` and point `/start` to return a 400 or redirect to `/start-with-progress`.

### Phase 3: Structural Refactor (Medium Term)
1.  **Extract Lifespan**: Move the complex `lifespan` logic out of `main.py` into a `lifecycle.py` or similar.
2.  **Fix Circular Imports**: Refactor `workers/tasks.py` dependencies so function-level imports are not needed.

---
**Status:** Audit Complete. awaiting user approval for implementation.
