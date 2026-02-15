# Coding Standards: SupoClip

This document consolidates the coding standards for the SupoClip project. It is the single source of truth for code style, tooling, and quality expectations.

## Python Standards (Backend)

### Language Requirements
- Python 3.11+ required
- Use modern type hints: `list[str]`, `dict[str, int]`, `X | None` (not `typing.List`, `typing.Optional`)
- PEP 8 compliance enforced via Ruff
- Google-style docstrings (PEP 257)

### Project Conventions
- **Imports**: Absolute from project root only (no relative imports)
- **File markers**: All source files start and end with `# start src/example/file.py`
- **Entry point**: `python -m src.main` (main.py orchestrates; core logic in modules)
- **Complexity**: Maximum radon grade B; grade C and below must be refactored
- **Nesting**: Maximum 2 levels of indentation depth
- **Package manager**: `uv` (not pip, not poetry)

### Configuration
- Pydantic BaseSettings for all configuration
- Environment variables via `.env` files (local development)
- No `os.getenv()` calls outside the Config class
- No hardcoded secrets or magic numbers

### Database
- SQLite via aiosqlite for async access
- SQLAlchemy models for type safety
- Async sessions via `AsyncSessionLocal` context manager
- No raw SQL strings; use SQLAlchemy Core or ORM

### Error Handling
- No bare `except:` or `except Exception:` clauses
- Define project-specific exceptions where appropriate
- Use `contextlib.suppress` for expected exceptions
- Resource safety: `with` statements and `finally` blocks

### Logging
- Python `logging` module exclusively
- Emoji indicators: startup, info, success, error, video ops, AI, download, stats
- No `print()` statements in production code
- Never log sensitive information

### Testing
- pytest for all tests
- Coverage target: 80%
- Test categories: model validation, database logic, API interactions, configuration
- Run `./checkpython.sh` before every commit

## TypeScript/React Standards (Frontend)

### Language Requirements
- TypeScript strict mode (`strict: true`, `noImplicitAny`, `strictNullChecks`)
- Next.js 15 App Router patterns
- React 19 conventions

### Project Conventions
- ShadCN UI for components
- TailwindCSS v4 for styling
- Better Auth for authentication
- Prisma Client for database access

### Quality Gates
- `npm run lint` must pass (zero ESLint errors)
- `npm run build` must succeed
- No `any` types
- Components under 200 lines

## Shared Standards

### Design Principles
| Principle | Meaning |
|-----------|---------|
| DRY | Don't Repeat Yourself |
| SPOT | Single Point of Truth |
| SOLID | Single responsibility, Open/closed, Liskov, Interface segregation, Dependency inversion |
| YAGNI | You Aren't Gonna Need It |

### Quality Gate Checklist (Backend)

| Tier | Tool | Purpose |
|------|------|---------|
| 1 | `ruff check` + `ruff format` | Linting and formatting |
| 1 | `mypy` | Type checking |
| 1 | `pytest` | Unit tests |
| 2 | `radon cc` | Cyclomatic complexity |
| 2 | `deptry` | Dependency analysis |
| 2 | `refurb` | Modernization suggestions |
| 3 | `bandit` | Security scanning |
| 3 | `pyright` | Additional type checking |

### Anti-Patterns (Never Do)
- Mutable default arguments in function signatures
- Bare `except:` clauses
- Circular imports
- Global variable overuse
- Hardcoded secrets or magic numbers
- `typing.List`, `typing.Dict`, `typing.Union` (use builtins + `|`)
- `print()` for logging
- Raw SQL strings outside repository layer
- Components created inside render functions (React)
- Missing useEffect cleanup (React)

### VUW Methodology
All debugging and code changes follow the Verifiable Units of Work pattern:
1. Git checkpoint before changes
2. Single-file or single-error scope
3. Mandatory verification via `./checkpython.sh`
4. Git checkpoint after verification passes

See CLAUDE.md for the full VUW template and campaign structure.
