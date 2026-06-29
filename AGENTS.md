# Repository Guidelines

## Project Structure & Module Organization

SupoClip is a **single all-Python application** — NiceGUI for the UI and FastAPI
for the API, running in one process with no frontend build step. There is no
React, TypeScript, Node, or monorepo.

- `src/`: application code.
  - `src/main.py`: FastAPI + NiceGUI entry point and page registration.
  - `src/config.py`: Pydantic `BaseSettings` configuration (`get_config()` singleton).
  - `src/database.py`, `src/models.py`: async SQLAlchemy + SQLite.
  - `src/exceptions.py`: centralized `SupoClipError` hierarchy.
  - `src/pages/`: NiceGUI pages (`home`, `task`, `history`, `settings`).
  - `src/pipeline/`: `download`, `transcribe`, `analyze`, `clip`, `subtitles`, `face_detect`.
  - `src/services/video_service.py`: pipeline orchestration.
- `fonts/`: custom TTF fonts for subtitle burn-in. `transitions/`: transition clips.
- `tests/`: pytest suite (`tests/unit`, `tests/integration`). Runtime output and
  logs land in `temp/` and `logs/` (gitignored).

## Build, Test, and Development Commands

Uses `uv` (not pip/poetry). ffmpeg **must be built with libass** for subtitle
burn-in (`ffmpeg -filters | grep ass`); on macOS install via the
`homebrew-ffmpeg/ffmpeg` tap if the core build lacks it.

```bash
uv sync
python -m src.main          # http://localhost:8008  (UI + API + Swagger at /docs)
uv run pytest tests/        # tests
./checkpython.sh            # mandatory quality gate (must be green before commit)
```

## Coding Style & Naming Conventions

- Python 3.11+. Type hints on all functions/methods. Google-style docstrings.
  PEP 8 via Ruff. Absolute imports from `src.*` only (no relative imports).
- Source files begin with a `# start <path>` comment.
- Use `structlog` for logging (never the stdlib `logging` module, no emoji logs).
- Read configuration via `get_config()`; no hardcoded secrets or magic numbers.
- Max radon/xenon complexity grade A or B; refactor grade C via helper extraction.

## Testing Guidelines

- pytest, files named `test_*.py`. `uv run pytest tests/`.
- 100% line+branch coverage is required, but it is a **floor over meaningful
  tests** — coverage achieved by mocking the thing under test is forbidden.
  Integration tests in `tests/integration` produce and inspect real ffmpeg
  artifacts (a real captioned `.mp4`, caption sync) and must run in the gate.
- `./checkpython.sh` runs ruff, mypy, pyright, bandit, radon, xenon, deptry,
  an import-cycle check, and the full pytest suite with coverage.

## Commit & Pull Request Guidelines

Conventional Commits with scoped prefixes; VUW checkpoint entries are common.
For PRs: concise summary, the tests you ran (commands + results), linked issues,
and explicit callouts for schema/config changes.

## Configuration & Secrets

Local dev uses a root `.env` (gitignored). Defaults are local-first (local LLM,
SQLite), so API keys are optional for offline workflows. See `docs/spec.md`.

## graphify

This project has a graphify knowledge graph at `graphify-out/`.

- Before answering architecture/codebase questions, read `graphify-out/GRAPH_REPORT.md`.
- If `graphify-out/wiki/index.md` exists, navigate it instead of raw files.
- After modifying code, run `graphify update .` to keep the graph current.
