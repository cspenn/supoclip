# Repository Guidelines

## Project Structure & Module Organization

SupoClip is a monorepo with three apps:

- `backend/`: FastAPI + Python 3.11 service. Core code lives in `backend/src`, with features split into `services/`, `repositories/`, and `api/routes/`.
- `frontend/`: Main Next.js 15 app in `frontend/src` (App Router). Shared UI in `frontend/src/components`, hooks in `frontend/src/hooks`, and utilities in `frontend/src/lib`.
- `waitlist/`: Next.js 15 landing page app in `waitlist/src`.

Supporting assets live in `backend/fonts`, `backend/transitions`, `frontend/public`, `waitlist/public`. Runtime output and logs commonly land in `temp/` and `logs/`. Backend tests live in `backend/tests`, while ad-hoc verification scripts and fixtures are under `tests/`.

## Build, Test, and Development Commands

Quick local boot (backend + frontend):

```bash
./start.sh
```

Backend (uses `uv`):

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv sync
python -m src.main   # auto-selects a free port
```

Frontend / Waitlist:

```bash
cd frontend && npm install && npm run dev
cd waitlist && npm install && npm run dev
```

Quality checks (backend):

```bash
cd backend && ./checkpython.sh
```

## Coding Style & Naming Conventions

- Python: follow existing FastAPI patterns in `backend/src`, keep modules small, and prefer type hints. See `docs/standards.md` for backend conventions.
- TypeScript/React: components are PascalCase (`TaskCard.tsx`), hooks start with `use` (`useTasks.ts`), and shared utilities live in `src/lib`.
- Keep new assets in the established folders (fonts in `backend/fonts`, static files in `*/public`).

## Testing Guidelines

- Backend uses pytest (see `backend/pytest.ini`). Tests are named `test_*.py` under `backend/tests`. Run: `cd backend && pytest` (use markers like `-m "not slow"`).
- Frontend uses Jest. Run `cd frontend && npm run test` (watch) or `npm run test:ci` (CI with coverage).
- Waitlist has linting only: `cd waitlist && npm run lint`.

## Commit & Pull Request Guidelines

Recent commit history uses Conventional Commits and scoped prefixes, plus VUW checkpoint entries:

- Examples: `fix(e2e): ...`, `chore(qa): ...`, `docs: ...`, `VUW_TEST-001: ...`.

For PRs, include a concise summary, list the tests you ran (commands + results), link relevant issues, and add screenshots for UI changes. Call out schema or config changes explicitly.

## Configuration & Secrets

Local dev uses `.env` files. The root `./start.sh` copies `.env.example` if needed and updates `frontend/.env.local`. Backend defaults to local-first settings in `backend/.env.example`, so API keys are optional for offline workflows.
