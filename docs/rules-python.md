# RULES-PYTHON-V2 — Python 3.12/3.11 Development Standards

**Target:** Python 3.12 preferred, 3.11 minimum. macOS/zsh. Governs all code generation and modification.

---

## PART 1: FIRST PRINCIPLES

Precedence: P1 overrides all. Each principle overrides all subsequent ones.

| #   | Principle                    | Rule                                                                                                              |
| --- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| P1  | Fix Over Create              | Modify existing code; create only when `radon cc` ≥ C or structure mandates. No page C or lower. Never average.   |
| P2  | Reusable Testing             | No one-off scripts; single quality utility in `src/scripts/`; tests in `tests/`                                   |
| P3  | Docs Location                | All docs in `docs/`; sole exception: `CLAUDE.md` at root                                                          |
| P4  | Never Defer                  | Clean code first priority; no "fix later"; no "out of scope"; no "unrelated"; hard work now                       |
| P5  | Use Agents                   | Parallel context windows; always use for non-dependent tasks                                                      |
| P6  | Anti-Elision                 | Exhaustive generation required. Stubs/truncation/`...`/`pass`/`# TODO` prohibited                                 |
| P7  | Contextual Strictness        | Pre-authoring source inspection mandatory. Zero assumption of signatures/state. Read before write                 |
| P8  | Explicit Failure Propagation | Zero exception swallowing. Boundary validation → immediate custom exceptions. `None` signals absence, not failure |
| P9  | Idempotent Mutation          | Execution multiplicity → identical state. Verify existing state pre-mutation                                      |
| P10 | Simplicity                   | Minimum complexity for current task; no premature abstraction; no patterns unless demonstrably required           |
| P11 | Test Coverage                | 100% test coverage, 100% passing unit and E2E. < 100% = FAILURE                                                   |
| P12 | Never Reinvent the Wheel     | Prefer existing proven FOSS packages/software instead of writing new custom code                                  |

---

## PART 2: HARD CONSTRAINTS

### 2.1 Banned Patterns

**Elision (→ P6):** `pass`/`...` bodies, `raise NotImplementedError` (non-`@abstractmethod`), `# TODO`/`# placeholder` comments.

> Inability to implement → state it in prose. Never emit placeholder code.

**Type annotation violations:**

```python
# BANNED — use builtins + | syntax
from typing import List, Dict, Union, Optional
List[str]       # → list[str]
Dict[str, int]  # → dict[str, int]
Union[X, Y]     # → X | Y
Optional[X]     # → X | None
```

**Security violations (all → BANNED):**

| Pattern                                           | Risk               | Replacement                                        |
| ------------------------------------------------- | ------------------ | -------------------------------------------------- |
| `pickle.loads(untrusted)`                         | RCE                | JSON + Pydantic schema                             |
| `yaml.load()` without SafeLoader                  | RCE                | `yaml.safe_load()`                                 |
| `eval()`/`exec()`/`compile()` on user input       | RCE                | `ast.literal_eval()` or parser                     |
| `subprocess.run(cmd, shell=True)` with user input | Cmd injection      | List-form subprocess                               |
| `os.system()`/`os.popen()`                        | Cmd injection      | `subprocess.run([], shell=False)`                  |
| `random` for security tokens                      | Predictable        | `secrets.token_urlsafe(32)`                        |
| f-string/format in SQLAlchemy `text()`            | SQLi               | Parameterized `text("... :param", {"param": val})` |
| `verify=False` in HTTPX/requests                  | MitM               | Always `verify=True`                               |
| `tempfile.mktemp()`                               | Race condition     | `tempfile.mkstemp()`                               |
| `assert` for runtime validation                   | Bypassed with `-O` | `if/raise`                                         |
| `__eq__` for secret comparison                    | Timing attack      | `hmac.compare_digest()`                            |
| `xml.etree` with untrusted XML                    | XXE                | `defusedxml`                                       |
| `shelve`/`marshal`/`dill` on untrusted data       | RCE                | Pydantic schema                                    |
| `jsonpickle` on untrusted data                    | RCE                | Structured Pydantic schema                         |

**Also banned:** mutable defaults · bare `except:` · circular imports · global mutation · magic numbers · hardcoded secrets · unvalidated inputs · debugger remnants (`breakpoint()`/`pdb`/`ipdb`) · `print()` (→ structlog) · deprecated typing imports (`List`/`Dict`/`Union`/`Optional` → builtins+`|`) · `poetry` (→ uv) · `tenacity` (→ stamina) · `tqdm` (→ rich.progress) · `requests` (→ HTTPX) · `logging` stdlib (→ structlog) · `autopep8`/`docformatter` (→ ruff)

### 2.2 Complexity Limits

All enforced via ruff. Violations MUST be refactored before commit.

| Limit                            | Max | Ruff Rule |
| -------------------------------- | --- | --------- |
| Statements per function          | 50  | `PLR0915` |
| Cyclomatic complexity            | 10  | `C901`    |
| Parameters per function          | 5   | `PLR0913` |
| Return statements                | 6   | `PLR0911` |
| Branches per function            | 12  | `PLR0912` |
| Inheritance depth                | 3   | —         |
| Nesting levels (inside function) | 4   | —         |

### 2.3 Abstraction Limits

- No ABC/Protocol without 3+ concrete implementations **extant now**
- No passthrough wrappers (sole body = single delegating call)
- No class with `__init__` + one method → function
- No stateless class → module with functions

### 2.4 DRY Limits

- 4+ shared consecutive lines → extract (named after function, not origin)
- Copy-paste + name/literal substitution → parameterize
- Pre-authoring: search for ≥80%-similar implementations; reuse/extend (→ P7)
- Single-use extraction only if readability gain is measurable
- Stdlib (`itertools`/`functools`/`collections`) before reimplementation

### 2.5 Design Principles

| Principle | Mandate                                                               |
| --------- | --------------------------------------------------------------------- |
| DRY       | Single implementation per concept; §2.4 enforces                      |
| SPOT      | One authoritative source per fact/config value                        |
| YAGNI     | No speculative features; build only what's needed now                 |
| SOLID     | SR/OC/L/IS/DI; violated by God classes and deep inheritance           |
| GRASP     | Assign responsibility to the class with the most relevant information |

### 2.6 Package Management

- **uv ONLY** — `uv init`, `uv add`, `uv run`, `uv sync`
- **poetry BANNED** — do not create `pyproject.toml` with `[tool.poetry]`
- **pip BANNED for project management** — use `uv pip` if pip syntax needed in CI

---

## PART 3: STANDARDS

### 3.1 Project Structure

| Requirement     | Rule                                                                              |
| --------------- | --------------------------------------------------------------------------------- |
| File markers    | `# start src/example/file.py` and `# end src/example/file.py`                     |
| Imports         | Absolute from source root only; no relative imports                               |
| Entry point     | `main.py` orchestrates only; no core logic; invoke via `python -m {project}.main` |
| Complexity gate | No file exceeds radon cc grade B; C/D/E MUST be refactored                        |

**Required files:** `docs/prd.md`, `checkpython.sh` (never modify), `.pre-commit-config.yaml`

### 3.2 Configuration

| Rule               | Detail                                                                     |
| ------------------ | -------------------------------------------------------------------------- |
| No env vars        | `config.yml` → settings; `credentials.yml` → secrets                       |
| Pydantic parsing   | `pydantic-settings` loads all YAML; models validated at startup            |
| Gitignore          | `credentials.yml` in `.gitignore`; ship `credentials.yml.dist` as template |
| Immutability       | Never overwrite user-set tokens/keys/passwords                             |
| Idempotency (→ P9) | Config setup must be re-runnable; verify state before mutation             |
| No hardcoding      | All values in config; none inline in code                                  |

### 3.3 CLI

- **Typer** for all CLI
- `config.yml` is primary config; CLI flags override YAML (`--dry-run`)
- No other CLI argument forms for configuration

### 3.4 Type Hints (3.12 syntax)

```python
# 3.12 preferred
type Point = tuple[float, float]          # type alias (3.12)
type Vector[T] = list[T]                  # generic alias (3.12)

class Stack[T]:                           # generic class (3.12)
    def push(self, item: T) -> None: ...

def first[T](lst: list[T]) -> T:          # generic function (3.12)
    return lst[0]

from typing import override, Self

class Child(Parent):
    @override                             # marks intentional override (3.12)
    def method(self) -> Self:
        return self

# 3.11 fallbacks
from typing import TypeAlias, TypeVar, Generic
Point: TypeAlias = tuple[float, float]    # 3.11 type alias
T = TypeVar("T")
class Stack(Generic[T]): ...             # 3.11 generic class
from typing_extensions import override   # 3.11 @override
```

**Always use:**

```python
def process(items: list[str]) -> dict[str, int]: ...
def fetch(url: str) -> bytes | None: ...         # X | Y not Union
```

### 3.5 Core Libraries

| Domain                        | Library           | Rule                                                        |
| ----------------------------- | ----------------- | ----------------------------------------------------------- |
| Package mgmt                  | uv                | ONLY; poetry BANNED                                         |
| Validation                    | Pydantic          | All config/data validation; `strict=True`, `extra="forbid"` |
| Config loading                | pydantic-settings | All YAML/secrets config loading                             |
| Database                      | SQLAlchemy        | All DB ops via Core or ORM; no raw SQL strings              |
| Migrations                    | Alembic           | All schema changes; no manual DB modifications              |
| HTTP                          | HTTPX             | All external HTTP; sync or async client; never requests     |
| CLI                           | Typer             | All CLI interfaces                                          |
| Logging                       | structlog         | All logging; NEVER stdlib logging in application code       |
| Console/Progress              | rich              | All console output, progress bars, tables, tracebacks       |
| Retries                       | stamina           | All retry logic; NEVER tenacity                             |
| JSON                          | orjson            | All JSON serialization/deserialization                      |
| DataFrames                    | polars            | New projects; pandas acceptable for existing                |
| High-throughput serialization | msgspec           | Data pipelines requiring high serialization throughput      |

### 3.6 Logging (structlog)

```python
import structlog
log = structlog.get_logger()

# Production: JSON output. Development: colored console output.
# Configuration in config.yml: log_level, log_file (timestamped in logs/)

log.info("processing.complete", records=150, duration_s=3.2)
log.warning("rate_limit.approaching", usage_pct=85, limit=1000)
log.error("connection.failed", host="api.example.com", retries=3, exc_info=True)

# Bind context once; appears in all subsequent entries
log = log.bind(request_id="abc123", user_id=42)
```

**Rules:** No secrets/PII/request-body logging · `log.debug()` not `print()` · level via `config.yml` · strip newlines from user strings (log-forging prevention)

### 3.7 Error Handling

→ P8 (Explicit Failure Propagation): zero swallowing; boundary validation → immediate custom exceptions; `None` signals absence, not failure.

- Custom exception hierarchy per project
- `stamina` for all retries; bare `except:` BANNED
- `except Exception` MUST NOT expose stack traces to clients
- Zero test output = complete failure; silence ≠ success

```python
import stamina

@stamina.retry(on=httpx.HTTPError, attempts=3)
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### 3.8 Security

#### Input Validation

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated, Literal

class UserInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")  # reject unknowns, no coercion

    username: Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")]
    role: Literal["user", "admin", "viewer"]  # enum validation
    # SecretStr prevents repr/logging leaks:
    password: SecretStr
```

| Config                                  | Effect                                |
| --------------------------------------- | ------------------------------------- |
| `strict=True`                           | No coercion (`"123"` ≠ `int`)         |
| `extra="forbid"`                        | Mass-assignment prevention            |
| `Literal[...]`                          | Enum validation                       |
| `SecretStr`                             | Prevents repr/log leaks               |
| `@field_validator` / `@model_validator` | Single-field / cross-field validation |

#### Database (SQLAlchemy)

```python
# SAFE — ORM auto-parameterizes
session.query(User).filter(User.id == user_id)

# SAFE — explicit parameterization
session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

# BANNED — SQLi
session.execute(text(f"SELECT * FROM users WHERE name = '{name}'"))
```

- Dynamic col/table names: allowlist validation before use

#### HTTP (HTTPX)

```python
client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    follow_redirects=False,  # validate targets manually; SSRF prevention
    verify=True,             # NEVER False
    http2=True,
)
```

Reuse client instances · always `raise_for_status()` · stream large responses with byte cap · SSRF: check `ipaddress.ip_address(ip).is_private` post-DNS resolution

#### Secrets

`credentials.yml` + `SecretStr` + `0600` perms · `detect-secrets` pre-commit · no Docker `ENV` (image history) · `hmac.compare_digest()` for all comparisons

#### Access Control

Service-layer authz (not route decorators alone) · default-deny · `Path.resolve()` + base-dir confirmation for file paths

### 3.9 Testing

100% test coverage mandatory. < 100% = FAILURE
100% passing unit tests mandatory. < 100% = FAILURE
100% E2E end to end integration tests mandatory. < 100% = FAILURE

```python
# pytest with coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80
```

| Category          | Tool                                        |
| ----------------- | ------------------------------------------- |
| Model validation  | Pydantic + pytest                           |
| DB logic          | SQLAlchemy + test DB                        |
| HTTP interactions | `pytest-httpx` (no real HTTP in unit tests) |
| Migrations        | Alembic + pytest                            |
| CLI overrides     | Typer + pytest                              |
| Property-based    | `hypothesis` (parsing/validation)           |
| Mutation          | `mutmut` (critical business logic)          |

### 3.10 Progress & Reporting

**rich** for all progress/tables/tracebacks. Reports: HTML + Tailwind + d3.js; client-side rendering only.

```python
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

with Progress(SpinnerColumn(), "[progress.description]{task.description}", TimeElapsedColumn()) as progress:
    task = progress.add_task("Processing...", total=len(items))
    for item in items:
        process(item)
        progress.advance(task)
```

---

## PART 4: QUALITY GATE

### Tier 1 — Gate (Must Pass Before Commit)

| Tool   | Command                                       | Purpose              |
| ------ | --------------------------------------------- | -------------------- |
| ruff   | `ruff check src/`                             | Linting (800+ rules) |
| ruff   | `ruff format src/`                            | Formatting           |
| mypy   | `mypy src/`                                   | Type checking        |
| pytest | `pytest tests/ --cov=src --cov-fail-under=80` | Tests + coverage     |
| deptry | `deptry src/`                                 | Dependency analysis  |

### Tier 2 — Quality Analysis

| Tool        | Command                            | Purpose                     |
| ----------- | ---------------------------------- | --------------------------- |
| radon       | `radon cc src/ -a -nb`             | Cyclomatic complexity       |
| bandit      | `bandit -r src/`                   | Security scanning           |
| interrogate | `interrogate src/`                 | Docstring coverage          |
| pylint      | `pylint src/`                      | Deep linting                |
| dodgy       | `dodgy`                            | Hardcoded secrets in source |
| cohesion    | `cohesion --below=50 src/`         | God class detection         |
| refurb      | `refurb src/`                      | Modernization suggestions   |
| vulture     | `vulture src/ --min-confidence 80` | Dead code                   |

### Tier 3 — Advanced

| Tool      | Command                                                       | Purpose                                            |
| --------- | ------------------------------------------------------------- | -------------------------------------------------- |
| xenon     | `xenon src/ --max-absolute B`                                 | Complexity enforcement                             |
| semgrep   | `semgrep --config auto src/`                                  | Security pattern detection                         |
| pip-audit | `pip-audit`                                                   | Dependency vulnerabilities                         |
| pyright   | `pyright src/`                                                | Additional type checking (faster, better generics) |
| jscpd     | `jscpd --min-lines 4 --min-tokens 50 --languages python src/` | Copy-paste detection                               |

### Specialized Tools

| Tool        | Purpose                                             |
| ----------- | --------------------------------------------------- |
| hypothesis  | Property-based testing                              |
| mutmut      | Mutation testing                                    |
| py-spy      | Performance profiling                               |
| wily        | Complexity trends                                   |
| beartype    | O(1) runtime type checking                          |
| typeguard   | Runtime type checking via decorators                |
| pydeps      | Dependency visualization                            |
| python-rope | Refactoring                                         |
| pandera     | DataFrame validation                                |
| instructor  | LLM structured outputs                              |
| orjson      | Fast JSON (also Tier 1 library)                     |
| msgspec     | High-throughput serialization (also Tier 1 library) |

### Ruff Configuration

```toml
[tool.ruff.lint]
select = [
  "E", "W",    # pycodestyle
  "F",         # pyflakes
  "B",         # bugbear
  "I",         # isort
  "UP",        # pyupgrade
  "TRY",       # exception handling
  "SIM",       # simplification
  "FURB",      # reimplemented stdlib
  "PIE790",    # anti-elision (pass/ellipsis)
  "ARG",       # unused args
  "C901",      # complexity
  "PLR0911", "PLR0912", "PLR0913", "PLR0915",  # limits
  "S",         # security (bandit subset)
  "TCH",       # type-checking imports
  "D",         # pydocstyle
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-returns = 6
max-branches = 12
max-statements = 50
```

---

## PART 5: 9-DIMENSION QA FRAMEWORK

| Dimension      | Question                              |
| -------------- | ------------------------------------- |
| Good           | What's working correctly?             |
| Bad            | What's broken or incorrect?           |
| Missing        | What functionality is absent?         |
| Unnecessary    | What code/features are superfluous?   |
| Fixed          | What was repaired in this change?     |
| Newly Broken   | What previously worked but now fails? |
| Silent Errors  | What hidden failures exist?           |
| Overengineered | What is unnecessarily complex?        |
| Dead           | What is technical debt/dead code?     |

---

## PART 6: VUW METHODOLOGY

**Verifiable Units of Work** — micro-plans for disciplined debugging.

| Element            | Rule                                                            |
| ------------------ | --------------------------------------------------------------- |
| Granularity        | One file or one error per VUW                                   |
| Definition of Done | All checklist items pass                                        |
| Execution          | Sequential; complete before next VUW                            |
| Instructions       | Literal; assume nothing                                         |
| Pre-work           | `git commit` before any changes                                 |
| Steps              | Exact code/paths; show changes as git diff format               |
| Verification       | `./checkpython.sh` clean, all tests pass, `ruff` + `mypy` clean |
| Post-work          | `git commit` after verification passes                          |

**Campaign priority:** (1) Application Stability — fix `pytest` blockers → (2) Type Safety — zero `mypy` errors → (3) Code Quality — zero `ruff` errors

---

## PART 7: PYTHON 3.12 FEATURES REFERENCE

### Type System (PEP 695) — 3.12 preferred; 3.11 fallbacks shown

| Feature          | 3.12                               | 3.11 Fallback                            |
| ---------------- | ---------------------------------- | ---------------------------------------- |
| Type alias       | `type Point = tuple[float, float]` | `Point: TypeAlias = tuple[float, float]` |
| Generic alias    | `type Vector[T] = list[T]`         | `TypeVar` + `TypeAlias`                  |
| Generic class    | `class Stack[T]:`                  | `class Stack(Generic[T]):`               |
| Generic function | `def first[T](lst: list[T]) -> T:` | `T = TypeVar("T")` + annotation          |
| `@override`      | `from typing import override`      | `from typing_extensions import override` |

### F-String Improvements (PEP 701) — 3.12 only

| Feature               | 3.12                                    |
| --------------------- | --------------------------------------- |
| Nested same-quotes    | `f"result: {', '.join(items)}"`         |
| Backslashes in expr   | `f"{'\n'.join(lines)}"`                 |
| Multi-line + comments | Expressions span lines, may include `#` |

### Standard Library Additions

| Feature                          | Usage                                     | Min  |
| -------------------------------- | ----------------------------------------- | ---- |
| `itertools.batched(it, n)`       | Yield size-n tuples (last may be smaller) | 3.12 |
| `pathlib.Path.walk()`            | `os.walk()` returning `Path` objects      | 3.12 |
| `Path.relative_to(walk_up=True)` | Allows `..` in relative paths             | 3.12 |
| `Path.glob(case_sensitive=)`     | Explicit case sensitivity                 | 3.12 |
| `tomllib`                        | TOML parsing (stdlib)                     | 3.11 |
| `match-case`                     | Pattern matching                          | 3.10 |
| `except*`                        | Exception groups                          | 3.11 |
| `Self` type                      | Class method return types                 | 3.11 |
| `dataclass(slots=True)`          | Memory-efficient dataclasses              | 3.10 |
| `contextlib.chdir`               | Context manager for dir changes           | 3.11 |
| `sys.monitoring`                 | Low-overhead debugger/profiler API        | 3.12 |
