# Pre-Release Refinement Checklist: SupoClip

## Code Quality

- [ ] `./checkpython.sh` passes with zero errors
- [ ] All `ruff check` warnings resolved
- [ ] All `mypy` type errors resolved
- [ ] No bare `except` clauses
- [ ] No unused imports or dead code
- [ ] No magic numbers (all extracted to named constants)
- [ ] All functions have type hints
- [ ] Google-style docstrings on public functions
- [ ] File path markers on all backend source files
- [ ] Maximum radon complexity grade B (no C or worse)

## Testing

- [ ] All pytest tests pass
- [ ] Coverage meets 80% threshold
- [ ] Test fixtures use isolated test database
- [ ] No flaky tests (run suite 3x to confirm)
- [ ] Edge cases covered: empty transcript, zero-duration clips, missing fonts

## Security

- [ ] No hardcoded secrets in source
- [ ] `.env` files in `.gitignore`
- [ ] Database files in `.gitignore`
- [ ] API endpoints validate input via Pydantic models
- [ ] File upload validates file type and size
- [ ] No SQL injection vectors (parameterized queries only)

## Configuration

- [ ] Config class uses Pydantic BaseSettings
- [ ] No `os.getenv()` calls outside Config
- [ ] All environment variables documented in CLAUDE.md
- [ ] Sensible defaults for all configuration values
- [ ] `.env.example` provided with placeholder values

## Frontend

- [ ] `npm run build` succeeds without warnings
- [ ] `npm run lint` passes
- [ ] No TypeScript `any` types
- [ ] Loading states for async operations
- [ ] Error boundaries around critical components
- [ ] Responsive layout tested at mobile and desktop breakpoints

## Documentation

- [ ] `docs/prd.md` up to date
- [ ] `docs/workplan.md` reflects current state
- [ ] `docs/standards.md` consolidated and accurate
- [ ] `CLAUDE.md` reflects actual tech stack (no stale references)
- [ ] API documentation accessible at `/docs`

## Dependencies

- [ ] No unused dependencies (`deptry` clean)
- [ ] No known vulnerabilities (`pip-audit` clean)
- [ ] Lock files committed (`uv.lock`, `package-lock.json`)
- [ ] Python 3.11+ required, documented in pyproject.toml

## Git Hygiene

- [ ] No committed artifacts (`.db`, `.coverage`, `htmlcov/`)
- [ ] `.gitignore` covers all generated files
- [ ] Pre-commit hooks configured and working
- [ ] No large binary files in repository history
