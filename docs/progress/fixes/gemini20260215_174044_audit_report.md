# SupoClip Full Code Audit Report
**Date:** February 15, 2026
**Status:** 🛑 CRITICAL FAILURES IDENTIFIED

## Executive Summary
The SupoClip project demonstrates a strong architectural foundation using modern tools (FastAPI, Pydantic AI, SQLAlchemy 2.0, Next.js 15), but suffers from severe "documentation rot," significant violations of established Python coding standards, and a critical configuration conflict that prevents the test suite from executing.

---

## 🟢 What's Good
*   **Modern Tech Stack:** Excellent choice of `uv` for dependency management, `Pydantic AI` for LLM orchestration, and `SQLAlchemy 2.0` with Mapped types.
*   **Layered Architecture:** Clear separation of concerns in `backend/src/` with `services/`, `repositories/`, and `api/`.
*   **FastAPI Implementation:** Clean use of dependency injection and modern FastAPI patterns (lifespan, routers).
*   **Local-First AI:** Integration with `parakeet-mlx` for offline transcription is a high-value feature.

## ❌ What's Bad
*   **Monolithic Bloat:** `backend/src/video_utils.py` is **1,933 lines long**, violating the 750-line maximum specified in `CLAUDE.MD` and `rules-python.md`.
*   **Configuration Conflict:** The root `.env` defines `DATABASE_URL=file:./supoclip.db` (Prisma format), which overrides the `backend/.env` setting and causes SQLAlchemy to crash during startup/testing (`sqlalchemy.exc.ArgumentError`).
*   **Standard Violations:**
    *   **Direct DB Access:** `video_utils.py` imports `sqlite3` and executes raw SQL, bypassing the SQLAlchemy ORM/Repository layer.
    *   **Raw SQL in App:** `main.py` contains raw SQL strings in several endpoints.
    *   **Missing File Markers:** Many files (e.g., `main.py`, `tasks.py`) lack the mandatory `# start path/to/file.py` comments.
*   **Complexity:** `create_optimized_clip` in `video_utils.py` has a Radon grade **C**, indicating it is too complex and needs refactoring.

## ❓ What's Missing
*   **Frontend Tests:** `frontend/` contains no actual tests despite having Jest configured. `npm run test:ci` reports 0 matches.
*   **Waitlist Tests:** The `waitlist/` application has no testing infrastructure or tests.
*   **CI/CD Pipeline:** No evidence of an automated CI pipeline in the repository structure.

## 🗑️ What's Unnecessary / Dead Code
*   **Documentation Drift:** `.serena/memories/project_overview.md` and `tech_stack.md` still reference **Redis**, **arq**, and **PostgreSQL**. The code has actually moved to a local **asyncio.Queue** and **SQLite**. This "ghost architecture" in docs is dangerous for new developers.

## 🛠️ What's Fixed (since last review)
*   The project successfully transitioned to `uv` for package management.
*   Transition from `AssemblyAI` (cloud) to `parakeet-mlx` (local) for transcription appears complete in the code.

## 💥 What's Newly Broken
*   **Test Suite execution:** The entire backend test suite is currently un-runnable due to the `DATABASE_URL` parsing error mentioned above.

## 🤫 Silent Errors
*   **Environment Variable Collisions:** The root `.env` silently poisoning the backend environment is a major "invisible" issue that developers will struggle to debug without deep SQLAlchemy knowledge.

## 🐷 Overengineered / Overcomplicated
*   **Video Processing Logic:** The `video_utils.py` file attempts to handle too many responsibilities: font resolution, face detection (3 different methods), subtitle positioning, and clip compositing. These should be separate service classes.

## 🚮 Technical Debt
*   **Raw SQL Dependency:** The reliance on `sqlite3` direct calls in `video_utils.py` prevents easy migration to other database backends (like PostgreSQL) in the future.
*   **Deprecated Endpoints:** `main.py` still contains a `/start` endpoint marked as deprecated (410 Gone) which should be removed to reduce noise.

---

## 📏 Python 3.11 Standard Compliance (rules-python.md)

| Rule | Status | Notes |
|------|--------|-------|
| **File Path Markers** | ❌ FAIL | Inconsistent application across the backend. |
| **Max File Length (750)**| ❌ FAIL | `video_utils.py` is ~2.5x the limit. |
| **No Raw SQL** | ❌ FAIL | Found in `main.py` and `video_utils.py`. |
| **Complexity < Grade B** | ❌ FAIL | `create_optimized_clip` is Grade C. |
| **Type Hints** | ✅ PASS | Good usage of modern Python 3.11 type hints. |
| **Google Docstrings** | 🟡 PARTIAL | Many functions lack complete Google-style docstrings. |

---

## 📋 Recommended Action Plan (VUWs)

### Campaign 1: Fix Blockers & Configuration
1. **VUW_FIX-001:** Standardize `DATABASE_URL` between root and backend `.env` files to support both Prisma and SQLAlchemy.
2. **VUW_FIX-002:** Fix `backend/src/database.py` to handle potential URL parsing edge cases.

### Campaign 2: Architecture Realignment
1. **VUW_DOC-001:** Update all memory files in `.serena/` to reflect the move to SQLite and local job queues.
2. **VUW_REFACTOR-001:** Split `video_utils.py` into smaller modules: `face_detection.py`, `font_service.py`, and `compositor.py`.
3. **VUW_REFACTOR-002:** Replace raw SQL in `main.py` with Repository method calls.

### Campaign 3: Quality Enforcement
1. **VUW_QA-001:** Add mandatory file markers to all Python files in `backend/src`.
2. **VUW_TEST-001:** Implement baseline unit tests for the Frontend components.
