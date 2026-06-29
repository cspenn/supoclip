# Dead Code & Technical Debt Audit

Auditor: deadcode-frontend agent
Date: 2026-06-29
Working directory: /Users/cspenn/Documents/github/supoclip
Scope: frontend/ leftovers, phantom quality gate, root cruft, .gitignore gaps, dead Python functions

---

## 1. frontend/ — Headline Dead Code (CRITICAL)

**Size:** 37 MB on disk
**Git-tracked files:** 123
**Working-tree files still present:** 30 (of 123 tracked)
**Working-tree files deleted but NOT committed:** 93 (show as ` D` in `git status`)

### What is still present on disk

```
frontend/next-env.d.ts          (Next.js generated TypeScript env declaration)
frontend/tsconfig.tsbuildinfo   (234 KB Next.js incremental compiler state)
frontend/src/generated/prisma/  (28 files: Prisma client JS/TS, wasm binaries,
                                  platform .dylib.node and .so.node, runtime bundles)
```

Files include compiled WebAssembly (`query_engine_bg.wasm`), platform-specific native addons
(`libquery_engine-darwin-arm64.dylib.node`, `libquery_engine-linux-arm64-openssl-3.0.x.so.node`),
and the full Prisma JS client runtime.

### PRD evidence for deletion from scope

`docs/prd.md:86-88` (Architecture Migration section):

> "SupoClip was originally built as a two-process split application: a Python/FastAPI backend
> and a React/Next.js frontend... The approved redesign consolidates everything into a single
> Python process using NiceGUI..."

`docs/prd.md:68` (Non-Functional Requirements table):

> "Frontend | NiceGUI 3.0+ (Python, built on FastAPI)"

The React/Next.js frontend was explicitly removed from scope. The `frontend/` directory is
entirely dead. None of its files are imported or referenced by any Python source file.

### graphify-out pollution

667 of 2056 nodes in `graphify-out/graph.json` (32%) originate from `frontend/` files
(next-env.d.ts, prisma wasm, client.js, edge.d.ts, etc). These stale nodes inflate the
community count and distort graph navigation. The graphify-out/ directory must be regenerated
after frontend/ is removed.

### Remediation

```
git rm -r frontend/                    # Remove all 123 tracked files + stage deletions
rm -rf frontend/                       # Remove remaining working-tree files
```

Then add `frontend/` to `.gitignore` (currently only `frontend/.next/` and
`frontend/node_modules/` are ignored, not the directory itself).

After removal, regenerate: `graphify update .`

---

## 2. checkpython.sh — Phantom Quality Gate (CRITICAL)

`checkpython.sh` is referenced as the mandatory quality gate by:
- `CLAUDE.md` — 5 references ("never modify", "run before every commit", mandatory VUW checklist)
- `AGENTS.md` — `cd backend && ./checkpython.sh`
- `docs/spec.md` — "enforced by checkpython.sh and the pre-commit hook"
- `docs/rules-python.md` — referenced as mandatory

**The file does not exist** in the working tree and has **zero git history** for it.
(`git log --all -- checkpython.sh` returns empty.)

This means every developer instruction that says "run ./checkpython.sh before committing"
is a no-op. The quality gate exists only in documentation.

### Remediation

Create `checkpython.sh` implementing what `docs/spec.md` documents it should run:
- `ruff check src tests`
- `mypy src`
- `pyright src`
- `bandit -r src`
- `radon cc src -n C` (fail if any grade C or below)
- `xenon --max-average A --max-modules B --max-absolute C src`
- `grimp`
- `pytest --cov=src --cov-fail-under=100 tests/`

---

## 3. .pre-commit-config.yaml — Entirely Stale (HIGH)

`/.pre-commit-config.yaml` has all hooks scoped to `^backend/` path:

```yaml
- id: ruff
  files: ^backend/
- id: ruff-format
  files: ^backend/
- id: mypy
  files: ^backend/src/
- id: pytest
  entry: bash -c 'cd backend && uv run pytest tests/ -x -q'
  files: ^backend/
```

The `backend/` directory does **not exist**. The project root is the Python package root
(entry point is `python -m src.main`). Every pre-commit hook is a no-op — none will ever
trigger because no staged file matches `^backend/`.

### Remediation

Rewrite `.pre-commit-config.yaml` to scope hooks to `^src/` and `^tests/`:

```yaml
- id: ruff
  files: ^(src|tests)/
- id: mypy
  files: ^src/
- entry: bash -c 'uv run pytest tests/ -x -q'
  files: ^(src|tests)/
```

---

## 4. tests/verify_subtitle_renderer.py — Dead Script (HIGH)

`tests/verify_subtitle_renderer.py` (git-tracked) imports:

```python
sys.path.append(str(Path(__file__).parent.parent / "backend"))
from src.subtitle_renderer import BrowserSubtitleRenderer
```

`BrowserSubtitleRenderer` was the old Playwright-based subtitle rendering module from the
React/backend split architecture. It was deleted during the NiceGUI migration. The module
`src.subtitle_renderer` does not exist anywhere in the current codebase.

This script is not part of the pytest test suite (not discovered by pytest's standard
collection because it has no `Test` class or `test_` prefixed functions). It is a standalone
manual verification script for deleted functionality.

`tests/output/logo_test.mp4` (4.5 KB, git-tracked) is the artifact this script was intended
to produce. Both should be removed.

### Remediation

```
git rm tests/verify_subtitle_renderer.py
git rm tests/output/logo_test.mp4
rmdir tests/output   # if empty after removal
```

---

## 5. get_video_info() — Dead Production Export (MEDIUM)

`src/pipeline/download.py:256`:

```python
async def get_video_info(url: str) -> dict[str, Any]:
```

This function is **not called from any file in `src/`**. It is only referenced by tests
(`tests/unit/test_download.py:265,280`). A search of all `src/` files confirms zero
production callers.

The 100% coverage requirement forces tests for this function to exist, masking the fact
that it is a dead export — tested in isolation but never invoked in the actual pipeline
(`src/services/video_service.py` does not call it; it calls `download_youtube_video()`
directly).

### Remediation

Either remove `get_video_info()` and its tests, or integrate it into the pipeline where
video metadata could genuinely be used (e.g., to display video title/duration before
processing starts).

---

## 6. Root Cruft — Non-Critical but Polluting

### 6a. supoclip.db tracked in git

`supoclip.db` (24 KB) is a development SQLite database tracked in git
(`git ls-files supoclip.db` confirms it's tracked). The `.gitignore` has `*.db` which
should cover it, but it was apparently added before that rule existed and was never removed
from tracking.

```
git rm --cached supoclip.db
```

`.gitignore` already has `*.db` so it will stay untracked after removal.

### 6b. .gitignore gaps

Current `.gitignore` is missing entries for:

| Missing entry | Reason needed |
|---|---|
| `frontend/` | Whole directory should be excluded; currently only `.next/` and `node_modules/` are excluded |
| `graphify-out/` | 13 MB generated output, currently untracked but not gitignored (shows as `?? graphify-out/`) |
| `backend/docs/reports/` | Listed in .gitignore but `backend/` directory does not exist — dead rule |

### 6c. .serena/ partially tracked in git

`.serena/memories/*.md` (12 files) are tracked in git. `.serena/` itself is not in
`.gitignore`. The `.serena/.gitignore` only excludes `/cache`. The memories are
AI-assistant context notes that change every session and have no value as git history.

```
git rm -r --cached .serena/memories/
echo ".serena/" >> .gitignore
```

### 6d. AGENTS.md references phantom path

`AGENTS.md` contains: `cd backend && ./checkpython.sh`

Both `backend/` (the directory) and `./checkpython.sh` (the file) are phantoms. The
correct invocation should be `./checkpython.sh` from the project root once it is created.

---

## 7. Complexity Violations — Grade C Functions (MEDIUM)

Three functions violate the project standard of "grade A or B; C and below must be
refactored" (`docs/rules-python.md`, `CLAUDE.md`):

| File | Line | Function | Grade |
|---|---|---|---|
| `src/pipeline/transcribe.py` | 195 | `_tokens_from_result` | C |
| `src/pages/settings.py` | 46 | `_discover_fonts` | C |
| `src/services/video_service.py` | 266 | `process_video` | C |

These are measured empirically (radon cc, provided as ground truth). mypy and ruff pass
clean; these are logic-complexity issues, not type or style issues.

---

## 8. Removal Candidate Summary

| Candidate | Size | Git-tracked | Action |
|---|---|---|---|
| `frontend/` (all 30 remaining files) | ~37 MB | 123 files | `git rm -r frontend/` |
| `frontend/` gitignore entry | — | — | Add `frontend/` to .gitignore |
| `checkpython.sh` | 0 (does not exist) | never existed | Create it |
| `.pre-commit-config.yaml` hooks | — | tracked | Rewrite `^backend/` → `^src/` |
| `tests/verify_subtitle_renderer.py` | — | tracked | `git rm` |
| `tests/output/logo_test.mp4` | 4.5 KB | tracked | `git rm` |
| `supoclip.db` | 24 KB | tracked | `git rm --cached` |
| `.serena/memories/` | ~308 KB | 12 files | `git rm -r --cached` |
| `graphify-out/` (not tracked) | 13 MB | no | Add to .gitignore |
| `get_video_info()` | function | n/a | Remove or integrate |

**Estimated repository size reduction from frontend/ alone: ~37 MB and 123 fewer tracked files.**
**Graphify node pollution eliminated: 667 stale nodes (32% of graph).**
