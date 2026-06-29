# Python Best Practices Reference -- Core Sections

This document is the authoritative expanded reference for Python 3.12+ development standards. It covers sections 1-10 and 21-23. Companion sections 11-20 cover web frameworks, data science, async, and observability. All rules derive from first principles; each section explains the *why* before the *what*. Where a rule has a silent failure mode or a common footgun, that is documented explicitly -- not buried in fine print.

Target runtime: Python 3.12 preferred, 3.11 minimum. Tool management: uv exclusively.

---

## 1. First Principles {#first-principles}

The principles below form a strict precedence chain. P1 overrides everything. Each subsequent principle overrides all that follow it. When two rules appear to conflict, the higher-numbered principle yields.

### 1.1 P1: Fix Over Create {#p1-fix-over-create}

**Motivation.** Every new file is a new maintenance surface. Every new class is a new concept a reader must hold in working memory. Software complexity compounds: a codebase with 200 modules is not twice as hard to understand as one with 100 -- it is exponentially harder, because complexity lives in the *relationships* between units, not just the units themselves. P1 therefore mandates that you reach for the refactoring tool before the new-file tool.

The specific trigger for creating a new file or class is a `radon cc` grade of C or worse on the *specific function or class* that needs changing -- not the file average. Averaging masks the fact that one 50-branch monster brings the whole file's mean to C while everything else is A. The rule is: a *function* at grade C is a refactor mandate; that refactor may or may not produce a new file. A file that is merely long but internally clean does not warrant splitting.

**Antipattern.** A developer encounters a `PaymentProcessor` class with a complex `process()` method. Rather than refactoring the method, they create `PaymentProcessorV2` alongside the original.

```python
# ANTIPATTERN -- creates parallel class rather than fixing the original
class PaymentProcessorV2:
    """New, cleaner version. TODO: migrate callers."""

    def process(self, payment: Payment) -> Result:
        # Duplicated logic with minor cleanup
        ...
```

This leaves the codebase with two competing implementations, undefined migration ownership, and all the original callers still using the broken version.

**Modern Pattern.** Refactor the existing function or class. If it has grown past the complexity limit, extract *named sub-functions* (named after their function, not their origin) within the same module.

```python
# MODERN PATTERN -- refactor the existing class
class PaymentProcessor:
    """Processes payments through the configured gateway."""

    def process(self, payment: Payment) -> Result:
        validated = self._validate_payment(payment)
        authorized = self._authorize(validated)
        return self._settle(authorized)

    def _validate_payment(self, payment: Payment) -> ValidatedPayment:
        ...

    def _authorize(self, payment: ValidatedPayment) -> AuthorizedPayment:
        ...

    def _settle(self, payment: AuthorizedPayment) -> Result:
        ...
```

**Gotcha.** "Create only when `radon cc` >= C" does not mean "create freely once the threshold is crossed." It means that threshold is the *minimum bar* to justify a new file. Structure requirements (a plugin must be a separate module, a CLI entry point must be in its own file) are independent grounds for creating files and are evaluated separately.

### 1.2 P2-P12 Summary {#p2-p12}

The twelve principles govern every code-generation and modification decision. They are listed here with their enforcement mechanism.

| # | Principle | Core Rule | Enforcement |
|---|-----------|-----------|-------------|
| P1 | Fix Over Create | Modify existing; create only when `radon cc` >= C or structure mandates | Code review + radon |
| P2 | Reusable Testing | No one-off scripts; single quality utility in `src/scripts/`; tests in `tests/` | Project structure check |
| P3 | Docs Location | All docs in `docs/`; sole exception: `CLAUDE.md` at root | Project structure check |
| P4 | Never Defer | Fix it now; no "fix later", no "out of scope", no "unrelated" | Code review |
| P5 | Use Agents | Parallel context windows for non-dependent tasks | Process discipline |
| P6 | Anti-Elision | Exhaustive generation required; stubs/truncation/`...`/`pass`/`# TODO` prohibited | ruff PIE, FIX, ERA, TD rules |
| P7 | Contextual Strictness | Read source before writing; zero assumption of signatures or state | Process discipline |
| P8 | Explicit Failure Propagation | Zero exception swallowing; boundary validation -> immediate custom exceptions | ruff TRY rules + code review |
| P9 | Idempotent Mutation | Verify existing state before any mutation | Code review |
| P10 | Simplicity | Minimum complexity for current task; no premature abstraction | radon cc + complexity limits |
| P11 | Test Coverage | 100% test coverage, 100% passing; < 100% = FAILURE | pytest --cov-fail-under=100 |
| P12 | Never Reinvent | Prefer proven FOSS packages over custom implementations | deptry + code review |

**P6 -- Anti-Elision** deserves extra emphasis because it is violated the most. Generating a stub method with `pass` or `raise NotImplementedError` in a non-abstract class is not "scaffolding" -- it is incomplete code that will fail at runtime. If you cannot implement a method in the current context, state that in prose and do not emit the stub. The `ruff` rules `PIE790` (no-pass/ellipsis), `FIX` (FIXME/TODO detection), `ERA` (commented-out code), and `TD` (TODO tracking) enforce this mechanically.

**P8 -- Explicit Failure Propagation** means that `None` is a legitimate return value meaning "this thing was absent." It is NOT a signal for "something went wrong." An absent database record is `None`. A database connection failure is an exception. Never collapse these two signals into a single `None` return; callers cannot distinguish them and will silently succeed when they should fail loudly.

---

## 2. Hard Constraints {#hard-constraints}

These constraints are non-negotiable. They are not suggestions. Violations must be refactored before any commit reaches the main branch. Each constraint has a mechanical enforcement mechanism; "but the linter didn't catch it" is not an excuse.

### 2.1 Banned Patterns {#banned-patterns}

#### 2.1.1 Elision {#elision}

Elision is the practice of writing incomplete code that compiles but does not function. It is prohibited in all its forms:

- `pass` as the sole body of a non-abstract, non-test method
- `...` (Ellipsis literal) as a method body outside Protocol/abstract definitions
- `raise NotImplementedError` in any non-`@abstractmethod` context
- `# TODO`, `# FIXME`, `# placeholder`, `# implement later` comments
- Truncation markers like `# ... rest of implementation`

The ruff rules `PIE790`, `FIX001`-`FIX004`, `ERA001`, and `TD001`-`TD006` enforce these mechanically. If ruff's coverage ever has a gap, `grep -rn "NotImplementedError\|# TODO\|# FIXME" src/` in CI catches the rest.

The reason this rule exists is psychological as much as technical. Once a codebase normalizes incomplete stubs, developers stop trusting that passing tests mean anything. A stub that raises `NotImplementedError` will fail at runtime; a stub with `pass` silently does nothing; both corrupt the assumption that green CI means the code works.

#### 2.1.2 Type Annotation Violations {#type-annotations}

Python 3.9 made built-in generics subscriptable (`list[str]`, `dict[str, int]`). Python 3.10 added union syntax (`X | Y`). Python 3.12 added PEP 695 generic syntax. The `typing` module imports are legacy compatibility shims -- using them in new code is a maintenance liability and signals unfamiliarity with the current language.

**Antipattern.**

```python
# ANTIPATTERN -- legacy typing imports, banned in Python 3.12+
from typing import List, Dict, Optional, Union, Tuple

def process(
    items: List[str],
    mapping: Dict[str, int],
    callback: Optional[callable] = None,
) -> Union[List[str], None]:
    ...
```

**Modern Pattern.**

```python
# MODERN PATTERN -- built-in generics + union syntax
from collections.abc import Callable

def process(
    items: list[str],
    mapping: dict[str, int],
    callback: Callable[..., None] | None = None,
) -> list[str] | None:
    ...
```

The full ban list:

| Banned import | Replacement |
|---------------|-------------|
| `typing.List` | `list` |
| `typing.Dict` | `dict` |
| `typing.Tuple` | `tuple` |
| `typing.Set` | `set` |
| `typing.FrozenSet` | `frozenset` |
| `typing.Type` | `type` |
| `typing.Optional[X]` | `X \| None` |
| `typing.Union[X, Y]` | `X \| Y` |
| `typing.Sequence` | `collections.abc.Sequence` |
| `typing.Mapping` | `collections.abc.Mapping` |
| `typing.Callable` | `collections.abc.Callable` |
| `typing.Iterable` | `collections.abc.Iterable` |
| `typing.Iterator` | `collections.abc.Iterator` |
| `typing.Generator` | `collections.abc.Generator` |
| `typing.Awaitable` | `collections.abc.Awaitable` |

The ruff `UP` (pyupgrade) ruleset enforces these automatically.

#### 2.1.3 Security Violations {#security-violations}

Each banned pattern below has a documented exploit class. These are not theoretical -- they are the actual vulnerability classes that appear in CVE databases against Python applications.

| Pattern | Risk Class | Safe Replacement |
|---------|-----------|------------------|
| `pickle.loads(untrusted)` | Remote code execution | JSON + Pydantic schema |
| `yaml.load()` without SafeLoader | Remote code execution | `yaml.safe_load()` |
| `eval()` / `exec()` / `compile()` on user input | Remote code execution | `ast.literal_eval()` or a proper parser |
| `subprocess.run(cmd, shell=True)` with user input | Command injection | List-form with `shell=False` |
| `os.system()` / `os.popen()` | Command injection | `subprocess.run([], check=True, capture_output=True, text=True)` |
| `random` for security tokens | Predictable secrets | `secrets.token_urlsafe(32)` |
| f-string interpolation in SQLAlchemy `text()` | SQL injection | Parameterized `text("... :param", {"param": val})` |
| `verify=False` in HTTPX/requests | Man-in-the-middle | Always `verify=True` |
| `tempfile.mktemp()` | TOCTOU race condition | `tempfile.NamedTemporaryFile(delete=True)` as context manager |
| `assert` for runtime validation | Bypassed by `python -O` | `if condition: raise ValueError(...)` |
| `__eq__` for secret comparison | Timing attack | `hmac.compare_digest()` with equal-length padding |
| `xml.etree` / `lxml` with untrusted XML | XXE injection | `defusedxml` |
| `shelve` / `marshal` / `dill` on untrusted data | Remote code execution | Pydantic schema |
| `jsonpickle` on untrusted data | Remote code execution | Structured Pydantic schema |

**Critical silent error -- `subprocess.run` without `check=True`.** The replacement for `os.system()` is `subprocess.run([], shell=False)`. But `subprocess.run` does *not* raise an exception on non-zero exit codes unless you pass `check=True`. This means:

```python
# ANTIPATTERN -- silently succeeds even when the command fails
result = subprocess.run(["git", "push"], shell=False)
# result.returncode is 1 but no exception is raised
# The caller assumes push succeeded

# MODERN PATTERN -- raises CalledProcessError on non-zero exit
result = subprocess.run(
    ["git", "push"],
    check=True,
    capture_output=True,
    text=True,
    shell=False,
)
```

**Critical silent error -- `tempfile.mkstemp()` tuple return.** The banned `tempfile.mktemp()` should NOT be replaced with `tempfile.mkstemp()` directly. `mkstemp()` returns a `(fd, path)` tuple. If you write `path = tempfile.mkstemp()`, `path` is now a tuple, the file descriptor leaks, and subsequent `open(path)` calls fail with a confusing error. The correct patterns:

```python
# ANTIPATTERN -- leaks file descriptor, path is a tuple
path = tempfile.mkstemp()  # wrong: path = (3, '/tmp/tmpXXXXXX')

# CORRECT -- explicit fd handling
fd, path = tempfile.mkstemp()
try:
    os.close(fd)
    # use path ...
finally:
    os.unlink(path)

# PREFERRED -- context manager handles cleanup automatically
with tempfile.NamedTemporaryFile(delete=True, suffix=".json") as tmp:
    tmp.write(data)
    tmp.flush()
    process_file(tmp.name)
```

**Also banned (complete list):**

- Mutable default arguments: `def f(items: list = [])` -- use `None` and assign inside the body
- Bare `except:` -- always name the exception class
- Circular imports -- restructure into a dependency-safe topology
- Global mutation -- use dependency injection or module-level singletons initialized once
- Magic numbers -- named constants or config values
- Hardcoded secrets -- `credentials.yml` + `SecretStr`
- Debugger remnants: `breakpoint()`, `pdb`, `ipdb`
- `print()` for application logging -- use structlog
- Deprecated tools: `poetry` (-> uv), `tenacity` (-> stamina), `tqdm` (-> rich.progress), `requests` (-> HTTPX), stdlib `logging` in application code (-> structlog), `autopep8` / `docformatter` (-> ruff)

### 2.2 Complexity Limits {#complexity-limits}

Complexity limits exist because complexity is the primary source of defects, the primary impediment to testing, and the primary reason codebases become unmaintainable. These are not aesthetic preferences; they are empirically validated thresholds from decades of software engineering research.

All limits are enforced via ruff rules. Violations must be refactored -- not suppressed -- before commit.

| Limit | Maximum | Ruff Rule | Why This Number |
|-------|---------|-----------|-----------------|
| Statements per function | 50 | `PLR0915` | Functions exceeding 50 statements are reliably harder to test and maintain |
| Cyclomatic complexity | 10 | `C901` | McCabe's original research identified 10 as the threshold above which defect rates increase sharply |
| Parameters per function | 5 | `PLR0913` | > 5 parameters indicates the function has too many concerns; use a data class or config object |
| Return statements | 6 | `PLR0911` | > 6 exit paths makes control flow impossible to trace without a debugger |
| Branches per function | 12 | `PLR0912` | Branches multiply test cases geometrically |
| Inheritance depth | 3 | Manual review | Deep hierarchies create fragile base class problems |
| Nesting levels (inside function) | 4 | Manual review | > 4 levels typically indicates a missing extraction |

When you hit a limit, the fix is always one of: (1) extract a named helper function, (2) replace a complex branch with a dispatch table, (3) use pattern matching (`match`/`case`), (4) introduce a data class to reduce parameter count. Suppressing with `# noqa` is a last resort reserved for generated code or unavoidable stdlib interactions.

### 2.3 Abstraction Limits {#abstraction-limits}

Abstraction has a cost: every layer of indirection requires a reader to follow a call graph instead of reading straight code. Premature abstraction is therefore not "good design" -- it is debt paid in advance for a flexibility that may never be needed.

**No ABC or Protocol without three or more concrete implementations that exist right now.** "We might need a second implementation later" is a bet on the future. Write the concrete implementation; add the abstraction when the third use case appears. The refactoring is straightforward at that point and costs nothing compared to maintaining an interface nobody needs.

**No passthrough wrappers.** A class or function whose sole body is a single delegating call to another object adds an indirection layer with no semantic content. It does not simplify the interface, it does not add validation, it does not add logging -- it just lengthens the call stack.

```python
# ANTIPATTERN -- pure passthrough wrapper
class DatabaseWrapper:
    def __init__(self, db: Database) -> None:
        self.db = db

    def query(self, sql: str) -> list[Row]:
        return self.db.query(sql)  # no transformation, no validation, no logging
```

**No class with `__init__` plus one method -- use a function.** A class that initializes some state and then exposes exactly one method is a function with extra syntax overhead. The caller must instantiate it, which creates a temporal coupling (`obj = Processor(config)` then `obj.run()`) that a simple `process(config, data)` function avoids entirely.

**No stateless class -- use a module with functions.** A class with no `__init__` and only `@staticmethod` methods is a module. Python already has modules. Use them.

### 2.4 DRY Enforcement {#dry-enforcement}

DRY (Don't Repeat Yourself) is enforced at the extraction threshold of four or more shared consecutive lines. Below that threshold, the cost of naming and maintaining an extraction can exceed the benefit.

The rules:

- Four or more consecutive lines shared between two or more locations: extract and name after the *function* being performed, not the location (not `process_data_from_payment_handler` but `normalize_currency_amount`).
- Copy-paste with only name or literal substitution: parameterize the extraction.
- Before writing any new implementation, search for >= 80% similar existing code in the codebase (ruff `ERA` rule catches commented-out duplicates; `FURB` catches reimplemented stdlib).
- Stdlib first: `itertools`, `functools`, `collections`, `pathlib`, `contextlib` before writing custom implementations.

The ruff `FURB` (refurb) ruleset automatically identifies patterns where you have reimplemented something from the stdlib. Key examples:

```python
# ANTIPATTERN -- reimplements itertools.batched
def batch(items: list, n: int) -> list[list]:
    return [items[i:i+n] for i in range(0, len(items), n)]

# MODERN PATTERN -- stdlib (Python 3.12+)
from itertools import batched
for chunk in batched(items, n):
    process(chunk)
```

### 2.5 Design Principles {#design-principles}

These five principles are not optional guidelines -- they are structural requirements enforced at code review.

**DRY (Don't Repeat Yourself):** One canonical implementation per concept. When you find yourself writing "basically the same as X but slightly different," that is a signal to generalize X.

**SPOT (Single Point of Truth):** Every fact, configuration value, and business rule exists in exactly one place. A database schema defined in both a migration and a Pydantic model with no canonical source is a SPOT violation -- the two will diverge.

**YAGNI (You Aren't Gonna Need It):** Do not build features the current requirements do not require. Speculative extensibility creates maintenance burden without value. The right design is always the simplest one that satisfies the current requirements.

**SOLID:** The five principles apply directly to Python. Single Responsibility means one reason to change -- a class that handles both parsing and persistence will change for two independent reasons. Open/Closed means extend via composition, not modification. Liskov Substitution means subtypes must be substitutable for their base types (violating this with `@override` returning different types is a silent bug). Interface Segregation means narrow interfaces over fat ones -- a Protocol with 12 methods is almost always too wide. Dependency Inversion means high-level modules depend on abstractions, not on concrete implementations.

**GRASP (General Responsibility Assignment Software Patterns):** Assign responsibility to the class that has the most relevant information. The class that holds the payment data should own payment validation. The class that holds the database connection should own query execution.

---

## 3. Package Management {#package-management}

### 3.1 uv Workflow {#uv-workflow}

`uv` is the sole package manager for all Python projects. `poetry`, `pip` (for project management), `pipenv`, and `conda` are banned. `pip` is acceptable only in CI when using `uv pip` for compatibility with CI tooling that expects pip syntax.

**Why uv exclusively?** uv implements dependency resolution in Rust, achieving 10-100x faster installs than pip. More importantly, it provides reproducible environments via `uv.lock`, integrates Python version management (`uv python install`), and has superseded poetry as the community standard (>75M monthly downloads as of 2026). Running two package managers in parallel creates split-brain environments where what works locally silently differs from CI.

The complete workflow:

```bash
# Initialize a new project
uv init myproject
cd myproject

# Add a dependency (updates pyproject.toml + uv.lock)
uv add httpx pydantic structlog

# Add a dev dependency
uv add --dev pytest pytest-cov ruff mypy

# Install all dependencies (uses lockfile for reproducibility)
uv sync

# Run a command in the project environment
uv run python -m myproject.main

# Run tests
uv run pytest tests/ --cov=src --cov-fail-under=100

# Update all dependencies (generates new lockfile)
uv lock --upgrade

# Sync production only (excludes dev dependencies)
uv sync --no-dev
```

The `pyproject.toml` must specify the Python version constraint:

```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.9",
    "structlog>=24.4",
]

[tool.uv]
python = "3.12.*"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 3.2 Lockfile Policy {#lockfile-policy}

**`uv.lock` must be committed to version control.** This is non-negotiable. A committed lockfile is the only guarantee that CI and developer machines install the same dependency graph.

**Critical silent error -- platform-specific lockfiles.** By default, `uv lock` generates a platform-specific lockfile. If you develop on macOS and CI runs on Linux, the lockfile may resolve different wheels for the same package -- especially packages with C extensions. This silently passes on both platforms but produces different binary behavior.

**Mandated pattern:**

```bash
# Generate a universal lockfile (works across platforms and Python versions)
uv lock --universal

# In CI: verify the lockfile is not stale
uv sync --frozen  # fails if uv.lock does not match pyproject.toml

# In CI: install without network (lockfile must be committed)
uv sync --frozen --no-dev
```

The `--universal` flag instructs uv to resolve dependencies for all supported platforms simultaneously, embedding all platform-conditional markers in the lockfile. This means the same `uv.lock` works on macOS, Linux, and Windows without regeneration.

**Dependency update cadence:**
- Security patches: within 48 hours of CVE disclosure
- Minor updates: weekly via automated PR (Dependabot or Renovate)
- Major updates: manual review cycle with changelog audit

```toml
# pyproject.toml -- pin Python version for reproducibility
[tool.uv]
python = "3.12.*"

# .github/dependabot.yml -- automated dependency updates
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      dev-dependencies:
        patterns: ["pytest*", "ruff", "mypy"]
```

---

## 4. Project Structure {#project-structure}

Every project follows the `src/` layout. This layout separates installed package code from project metadata, tests, and scripts -- preventing import confusion between the installed package and the source directory.

```
myproject/
+-- src/
|   +-- myproject/
|       +-- __init__.py
|       +-- main.py          # Orchestrates only; no business logic
|       +-- config.py        # Config loading via pydantic-settings
|       +-- models.py        # Pydantic data models
|       +-- services/        # Business logic
|       +-- api/             # HTTP layer (if applicable)
|       +-- db/              # SQLAlchemy models and session
|       +-- scripts/         # Utility scripts (one per function)
+-- tests/
|   +-- conftest.py
|   +-- unit/
|   +-- integration/
|   +-- e2e/
+-- docs/
|   +-- prd.md
|   +-- spec.md
|   +-- orientation.md
+-- config.yml               # Application config (committed)
+-- credentials.yml          # Secrets (gitignored; .dist committed)
+-- credentials.yml.dist     # Template with placeholder values
+-- pyproject.toml
+-- uv.lock
+-- .pre-commit-config.yaml
+-- checkpython.sh           # Quality gate runner (never modify)
+-- CLAUDE.md                # Project-level AI assistant instructions
```

**`main.py` orchestrates only.** The entry point module initializes config, wires dependencies, and starts the application. It contains no business logic. This keeps it testable in isolation and prevents import cycles.

**Absolute imports only.** Relative imports (`from . import utils`) are banned. Absolute imports from the source root (`from myproject.utils import ...`) are unambiguous and survive module restructuring.

**`docs/orientation.md` is mandatory.** Before any code authoring, read `docs/orientation.md`. It documents the project's architecture, key design decisions, and the contracts between modules. Without this, P7 (Contextual Strictness) cannot be satisfied.

**Required project files:**

| File | Purpose |
|------|---------|
| `docs/prd.md` | Product requirements |
| `docs/spec.md` | Technical specification |
| `docs/orientation.md` | Architecture map for new contributors |
| `checkpython.sh` | Quality gate runner -- never modify |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `credentials.yml.dist` | Secret template with placeholder values |

---

## 5. Configuration {#configuration}

### 5.1 YAML Config Pattern {#yaml-config}

All application configuration lives in `config.yml`. Secrets live in `credentials.yml`. Environment variables are not the primary configuration mechanism -- they are a bridge for deployment environments that cannot mount files (documented in section 5.3).

`config.yml` is committed. `credentials.yml` is gitignored. The `.dist` template is committed.

```yaml
# config.yml -- application configuration
app:
  name: "myproject"
  debug: false
  log_level: "INFO"
  log_file: "logs/app.log"

database:
  host: "localhost"
  port: 5432
  name: "myproject_db"
  pool_size: 10
  pool_timeout: 30

http_client:
  timeout_connect: 5.0
  timeout_read: 30.0
  max_connections: 100
```

```yaml
# credentials.yml.dist -- commit this template
database:
  user: "REPLACE_ME"
  password: "REPLACE_ME"

api_keys:
  openai: "REPLACE_ME"
  stripe: "REPLACE_ME"
```

### 5.2 pydantic-settings YAML Source {#pydantic-settings-yaml}

**Critical bug in common usage.** The `pydantic-settings` library has NO built-in YAML support. Calling `BaseSettings` with a YAML file will silently read nothing -- or raise a confusing error about missing fields -- because `pydantic-settings` only natively supports `.env` files and environment variables. This is the number-one footgun for developers reading the mandated config pattern without reading this section.

You MUST write a custom `YamlConfigSettingsSource` by subclassing `PydanticBaseSettingsSource`. The full implementation:

```python
# src/myproject/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Load settings from a YAML file.

    pydantic-settings has no built-in YAML support. This custom source
    is required. Without it, BaseSettings silently ignores YAML files.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        yaml_file: str | Path,
    ) -> None:
        super().__init__(settings_cls)
        self._yaml_file = Path(yaml_file)
        self._yaml_data: dict[str, Any] = {}
        if self._yaml_file.exists():
            with self._yaml_file.open() as f:
                self._yaml_data = yaml.safe_load(f) or {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        field_value = self._yaml_data.get(field_name)
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data


class DatabaseCredentials(BaseModel):
    """Database connection secrets."""

    model_config = ConfigDict(extra="forbid")

    user: str
    password: SecretStr


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str = "localhost"
    port: int = 5432
    name: str = "myproject_db"
    pool_size: int = 10
    pool_timeout: int = 30


class AppSettings(BaseSettings):
    """Application settings loaded from YAML files.

    Load order (later sources override earlier):
    1. config.yml (application config)
    2. credentials.yml (secrets -- gitignored)
    3. Environment variables (bridge for containerized deploys)
    """

    model_config = ConfigDict(extra="forbid")

    app_name: str = "myproject"
    debug: bool = False
    log_level: str = "INFO"
    database: DatabaseConfig = DatabaseConfig()
    db_credentials: DatabaseCredentials | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_file = os.getenv("CONFIG_FILE", "config.yml")
        creds_file = os.getenv("CREDENTIALS_FILE", "credentials.yml")
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls, config_file),
            YamlConfigSettingsSource(settings_cls, creds_file),
            env_settings,  # env vars override YAML for deployment bridges
        )


# Module-level singleton, initialized once at startup
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return the application settings singleton.

    Raises:
        ValidationError: If required settings are missing or invalid.
    """
    global _settings  # noqa: PLW0603 -- intentional module-level singleton
    if _settings is None:
        _settings = AppSettings()
    return _settings
```

### 5.3 Env-Var Bridge Policy {#env-var-bridge}

The "no env vars" stance is a purist position incompatible with real-world container deployments. Kubernetes, Docker, ECS, Render, Fly, and Heroku all inject secrets via environment variables. The resolution is a sanctioned bridge: environment variables are allowed, but only when funneled through `pydantic-settings` with a controlled `env_prefix`.

The policy:

1. YAML is the canonical config for local development and testing.
2. Environment variables may override YAML values in deployed environments.
3. No code reads `os.environ` directly -- all env access goes through `AppSettings`.
4. Prefix all project env vars to avoid collisions: `MYPROJECT_DATABASE__HOST=db.prod`.

```python
# pydantic-settings supports nested env var overrides with __ separator
# MYPROJECT_DATABASE__HOST=prod-db.internal overrides database.host in YAML

class AppSettings(BaseSettings):
    model_config = ConfigDict(
        extra="forbid",
        env_prefix="MYPROJECT_",
        env_nested_delimiter="__",
    )
    # Now: MYPROJECT_LOG_LEVEL=DEBUG overrides log_level
    # And: MYPROJECT_DATABASE__HOST=prod overrides database.host
```

---

## 6. Type System {#type-system}

### 6.1 Python 3.12 PEP 695 Syntax {#pep695}

PEP 695, introduced in Python 3.12, provides first-class syntax for type parameters. It replaces the verbose `TypeVar`/`Generic` pattern with a cleaner bracket syntax that mirrors generics in other statically typed languages.

**Why this matters beyond aesthetics.** The old `TypeVar` pattern requires defining the variable at module scope, creating a name in the module's namespace that serves no runtime purpose. PEP 695 type parameters are scoped to the function or class they parameterize, preventing namespace pollution and making the relationship between the type parameter and its consumer explicit.

```python
# ANTIPATTERN -- Python 3.11 / legacy TypeVar pattern
from typing import TypeAlias, TypeVar, Generic

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

Point: TypeAlias = tuple[float, float]

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

def first(lst: list[T]) -> T:
    return lst[0]
```

```python
# MODERN PATTERN -- Python 3.12 PEP 695 syntax
type Point = tuple[float, float]  # type alias, scoped and explicit
type Vector[T] = list[T]          # generic alias

class Stack[T]:                   # generic class; T is scoped to Stack
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

def first[T](lst: list[T]) -> T:  # generic function; T scoped to first()
    return lst[0]
```

**3.11 fallbacks** (for code that must maintain 3.11 compatibility):

```python
from typing import TypeAlias, TypeVar, Generic
from typing_extensions import override  # backport of typing.override

T = TypeVar("T")
Point: TypeAlias = tuple[float, float]

class Stack(Generic[T]):
    ...
```

When targeting 3.12 exclusively (the standard for new projects), use PEP 695 syntax exclusively and do not import from `typing_extensions`.

### 6.2 Override and Self {#override-self}

Two typing utilities deserve special attention because they prevent entire classes of inheritance bugs.

**`@override`.** When a subclass reintends to override a method from its parent, the `@override` decorator documents that intent. More importantly, when the parent method is renamed or removed, mypy raises an error on the `@override` decorator -- catching broken overrides at type-check time instead of runtime.

```python
from typing import override, Self

class Animal:
    def sound(self) -> str:
        return ""

    def clone(self) -> Self:
        return type(self)()

class Dog(Animal):
    @override  # mypy error if Animal.sound() is renamed or removed
    def sound(self) -> str:
        return "woof"

    @override
    def clone(self) -> Self:  # Self correctly infers as Dog in Dog context
        return type(self)()
```

**`Self`.** The `Self` type annotation means "an instance of this class or any subclass." Without it, a method that returns `self` typed as the base class breaks type inference for subclasses. Using `Self` correctly models the builder pattern, fluent interfaces, and class method constructors.

**Gotcha.** `@override` is type-only -- there is no runtime enforcement. If mypy is not run (for example, in a hot-fix situation), a broken override passes silently. This is a strong argument for keeping mypy in the Tier 1 commit gate and not deferring it to Tier 2.

### 6.3 TYPE_CHECKING Imports {#type-checking-imports}

Some imports are needed only for type annotations, not at runtime. Placing these inside `if TYPE_CHECKING:` blocks prevents circular imports and reduces module startup time.

```python
from __future__ import annotations  # required for forward references

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from myproject.services.payment import PaymentService


class OrderProcessor:
    def __init__(self, payment_service: PaymentService) -> None:
        # PaymentService is only needed at type-check time, not at runtime
        # This breaks what would otherwise be a circular import
        self._payment = payment_service

    def process_order(self, order_id: int) -> Generator[str, None, None]:
        ...
```

The `from __future__ import annotations` at the top of the file makes all annotations strings (lazy evaluation), which is required for TYPE_CHECKING imports to work without `NameError` at runtime. This import is mandatory in any file using TYPE_CHECKING.

The ruff `TCH` ruleset automatically identifies imports that should be moved into `TYPE_CHECKING` blocks.

---

## 7. Core Libraries {#core-libraries}

### 7.1 HTTP Client: HTTPX {#httpx}

HTTPX is the sole HTTP client library. The `requests` library is banned -- not because it is broken, but because it does not support async, lacks HTTP/2, and its session management model encourages connection leaks. HTTPX provides a nearly identical API while supporting both sync and async, HTTP/2, and structured timeout configuration.

**Critical silent error -- connection leaks with `raise_for_status()`.** Outside an `async with` context manager, calling `response.raise_for_status()` without a preceding `await response.aclose()` leaks the connection if an exception is raised. The connection is returned to the pool only when the response object is garbage collected -- which in CPython may be immediate, but in other implementations may not be. Always use the context manager.

```python
# ANTIPATTERN -- potential connection leak
async def fetch_user(user_id: int) -> dict:
    client = httpx.AsyncClient()
    response = await client.get(f"/users/{user_id}")
    response.raise_for_status()  # if this raises, connection may leak
    return response.json()

# MODERN PATTERN -- context manager guarantees connection cleanup
async def fetch_user(user_id: int) -> dict:
    async with httpx.AsyncClient(
        base_url="https://api.example.com",
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
        follow_redirects=False,  # explicit redirect handling; SSRF prevention
        verify=True,             # NEVER False
        http2=True,
    ) as client:
        response = await client.get(f"/users/{user_id}")
        response.raise_for_status()
        return response.json()
```

**Client reuse.** For high-throughput applications, create a single `AsyncClient` instance at application startup and inject it. Creating a new client per-request defeats connection pooling.

```python
# Production pattern -- client as dependency
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import httpx

@asynccontextmanager
async def lifespan_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Application-lifetime HTTP client with connection pooling."""
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
        follow_redirects=False,
        verify=True,
        http2=True,
        limits=limits,
    ) as client:
        yield client
```

**SSRF prevention.** `follow_redirects=False` is the first line of defense. The second is post-DNS IP validation for any URL derived from user input:

```python
import ipaddress
import socket

def is_safe_url(host: str) -> bool:
    """Return True only if the resolved IP is not private/loopback."""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except (OSError, ValueError):
        return False
```

### 7.2 Validation: Pydantic v2 {#pydantic}

Pydantic v2 is used for all data validation: API request/response models, configuration, database row models, and any structured data crossing a boundary. The v2 rewrite provides a Rust core that validates approximately 5-50x faster than v1.

**Mandatory configuration.**

```python
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Annotated, Literal

class InternalUserModel(BaseModel):
    """Internal model with strict validation -- extra fields are forbidden."""

    model_config = ConfigDict(
        strict=True,     # no coercion: "123" is not an int
        extra="forbid",  # reject unknown fields (mass-assignment prevention)
    )

    username: Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")]
    role: Literal["user", "admin", "viewer"]
    password: SecretStr
```

**Critical footgun -- `extra="forbid"` and API evolution.** `extra="forbid"` is the correct default for internal models -- it prevents mass-assignment attacks. However, for models that deserialize responses from external/partner APIs, `extra="forbid"` means that every new optional field the partner adds breaks your client with a `ValidationError`. This is a silent breakage in production because the partner's change requires no action on your end, yet your service starts throwing validation errors.

The policy:

- **Internal models** (data you own): `extra="forbid"`. Be strict.
- **External/boundary models** (partner APIs, third-party webhooks): `extra="ignore"`. Be tolerant.

```python
# External API response model -- tolerant of new fields
class StripeWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Stripe adds fields regularly

    id: str
    type: str
    data: dict[str, object]


# Internal domain model -- strict
class PaymentRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    payment_id: str
    amount_cents: int
    currency: Literal["USD", "EUR", "GBP"]
    status: Literal["pending", "completed", "failed"]
```

**Critical silent error -- `SecretStr` serialization.** `SecretStr` prevents the secret value from appearing in `repr()` and `str()`, which protects against log leaks. However:

- `model.model_dump()` returns `{'password': SecretStr('**********')}` -- the string `'**********'`, NOT the secret value.
- `model.model_dump(mode='json')` returns `{'password': 'secret_plaintext'}` -- the actual cleartext secret.

This means serializing a model to JSON (for example, to send to a logging backend or cache) silently leaks the secret value. The safe pattern:

```python
from pydantic import BaseModel, ConfigDict, SecretStr

class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr

creds = Credentials(api_key="sk-1234")

# SAFE -- SecretStr masked in repr
print(creds)                          # api_key=SecretStr('**********')

# SAFE -- masked in dict
print(creds.model_dump())             # {'api_key': SecretStr('**********')}

# DANGER -- cleartext in JSON mode
print(creds.model_dump(mode="json"))  # {'api_key': 'sk-1234'} -- LEAKS!

# SAFE pattern for JSON serialization
def serialize_safe(model: BaseModel) -> dict:
    """Serialize model, excluding all SecretStr fields."""
    return model.model_dump(
        exclude={
            field_name
            for field_name, field_info in model.model_fields.items()
            if field_info.annotation is SecretStr
        }
    )

# To access the secret value explicitly (only where required)
key = creds.api_key.get_secret_value()  # explicit, greppable, auditable
```

### 7.3 Logging: structlog + orjson {#structlog}

structlog is the sole logging framework. The stdlib `logging` module is banned in application code. The reason: `logging` is event-string-based -- it produces unstructured text that requires regex parsing for observability pipelines. structlog produces structured key-value log entries that feed directly into Elasticsearch, Datadog, Loki, or any JSON-based log aggregator.

**Critical silent error -- structlog + orjson not wired.** Both libraries are mandated, but they must be explicitly wired together. If you install both and call `structlog.get_logger()` without configuration, structlog uses the stdlib `json` renderer -- the slow path that orjson was chosen to replace. The integration must be explicit.

The `JSONRenderer` in structlog accepts a `serializer` argument. orjson's `dumps()` function returns `bytes`, but structlog expects `str`. The bridge requires a decode step.

```python
# src/myproject/logging_config.py
from __future__ import annotations

import logging
import sys
from typing import Any

import orjson
import structlog


def _orjson_serializer(obj: Any, **kwargs: Any) -> str:
    """orjson serializer bridge for structlog.

    orjson.dumps() returns bytes; structlog's JSONRenderer expects str.
    This bridge decodes the bytes to str.
    """
    return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_UTC_Z).decode()


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog with orjson serialization.

    Call once at application startup before any logging occurs.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, emit JSON lines. If False, emit colored console output.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(serializer=_orjson_serializer),
        ]
        wrapper_class = structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        )
        structlog.configure(
            processors=processors,
            wrapper_class=wrapper_class,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # Development: colored, human-readable output
        processors_dev: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        structlog.configure(
            processors=processors_dev,
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.getLevelName(log_level)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Bridge stdlib logging into structlog so third-party libraries
    # that use logging also emit structured JSON
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    logging.getLogger().handlers.clear()
```

Usage throughout the application:

```python
import structlog

log = structlog.get_logger(__name__)

# Structured key-value pairs -- not format strings
log.info("request.received", method="POST", path="/payments", user_id=42)
log.warning("rate_limit.approaching", usage_pct=85.3, limit=1000)
log.error("payment.failed", payment_id="pay_abc123", error="insufficient_funds")

# Bind context for request-scoped logging
structlog.contextvars.bind_contextvars(request_id="req-xyz", user_id=42)
# All subsequent log calls in this context include request_id and user_id
```

**Log-forging prevention.** Strip newlines from any user-supplied string before logging:

```python
def sanitize_log_value(value: str) -> str:
    """Remove characters that could inject fake log entries."""
    return value.replace("\n", "\\n").replace("\r", "\\r").replace("\x00", "")
```

### 7.4 Retries: stamina {#stamina}

stamina is the sole retry library. `tenacity` is banned. stamina's design is opinionated: it provides sensible defaults, integrates with structlog out-of-the-box, and can export retry metrics to Prometheus. It prevents the common mistake of writing custom retry loops that either don't back off, don't jitter, or silently swallow exceptions.

**Critical gap in common usage.** Most examples show stamina with only `attempts=3`. This omits the backoff configuration that makes retries safe in production. Without `wait_max`, a retry loop can wait arbitrarily long. Without `wait_jitter`, every client retries simultaneously after a server blip (thundering herd). Without `wait_initial`, the first retry is immediate rather than giving the upstream service time to recover.

```python
# ANTIPATTERN -- minimal stamina usage, missing backoff config
@stamina.retry(on=httpx.HTTPError, attempts=3)
async def fetch_data(url: str) -> dict:
    ...

# MODERN PATTERN -- full backoff configuration with structlog hookup
import stamina
import structlog
import httpx

log = structlog.get_logger(__name__)


@stamina.retry(
    on=httpx.HTTPStatusError,
    attempts=5,
    wait_initial=0.5,    # seconds before first retry
    wait_max=30.0,       # cap the exponential backoff
    wait_jitter=2.0,     # randomize by up to 2s to prevent thundering herd
    wait_exp_base=2.0,   # exponential base for backoff calculation
)
async def fetch_payment(client: httpx.AsyncClient, payment_id: str) -> dict:
    """Fetch a payment record with retry on transient HTTP errors.

    Retries on HTTPStatusError (5xx). Does NOT retry on 4xx client errors
    because those indicate problems with the request, not the server.

    Args:
        client: Shared HTTPX async client.
        payment_id: The payment identifier to fetch.

    Returns:
        Payment record as a dictionary.

    Raises:
        httpx.HTTPStatusError: If all retry attempts are exhausted.
    """
    response = await client.get(f"/payments/{payment_id}")
    response.raise_for_status()
    return response.json()
```

**Instrumenting retry events.** stamina emits structured log events at each retry attempt when structlog is configured. The hook pattern for custom per-attempt logging:

```python
import stamina

def on_retry(details: stamina.RetryDetails) -> None:
    log = structlog.get_logger(__name__)
    log.warning(
        "retry.attempt",
        function=details.name,
        attempt=details.num,
        wait_secs=round(details.wait, 2),
        exception_type=type(details.exc).__name__,
        exception=str(details.exc),
    )

@stamina.retry(on=httpx.HTTPStatusError, attempts=5, on_retry=on_retry)
async def fetch_payment(client: httpx.AsyncClient, payment_id: str) -> dict:
    ...
```

### 7.5 Database: SQLAlchemy + Alembic {#sqlalchemy}

SQLAlchemy is the sole ORM and query builder. All schema changes go through Alembic migrations -- manual `ALTER TABLE` statements in production are banned. The reason: schema changes without migrations cannot be tracked, rolled back, or applied consistently across environments.

Always use parameterized queries. The ORM auto-parameterizes attribute comparisons. For raw SQL, use named parameters.

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# SAFE -- ORM auto-parameterizes
async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

# SAFE -- explicit named parameter
async def search_users(session: AsyncSession, search_term: str) -> list[User]:
    result = await session.execute(
        text("SELECT * FROM users WHERE username ILIKE :term"),
        {"term": f"%{search_term}%"},  # parameterized; not f-string
    )
    return list(result.fetchall())

# BANNED -- SQL injection
async def bad_search(session: AsyncSession, name: str) -> list:
    return await session.execute(
        text(f"SELECT * FROM users WHERE name = '{name}'")  # injection!
    )
```

### 7.6 CLI: Typer {#typer}

Typer is the sole CLI framework. Raw `argparse` and `click` are acceptable for legacy codebases but not greenfield. Typer builds on click but derives the CLI interface from Python type annotations, eliminating the duplicated argument declaration that click requires.

The pattern for CLI-to-config integration:

```python
import typer
from typing import Annotated

app = typer.Typer()


@app.command()
def main(
    config_file: Annotated[str, typer.Option("--config", help="Path to config.yml")] = "config.yml",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without writing")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Process payments from the configured source."""
    settings = get_settings()
    # CLI flags override YAML config
    if verbose:
        settings = settings.model_copy(update={"log_level": "DEBUG"})
    if dry_run:
        typer.echo("Dry run mode -- no changes will be written")
    run(settings)


if __name__ == "__main__":
    app()
```

**`typer.echo` for CLI output; structlog for application logging.** Typer's `typer.echo()` is the appropriate function for user-facing CLI output (progress messages, confirmations, results). `print()` is banned. structlog is for application events.

### 7.7 Serialization: orjson and msgspec {#serialization}

**orjson** is the standard JSON library. stdlib `json` is banned in application code. orjson is 3-10x faster than stdlib `json`, correctly handles `datetime`, `UUID`, `Decimal`, `numpy` arrays, and `dataclasses` without custom encoders.

```python
import orjson

# Serialize -- returns bytes, not str
data = {"timestamp": datetime.now(UTC), "user_id": 42}
serialized: bytes = orjson.dumps(data, option=orjson.OPT_UTC_Z)

# Deserialize
record: dict = orjson.loads(serialized)

# Pretty-print for debugging (still returns bytes)
pretty: bytes = orjson.dumps(data, option=orjson.OPT_INDENT_2)
```

**msgspec** is for high-throughput serialization in data pipelines where you need sub-millisecond encoding of validated structures. It is approximately 2-5x faster than orjson for its own `Struct` types because validation and serialization happen in a single Rust pass.

```python
import msgspec

class TradeRecord(msgspec.Struct, frozen=True):
    symbol: str
    price: float
    volume: int
    timestamp: int  # unix ms

encoder = msgspec.json.Encoder()
decoder = msgspec.json.Decoder(TradeRecord)

# Encode -- returns bytes
raw: bytes = encoder.encode(TradeRecord("AAPL", 185.50, 1000, 1714000000000))

# Decode with validation -- raises DecodeError on bad input
record: TradeRecord = decoder.decode(raw)
```

Use orjson for general-purpose JSON. Use msgspec where you have identified serialization as a hot path through profiling (`py-spy`).

### 7.8 DataFrames: polars and pandas {#dataframes}

polars is the default for new projects. pandas is acceptable for existing projects and when the ecosystem demands it (many ML libraries have deeper pandas integration). The two are not interchangeable in an operational sense -- polars is memory-mapped, expression-lazy, and runs query plans in parallel; pandas is eager and single-threaded by default.

```python
import polars as pl

# polars -- lazy evaluation, expression API
df = (
    pl.scan_parquet("data/*.parquet")  # lazy -- no data loaded yet
    .filter(pl.col("status") == "active")
    .group_by("region")
    .agg([
        pl.col("revenue").sum().alias("total_revenue"),
        pl.col("user_id").n_unique().alias("unique_users"),
    ])
    .sort("total_revenue", descending=True)
    .collect()  # execute the query plan
)
```

For DataFrame validation, use **pandera** schemas -- promoted from Tier 3 to an active recommendation for any pipeline where data shape must be verified:

```python
import pandera.polars as pa

class RevenueSchema(pa.DataFrameModel):
    region: str = pa.Field(nullable=False)
    total_revenue: float = pa.Field(ge=0.0)
    unique_users: int = pa.Field(ge=0)

    class Config:
        strict = True  # reject extra columns

@pa.check_types
def process_revenue(df: pa.AnnotatedType[RevenueSchema]) -> pl.DataFrame:
    return df.with_columns(
        (pl.col("total_revenue") / pl.col("unique_users")).alias("revenue_per_user")
    )
```

---

## 8. Error Handling {#error-handling}

### 8.1 Exception Hierarchy Design {#exception-hierarchy}

Every project defines a custom exception hierarchy rooted in a project-specific base class. This makes it possible to catch all project exceptions in a single handler at the application boundary, while still allowing fine-grained handling at intermediate layers.

```python
# src/myproject/exceptions.py


class MyProjectError(Exception):
    """Base exception for all myproject errors.

    Catch this at application boundaries to prevent
    implementation details from leaking to callers.
    """


class ConfigurationError(MyProjectError):
    """Configuration is missing or invalid."""


class DatabaseError(MyProjectError):
    """Database operation failed."""


class NotFoundError(DatabaseError):
    """Requested resource does not exist."""


class ValidationError(MyProjectError):
    """Input data failed validation."""


class ExternalServiceError(MyProjectError):
    """External service returned an error or is unavailable."""


class RateLimitError(ExternalServiceError):
    """External service rate limit exceeded."""
```

**Inheritance depth limit: 3.** `MyProjectError -> DatabaseError -> NotFoundError` is the maximum. Deeper hierarchies create fragile base class problems and make it difficult to know which catch clauses will match.

**Never swallow exceptions.** The pattern `except Exception: pass` (bare except, implicit swallow) is the most common cause of silent data corruption in Python. If you catch an exception and do not re-raise it, you must log it with full context and return an appropriate error value.

```python
# ANTIPATTERN -- swallowed exception
try:
    result = process_payment(payment)
except Exception:
    pass  # caller receives None; has no idea payment failed

# MODERN PATTERN -- log and re-raise or convert to domain exception
try:
    result = process_payment(payment)
except httpx.HTTPStatusError as exc:
    log.error(
        "payment.service_error",
        status_code=exc.response.status_code,
        payment_id=payment.id,
        exc_info=True,
    )
    raise ExternalServiceError(f"Payment service returned {exc.response.status_code}") from exc
```

### 8.2 Stamina Retry Patterns {#stamina-pattern}

See section 7.4 for the full stamina pattern including `wait_initial`, `wait_max`, `wait_jitter`, and the structlog instrumentation hookup. The key principle restated: only retry on transient errors. Retrying on 4xx client errors wastes time and masks programming bugs.

```python
# Retry only on the specific transient conditions
@stamina.retry(
    on=(httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError),
    attempts=4,
    wait_initial=1.0,
    wait_max=20.0,
    wait_jitter=1.5,
)
async def call_upstream(client: httpx.AsyncClient, payload: dict) -> dict:
    ...
```

For 5xx errors from HTTP services, catch `httpx.HTTPStatusError` and filter:

```python
@stamina.retry(on=httpx.HTTPStatusError, attempts=3, wait_initial=2.0, wait_max=30.0)
async def fetch_with_status_retry(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    if response.status_code < 500:
        response.raise_for_status()  # 4xx -- raise immediately, no retry
    response.raise_for_status()      # 5xx -- stamina will retry
    return response.json()
```

### 8.3 Silent Failure Landmines {#silent-failures}

These are the patterns most likely to cause production incidents that look like "the system silently did nothing."

**`subprocess.run` without `check=True`.** Documented in section 2.1.3. Always add `check=True`.

**Empty except blocks.** Any `except` clause that does not re-raise, log, or convert to a domain exception is a silence mechanism. Code review must reject these unconditionally.

**`dict.get()` with a None default for required keys.** `config.get("api_key")` returns `None` if the key is missing. If the code then passes this `None` to an HTTP call, it may succeed (producing a call with no auth) rather than failing immediately. Use `config["api_key"]` for required values and let `KeyError` propagate.

**Pydantic `model_dump(mode="json")` with `SecretStr`.** Documented in section 7.2.

**`hmac.compare_digest` length leak.** `hmac.compare_digest` is constant-time only when both inputs are the same length. When the lengths differ, it returns `False` immediately -- leaking the length of the expected value through timing. For short secrets (API keys, tokens), an attacker can binary-search the length in O(log n) comparisons. The safe pattern:

```python
import hmac
import hashlib

# ANTIPATTERN -- leaks length through early return
def verify_token_unsafe(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided, expected)

# MODERN PATTERN -- hash both values first to normalize to fixed length
def verify_token(provided: str, expected: str) -> bool:
    """Constant-time token comparison resistant to length oracle.

    Both inputs are SHA-256 hashed before comparison.
    This normalizes them to the same length regardless of input length,
    eliminating the length-leak present in direct hmac.compare_digest.
    """
    provided_hash = hashlib.sha256(provided.encode()).digest()
    expected_hash = hashlib.sha256(expected.encode()).digest()
    return hmac.compare_digest(provided_hash, expected_hash)
```

**`uv.lock` platform drift.** Without `uv lock --universal`, the lockfile is platform-specific. CI on Linux with dev on macOS silently installs different wheels. Use `uv sync --frozen` in CI to fail explicitly if the lockfile is stale.

**`structlog` without orjson wired.** Documented in section 7.3.

**`pydantic-settings` without custom YAML source.** Documented in section 5.2.

---

## 9. Security {#security}

### 9.1 Input Validation {#input-validation}

All input crossing a trust boundary must be validated before use. "Trust boundary" includes HTTP request bodies, query parameters, file uploads, database results from external systems, message queue payloads, and environment variables.

Pydantic is the validation layer. The configuration mandates:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Annotated, Literal

class CreateUserRequest(BaseModel):
    """Validated user creation request from HTTP POST body."""

    model_config = ConfigDict(strict=True, extra="forbid")

    username: Annotated[
        str,
        Field(
            min_length=3,
            max_length=64,
            pattern=r"^[a-zA-Z0-9_]+$",
            description="Alphanumeric + underscore only",
        ),
    ]
    email: Annotated[str, Field(max_length=320)]
    role: Literal["user", "viewer"]  # explicit allowlist; never accept "admin" from untrusted input
    age: Annotated[int, Field(ge=0, le=150)]

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()
```

**Never use `assert` for runtime validation.** Python's `-O` (optimize) flag strips all `assert` statements at runtime. Any validation written as `assert x > 0` silently disappears in optimized mode. Use `if/raise` instead.

**`Literal[...]` for enum inputs.** Never validate enum-style inputs with `if value in allowed_set`. Use `Literal["option1", "option2"]` -- Pydantic enforces it, mypy type-checks callers, and the allowed set is documented in the type annotation.

### 9.2 Database Security {#database-security}

SQL injection in SQLAlchemy applications comes from two sources: (1) using f-strings in `text()` expressions, and (2) constructing column or table names dynamically. The ORM's attribute comparison syntax auto-parameterizes, eliminating injection risk at that level.

```python
# SAFE -- ORM attribute comparison (auto-parameterized)
user = await session.scalar(select(User).where(User.email == email))

# SAFE -- named parameter in text()
result = await session.execute(
    text("SELECT * FROM orders WHERE status = :status AND user_id = :uid"),
    {"status": status, "uid": user_id},
)

# BANNED -- f-string in text() = SQL injection
result = await session.execute(
    text(f"SELECT * FROM orders WHERE status = '{status}'")
)

# Dynamic column/table names require allowlist validation
ALLOWED_SORT_COLUMNS = frozenset({"created_at", "updated_at", "amount"})

def build_sorted_query(sort_column: str) -> Select:
    if sort_column not in ALLOWED_SORT_COLUMNS:
        raise ValueError(f"Invalid sort column: {sort_column!r}")
    return select(Order).order_by(text(sort_column))  # safe after allowlist
```

**LIKE-pattern injection.** The parameterized `LIKE :term` pattern does not escape LIKE wildcard characters (`%`, `_`). A user who submits `%` as a search term gets a full table scan. Escape wildcards before passing them as LIKE parameters:

```python
def escape_like(value: str) -> str:
    """Escape LIKE wildcards to prevent pattern injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

search_result = await session.execute(
    text("SELECT * FROM users WHERE username LIKE :term ESCAPE '\\'"),
    {"term": f"%{escape_like(search_input)}%"},
)
```

### 9.3 HTTP Security and SSRF Prevention {#http-security}

See section 7.1 for the full HTTPX configuration. Key security settings:

- `verify=True` -- never disable TLS verification
- `follow_redirects=False` -- prevents redirect chains to internal services
- Post-DNS IP validation for user-supplied URLs (SSRF prevention)
- Explicit `timeout` -- prevents slowloris-style denial via open connections

```python
import ipaddress
import socket
from urllib.parse import urlparse

PRIVATE_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 ULA
)


def validate_url_for_fetch(url: str) -> str:
    """Validate that a URL is safe to fetch (SSRF prevention).

    Resolves the hostname via DNS and rejects private/loopback addresses.

    Args:
        url: The URL to validate.

    Returns:
        The validated URL (unchanged).

    Raises:
        ValueError: If the URL resolves to a private or reserved IP.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Scheme not allowed: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no hostname")
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot resolve hostname: {host!r}") from exc
    for network in PRIVATE_RANGES:
        if ip in network:
            raise ValueError(f"URL resolves to private address: {ip}")
    return url
```

### 9.4 Secrets Management {#secrets-management}

Secrets (API keys, database passwords, signing keys) must never appear in:
- Source code
- Committed configuration files
- Docker `ENV` instructions (leaked in image history via `docker history`)
- Log output
- Error messages returned to clients

The secret management chain:

1. Local development: `credentials.yml` (gitignored, `chmod 0600`)
2. CI: encrypted secrets in GitHub Actions secrets store
3. Production: environment variables injected by the runtime (k8s secrets, ECS task env, Docker secrets) -- funneled through `pydantic-settings` as documented in section 5.3

**Pre-commit hook for secret detection.** Both `detect-secrets` and `gitleaks` are required. They serve different purposes: `detect-secrets` detects secrets in the current working tree; `gitleaks` scans the full git history.

```yaml
# .pre-commit-config.yaml (excerpt)
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

**Docker secrets.** Never use `ENV` for secrets in Dockerfiles. Use Docker secrets or build-time ARG with no default:

```dockerfile
# ANTIPATTERN -- secret in image history
ENV API_KEY=sk-1234

# MODERN PATTERN -- secret injected at runtime, not baked into image
# Dockerfile contains no secret references
# docker run --env API_KEY="$(vault read -field=key secret/api)" ...
```

### 9.5 Access Control {#access-control}

Authorization logic belongs in the service layer, not in route decorators alone. Route-level authentication (who are you?) and service-level authorization (are you allowed to do this?) are separate concerns.

```python
# ANTIPATTERN -- authorization only at route level
@app.get("/admin/users")
@require_admin  # what if this route is called from another route?
async def list_all_users() -> list[UserResponse]:
    return await user_service.list_all()


# MODERN PATTERN -- authorization in service layer
@app.get("/admin/users")
async def list_all_users(current_user: User = Depends(get_current_user)) -> list[UserResponse]:
    return await user_service.list_all(requesting_user=current_user)

class UserService:
    async def list_all(self, requesting_user: User) -> list[User]:
        if requesting_user.role != "admin":
            raise PermissionError("Admin role required to list all users")
        return await self._repo.list_all()
```

**File path traversal prevention.** Any file path derived from user input must be resolved and validated against an allowed base directory:

```python
from pathlib import Path

UPLOAD_BASE = Path("/var/uploads").resolve()

def safe_upload_path(filename: str) -> Path:
    """Return a safe path within UPLOAD_BASE.

    Raises:
        ValueError: If the resolved path escapes UPLOAD_BASE.
    """
    candidate = (UPLOAD_BASE / filename).resolve()
    if not str(candidate).startswith(str(UPLOAD_BASE)):
        raise ValueError(f"Path traversal attempt: {filename!r}")
    return candidate
```

**Default-deny.** Authorization logic should start from "no access" and grant explicitly, not start from "full access" and restrict. An `if role == "admin"` check that falls through to an implicit `return data` is a default-allow pattern.

### 9.6 Timing-Safe Operations {#timing-safe}

Timing attacks exploit the fact that string comparison returns early when it finds the first differing character. An attacker who can measure response time can determine, byte by byte, how many characters of their guess matched. For API keys, session tokens, and HMAC signatures, `==` comparison is banned.

**Critical caveat -- `hmac.compare_digest` length leak.** This function is constant-time only when both inputs are the same length. When lengths differ, the function returns `False` immediately, leaking whether the lengths match. The complete safe pattern -- documented in section 8.3 -- hashes both inputs before comparison:

```python
import hashlib
import hmac
import secrets

def verify_api_key(provided: str, expected: str) -> bool:
    """Verify an API key in constant time, resistant to length oracle."""
    # Hash both to normalize length (SHA-256 always produces 32 bytes)
    h_provided = hashlib.sha256(provided.encode("utf-8")).digest()
    h_expected = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(h_provided, h_expected)


def verify_hmac_signature(payload: bytes, signature: str, key: bytes) -> bool:
    """Verify an HMAC-SHA256 signature in constant time."""
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(
        signature.encode("utf-8"),
        expected.encode("utf-8"),
    )
```

`secrets.compare_digest` (available since Python 3.6) is an alias for `hmac.compare_digest` and has the same length-leak behavior. The hash-normalization pattern applies to both.

### 9.7 Password Hashing {#password-hashing}

Timing-safe comparison is for comparing tokens and signatures. For passwords, you need a slow, memory-hard hashing algorithm. `hashlib.sha256(password)` and `hashlib.md5(password)` are banned for password storage -- they are fast, making brute-force trivial.

**Mandated library: `argon2-cffi`.** Argon2 won the Password Hashing Competition in 2015. It is memory-hard, GPU-resistant, and has configurable time/memory cost parameters. It is the 2026 standard for password storage.

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# Application-lifetime instance with tuned parameters
_hasher = PasswordHasher(
    time_cost=2,       # number of iterations
    memory_cost=65536, # 64 MB
    parallelism=2,     # number of parallel threads
    hash_len=32,       # hash output length in bytes
    salt_len=16,       # salt length in bytes
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: The plaintext password to hash.

    Returns:
        The Argon2 hash string (includes algorithm parameters and salt).
    """
    return _hasher.hash(password)


def verify_password(hashed: str, provided: str) -> bool:
    """Verify a password against its Argon2 hash.

    Args:
        hashed: The stored Argon2 hash string.
        provided: The plaintext password to verify.

    Returns:
        True if the password matches the hash.

    Raises:
        ValueError: If the hash is malformed or uses an unsupported algorithm.
    """
    try:
        return _hasher.verify(hashed, provided)
    except VerifyMismatchError:
        return False  # wrong password -- not an error condition
    except (VerificationError, InvalidHashError) as exc:
        raise ValueError(f"Invalid password hash: {exc}") from exc


def password_needs_rehash(hashed: str) -> bool:
    """Check if a stored hash uses outdated parameters.

    Call this after a successful verification. If True, re-hash the
    plaintext password with current parameters and store the new hash.
    """
    return _hasher.check_needs_rehash(hashed)
```

---

## 10. Testing {#testing}

100% test coverage is a hard requirement. Less than 100% is a FAILURE state, not a goal to aspire to. 100% coverage means every line, branch, and exception path has been exercised by at least one test. It does not guarantee correctness, but it guarantees that no code path is entirely untested.

100% passing unit tests is a hard requirement. 100% passing end-to-end integration tests is a hard requirement. Flaky tests are bugs in tests -- fix them, do not skip them.

### 10.1 Coverage Configuration {#coverage-config}

```toml
# pyproject.toml

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=100",
    "--strict-markers",
    "--tb=short",
    "-W", "error::DeprecationWarning",  # surface future breakage now
]
filterwarnings = [
    "error::DeprecationWarning",   # all DeprecationWarnings become test errors
    "error::PendingDeprecationWarning",
]

[tool.coverage.run]
branch = true                      # branch coverage, not just line coverage
source = ["src"]
relative_files = true
omit = [
    "*/tests/*",
    "*/conftest.py",
    "*/__init__.py",
    "*/migrations/*",
]
concurrency = ["thread", "greenlet"]  # required for SQLAlchemy async coverage

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",   # only in @abstractmethod
    "if __name__ == .__main__.:",
    "@(abc\\.)?abstractmethod",
]
fail_under = 100
```

**Why `-W error::DeprecationWarning`?** Python silently suppresses `DeprecationWarning` in non-`__main__` code. Many stdlib functions deprecated in 3.11-3.12 will be removed in 3.14-3.15. Without converting warnings to errors in tests, you discover these at upgrade time -- when fixing them costs much more. Forcing errors during tests surfaces them immediately, when the fix is cheap.

**Why `branch = true`?** Line coverage measures whether a line was executed. Branch coverage measures whether *each branch from a line* was taken. A function with `if condition: return early` has 100% line coverage if tests exercise both the early return and the fall-through, but only 100% branch coverage if both the true and false branch of the condition are tested. Branch coverage is the meaningful metric.

### 10.2 Async Testing {#async-testing}

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # pytest-asyncio mode; "auto" marks all async tests
```

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """In-memory SQLite session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
```

**`asyncio_mode = "auto"` vs `"strict"`.** In `"auto"` mode, all `async def test_*` functions are automatically treated as async tests without requiring the `@pytest.mark.asyncio` decorator. This is the recommended default for projects that are consistently async. Use `"strict"` if you have a mixed codebase and need to explicitly mark tests to prevent accidental async collection.

### 10.3 HTTP Mocking with pytest-httpx {#http-mocking}

Unit tests must not make real HTTP calls. `pytest-httpx` provides an `httpx_mock` fixture that intercepts HTTPX calls and returns configured responses.

```python
import pytest
import httpx
from pytest_httpx import HTTPXMock

from myproject.services.payment import PaymentService


@pytest.fixture
def payment_service() -> PaymentService:
    return PaymentService(base_url="https://api.stripe.com")


async def test_fetch_payment_success(
    httpx_mock: HTTPXMock,
    payment_service: PaymentService,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.stripe.com/v1/charges/ch_abc123",
        json={"id": "ch_abc123", "amount": 1000, "status": "succeeded"},
        status_code=200,
    )
    payment = await payment_service.fetch("ch_abc123")
    assert payment.id == "ch_abc123"
    assert payment.amount == 1000


async def test_fetch_payment_not_found(
    httpx_mock: HTTPXMock,
    payment_service: PaymentService,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.stripe.com/v1/charges/ch_missing",
        status_code=404,
        json={"error": {"message": "No such charge"}},
    )
    with pytest.raises(PaymentNotFoundError):
        await payment_service.fetch("ch_missing")
```

### 10.4 Fixtures, Factories, and Determinism {#fixtures}

**Use factories for complex model creation.** polyfactory generates valid Pydantic models with realistic random data, eliminating hand-crafted fixture dictionaries that drift from the model definition.

```python
# tests/factories.py
from polyfactory.factories.pydantic_factory import ModelFactory

from myproject.models import User, Order, PaymentRecord


class UserFactory(ModelFactory):
    __model__ = User

    role = "user"  # override specific fields; rest are auto-generated


class OrderFactory(ModelFactory):
    __model__ = Order

    status = "pending"
    amount_cents = ModelFactory.__random__.randint(100, 100000)


# In tests
def test_admin_can_see_all_orders() -> None:
    admin = UserFactory.build(role="admin")
    orders = OrderFactory.batch(5)
    assert all_visible(admin, orders)
```

**Determinism.** Set `PYTHONHASHSEED=0` in the test environment to neutralize hash randomization. Use `pytest-randomly` to randomize test *order* (catching order-dependent bugs) with a fixed seed for reproducibility.

```toml
[tool.pytest.ini_options]
addopts = ["-p", "randomly", "--randomly-seed=last"]  # rerun with same order on failure
```

**`pytest-timeout`.** Long-running or hanging tests mask bugs -- a coroutine that never resolves looks like a slow test until it times out CI. Set a global timeout:

```toml
[tool.pytest.ini_options]
timeout = 30  # seconds; individual tests can override with @pytest.mark.timeout(n)
```

### 10.5 Time and Clock Testing {#time-testing}

Never call `datetime.now()` or `time.time()` directly inside business logic. Pass the current time as a parameter, or use a clock abstraction that can be overridden in tests. For the common case of patching `datetime.now`, use `time-machine`:

```python
import time_machine
from datetime import datetime, timezone

async def test_invoice_expires_after_30_days() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with time_machine.travel(created_at, tick=False):
        invoice = await create_invoice(amount=100)

    future = datetime(2026, 2, 1, tzinfo=timezone.utc)  # 31 days later
    with time_machine.travel(future, tick=False):
        assert invoice.is_expired()
```

`time-machine` patches `datetime.now()`, `datetime.utcnow()`, `time.time()`, `time.localtime()`, and `time.gmtime()` atomically, making it more reliable than `freezegun` for async code where multiple coroutines may be reading the clock concurrently.

### 10.6 Property-Based Testing: hypothesis {#property-testing}

hypothesis generates a large number of inputs automatically, searching for edge cases that break your invariants. It excels at:
- Parsing functions (any input must either parse successfully or raise a documented exception, never silently corrupt)
- Serialization round-trips (serialize then deserialize must recover the original value)
- Mathematical invariants (sum of parts equals total)
- Security properties (valid input must never cause a panic or information leak)

```python
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite


@composite
def valid_usernames(draw: st.DrawFn) -> str:
    length = draw(st.integers(min_value=3, max_value=64))
    chars = draw(st.lists(
        st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
        min_size=length,
        max_size=length,
    ))
    return "".join(chars)


@given(username=valid_usernames())
@settings(max_examples=500)
def test_username_validation_accepts_valid_inputs(username: str) -> None:
    """hypothesis: all valid usernames must be accepted without error."""
    user = CreateUserRequest(username=username, email="test@example.com", role="user", age=25)
    assert user.username == username


@given(username=st.text(min_size=1, max_size=200))
def test_username_validation_never_panics(username: str) -> None:
    """hypothesis: validation must either accept or raise ValidationError, never panic."""
    try:
        CreateUserRequest(username=username, email="test@example.com", role="user", age=25)
    except Exception as exc:
        # Only ValidationError is acceptable for bad input
        from pydantic import ValidationError as PydanticValidationError
        assert isinstance(exc, PydanticValidationError), (
            f"Unexpected exception type {type(exc)} for username {username!r}"
        )
```

### 10.7 Mutation Testing: mutmut {#mutation-testing}

Mutation testing verifies that your tests actually detect bugs by introducing small, deliberate code changes ("mutations") and checking that the test suite fails. If a mutation passes all tests, your coverage is insufficient -- you have a line covered but the behavior on that line is not verified.

mutmut is appropriate for critical business logic (pricing calculations, authorization checks, cryptographic operations). It is too slow for a Tier 1 gate -- use it as a quarterly audit or pre-release check on high-risk modules.

```bash
# Run mutmut on a specific module
uv run mutmut run --paths-to-mutate src/myproject/pricing.py

# Show surviving mutants (mutations your tests did not catch)
uv run mutmut results

# Show the diff for a specific surviving mutant
uv run mutmut show 42
```

A surviving mutant typically indicates one of: (1) a missing assertion in a test that covers the line, (2) a test that covers the line but does not verify the behavior it produces, or (3) dead code that no test path reaches (covered by `--cov-fail-under=100` but not by mutation testing).

---


## 11. HTTP Server / Web API {#http-server}

### 11.1 FastAPI (Default) {#fastapi}

FastAPI is the default framework for all new Python HTTP services as of 2026. It is built on top of Starlette (the ASGI toolkit) and is Pydantic-native, meaning request and response body validation, serialization, and documentation all derive from the same Pydantic models you use throughout the codebase. The result is automatic OpenAPI and JSON Schema docs (served at `/docs` and `/redoc`) that are always in sync with the actual code -- no separate documentation step required.

FastAPI should be chosen over all alternatives when starting a new HTTP service. Its async-first design means request handlers are `async def` by default, which integrates cleanly with `asyncio`, `httpx.AsyncClient`, async SQLAlchemy 2.x, and every other async library in the stack. It wins on three axes simultaneously: developer experience (Pydantic integration, auto-docs), production correctness (type-checked request parsing, response serialization with `response_model`), and performance (Starlette's raw throughput, augmented by Pydantic v2's Rust core for validation).

**When to use FastAPI vs. the alternatives:**
- FastAPI: new greenfield REST APIs, internal services, ML serving endpoints, anything that benefits from automatic OpenAPI docs and Pydantic-validated I/O.
- Starlette (see 11.2): when you need fine-grained ASGI middleware control and FastAPI's overhead or abstractions are unwanted.
- Litestar (see 11.2): when team preferences favor more opinionated conventions than FastAPI provides, or when built-in dependency injection patterns are preferred.
- Flask (see 11.4): only for legacy codebases or extremely simple one-route services where the team is already heavily invested in Flask's ecosystem.
- Django (see 11.4): when you need an admin interface, a full ORM (Django ORM), authentication, or the full Django ecosystem; not for pure API services.

**Minimal working example:**

```python
# src/api/main.py
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

log = structlog.get_logger()


class ItemCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=128)]
    price: Annotated[float, Field(gt=0)]


class ItemResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int
    name: str
    price: float


# In-memory store for example purposes only
_store: dict[int, ItemResponse] = {}
_counter = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api.startup")
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="Item Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemCreate) -> ItemResponse:
    global _counter
    _counter += 1
    item = ItemResponse(id=_counter, name=body.name, price=body.price)
    _store[item.id] = item
    log.info("item.created", item_id=item.id, name=item.name)
    return item


@app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int) -> ItemResponse:
    item = _store.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
```

**Production configuration:**

Use lifespan context managers (the `asynccontextmanager` approach shown above) rather than the deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` decorators, which were removed in FastAPI 0.115+. The lifespan pattern is also the place to initialize connection pools, load ML models, and create shared state.

```python
# Production lifespan: initialize DB pool and shared HTTPX client
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_engine: AsyncEngine | None = None
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _engine, _http_client
    _engine = create_async_engine("postgresql+asyncpg://...", pool_size=10, max_overflow=5)
    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        follow_redirects=False,
        verify=True,
        http2=True,
    )
    yield
    await _engine.dispose()
    await _http_client.aclose()
```

**Common antipatterns:**

```python
# Antipattern: dict-based responses bypass Pydantic validation and OpenAPI generation
@app.get("/items/{item_id}")
async def get_item_bad(item_id: int) -> dict:
    return {"id": item_id, "name": "thing"}  # no schema, no validation, no docs

# Correct pattern: always declare response_model and return the Pydantic instance
@app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item_good(item_id: int) -> ItemResponse:
    item = _store.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

```python
# Antipattern: creating a new DB connection per request
@app.get("/users/{user_id}")
async def get_user_bad(user_id: int):
    engine = create_async_engine("postgresql+asyncpg://...")  # created per request -- wrong
    async with engine.begin() as conn:
        ...

# Correct pattern: inject the session via FastAPI's Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/users/{user_id}")
async def get_user_good(user_id: int, db: AsyncSession = Depends(get_db)):
    ...
```

**Gotchas:**
- Always set `response_model` explicitly; omitting it leaks internal fields and breaks OpenAPI docs.
- `HTTPException` with a detail dict is serialized as JSON. Never put internal stack traces in `detail`.
- Background tasks (`BackgroundTasks`) run in the same process after the response is sent -- they are not a substitute for a real task queue (see section 19). For anything that can fail, retry, or take more than a second, use arq or Celery.
- Middleware must be added before startup, not after `app = FastAPI(...)` in the same request cycle.

---

### 11.2 Starlette and Litestar {#starlette-litestar}

**Starlette** is the ASGI micro-framework that FastAPI is built on. It provides WebSocket support, static file serving, template rendering via Jinja2, middleware chaining, and a `TestClient` based on HTTPX. You should reach for raw Starlette when building custom ASGI middleware layers, protocol-level adapters, WebSocket-heavy applications, or when FastAPI's Pydantic-validation layer adds overhead you cannot afford in a hot path. Starlette provides `Request`, `Response`, `JSONResponse`, `WebSocket`, and `Route` directly. The tradeoff: you lose Pydantic-native request parsing and auto-generated OpenAPI docs.

```python
# Starlette example: minimal JSON API with route-level typing
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


async def homepage(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "1.0"})


async def item_detail(request: Request) -> JSONResponse:
    item_id = request.path_params["item_id"]
    return JSONResponse({"id": item_id})


app = Starlette(
    debug=False,
    routes=[
        Route("/", homepage),
        Route("/items/{item_id:int}", item_detail),
    ],
)
```

**Litestar** (formerly Starlite) is a production-ready FastAPI alternative with stronger built-in conventions: a class-based controller system, first-class dependency injection (separate from Pydantic), integrated DTOs, OpenAPI 3.1 docs, and a cache layer. Litestar's controller pattern is idiomatic when grouping related routes:

```python
# Litestar example: controller-based routing
from litestar import Controller, Litestar, get, post
from litestar.dto import DataclassDTO
from dataclasses import dataclass


@dataclass
class Item:
    id: int
    name: str
    price: float


class ItemController(Controller):
    path = "/items"

    @get("/{item_id:int}")
    async def get_item(self, item_id: int) -> Item:
        return Item(id=item_id, name="Widget", price=9.99)

    @post("/")
    async def create_item(self, data: Item) -> Item:
        return data


app = Litestar(route_handlers=[ItemController])
```

Litestar is a reasonable choice when a team wants more structure than FastAPI provides, built-in caching decorators, or the class-based controller model for larger route trees. Its community is smaller than FastAPI's -- expect fewer third-party tutorials and plugins. Both Starlette and Litestar remain compatible with the same ASGI servers (uvicorn, granian, hypercorn).

---

### 11.3 ASGI Servers: uvicorn, hypercorn, granian {#asgi-servers}

The ASGI server is the process that receives TCP connections, implements HTTP/1.1 and HTTP/2 framing, manages worker processes, and calls into your ASGI app. Choosing the wrong server is invisible in development but critical in production.

**uvicorn** is the standard ASGI server in 2026. It is fast, well-documented, and supported by the FastAPI/Starlette authors. For production, always run uvicorn via `gunicorn` with the uvicorn worker class, which gives you process management, graceful restarts, and signal handling:

```bash
# Production launch via gunicorn + uvicorn workers
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 30 \
  --graceful-timeout 10 \
  --keep-alive 5
```

**granian** is a Rust-native ASGI server that has seen rapid adoption since 2024. It implements both RSGI (its own protocol) and ASGI, and benchmarks show 2-5x throughput over uvicorn for CPU-bound workloads. For IO-bound services (DB queries, external HTTP calls) the difference is smaller. Granian is the recommended alternative when raw throughput under load is a priority:

```bash
# granian production launch
granian --interface asgi --host 0.0.0.0 --port 8000 --workers 4 src.api.main:app
```

**hypercorn** supports HTTP/3 (QUIC) and HTTP/2 Server Push, making it the server of choice when HTTP/3 support is a hard requirement. Its throughput is comparable to uvicorn for standard workloads. Use hypercorn when deploying services to environments where clients benefit from HTTP/3's reduced connection latency (mobile-heavy APIs, high-latency last-mile connections):

```bash
# hypercorn with HTTP/3
hypercorn src.api.main:app --bind "[::]:8000" --quic-bind "[::]:8443"
```

**Decision matrix:**

| Requirement | Server |
|---|---|
| Default, well-supported, production-proven | uvicorn + gunicorn |
| Maximum raw throughput, benchmarking | granian |
| HTTP/3 (QUIC) support | hypercorn |
| Simplest local development | `uvicorn src.api.main:app --reload` |

**Gotchas:**
- Never run `uvicorn src.api.main:app --reload` in production. The `--reload` flag disables process isolation and leaks file handles.
- With gunicorn, `--workers` should be `(2 * CPU cores) + 1` for IO-bound apps. For CPU-bound apps (heavy computation per request), match CPU core count.
- ASGI apps must not share mutable state between workers. Use Redis or a database for shared state; in-process globals are invisible to sibling workers.

---

### 11.4 Flask and Django {#flask-django}

**Flask** is a synchronous WSGI micro-framework. In 2026, it is not a greenfield choice for new Python services. However, Flask is acceptable in two scenarios: (1) existing Flask codebases that would cost more to migrate than to maintain, and (2) extremely simple single-file scripts where the overhead of FastAPI's Pydantic wiring is disproportionate to the problem. Flask's `app.route` pattern is ergonomic for small tools. When using Flask in a new context, always run it behind gunicorn:

```python
# Flask: minimal example for legacy/simple cases
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
```

```bash
gunicorn src.app:app --workers 4 --bind 0.0.0.0:8000
```

Flask's synchronous request handling means every blocking operation (DB query, HTTP call) blocks a worker thread. Flask 2.x added `async def` support via `asgiref`, but the integration is incomplete relative to FastAPI's native async design.

**Django** occupies a fundamentally different niche from FastAPI or Flask. Django is the batteries-included framework: it ships an ORM (Django ORM), an admin interface, an authentication system, form validation, a templating engine, and a migrations system (inspired Alembic). Django is the correct choice when you need all of these components and want them to work together out of the box -- for example, a content management system, an e-commerce admin backend, or an internal tool with user management.

Django REST Framework (DRF) adds API-layer features (serializers, ViewSets, browsable API) on top of Django. In 2026, `django-ninja` (which brings FastAPI-style Pydantic validation to Django views) is a popular alternative to DRF for teams that want Pydantic I/O validation within Django.

```python
# django-ninja: Pydantic-style API inside Django
from ninja import NinjaAPI, Schema

api = NinjaAPI()


class UserIn(Schema):
    name: str
    email: str


class UserOut(Schema):
    id: int
    name: str


@api.post("/users", response=UserOut)
def create_user(request, payload: UserIn) -> UserOut:
    user = User.objects.create(name=payload.name, email=payload.email)
    return UserOut(id=user.id, name=user.name)
```

The rule: if you need the Django admin interface, Django ORM, or Django's authentication system, use Django. If you need a pure API service, use FastAPI.

---

## 12. Web UI Frameworks {#web-ui}

### 12.1 Selection Guide {#web-ui-selection}

Python's web UI landscape in 2026 has fragmented into distinct niches. No single framework is the right answer for every problem -- the correct choice depends on the audience, interactivity model, deployment target, and whether the UI is incidental to the application or its primary purpose.

Use this guide before reaching for a framework:

| Use case | Framework |
|---|---|
| Admin panel, monitoring dashboard, internal form-based tool | NiceGUI |
| Data dashboard with charts, ML demo, analyst-facing tool | Streamlit |
| Full-stack Python app with complex server-side state | Reflex |
| Content site or marketing page with islands of interactivity (HTMX-style) | FastHTML |
| ML model demo, Hugging Face Space, prompt iteration UI | Gradio |
| General-purpose SPA requiring full frontend control | FastAPI + React/Vue (not covered here -- use a JavaScript framework) |

All five frameworks allow you to write Python code that produces a browser-based interface. They differ fundamentally in their execution model and deployment story, which is why the selection matters more than it appears at first glance.

---

### 12.2 NiceGUI (Default for Apps) {#nicegui}

NiceGUI is the default recommendation for internal tools, admin panels, operations dashboards, and any Python application that needs a polished browser-based UI but where the developers are Python engineers, not frontend engineers. NiceGUI is built on FastAPI and Vue.js. Its Python API creates Vue components that communicate with the FastAPI backend over a WebSocket connection, meaning the application logic stays entirely in Python while the UI renders in the browser.

NiceGUI is chosen as the default for apps because it handles the full application lifecycle (not just the UI layer): it runs its own FastAPI instance, manages WebSocket state, and can render natively as a desktop window via its `native=True` option, which uses a system webview. This makes it the only Python UI framework in this list that cleanly serves both browser-based and desktop-window deployment from the same codebase.

```python
# NiceGUI: admin panel with form, table, and live updates
import asyncio
from datetime import datetime

from nicegui import app, ui


async def fetch_records() -> list[dict]:
    # Replace with actual DB query
    await asyncio.sleep(0.1)
    return [{"id": 1, "name": "Alice", "ts": datetime.utcnow().isoformat()}]


@ui.page("/")
async def index():
    with ui.card().classes("w-full"):
        ui.label("Operations Dashboard").classes("text-2xl font-bold")

    table = ui.table(
        columns=[
            {"name": "id", "label": "ID", "field": "id"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "ts", "label": "Timestamp", "field": "ts"},
        ],
        rows=[],
    ).classes("w-full")

    async def refresh():
        rows = await fetch_records()
        table.rows = rows
        table.update()

    ui.button("Refresh", on_click=refresh)
    await refresh()


ui.run(host="0.0.0.0", port=8080, title="Ops Dashboard", reload=False)
```

**Production configuration:** NiceGUI's `ui.run()` accepts `host`, `port`, `ssl_certfile`, `ssl_keyfile`, and `storage_secret` (for session encryption). For multi-worker deployments, NiceGUI requires sticky sessions (route clients to the same backend instance) because WebSocket state is per-process. Use a reverse proxy (nginx, Caddy) with ip-hash or cookie-based affinity.

```python
# NiceGUI desktop window mode (wraps a system webview)
ui.run(native=True, window_size=(1200, 800), title="My Tool", reload=False)
```

**Gotchas:**
- NiceGUI's WebSocket connection means the server must stay alive for the UI to remain interactive. If the server process restarts, clients see a disconnected state.
- Do not block the event loop inside NiceGUI handlers. All slow operations (DB queries, HTTP calls, file I/O) must be `async def` or dispatched via `run.io_bound()` / `run.cpu_bound()`.
- NiceGUI bundles Vue components into its own distribution. Upgrading NiceGUI may change component behavior without a Python API change. Pin NiceGUI versions in `pyproject.toml`.

---

### 12.3 Streamlit (Data Dashboards) {#streamlit}

Streamlit is the dominant framework for data dashboards and ML demos. Its execution model is deliberately simple: every user interaction re-runs the entire Python script from top to bottom. This "reactive script" model makes it trivially easy to build dashboards -- you write a Python script and Streamlit handles state, rendering, and the widget-to-rerun cycle automatically.

The simplicity that makes Streamlit excellent for dashboards is also its central limitation. Complex stateful applications (multi-step wizards, live-updating feeds, fine-grained state management) require increasingly heavy use of `st.session_state` and `st.cache_data`, which fights the framework's grain. For those cases, prefer NiceGUI or Reflex.

Streamlit is the right choice when: the audience is analysts or data scientists, the primary output is charts and tables, and the application logic is a linear data pipeline (load -> transform -> visualize).

```python
# Streamlit: data dashboard with filtering and Plotly chart
import polars as pl
import streamlit as st
import plotly.express as px


@st.cache_data(ttl=300)  # cache for 5 minutes; invalidated on rerun after TTL
def load_sales_data() -> pl.DataFrame:
    # Replace with actual data source
    return pl.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "revenue": [120_000, 135_000, 128_000, 145_000, 162_000, 158_000],
            "region": ["North", "North", "South", "South", "North", "South"],
        }
    )


def main() -> None:
    st.title("Sales Dashboard")
    st.caption("Revenue by month and region")

    df = load_sales_data()

    regions = df["region"].unique().to_list()
    selected_regions = st.multiselect(
        "Filter by region", options=regions, default=regions
    )

    filtered = df.filter(pl.col("region").is_in(selected_regions))

    fig = px.bar(
        filtered.to_pandas(),  # Plotly requires pandas or dict for now
        x="month",
        y="revenue",
        color="region",
        title="Monthly Revenue",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(filtered, use_container_width=True)


if __name__ == "__main__":
    main()
```

**Production deployment:** Use `streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true`. For containerized deployments, set `STREAMLIT_SERVER_HEADLESS=true`. Streamlit Cloud (free tier) is the fastest path to a shareable URL for internal tools.

**Gotchas:**
- Every widget interaction re-runs the whole script. Expensive operations must be wrapped in `@st.cache_data` or `@st.cache_resource`.
- `st.session_state` is per-user-session, not shared between users. For shared state (e.g., a live counter), use Redis.
- Streamlit does not support `asyncio` event loop in the main thread. Async DB queries require `asyncio.run()` wrapping, which is inefficient. Prefer sync DB drivers (`psycopg2`, `sqlite3`) in Streamlit apps.

---

### 12.4 Reflex (Full-Stack Python) {#reflex}

Reflex is a full-stack Python framework that compiles server-side Python state management into FastAPI (backend) and React (frontend). The developer writes only Python; Reflex generates the React components and the FastAPI WebSocket layer. State classes are Python classes that inherit from `rx.State`; state mutations trigger reactive re-renders in the browser.

Reflex is the right choice when you need a full-featured web application -- not just a dashboard -- but want to stay entirely in Python. Its compile step means you need a build phase before deployment, which differentiates it from Streamlit and NiceGUI.

```python
# Reflex: counter app demonstrating state management
import reflex as rx


class CounterState(rx.State):
    count: int = 0

    def increment(self) -> None:
        self.count += 1

    def decrement(self) -> None:
        self.count -= 1

    def reset_count(self) -> None:
        self.count = 0


def counter_page() -> rx.Component:
    return rx.vstack(
        rx.heading("Counter", size="2xl"),
        rx.text(f"Count: {CounterState.count}", font_size="xl"),
        rx.hstack(
            rx.button("Decrement", on_click=CounterState.decrement),
            rx.button("Reset", on_click=CounterState.reset_count, color_scheme="gray"),
            rx.button("Increment", on_click=CounterState.increment, color_scheme="blue"),
        ),
        align="center",
        spacing="4",
    )


app = rx.App()
app.add_page(counter_page, route="/")
```

**Gotchas:** Reflex's state persistence is in-memory by default; for production you need a Redis-backed state backend. The compile step adds 10-30 seconds to cold deployment. Reflex is under active development -- check the changelog before upgrading across minor versions.

---

### 12.5 FastHTML (HTMX-style Sites) {#fasthtml}

FastHTML combines Python with HTMX to produce server-rendered HTML sites with islands of interactivity without a JavaScript build step. It is built on Starlette and uvicorn. The programming model is "return HTML fragments from Python functions, swap them into the DOM via HTMX attributes." This is the Python answer to the HTMX architecture pattern.

FastHTML is appropriate for: content-heavy sites, marketing pages, simple web applications where the complexity of a React/Vue SPA is unwarranted, and internal tools where the developer prefers server-rendered HTML over JSON APIs. It is not appropriate for highly interactive UIs with complex client-side state (use Reflex or a JavaScript framework).

```python
# FastHTML: simple HTMX-powered list with live add
from fasthtml.common import (
    A, Body, Button, Div, Form, H1, Head, Html, Input,
    Li, Script, Title, Titled, Ul, fast_app, serve
)

app, rt = fast_app()

_items: list[str] = ["Item A", "Item B"]


def item_list() -> Ul:
    return Ul(*[Li(item) for item in _items], id="item-list")


@rt("/")
def get():
    return Titled(
        "FastHTML Demo",
        item_list(),
        Form(
            Input(name="item", placeholder="New item"),
            Button("Add", type="submit"),
            hx_post="/add",
            hx_target="#item-list",
            hx_swap="outerHTML",
        ),
    )


@rt("/add")
def post(item: str):
    _items.append(item)
    return item_list()


serve()
```

**Gotchas:** FastHTML's in-process list (`_items` above) is not shared across workers. For multi-process deployments, replace in-memory state with a database. HTMX-style development requires understanding which DOM fragment each endpoint returns -- `hx_target` and `hx_swap` attributes must match endpoint response shapes.

---

### 12.6 Gradio (ML Demos) {#gradio}

Gradio is specifically designed for ML model demos, inference UIs, and Hugging Face Spaces. It is not a general-purpose web UI framework. Its strengths are: zero-configuration deployment to Hugging Face Spaces, built-in support for image/audio/video/file upload inputs and outputs, and a concise Python API that maps directly to model function signatures.

Use Gradio when: you are prototyping a model, creating a Hugging Face Space, or building a UI for a single inference function. Do not use Gradio as the UI layer for production applications -- use NiceGUI or Streamlit instead.

```python
# Gradio: image classification demo
import gradio as gr
import numpy as np


def classify_image(image: np.ndarray) -> dict[str, float]:
    # Replace with actual model inference
    return {"cat": 0.87, "dog": 0.10, "bird": 0.03}


demo = gr.Interface(
    fn=classify_image,
    inputs=gr.Image(type="numpy", label="Upload an image"),
    outputs=gr.Label(num_top_classes=3, label="Predictions"),
    title="Image Classifier",
    description="Upload an image to see classification results.",
    examples=[],  # add example image paths here
)

if __name__ == "__main__":
    demo.launch(server_port=7860, share=False)
```

For Hugging Face Spaces deployment, `demo.launch()` with no arguments uses the Spaces runtime. The `share=True` parameter creates a public Gradio tunnel URL -- acceptable for demos, not for production (traffic routes through Gradio's relay servers).

---

## 13. Desktop GUI {#desktop-gui}

### 13.1 PySide6 (Default Commercial) {#pyside6}

PySide6 is the default recommendation for Python desktop GUI applications in commercial and proprietary contexts. It is Qt for Python, the official Python binding for the Qt 6 framework, maintained by The Qt Company. Critically, PySide6 is licensed under LGPL 3.0, which means it can be included in proprietary applications without triggering copyleft requirements -- you can ship a commercial desktop application using PySide6 without open-sourcing your application code.

This license distinction is the single most important reason to choose PySide6 over PyQt6. PyQt6, the competing Qt Python binding from Riverbank Computing, uses GPL v3, meaning any application that imports PyQt6 must itself be GPL v3 unless you purchase a commercial PyQt license. PySide6 eliminates this requirement entirely under LGPL.

Qt 6 via PySide6 provides: a full widget toolkit (buttons, tables, trees, dialogs, text editors), a signals-and-slots event system, Qt Designer for visual layout editing, QML for declarative UI design, Qt Multimedia, Qt Network, and hundreds of other modules. It is the most feature-complete GUI toolkit available for Python.

```python
# PySide6: minimal application with main window and menu
import sys

from PySide6.QtCore import QSettings, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("My Application")
        self.resize(800, 600)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self._label = QLabel("Ready")
        layout.addWidget(self._label)

        # Menu bar
        file_menu = self.menuBar().addMenu("File")
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._on_quit)
        file_menu.addAction(quit_action)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Application started")

    @Slot()
    def _on_quit(self) -> None:
        QApplication.quit()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MyApp")
    app.setOrganizationName("MyOrg")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

**Async integration:** Qt's event loop (`app.exec()`) and Python's `asyncio` event loop run on the same thread and conflict by default. Use `qasync` to bridge them:

```python
# qasync: running asyncio coroutines inside a PySide6 application
import asyncio
import sys

import qasync
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
import httpx


class AsyncWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        button = QPushButton("Fetch Data")
        button.clicked.connect(self._on_fetch)
        layout.addWidget(button)

    def _on_fetch(self) -> None:
        asyncio.ensure_future(self._fetch_async())

    async def _fetch_async(self) -> None:
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get("https://httpbin.org/get")
            print(response.json())


def main() -> None:
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = AsyncWindow()
    window.show()
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
```

**Gotchas:**
- All UI updates must happen on the main thread. Use `QThread` with signals to pass results from worker threads to the UI.
- Never create a `QApplication` after the first one; use `QApplication.instance()` to retrieve it.
- PySide6 signal connections must be made to `@Slot`-decorated methods for the garbage collector to behave predictably.
- Packaging PySide6 applications for distribution requires `PyInstaller` or `Nuitka`. The Qt shared libraries add 30-50 MB to the distribution size.

---

### 13.2 CustomTkinter (Simple Tools) {#customtkinter}

CustomTkinter is a modern-looking replacement for the standard Tkinter widget toolkit. It ships as a pure-Python package with no external dependencies beyond Tkinter (which is bundled with the CPython distribution on macOS and Windows). The widgets use rounded corners, customizable color themes, and a generally more contemporary appearance than vanilla Tkinter.

CustomTkinter is the right choice for simple internal tools where: the developer wants minimal setup (no Qt install), the tool is not commercially distributed, and the UI complexity is low (a few forms, labels, buttons, and text inputs). Its limitations -- no tree view, limited table support, no MDI, no native platform integration beyond basic dialogs -- make it unsuitable for complex applications.

```python
# CustomTkinter: simple configuration tool
import customtkinter as ctk


def main() -> None:
    ctk.set_appearance_mode("system")  # "dark", "light", or "system"
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Config Tool")
    app.geometry("400x300")

    ctk.CTkLabel(app, text="API Endpoint").grid(row=0, column=0, padx=20, pady=10, sticky="w")
    endpoint_entry = ctk.CTkEntry(app, placeholder_text="https://api.example.com")
    endpoint_entry.grid(row=0, column=1, padx=20, pady=10)

    ctk.CTkLabel(app, text="Timeout (s)").grid(row=1, column=0, padx=20, pady=10, sticky="w")
    timeout_entry = ctk.CTkEntry(app, placeholder_text="30")
    timeout_entry.grid(row=1, column=1, padx=20, pady=10)

    def on_save() -> None:
        endpoint = endpoint_entry.get()
        timeout = timeout_entry.get()
        print(f"Saving: endpoint={endpoint}, timeout={timeout}")

    ctk.CTkButton(app, text="Save", command=on_save).grid(
        row=2, column=0, columnspan=2, pady=20
    )

    app.mainloop()


if __name__ == "__main__":
    main()
```

---

### 13.3 Cross-Platform: Toga, Flet, Kivy {#cross-platform-gui}

Three additional frameworks cover cross-platform use cases beyond desktop-only deployment:

**Toga (BeeWare)** provides native widgets on Windows, macOS, Linux, iOS, and Android from a single Python codebase. The BeeWare project compiles Python to native binaries for each platform via `briefcase`. Toga is less mature than Qt -- widget coverage is incomplete and platform behavior is inconsistent as of 2026 -- but it is the only pure-Python path to iOS and Android from a single codebase without wrapping a web view.

```python
# Toga: BeeWare native cross-platform app skeleton
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW


class HelloApp(toga.App):
    def startup(self) -> None:
        main_box = toga.Box(style=Pack(direction=COLUMN))
        self.label = toga.Label("Hello, World!", style=Pack(padding=10))
        button = toga.Button("Press me", on_press=self.on_press, style=Pack(padding=10))
        main_box.add(self.label)
        main_box.add(button)
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def on_press(self, widget: toga.Button) -> None:
        self.label.text = "Button was pressed."


def main() -> HelloApp:
    return HelloApp("Hello World", "org.example.hello")
```

**Flet** is built on Flutter's widget library, using a Python-to-Dart bridge. It supports desktop, browser, and mobile deployment with a Flutter Material Design UI. Flet's programming model is imperative and event-driven. Because Flet runs a Flutter engine, it ships a larger binary than CustomTkinter but produces better mobile UIs than Toga:

```python
# Flet: counter application
import flet as ft


def main(page: ft.Page) -> None:
    page.title = "Counter"
    count = ft.Text("0", size=40)

    def on_increment(_e: ft.ControlEvent) -> None:
        count.value = str(int(count.value) + 1)
        page.update()

    page.add(
        ft.Column(
            [count, ft.ElevatedButton("Increment", on_click=on_increment)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


ft.app(target=main)
```

**Kivy** is a mature, touch-first cross-platform framework that targets mobile (iOS, Android), desktop, and Raspberry Pi. It uses its own rendering engine (OpenGL-based) rather than native widgets, giving it consistent appearance across platforms. Kivy is heavy (pulls in many C extensions) and the programming model -- a declarative KV language plus Python -- has a steep learning curve. Use Kivy for touch-screen kiosks, Raspberry Pi displays, or applications where touch input is the primary interface.

**Selection summary:** PySide6 for production desktop apps. CustomTkinter for simple tools. Toga for iOS/Android native apps. Flet for Flutter-style mobile/desktop. Kivy for touch-first embedded or kiosk apps.

---

## 14. Terminal UI {#terminal-ui}

### 14.1 Textual (Default Interactive TUI) {#textual}

Textual is the 2026 standard for interactive terminal user interfaces in Python. It is built on Rich (see section 14.2), adding an async event loop, a CSS-like layout engine, widgets (DataTable, Input, Button, ListView, ProgressBar, TextArea), keyboard navigation, and mouse support. Textual applications are full terminal programs that accept user input, manage focus, and render complex layouts -- not just formatted output.

The critical distinction between Rich and Textual: Rich is for output (print a styled table, render a progress bar, format a traceback). Textual is for interactive applications (a file browser, a database client, a monitoring dashboard, a configuration wizard). If the user needs to navigate, type, select, or interact with elements, use Textual.

Textual applications run in any terminal and also in the browser via Textual Web (`textual-web` package), which serves the same application over a WebSocket with a web-based terminal renderer. This makes Textual the only TUI framework that deploys to both terminal and web without code changes.

```python
# Textual: interactive task manager TUI
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Header, Input, Label
from textual.containers import Container, Horizontal


class TaskApp(App):
    CSS = """
    Screen { align: center middle; }
    Container { width: 80%; height: 80%; }
    #input-row { height: 5; margin-bottom: 1; }
    #task-input { width: 70%; }
    #add-btn { width: 28%; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_selected", "Delete"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container():
            with Horizontal(id="input-row"):
                yield Input(placeholder="Enter task description...", id="task-input")
                yield Button("Add Task", id="add-btn", variant="primary")
            yield DataTable(id="task-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("ID", "Task", "Status")
        self._next_id = 1

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._add_task()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._add_task()

    def _add_task(self) -> None:
        task_input = self.query_one("#task-input", Input)
        description = task_input.value.strip()
        if not description:
            return
        table = self.query_one(DataTable)
        table.add_row(str(self._next_id), description, "Pending")
        self._next_id += 1
        task_input.clear()

    def action_delete_selected(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            table.remove_row(table.get_row_at(table.cursor_row)[0])


def main() -> None:
    app = TaskApp()
    app.run()


if __name__ == "__main__":
    main()
```

**Production considerations:** Textual's async event loop means all blocking operations must use `asyncio` or run in a thread via `run_in_executor`. Long-running operations should be wrapped in `self.run_worker()` to keep the UI responsive. Textual CSS provides a subset of flexbox-style layout that is documented at https://textual.textualize.io/.

**Gotchas:**
- Textual applications cannot run inside non-interactive terminals (pipes, redirected stdout). Always test with an actual TTY.
- Widgets are composed in `compose()` -- do not create widgets in `__init__`. The `on_mount()` handler is the place to populate data after the DOM is ready.
- `query_one()` raises `NoMatches` if the selector matches nothing and `TooManyMatches` if it matches more than one. Provide unique IDs for widgets you query directly.

---

### 14.2 Rich Integration {#rich-tui}

Rich is the standard for styled terminal output in this codebase (mandated in `docs/rules-python.md` section 3.10). This section clarifies the boundary between Rich (output) and Textual (interactive apps) and shows how they compose.

Rich's primary objects:
- `Console`: the output sink; use a single shared instance per application.
- `Table`: formatted tables with column alignment, padding, styles.
- `Panel`: boxed content with optional title.
- `Progress`: live progress bars with spinners and elapsed time.
- `Syntax`: source-code highlighting.
- `Traceback`: formatted exception display.

Textual uses Rich internally for rendering -- every Textual widget is ultimately rendered as Rich markup on a canvas. When building a Textual application, you can use Rich markup strings directly in widget labels and text content. However, you do not create a Rich `Console` inside a Textual application; use Textual's built-in rendering instead.

```python
# Rich: structured output for CLI tools and scripts
import structlog
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table

console = Console()
log = structlog.get_logger()


def display_results(records: list[dict]) -> None:
    table = Table(title="Query Results", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Score", justify="right", style="green")

    for record in records:
        table.add_row(str(record["id"]), record["name"], f"{record['score']:.2f}")

    console.print(table)


def process_with_progress(items: list[str]) -> None:
    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing items...", total=len(items))
        for item in items:
            _process_item(item)
            progress.advance(task)


def _process_item(item: str) -> None:
    import time
    time.sleep(0.05)  # replace with actual work
```

**Antipattern: mixing Rich and Textual output streams**

```python
# Antipattern: printing to Rich Console inside a Textual app corrupts the display
from rich.console import Console
from textual.app import App

console = Console()

class MyApp(App):
    def on_mount(self) -> None:
        console.print("This will corrupt the Textual display")  # WRONG

# Correct pattern: use Textual's built-in notification or log
class MyApp(App):
    def on_mount(self) -> None:
        self.notify("Application mounted")   # correct: Textual notification
        self.log("Internal debug message")   # correct: Textual log
```

---

## 15. Notebooks {#notebooks}

### 15.1 marimo (Default Reactive Notebook) {#marimo}

marimo is the default recommendation for new Python notebook work. It replaces Jupyter for greenfield projects. The design difference is fundamental: in a marimo notebook, each cell declares its dependencies through Python variable names, and marimo automatically determines the directed acyclic graph (DAG) of cell dependencies. When you change a cell, all downstream cells recompute automatically. This eliminates the most dangerous property of Jupyter notebooks: the ability to run cells out of order and leave the notebook in an inconsistent state.

The second major advantage is file format. marimo notebooks are stored as `.py` files -- pure Python modules with marimo-specific metadata as function decorators. This means: git diffs are readable, `ruff` and `mypy` work on notebooks without conversion, the notebook can be run as a standard Python script (`python notebook.py`), and it can be converted to a Streamlit-like web app (`marimo run notebook.py`). Jupyter's `.ipynb` format is a JSON blob; diffs are unreadable, and static analysis requires `nbqa` or conversion steps.

```python
# marimo notebook: example cell structure (saved as a .py file)
import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import marimo as mo
    return mo, pl


@app.cell
def _(pl):
    # This cell depends on `pl` from the cell above
    df = pl.read_csv("sales_data.csv")
    return (df,)


@app.cell
def _(df, mo):
    # This cell depends on `df` -- will recompute when df changes
    filtered = df.filter(pl.col("revenue") > 100_000)
    mo.show_table(filtered)
    return (filtered,)


@app.cell
def _(mo):
    # Interactive slider -- changing value reruns dependent cells
    threshold = mo.ui.slider(start=0, stop=500_000, step=10_000, value=100_000, label="Revenue threshold")
    return (threshold,)


@app.cell
def _(df, threshold):
    # Depends on both df and the slider value
    import plotly.express as px
    filtered = df.filter(pl.col("revenue") > threshold.value)
    fig = px.bar(filtered.to_pandas(), x="month", y="revenue", title=f"Revenue > {threshold.value:,}")
    fig
    return (filtered, fig)


if __name__ == "__main__":
    app.run()
```

**Running marimo:**

```bash
# Interactive notebook editor
marimo edit notebook.py

# Run as a web app (Streamlit-like, no edit capabilities)
marimo run notebook.py --port 8080

# Run as a Python script (no UI)
python notebook.py
```

**Gotchas:**
- marimo's DAG requires that all inter-cell dependencies are through Python variable names. Side effects (writing files, mutating global state) outside the return tuple break reactivity and should be avoided.
- marimo notebooks cannot import each other directly. Extract shared logic into a regular Python module in `src/` and import from both notebooks.
- `mo.ui` widgets (sliders, dropdowns, text inputs) create reactive bindings. The widget's `.value` property is read in downstream cells. Cells that read `.value` will recompute when the user changes the widget.

---

### 15.2 Jupyter {#jupyter}

Jupyter remains the right choice when: the team has an existing corpus of `.ipynb` notebooks that would require migration effort, notebook sharing requires `.ipynb` format (e.g., GitHub rendering, nbviewer), a third-party tool requires `.ipynb` format as input, or the team is deeply invested in JupyterHub / JupyterLab extensions.

Jupyter's ecosystem advantage -- nbval, nbformat, papermill, nbconvert, nbqa, and thousands of extensions -- is real and should not be discarded without evaluating the migration cost.

For Jupyter notebooks in production pipelines, use papermill for parameterized execution:

```bash
# papermill: run notebook with parameters and capture output
papermill input_notebook.ipynb output_notebook.ipynb \
  -p data_path /data/sales_2026.csv \
  -p threshold 100000 \
  --no-progress-bar
```

**Quality controls for Jupyter:**
- Use `nbqa ruff notebooks/` to lint notebooks without conversion.
- Use `nbqa mypy notebooks/` for type checking.
- Use `nbstripout` as a pre-commit hook to strip output cells from version control (prevents committing large binary blobs and sensitive data in cell outputs).
- Use `jupyter nbconvert --to script notebook.ipynb` to produce a `.py` version for CI testing.

```bash
# pre-commit configuration for Jupyter notebooks
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/kynan/nbstripout
    rev: 0.7.1
    hooks:
      - id: nbstripout
```

**Antipattern: treating Jupyter as a production compute environment**

```
# Antipattern: running cells out of order to "fix" an intermediate result
Cell 1: df = load_data()       # run
Cell 4: df = df.head(100)      # run out of order to reduce data
Cell 2: cleaned = clean(df)    # run -- now uses the head(100) version
Cell 3: result = analyze(cleaned)  # result is wrong but notebook looks correct

# Correct pattern: use marimo (enforces DAG), or use papermill for
# parameterized Jupyter execution in a defined order.
```

---

## 16. Data Science Stack {#data-science}

### 16.1 The 2026 Stack: DuckDB + Polars + PyArrow {#duckdb-polars-pyarrow}

The 2026 Python data science stack for analytical workloads is: **Polars** for dataframe manipulation, **DuckDB** for SQL-style OLAP queries and data ingestion, and **PyArrow** as the interchange format and Parquet I/O layer. These three libraries interoperate without copying data: DuckDB can query Polars DataFrames directly, Polars can consume PyArrow tables natively, and all three share the Arrow columnar memory format.

This stack is preferred over pandas for new projects because:
- Polars is 10-100x faster than pandas for pipeline operations due to its Rust implementation and lazy evaluation engine.
- DuckDB provides ANSI SQL over local files (Parquet, CSV, Arrow) without a database server -- the "SQLite for analytics."
- PyArrow provides Parquet I/O with predicate pushdown, column pruning, and metadata handling that is far richer than pandas' Parquet support.
- All three integrate natively with cloud storage (S3, GCS, Azure Blob) via their respective extension mechanisms.

The stack is not a wholesale replacement for everything:
- pandas remains acceptable in existing codebases or when integrating with libraries that only accept `pandas.DataFrame` (some visualization tools, sklearn estimators, legacy APIs).
- numpy remains essential for numerical computation, linear algebra, and interfacing with C extensions.
- scipy remains the standard for scientific computing on top of numpy.

---

### 16.2 DuckDB {#duckdb}

DuckDB is an in-process OLAP database engine. It runs inside the Python process (no server, no network), reads and writes Parquet, Arrow, CSV, and JSON directly, and exposes a SQL API. DuckDB is the correct tool when you need to: run complex analytical SQL on files or DataFrames without a database server, aggregate multi-file Parquet datasets, join large tables that fit on disk but not in memory, or prototype queries before moving to a warehouse.

DuckDB's zero-copy integration with Polars and PyArrow is its defining feature: you can register a Polars DataFrame as a DuckDB table and query it with SQL -- no serialization, no copying.

```python
# DuckDB: in-process OLAP with Polars and Parquet
import duckdb
import polars as pl

# Connect to an in-memory DuckDB instance
con = duckdb.connect(":memory:")

# Register a Polars DataFrame as a virtual table
sales_df = pl.read_parquet("sales/*.parquet")
con.register("sales", sales_df)

# Query with SQL -- DuckDB reads the Polars DataFrame in zero-copy
result = con.execute("""
    SELECT
        region,
        DATE_TRUNC('month', sale_date) AS month,
        SUM(amount) AS total_revenue,
        COUNT(*) AS transaction_count
    FROM sales
    WHERE amount > 0
    GROUP BY region, month
    ORDER BY month, total_revenue DESC
""").pl()  # .pl() returns a Polars DataFrame directly

print(result)
```

**Reading Parquet directly (no DataFrame intermediate):**

```python
# DuckDB can query Parquet files without loading into memory first
result = duckdb.execute("""
    SELECT region, SUM(amount) as revenue
    FROM read_parquet('s3://my-bucket/sales/2026/*.parquet')
    GROUP BY region
    ORDER BY revenue DESC
    LIMIT 20
""").pl()
```

**Production configuration:**

```python
# DuckDB with tuned memory and parallelism
con = duckdb.connect(
    database=":memory:",
    config={
        "threads": 8,
        "memory_limit": "4GB",
        "temp_directory": "/tmp/duckdb_spill",
    },
)

# For persistent databases (file-backed):
con = duckdb.connect("analytics.duckdb")
```

**Antipattern: using pandas as the DuckDB result format**

```python
# Antipattern: converting to pandas when Polars is available
result = con.execute("SELECT ...").fetchdf()  # returns pandas -- adds pandas dependency

# Correct pattern: use .pl() for Polars or .arrow() for PyArrow
result_polars = con.execute("SELECT ...").pl()
result_arrow = con.execute("SELECT ...").arrow()
```

**Gotchas:**
- DuckDB's in-memory mode loses all data on connection close. For persistent analytics databases, use a file path: `duckdb.connect("analytics.duckdb")`.
- DuckDB is not a row-oriented transactional database. Do not use it for OLTP workloads (high-frequency inserts/updates). Use PostgreSQL for that.
- DuckDB 1.x supports multiple readers but only one writer at a time. Concurrent write access from multiple processes requires an external locking mechanism or a file-backed WAL setup.

---

### 16.3 PyArrow {#pyarrow}

PyArrow is the columnar in-memory format and I/O library that underpins the 2026 Python data stack. Polars, pandas 2.x, DuckDB, and many cloud connectors all use Arrow as their internal representation. PyArrow provides: Parquet read/write with predicate pushdown and column pruning, Arrow IPC (inter-process communication via shared memory or file), and the `pyarrow.dataset` API for partitioned multi-file datasets.

Use PyArrow for all Parquet I/O operations -- it provides richer metadata control, compression options, and predicate pushdown than `fastparquet` or pandas' built-in Parquet support.

```python
# PyArrow: Parquet I/O with schema enforcement and predicate pushdown
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

# Define schema explicitly for write-time validation
schema = pa.schema([
    ("id", pa.int64()),
    ("name", pa.utf8()),
    ("amount", pa.float64()),
    ("sale_date", pa.date32()),
    ("region", pa.dictionary(pa.int16(), pa.utf8())),  # efficient for low-cardinality strings
])


def write_sales_parquet(data: list[dict], output_path: Path) -> None:
    table = pa.Table.from_pylist(data, schema=schema)
    pq.write_table(
        table,
        output_path,
        compression="zstd",           # zstd: best compression/speed tradeoff
        compression_level=3,
        use_dictionary=True,           # dictionary-encode string columns
        write_statistics=True,         # enables predicate pushdown on read
        row_group_size=100_000,        # tune for your query patterns
    )


def read_sales_filtered(parquet_path: Path, min_amount: float) -> pa.Table:
    # Predicate pushdown: DuckDB/Parquet skips row groups that cannot match
    return pq.read_table(
        parquet_path,
        filters=[("amount", ">=", min_amount)],  # pushed down to row-group level
        columns=["id", "name", "amount", "region"],  # column pruning
    )
```

**Partitioned dataset API for multi-file Parquet:**

```python
# pyarrow.dataset: read partitioned Parquet datasets efficiently
import pyarrow.dataset as ds

dataset = ds.dataset(
    "s3://my-bucket/sales/",
    format="parquet",
    partitioning=ds.partitioning(
        pa.schema([("year", pa.int32()), ("month", pa.int32())]),
        flavor="hive",  # year=2026/month=04/...
    ),
)

# Scan only 2026 data -- partition pruning skips other directories
scanner = dataset.scanner(
    filter=(ds.field("year") == 2026),
    columns=["region", "amount", "sale_date"],
)
table = scanner.to_table()
```

**Gotchas:**
- PyArrow uses 1-based null counting (`pa.array.null_count` is a valid attribute). Be consistent about null handling when converting between Arrow and Python types.
- Arrow arrays are immutable. To modify data, convert to a mutable format (pandas, Polars), operate, then convert back.
- Use `zstd` compression for Parquet files in production. `snappy` (the pandas default) has lower compression ratio. `gzip` has better compression but slower decompression. For archival storage with infrequent reads, use `brotli` or `lz4`.

---

### 16.4 numpy and scipy {#numpy-scipy}

**numpy** is the foundation of all numerical Python work. Its n-dimensional array (`ndarray`) is the universal data container for numerical computation, and virtually every scientific Python library (scipy, scikit-learn, PyTorch, matplotlib) either consumes or produces numpy arrays. numpy is not being replaced by Polars -- they serve different purposes. Polars is a DataFrame library for tabular data pipelines. numpy is for array mathematics, linear algebra, and numerical algorithms.

numpy is the correct tool for: matrix operations, Fourier transforms, random number generation, sorting and searching large arrays, and any algorithm that operates on dense numerical arrays.

```python
# numpy: vectorized operations and linear algebra
import numpy as np

# Vectorized operations -- always prefer over Python loops
x = np.linspace(0, 2 * np.pi, 1_000_000)
y = np.sin(x) * np.exp(-x / 10)  # 1M elements, computed in C

# Linear algebra
A = np.random.default_rng(42).standard_normal((100, 100))
b = np.random.default_rng(42).standard_normal(100)
x_solution = np.linalg.solve(A, b)  # Ax = b

# Structured arrays for heterogeneous data
dtype = np.dtype([("id", np.int32), ("value", np.float64), ("flag", np.bool_)])
records = np.zeros(1000, dtype=dtype)
records["id"] = np.arange(1000)

# Random number generation (numpy 1.17+ style -- do not use np.random.seed)
rng = np.random.default_rng(seed=42)
samples = rng.normal(loc=0.0, scale=1.0, size=(100, 50))
```

**Antipattern: looping over numpy arrays**

```python
# Antipattern: Python loop over a numpy array negates all performance benefit
import numpy as np

arr = np.arange(1_000_000)
result = np.zeros(1_000_000)
for i in range(len(arr)):      # 50-100x slower than vectorized equivalent
    result[i] = arr[i] ** 2 + arr[i]

# Correct pattern: vectorized operations
result = arr ** 2 + arr
```

**scipy** provides scientific computing algorithms on top of numpy: statistics (`scipy.stats`), optimization (`scipy.optimize`), signal processing (`scipy.signal`), linear algebra extensions (`scipy.linalg`), interpolation (`scipy.interpolate`), spatial algorithms (`scipy.spatial`), and sparse matrices (`scipy.sparse`). Use scipy when numpy's built-in functions are insufficient:

```python
# scipy: optimization and statistical testing
from scipy import optimize, stats
import numpy as np


def rosenbrock(x: np.ndarray) -> float:
    """Rosenbrock function -- standard optimization test case."""
    return float(sum(100.0 * (x[1:] - x[:-1]**2.0)**2.0 + (1 - x[:-1])**2.0))


result = optimize.minimize(rosenbrock, x0=np.array([0.0, 0.0]), method="L-BFGS-B")
print(f"Minimum at x={result.x}, f={result.fun:.6f}")

# Two-sample t-test
control = stats.norm.rvs(loc=5.0, scale=1.0, size=100, random_state=42)
treatment = stats.norm.rvs(loc=5.5, scale=1.0, size=100, random_state=43)
t_stat, p_value = stats.ttest_ind(control, treatment)
print(f"t={t_stat:.3f}, p={p_value:.4f}")
```

---

### 16.5 DataFrame Validation: pandera {#pandera}

pandera 0.29+ is the "Pydantic for DataFrames." It defines schemas for pandas, Polars, and other DataFrame backends and validates data at schema boundaries, catching type errors, constraint violations, and unexpected nulls before they propagate silently through a pipeline.

pandera is the correct tool for: notebook/ML pipeline validation, API response validation involving tabular data, ETL pipeline schema enforcement, and data contracts between pipeline stages. Its Pydantic v2 integration means pandera schemas compose naturally with the rest of the Pydantic-first codebase.

```python
# pandera: schema definition and validation for Polars DataFrames
import pandera.polars as pa
import polars as pl
from pandera.typing.polars import DataFrame, Series


class SalesSchema(pa.DataFrameModel):
    """Schema for validated sales records."""
    id: Series[int] = pa.Field(gt=0, unique=True)
    name: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 128})
    amount: Series[float] = pa.Field(ge=0.0)
    region: Series[str] = pa.Field(isin=["North", "South", "East", "West"])

    class Config:
        strict = True      # fail on extra columns
        coerce = False     # do not coerce types -- fail on mismatch


def process_sales(raw: pl.DataFrame) -> DataFrame[SalesSchema]:
    """Validate input against schema; raises SchemaError on violation."""
    return SalesSchema.validate(raw, lazy=True)  # lazy=True: collect all errors before raising
```

**Validating at pipeline stage boundaries:**

```python
# pandera decorator: validate input and output types automatically
from pandera.typing.polars import DataFrame
import pandera.polars as pa


class RawSales(pa.DataFrameModel):
    id: pa.typing.polars.Series[int]
    raw_amount: pa.typing.polars.Series[str]  # string before cleaning


class CleanSales(pa.DataFrameModel):
    id: pa.typing.polars.Series[int]
    amount: pa.typing.polars.Series[float]


@pa.check_types
def clean_sales(df: DataFrame[RawSales]) -> DataFrame[CleanSales]:
    return df.with_columns(
        pl.col("raw_amount").str.replace_all(r"[^0-9.]", "").cast(pl.Float64).alias("amount")
    ).drop("raw_amount")
```

**pandera vs Great Expectations (see 16.6):**
- pandera (12 dependencies): schema definition in code, Pydantic-native, fast, suitable for notebook validation and ML pipelines.
- Great Expectations (107 dependencies): data warehouse integration, monitoring dashboards, alerting, documentation generation, suitable for production data quality systems.
- Use pandera for development-time schema enforcement. Use Great Expectations when data quality is a production operational concern with monitoring requirements.

---

### 16.6 Production Data Quality: Great Expectations {#great-expectations}

Great Expectations (GE) is a production data quality framework that provides: expectation suites (declarative data contracts), data docs (auto-generated HTML documentation of expectations and validation results), and integration with data warehouses (Snowflake, BigQuery, Redshift, Spark). GE is appropriate when data quality is an operational requirement, not just a development concern -- when violations need to generate alerts, be tracked over time, or integrate with orchestration tools like Airflow or Dagster.

The weight of GE (107 package dependencies vs pandera's 12) reflects its scope. It is not appropriate for notebook-level validation or ML pipeline schemas. Reach for GE when all of these are true: (1) the data source is external and uncontrolled, (2) violations need to be logged and monitored over time, (3) a non-technical stakeholder needs to review data quality reports, and (4) the data pipeline runs in a scheduled production environment.

```python
# Great Expectations: minimal expectation suite setup
import great_expectations as gx
import pandas as pd

# Initialize a GE Data Context (manages config, stores, and data docs)
context = gx.get_context()

# Add a data source -- here, a pandas DataFrame
datasource = context.sources.add_or_update_pandas(name="sales_source")
asset = datasource.add_dataframe_asset(name="sales_records")

# Build a batch request
batch_request = asset.build_batch_request(dataframe=pd.read_csv("sales.csv"))

# Create an expectation suite
suite = context.add_or_update_expectation_suite("sales_suite")

# Create a validator
validator = context.get_validator(
    batch_request=batch_request,
    expectation_suite_name="sales_suite",
)

# Define expectations
validator.expect_column_to_exist("id")
validator.expect_column_values_to_not_be_null("id")
validator.expect_column_values_to_be_between("amount", min_value=0)
validator.expect_column_values_to_be_in_set("region", value_set=["North", "South", "East", "West"])
validator.expect_column_values_to_be_unique("id")
validator.save_expectation_suite(discard_failed_expectations=False)

# Run validation
checkpoint = context.add_or_update_checkpoint(
    name="sales_checkpoint",
    validator=validator,
)
results = checkpoint.run()
context.view_validation_result(results)
```

---

## 17. Machine Learning {#machine-learning}

### 17.1 scikit-learn {#scikit-learn}

scikit-learn is the canonical library for classical machine learning in Python. It provides: regression (linear, ridge, lasso, elastic net, SVR), classification (logistic regression, SVM, random forests, gradient boosting), clustering (k-means, DBSCAN, hierarchical), dimensionality reduction (PCA, t-SNE, UMAP via umap-learn), preprocessing (StandardScaler, MinMaxScaler, OneHotEncoder, PolynomialFeatures), and the `Pipeline` and `ColumnTransformer` APIs for building end-to-end ML workflows.

scikit-learn's `Pipeline` is the single most important abstraction for preventing data leakage in ML workflows. Always build preprocessing and model steps inside a Pipeline -- never fit a scaler on the entire dataset before splitting.

```python
# scikit-learn: pipeline with preprocessing, feature engineering, and model
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Simulated data
rng = np.random.default_rng(42)
n = 1000
X = {
    "age": rng.integers(18, 80, size=n).astype(float),
    "income": rng.exponential(50_000, size=n),
    "region": rng.choice(["North", "South", "East", "West"], size=n),
    "category": rng.choice(["A", "B", "C"], size=n),
}
import pandas as pd
X_df = pd.DataFrame(X)
y = (X_df["income"] > 50_000).astype(int).values

numeric_features = ["age", "income"]
categorical_features = ["region", "category"]

# Preprocessing: numeric (scale) + categorical (encode)
numeric_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])
categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
])

preprocessor = ColumnTransformer([
    ("num", numeric_transformer, numeric_features),
    ("cat", categorical_transformer, categorical_features),
])

# Full pipeline: preprocessor + model
model = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)),
])

# Cross-validation (fit on each fold; no data leakage)
X_train, X_test, y_train, y_test = train_test_split(X_df, y, test_size=0.2, stratify=y, random_state=42)
cv_scores = cross_val_score(model, X_train, y_train, cv=StratifiedKFold(n_splits=5), scoring="roc_auc")
print(f"CV AUC: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

# Final fit and evaluation
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred))
```

**Antipattern: fitting the scaler before the train/test split**

```python
# Antipattern: data leakage -- scaler sees test data during fit
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_df[numeric_features])  # sees all data including test set
X_train, X_test = train_test_split(X_scaled)             # leakage already occurred

# Correct pattern: include scaler in Pipeline; fit only on training data
model = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression())])
model.fit(X_train, y_train)      # scaler is fit only on X_train
model.predict(X_test)            # scaler transforms X_test using train parameters
```

---

### 17.2 PyTorch (Default DL Framework) {#pytorch}

PyTorch is the default deep learning framework in 2026. It is recommended over TensorFlow/Keras for new projects because: it has become the dominant framework in research (virtually all major research papers release PyTorch code), it supports Apple Silicon (MPS backend) natively, its eager execution model is easier to debug than TensorFlow's graph mode, and TorchScript provides a production serving path that does not require the Python runtime.

```python
# PyTorch: minimal training loop with MPS/CUDA/CPU device selection
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")  # Apple Silicon
    return torch.device("cpu")


class MLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(p=0.3),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(p=0.3),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def train(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    for X_batch, y_batch in loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        optimizer.zero_grad()
        logits = model(X_batch)
        loss = criterion(logits, y_batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(X_batch)
    return total_loss / len(loader.dataset)


def main() -> None:
    device = get_device()
    torch.manual_seed(42)

    # Synthetic data
    X = torch.randn(1000, 20)
    y = (X[:, 0] + X[:, 1] > 0).long()
    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    model = MLP(input_dim=20, hidden_dim=64, output_dim=2).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(10):
        loss = train(model, loader, optimizer, criterion, device)
        print(f"Epoch {epoch+1:02d}: loss={loss:.4f}")

    # Export to TorchScript for production serving (no Python runtime required)
    scripted = torch.jit.script(model.cpu())
    torch.jit.save(scripted, "model.pt")
```

**Gotchas:**
- Always call `optimizer.zero_grad()` before `loss.backward()`. Gradients accumulate by default; forgetting this produces incorrect updates.
- Move both model and batch data to the same device before calling `forward()`.
- TorchScript has limitations: not all Python constructs are scriptable. Test `torch.jit.script(model)` early in development.
- Use `torch.no_grad()` context manager during inference to save memory and speed up computation.
- TensorFlow/Keras: use only when an existing codebase mandates it. TensorFlow's development velocity has decreased relative to PyTorch. Do not start new projects on TensorFlow.

---

### 17.3 JAX (Research / High Performance) {#jax}

JAX is Google's research framework combining numpy-compatible array operations with composable functional transforms: `jit` (just-in-time compilation to XLA), `grad` (automatic differentiation), `vmap` (vectorization over a batch dimension), and `pmap` (parallelization over devices). JAX is not a drop-in replacement for PyTorch -- it requires a functional programming style (no in-place mutation, no stateful modules) but rewards that discipline with dramatically higher performance on custom research code.

JAX is the right choice when: the workload is research code requiring custom gradients, the team is comfortable with functional programming, or the performance requirements exceed what PyTorch's eager mode can deliver for the specific computation. JAX is not beginner-friendly. Choose PyTorch for most DL work and reach for JAX specifically when you need XLA compilation or custom gradient transforms.

```python
# JAX: function composition, JIT, and gradient computation
import jax
import jax.numpy as jnp
from jax import grad, jit, vmap


# Pure functions only -- no in-place mutation
def relu(x: jnp.ndarray) -> jnp.ndarray:
    return jnp.maximum(0, x)


def linear(params: tuple, x: jnp.ndarray) -> jnp.ndarray:
    W, b = params
    return x @ W + b


def model(params: list, x: jnp.ndarray) -> jnp.ndarray:
    for W, b in params[:-1]:
        x = relu(linear((W, b), x))
    W, b = params[-1]
    return linear((W, b), x)


def mse_loss(params: list, X: jnp.ndarray, y: jnp.ndarray) -> jnp.ndarray:
    predictions = model(params, X)
    return jnp.mean((predictions - y) ** 2)


# JIT compile the loss and its gradient
loss_and_grad = jit(jax.value_and_grad(mse_loss))

# vmap: vectorize over a batch dimension without explicit loops
batched_model = vmap(lambda x: model(params, x))  # type: ignore[name-defined]

# Initialize parameters with JAX's PRNG (explicit keys, not global state)
key = jax.random.PRNGKey(42)
key, k1, k2 = jax.random.split(key, 3)
W1 = jax.random.normal(k1, shape=(20, 64)) * 0.01
b1 = jnp.zeros(64)
W2 = jax.random.normal(k2, shape=(64, 1)) * 0.01
b2 = jnp.zeros(1)
params = [(W1, b1), (W2, b2)]
```

**Gotchas:** JAX requires explicit PRNG key management -- there is no global random state. Pass keys explicitly and split them rather than reusing. JAX arrays are immutable; use `jax.ops.index_update` patterns for indexed mutation. The first `jit`-compiled call is slow (compilation); subsequent calls are fast.

---

### 17.4 Hugging Face Ecosystem {#huggingface}

The Hugging Face ecosystem is the standard for working with pre-trained NLP and vision models in Python. The core packages:

- `transformers`: model architectures and pre-trained weights for BERT, GPT, T5, LLaMA, Whisper, CLIP, etc.
- `datasets`: efficient streaming dataset loading from the Hugging Face Hub and local files.
- `evaluate`: standardized metrics (accuracy, F1, BLEU, ROUGE, perplexity).
- `peft`: parameter-efficient fine-tuning (LoRA, QLoRA, prefix tuning) -- fine-tune large models with a fraction of the memory and compute.
- `accelerate`: distributed training and device management across multiple GPUs, TPUs, and mixed-precision.
- `tokenizers`: fast Rust-backed tokenizers.

```python
# Hugging Face: fine-tuning a text classifier with PEFT (LoRA)
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)
import evaluate
import numpy as np


def main() -> None:
    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    base_model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

    # LoRA configuration: only train a small number of adapter parameters
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=8,                   # LoRA rank
        lora_alpha=32,
        target_modules=["q_lin", "k_lin"],
        lora_dropout=0.1,
        bias="none",
    )
    model = get_peft_model(base_model, lora_config)
    model.print_trainable_parameters()  # typically <1% of total params

    # Load and tokenize dataset
    dataset = load_dataset("imdb", split={"train": "train[:2000]", "test": "test[:500]"})

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=256)

    tokenized = dataset.map(tokenize, batched=True)

    # Training
    metric = evaluate.load("accuracy")

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        return metric.compute(predictions=predictions, references=labels)

    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=3,
        per_device_train_batch_size=16,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        report_to="none",  # disable wandb/mlflow for this example
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        compute_metrics=compute_metrics,
    )
    trainer.train()
```

---

### 17.5 Experiment Tracking {#experiment-tracking}

Experiment tracking records hyperparameters, metrics, artifacts, and code versions across training runs. Without it, ML development degenerates into unreproducible experiments where the best model checkpoint is lost or the conditions that produced it are unknown.

**MLflow** is the default for self-hosted or enterprise environments. It provides a tracking UI, model registry, and can be backed by any SQL database. It integrates with scikit-learn, PyTorch, and Hugging Face via autologging.

**Weights & Biases (wandb)** is the most popular cloud-based experiment tracker in research and fast-iteration settings. It provides superior visualization (parallel coordinates, custom plots), a sweep API for hyperparameter search, and artifact versioning. Use wandb when: the team values visualization over self-hosting, cloud storage of artifacts is acceptable, and budget allows.

**Aim** is an open-source alternative to wandb that runs self-hosted. It provides the wandb-style visualization (parallel coordinates, custom dashboards) without cloud storage costs.

```python
# MLflow: experiment tracking for a PyTorch training loop
import mlflow
import mlflow.pytorch
import torch.nn as nn

# Start a run
with mlflow.start_run(run_name="mlp_baseline"):
    # Log hyperparameters
    mlflow.log_params({
        "learning_rate": 1e-3,
        "batch_size": 64,
        "hidden_dim": 128,
        "epochs": 20,
    })

    for epoch in range(20):
        train_loss = train(...)
        val_accuracy = evaluate(...)

        # Log metrics per epoch
        mlflow.log_metrics({
            "train_loss": train_loss,
            "val_accuracy": val_accuracy,
        }, step=epoch)

    # Log the trained model as an MLflow artifact
    mlflow.pytorch.log_model(model, "model", registered_model_name="mlp_classifier")
```

```python
# wandb: experiment tracking with sweep support
import wandb

wandb.init(
    project="sales-classifier",
    config={
        "learning_rate": 1e-3,
        "architecture": "MLP",
        "dataset": "sales_2026",
        "epochs": 20,
    },
)

for epoch in range(20):
    train_loss = train(...)
    wandb.log({"train_loss": train_loss, "epoch": epoch})

wandb.finish()
```

---

## 18. Visualization {#visualization}

### 18.1 Selection Guide {#viz-selection}

Python's visualization landscape has stabilized around four libraries with distinct strengths. Choose based on output target, interactivity requirements, and audience:

| Use case | Library |
|---|---|
| Interactive charts in notebooks, web apps, Streamlit dashboards | Plotly |
| Exploratory notebook analysis, grammar-of-graphics declarative style | Altair |
| Publication-quality static figures, journal plots, precise layout control | Matplotlib |
| Statistical visualization (distributions, correlations, pair plots) | Seaborn |

The hierarchy: Seaborn is built on Matplotlib. Altair is a wrapper around Vega-Lite. Plotly is independent. When in doubt, start with Plotly Express for interactive work and Matplotlib for static output.

---

### 18.2 Plotly (Default Interactive) {#plotly}

Plotly is the default for all interactive visualizations. It renders in Jupyter notebooks, Streamlit apps, NiceGUI pages, FastAPI responses (as JSON), and standalone HTML files. Plotly Express provides a high-level API (one function call per chart type). `plotly.graph_objects` provides full control over every trace, axis, annotation, and layout property.

```python
# Plotly Express: quick interactive charts
import plotly.express as px
import polars as pl

df = pl.DataFrame({
    "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    "revenue": [120_000, 135_000, 128_000, 145_000, 162_000, 158_000],
    "region": ["North", "South", "North", "South", "North", "South"],
})

# Bar chart with color grouping
fig = px.bar(
    df.to_pandas(),
    x="month",
    y="revenue",
    color="region",
    title="Monthly Revenue by Region",
    labels={"revenue": "Revenue (USD)", "month": "Month"},
    template="plotly_white",
)
fig.update_layout(
    yaxis_tickformat="$,.0f",
    legend_title="Region",
    bargap=0.15,
)
fig.show()
# Save as standalone HTML
fig.write_html("revenue_chart.html", include_plotlyjs="cdn")
```

```python
# plotly.graph_objects: full control for multi-trace custom charts
import plotly.graph_objects as go
import numpy as np

x = np.linspace(0, 4 * np.pi, 200)
fig = go.Figure()
fig.add_trace(go.Scatter(x=x, y=np.sin(x), name="sin(x)", line={"color": "royalblue", "width": 2}))
fig.add_trace(go.Scatter(x=x, y=np.cos(x), name="cos(x)", line={"color": "firebrick", "width": 2, "dash": "dash"}))
fig.update_layout(
    title="Trigonometric Functions",
    xaxis_title="x",
    yaxis_title="f(x)",
    legend={"x": 0.02, "y": 0.98},
    template="plotly_white",
    width=900,
    height=450,
)
fig.show()
```

**Serving Plotly charts via FastAPI:**

```python
# Return a Plotly chart as JSON from a FastAPI endpoint
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import plotly.express as px
import plotly.io as pio

app = FastAPI()


@app.get("/chart", response_class=HTMLResponse)
async def get_chart() -> str:
    fig = px.line(x=[1, 2, 3], y=[4, 1, 7], title="Sample Chart")
    return pio.to_html(fig, full_html=True, include_plotlyjs="cdn")
```

---

### 18.3 Altair (Grammar of Graphics / Notebooks) {#altair}

Altair is a declarative visualization library based on the Vega-Lite grammar. Instead of describing *how* to draw a chart, you describe *what* the chart should encode: data, mark type, channels (x, y, color, size), and scales. Altair's concise, composable API makes it the preferred choice for exploratory analysis in notebooks, especially when building linked and layered views.

Altair charts serialize to Vega-Lite JSON, which renders interactively in JupyterLab, marimo, and VS Code. For large datasets (>5000 rows), use the VegaFusion backend to enable server-side aggregation.

```python
# Altair: declarative chart composition
import altair as alt
import polars as pl

df = pl.DataFrame({
    "x": list(range(50)),
    "y": [i**0.5 + i * 0.1 for i in range(50)],
    "category": ["A" if i % 2 == 0 else "B" for i in range(50)],
}).to_pandas()

# Scatter plot with color encoding and interactive selection
selection = alt.selection_point(fields=["category"], bind="legend")

chart = (
    alt.Chart(df)
    .mark_circle(size=60)
    .encode(
        x=alt.X("x:Q", title="X Axis"),
        y=alt.Y("y:Q", title="Y Axis"),
        color=alt.Color("category:N", legend=alt.Legend(title="Category")),
        opacity=alt.condition(selection, alt.value(1.0), alt.value(0.1)),
        tooltip=["x", "y", "category"],
    )
    .add_params(selection)
    .properties(width=500, height=350, title="Altair Scatter with Selection")
    .interactive()
)

chart
```

**Layered views:**

```python
# Altair: layered chart with trend line
import numpy as np

base = alt.Chart(df).mark_circle().encode(x="x:Q", y="y:Q")
trend = base.transform_regression("x", "y").mark_line(color="red", strokeDash=[5, 3])
layered = alt.layer(base, trend).properties(width=500, height=300)
layered
```

**Gotchas:** Altair passes the full dataset as JSON into the chart specification by default. For datasets larger than 5000 rows, enable VegaFusion: `alt.data_transformers.enable("vegafusion")`. Altair 5+ uses Pydantic v2 for its schema validation; ensure `pydantic >= 2.0` is installed.

---

### 18.4 Matplotlib (Static / Publication) {#matplotlib}

Matplotlib is the foundation of Python's static visualization ecosystem. It provides pixel-level control over every element of a figure and is required for: journal-quality figures in PDF/SVG format, complex multi-panel layouts, custom annotations, embedding in PySide6/PyQt6 GUIs, and any visualization that needs precise control over fonts, spacing, tick placement, and line styles.

Always use the object-oriented API (`fig, ax = plt.subplots()`), not the stateful pyplot API (`plt.plot()`, `plt.xlabel()`). The pyplot API relies on implicit global state that breaks in multi-figure, multi-threaded, and notebook contexts.

```python
# Matplotlib: publication-quality multi-panel figure
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Always use object-oriented API
fig, axes = plt.subplots(1, 2, figsize=(10, 4), dpi=150)
fig.suptitle("Statistical Summary", fontsize=14, fontweight="bold")

rng = np.random.default_rng(42)
data_a = rng.normal(loc=5.0, scale=1.2, size=500)
data_b = rng.normal(loc=5.8, scale=0.9, size=500)

# Left panel: histogram with KDE
ax = axes[0]
ax.hist(data_a, bins=30, alpha=0.6, color="royalblue", label="Group A", density=True)
ax.hist(data_b, bins=30, alpha=0.6, color="firebrick", label="Group B", density=True)
ax.set_xlabel("Value", fontsize=11)
ax.set_ylabel("Density", fontsize=11)
ax.set_title("Distribution Comparison")
ax.legend(framealpha=0.7)

# Right panel: box plot
ax = axes[1]
bp = ax.boxplot([data_a, data_b], labels=["Group A", "Group B"], patch_artist=True)
bp["boxes"][0].set_facecolor("royalblue")
bp["boxes"][1].set_facecolor("firebrick")
for box in bp["boxes"]:
    box.set_alpha(0.6)
ax.set_ylabel("Value", fontsize=11)
ax.set_title("Box Plot")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

plt.tight_layout()
fig.savefig("figure.pdf", bbox_inches="tight", dpi=300)
plt.close(fig)  # always close figures to release memory
```

**Antipattern: the pyplot stateful API**

```python
# Antipattern: stateful pyplot API -- breaks in multi-figure contexts
import matplotlib.pyplot as plt
plt.figure()
plt.plot([1, 2, 3], [4, 1, 7])
plt.title("My Chart")
plt.xlabel("X")
plt.ylabel("Y")
plt.show()

# Correct pattern: object-oriented API
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot([1, 2, 3], [4, 1, 7], color="royalblue", linewidth=2)
ax.set_title("My Chart")
ax.set_xlabel("X")
ax.set_ylabel("Y")
plt.tight_layout()
fig.savefig("chart.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

---

### 18.5 Seaborn (Statistical Visualization) {#seaborn}

Seaborn is built on Matplotlib and provides a higher-level API for statistical visualization. It automatically handles categorical aggregation, confidence intervals, and faceting. Seaborn is the fastest path to standard statistical plots: pair plots, correlation heatmaps, violin plots, categorical strip plots, regression plots, and distribution plots.

Seaborn integrates with pandas DataFrames directly. All Seaborn figures are Matplotlib `Figure` objects underneath and can be customized with Matplotlib's API after Seaborn creates them.

```python
# Seaborn: statistical visualization suite
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)

rng = np.random.default_rng(42)
df = pd.DataFrame({
    "score": np.concatenate([
        rng.normal(70, 12, 150),
        rng.normal(80, 10, 150),
    ]),
    "group": ["Control"] * 150 + ["Treatment"] * 150,
    "feature_a": rng.normal(0, 1, 300),
    "feature_b": rng.normal(0, 1, 300),
})

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Violin plot: shows distribution shape and quartiles
sns.violinplot(data=df, x="group", y="score", ax=axes[0], inner="box", palette="muted")
axes[0].set_title("Score Distribution by Group")

# Regression plot: scatter with linear fit and confidence interval
sns.regplot(data=df, x="feature_a", y="score", ax=axes[1], scatter_kws={"alpha": 0.3}, line_kws={"color": "firebrick"})
axes[1].set_title("Score vs Feature A")

# Correlation heatmap
corr = df[["score", "feature_a", "feature_b"]].corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, ax=axes[2], square=True)
axes[2].set_title("Correlation Matrix")

plt.tight_layout()
fig.savefig("statistical_summary.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

---

## 19. Background Jobs and Messaging {#background-jobs}

### 19.1 arq (Default Async Queue) {#arq}

arq is the default task queue for new Python services. It is built on Redis and designed specifically for Python's `asyncio` -- all task functions are `async def`, the worker is an async event loop, and the client API is fully async. arq is the correct choice when the application is already async (FastAPI, Starlette) and the team wants a simple, Python-idiomatic task queue without the operational complexity of Celery.

arq's design philosophy: tasks are normal async Python functions, decorated with nothing at definition time -- you call them as jobs via the `ArqRedis` enqueue API. Workers are started as standalone processes and pick up jobs from Redis queues.

```python
# arq: task definitions (src/tasks/jobs.py)
import structlog
import httpx
from arq import create_pool
from arq.connections import RedisSettings

log = structlog.get_logger()


async def send_report(ctx: dict, report_id: int, recipient: str) -> dict:
    """Generate and email a report. ctx is the arq worker context."""
    log.info("report.generating", report_id=report_id, recipient=recipient)
    async with httpx.AsyncClient(verify=True) as client:
        # ... generate report, call email service, etc.
        response = await client.post(
            "https://mail-service/send",
            json={"to": recipient, "report_id": report_id},
            timeout=30.0,
        )
        response.raise_for_status()
    log.info("report.sent", report_id=report_id)
    return {"status": "sent", "report_id": report_id}


async def process_upload(ctx: dict, file_path: str, user_id: int) -> str:
    """Process an uploaded file asynchronously."""
    log.info("upload.processing", file_path=file_path, user_id=user_id)
    # ... processing logic
    return f"processed:{file_path}"


# Worker settings
class WorkerSettings:
    functions = [send_report, process_upload]
    redis_settings = RedisSettings(host="localhost", port=6379)
    max_jobs = 10
    job_timeout = 300          # seconds before a running job is considered stuck
    keep_result = 3600         # seconds to keep job results in Redis
    retry_jobs = True
    max_tries = 3
```

```python
# arq: enqueuing jobs from a FastAPI endpoint
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()
_arq_pool = None


async def get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings(host="localhost", port=6379))
    return _arq_pool


@app.post("/reports/{report_id}/send")
async def enqueue_report(report_id: int, recipient: str) -> dict:
    pool = await get_arq_pool()
    job = await pool.enqueue_job("send_report", report_id, recipient)
    return {"job_id": job.job_id, "status": "queued"}
```

```bash
# Start the arq worker
python -m arq src.tasks.jobs.WorkerSettings
```

**Gotchas:**
- arq requires Redis 6.2+ for some features. Valkey (the FOSS Redis fork) is a compatible drop-in.
- `ctx` (the first argument to every arq task) contains the worker context, including any resources initialized in `on_startup`. Use `on_startup` to create DB connections and HTTP client pools that persist across jobs within one worker process.
- arq does not support complex task graphs (chains, chords, groups). For orchestrated workflows with dependencies between tasks, use Celery (see 19.2) or a dedicated workflow orchestrator (Prefect, Dagster).

---

### 19.2 Celery (Legacy / Sync-heavy Workloads) {#celery}

Celery is the mature, battle-tested task queue that has been the Python industry standard for over a decade. It provides: complex task primitives (chains, chords, groups, canvas), multiple broker backends (Redis, RabbitMQ), result backends, periodic tasks via Celery Beat, and a robust retry and routing API.

Celery is the right choice when: (1) the team has significant existing Celery investment and migration is not justified, (2) the workload requires complex task orchestration (chains/chords/groups), (3) the application is synchronous-first and async-first arq is a poor fit, or (4) advanced routing (priority queues, rate limiting, routing by task type) is required.

Celery's async support is limited -- `async def` tasks require `gevent` or `eventlet` pool types, and the integration is less natural than arq's native asyncio design.

```python
# Celery: task definitions with retry and routing
from celery import Celery
from celery.utils.log import get_task_logger
import structlog

app = Celery(
    "myapp",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,        # acknowledge only after task completes (safer for crashes)
    worker_prefetch_multiplier=1,  # one task at a time per worker -- prevents starvation
    task_routes={
        "myapp.tasks.send_report": {"queue": "reports"},
        "myapp.tasks.process_upload": {"queue": "uploads"},
    },
)

log = get_task_logger(__name__)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def send_report(self, report_id: int, recipient: str) -> dict:
    log.info("Generating report %s for %s", report_id, recipient)
    try:
        # ... report generation and email logic
        return {"status": "sent", "report_id": report_id}
    except Exception as exc:
        raise self.retry(exc=exc)


# Chain example: generate then notify
from celery import chain

workflow = chain(
    send_report.s(report_id=42, recipient="user@example.com"),
    # ... additional chained tasks
)
workflow.apply_async()
```

```bash
# Start Celery workers with concurrency
celery -A src.tasks worker --loglevel=info --concurrency=4 -Q reports,uploads

# Start Celery Beat for periodic tasks
celery -A src.tasks beat --loglevel=info
```

---

### 19.3 Dramatiq (Alternative) {#dramatiq}

Dramatiq is a simpler, more opinionated task queue that sits between arq and Celery in complexity. It is synchronous-first (like Celery) but has a cleaner API and better default behavior: tasks acknowledge only after completion, dead-letter queues are built-in, and the middleware system is composable. Dramatiq does not support complex canvas primitives (no chords) but covers the majority of practical task queue use cases.

Use Dramatiq when the service is sync-first, the team finds Celery's configuration surface overwhelming, and the task graphs are simple (no chords/chains required).

```python
# Dramatiq: task definition and enqueue
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Retries, TimeLimit
import structlog

log = structlog.get_logger()

broker = RedisBroker(url="redis://localhost:6379")
broker.add_middleware(Retries(max_retries=3, min_backoff=1000, max_backoff=60_000))
broker.add_middleware(TimeLimit(time_limit=300_000))  # 5-minute limit per task
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="emails", max_retries=3, time_limit=30_000)
def send_welcome_email(user_id: int, email: str) -> None:
    log.info("email.sending", user_id=user_id, email=email)
    # ... send logic


# Enqueue from application code
send_welcome_email.send(user_id=123, email="user@example.com")
```

```bash
# Start Dramatiq workers
dramatiq src.tasks --processes 2 --threads 4
```

---

### 19.4 Messaging Brokers {#messaging}

Background job libraries (arq, Celery, Dramatiq) use a message broker for task queuing. Beyond task queues, direct messaging is required for: event-driven architectures, pub/sub patterns, and high-throughput streaming workloads.

**Redis / Valkey:** The default broker. `redis-py` 5.x provides both sync and async clients. Use `redis.asyncio` for async applications. Valkey is the Linux Foundation fork of Redis maintained after Redis changed its license in 2024 -- it is fully API-compatible with `redis-py`.

```python
# redis.asyncio: async Redis client for caching, pub/sub, and task queues
import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()


async def publish_event(redis_url: str, channel: str, payload: dict) -> None:
    async with aioredis.from_url(redis_url, decode_responses=True) as client:
        import orjson
        await client.publish(channel, orjson.dumps(payload).decode())
        log.info("event.published", channel=channel)


async def subscribe_events(redis_url: str, channel: str) -> None:
    async with aioredis.from_url(redis_url, decode_responses=True) as client:
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    log.info("event.received", channel=channel, data=message["data"])
```

**RabbitMQ via aio-pika:** For workloads requiring AMQP semantics (dead-letter exchanges, priority queues, complex routing), RabbitMQ with `aio-pika` is the async Python client:

```python
# aio-pika: RabbitMQ async producer
import aio_pika
import orjson


async def publish_to_rabbitmq(amqp_url: str, routing_key: str, payload: dict) -> None:
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=orjson.dumps(payload),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
```

**Kafka via aiokafka:** For high-throughput event streaming (millions of messages per second, multi-consumer fan-out, log compaction, long retention), use Kafka with `aiokafka` or `confluent-kafka-python`. Kafka is the appropriate choice when message retention, replay, and high-throughput are requirements -- not for simple task queues.

```python
# aiokafka: async Kafka producer
from aiokafka import AIOKafkaProducer
import orjson


async def produce_event(bootstrap_servers: str, topic: str, payload: dict) -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: orjson.dumps(v),
        compression_type="zstd",
    )
    await producer.start()
    try:
        await producer.send_and_wait(topic, payload)
    finally:
        await producer.stop()
```

**Broker selection:**

| Requirement | Broker |
|---|---|
| Simple task queues, small-medium scale | Redis / Valkey |
| Complex routing, dead-letters, AMQP | RabbitMQ + aio-pika |
| High-throughput streaming, replay, fan-out | Kafka + aiokafka |
| Operational simplicity, no additional infrastructure | Redis (already in stack) |

---

## 20. Caching {#caching}

### 20.1 Redis / Valkey (Default) {#redis-valkey}

Redis is the default distributed cache. For new deployments, **Valkey** is the recommended alternative -- it is the Linux Foundation fork of Redis created after Redis Ltd changed its license from BSD to SSPL in 2024. Valkey is 100% API-compatible with Redis and the `redis-py` client works with both without modification.

Use distributed caching (Redis/Valkey) when: cache state must be shared across multiple application instances, cache entries must survive application restarts, or cache size exceeds available application memory.

```python
# redis.asyncio: async cache with TTL, pipeline batching, and JSON serialization
from __future__ import annotations

import orjson
import redis.asyncio as aioredis
import structlog
from typing import Any

log = structlog.get_logger()

_redis_client: aioredis.Redis | None = None


async def get_redis(redis_url: str = "redis://localhost:6379") -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            redis_url,
            decode_responses=False,  # False for binary (orjson bytes); True for string-only data
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
    return _redis_client


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    client = await get_redis()
    serialized = orjson.dumps(value)
    await client.setex(key, ttl_seconds, serialized)
    log.debug("cache.set", key=key, ttl=ttl_seconds)


async def cache_get(key: str) -> Any | None:
    client = await get_redis()
    raw = await client.get(key)
    if raw is None:
        log.debug("cache.miss", key=key)
        return None
    log.debug("cache.hit", key=key)
    return orjson.loads(raw)


async def cache_delete(key: str) -> None:
    client = await get_redis()
    await client.delete(key)
    log.debug("cache.delete", key=key)


# Pipeline: batch multiple cache writes in one round-trip
async def cache_set_many(items: dict[str, Any], ttl_seconds: int = 300) -> None:
    client = await get_redis()
    async with client.pipeline(transaction=False) as pipe:
        for key, value in items.items():
            await pipe.setex(key, ttl_seconds, orjson.dumps(value))
        await pipe.execute()
    log.debug("cache.set_many", count=len(items))
```

**Cache invalidation pattern for FastAPI:**

```python
# FastAPI dependency: cache-aside pattern
from fastapi import Depends
from typing import Callable


def cached(key_fn: Callable, ttl: int = 300):
    """Decorator factory for cache-aside in FastAPI route handlers."""
    def decorator(func: Callable) -> Callable:
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = key_fn(*args, **kwargs)
            cached_value = await cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            await cache_set(cache_key, result, ttl_seconds=ttl)
            return result

        return wrapper
    return decorator


# Usage in a FastAPI route
@app.get("/products/{product_id}")
@cached(key_fn=lambda product_id: f"product:{product_id}", ttl=600)
async def get_product(product_id: int) -> dict:
    # ... DB query
    return {"id": product_id, "name": "Widget"}
```

**Gotchas:**
- Always use `setex` (set with expiry) rather than `set` without a TTL. Keys without expiry grow unbounded and fill Redis memory.
- Redis/Valkey is not a durable store by default. With `appendonly no` (the default), data is lost on crash. For durability, enable AOF persistence or use a separate durable store as the source of truth with Redis as a cache only.
- Do not share a single Redis database (db=0) between the cache, Celery broker, arq queue, and session store. Use separate databases (`db=1`, `db=2`, etc.) or separate Redis instances to isolate failure domains.
- The `decode_responses=True` client setting is convenient for string data but silently decodes bytes. For binary data (orjson bytes), use `decode_responses=False` and decode manually.

---

### 20.2 In-Process Caching {#in-process-cache}

In-process caching stores values in the application process's memory. It is faster than Redis (no network round-trip), requires zero infrastructure, and is appropriate when: cache state does not need to be shared between processes, the dataset fits in memory, and cache invalidation on application restart is acceptable.

Python's standard library provides two caching utilities:

- `functools.cache` (Python 3.9+): unbounded LRU cache. Equivalent to `lru_cache(maxsize=None)`. Use for pure functions with a small result space.
- `functools.lru_cache(maxsize=N)`: LRU cache with a bounded size. Once the cache reaches `maxsize` entries, the least-recently-used entry is evicted.

```python
# functools: in-process memoization
import functools
import time


# Unbounded cache -- suitable for pure functions with finite input space
@functools.cache
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


# Bounded LRU cache -- use when input space is large or unbounded
@functools.lru_cache(maxsize=256)
def expensive_lookup(key: str) -> dict:
    time.sleep(0.1)  # simulate slow lookup
    return {"key": key, "value": hash(key)}


# Introspect cache performance
info = expensive_lookup.cache_info()
print(f"hits={info.hits}, misses={info.misses}, size={info.currsize}")

# Invalidate the entire cache
expensive_lookup.cache_clear()
```

For TTL-based expiry, LFU eviction, or cache size limits beyond LRU, use **cachetools**:

```python
# cachetools: TTL and LFU in-process caches
from cachetools import TTLCache, LFUCache, cached
from cachetools.keys import hashkey
import threading

# Thread-safe TTL cache: entries expire after 5 minutes
_cache = TTLCache(maxsize=1000, ttl=300)
_lock = threading.RLock()


@cached(cache=_cache, key=lambda user_id: hashkey(user_id), lock=_lock)
def get_user_permissions(user_id: int) -> set[str]:
    # ... DB query
    return {"read", "write"}


# LFU cache: evicts least-frequently-used entries
_lfu_cache = LFUCache(maxsize=500)

@cached(cache=_lfu_cache, key=lambda symbol: hashkey(symbol))
def get_stock_quote(symbol: str) -> float:
    # ... market data lookup
    return 150.25
```

**Antipattern: mutable default argument as a manual cache**

```python
# Antipattern: mutable default as hidden cache -- breaks between test runs
def get_config(cache: dict = {}) -> dict:   # mutable default -- shared across all calls
    if not cache:
        cache.update({"key": "value"})
    return cache

# Correct pattern: functools.cache or module-level cache with explicit init
_config_cache: dict | None = None

def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = {"key": "value"}
    return _config_cache
```

---

### 20.3 aiocache (Async) {#aiocache}

aiocache provides a unified async caching API with pluggable backends: in-memory, Redis, and Memcached. Its primary value is the `@cached` decorator for async functions and the ability to swap backends (development uses memory, production uses Redis) via configuration.

```python
# aiocache: async function caching with Redis backend
from aiocache import Cache, cached
from aiocache.serializers import JsonSerializer
import structlog

log = structlog.get_logger()

# Configure the default cache globally
Cache.REDIS.configure(
    endpoint="localhost",
    port=6379,
    serializer=JsonSerializer(),
    namespace="myapp",
)


# Decorator: cache async function results with TTL
@cached(ttl=300, cache=Cache.REDIS, key_builder=lambda fn, *args, **kwargs: f"user:{args[0]}")
async def get_user_profile(user_id: int) -> dict:
    log.info("cache.miss.fetching", user_id=user_id)
    # ... DB query
    return {"id": user_id, "name": "Alice"}


# Programmatic API: set, get, delete
async def demo_aiocache() -> None:
    cache = Cache(Cache.REDIS, endpoint="localhost", port=6379, serializer=JsonSerializer())

    await cache.set("my_key", {"value": 42}, ttl=60)
    result = await cache.get("my_key")
    log.info("cache.get", result=result)

    exists = await cache.exists("my_key")
    await cache.delete("my_key")


# Multi-level: in-memory L1 + Redis L2 (aiocache multi)
from aiocache.backends.memory import SimpleMemoryCache

async def get_with_multilevel(key: str) -> dict | None:
    l1 = SimpleMemoryCache(ttl=30)
    l2 = Cache(Cache.REDIS, endpoint="localhost", port=6379, serializer=JsonSerializer())

    value = await l1.get(key)
    if value is not None:
        return value

    value = await l2.get(key)
    if value is not None:
        await l1.set(key, value, ttl=30)  # promote to L1
        return value

    return None
```

**When to use aiocache vs redis.asyncio directly:**
- Use `redis.asyncio` directly when you need full Redis API access (pub/sub, pipelines, Lua scripts, sorted sets, streams) and the caching use case is just one of many Redis usages in the application.
- Use `aiocache` when the caching concern is the primary interface and you want a clean decorator API with backend-swappable configuration (useful for testing with an in-memory backend while using Redis in production).

**Gotchas:** aiocache's `@cached` decorator does not handle `None` return values correctly by default -- a cached `None` is indistinguishable from a cache miss. If your function can legitimately return `None`, implement manual cache logic with `redis.asyncio` using a sentinel value (`""`) to distinguish cache miss from cached None.

## 21. Quality Gate Reference {#quality-gate}

### 21.1 Tier 1: Commit Gate {#tier-1}

These tools must all pass before any commit reaches the main branch. The gate is automated via `.pre-commit-config.yaml` and enforced in CI. A developer who commits without a passing Tier 1 gate has committed to a broken state.

| Tool | Command | Purpose |
|------|---------|---------|
| ruff check | `ruff check src/ tests/` | Linting (800+ rules including security subset) |
| ruff format | `ruff format --check src/ tests/` | Formatting consistency |
| mypy | `mypy --strict src/` | Static type checking in strict mode |
| pytest | `pytest tests/ --cov=src --cov-fail-under=100` | Tests + 100% coverage |
| deptry | `deptry src/` | Undeclared / unused dependencies |
| bandit | `bandit -r src/ -ll` | Security vulnerability scanning |
| pip-audit | `pip-audit` | Known CVEs in dependency graph |

**mypy must run with `--strict`.** Without `strict`, mypy silently ignores functions without type annotations (`disallow_untyped_defs = false` by default) and passes many code patterns that are type-unsafe. `--strict` enables `disallow_untyped_defs`, `disallow_any_generics`, `warn_return_any`, `no_implicit_optional`, and a dozen other checks that are all off by default.

The complete `.pre-commit-config.yaml` for Tier 1:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--strict]
        additional_dependencies:
          - pydantic>=2.9
          - types-PyYAML

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=500]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

### 21.2 Tier 2: Quality Analysis {#tier-2}

Run in CI on every pull request. These tools identify quality issues that are not outright bugs but degrade maintainability over time.

| Tool | Command | Purpose |
|------|---------|---------|
| radon cc | `radon cc src/ -a -nb` | Cyclomatic complexity -- fail on grade C+ |
| pyright | `pyright src/` | Second type checker; faster, better generics |
| semgrep | `semgrep --config auto src/` | Security pattern detection (broader than bandit) |
| interrogate | `interrogate src/ --fail-under 90` | Docstring coverage |
| osv-scanner | `osv-scanner --lockfile uv.lock` | CVEs from OSV database (broader than pip-audit) |
| detect-secrets | `detect-secrets scan` | Hardcoded secrets baseline check |

**Why both mypy and pyright?** They use different type inference engines and catch different bugs. mypy is the gate (must pass before commit). pyright is quality analysis (advisory on PR). Run both but do not require both to be clean before merge -- that creates too much friction. The development target is clean mypy; pyright findings inform refactors.

### 21.3 Tier 3: Advanced {#tier-3}

These tools are run on a cadence (weekly, pre-release, or on-demand) rather than on every commit or PR.

| Tool | Command | Cadence |
|------|---------|---------|
| mutmut | `mutmut run --paths-to-mutate src/myproject/` | Pre-release, high-risk modules |
| py-spy | `py-spy record -o profile.svg -- python -m myproject.main` | Performance regression investigation |
| pandera | In tests via `@pa.check_types` | Continuous (already in tests) |
| beartype OR typeguard | `@beartype` or `@typechecked` decorator | Selective -- add to hot paths in staging |
| wily | `wily build src/ && wily report src/` | Monthly complexity trend analysis |

**Pick beartype OR typeguard, not both.** Both provide runtime type checking via decoration. beartype checks at O(1) by inspecting only the outermost container type. typeguard checks recursively but has higher overhead. Pick based on your performance budget. Do not run both -- the overlapping diagnostic output creates noise.

### 21.4 Ruff Configuration {#ruff-config}

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
  "E", "W",     # pycodestyle
  "F",          # pyflakes
  "B",          # bugbear
  "I",          # isort
  "UP",         # pyupgrade (enforces 3.12 syntax)
  "TRY",        # exception handling patterns
  "SIM",        # simplification
  "FURB",       # reimplemented stdlib (replaces refurb tool)
  "PIE",        # anti-elision: PIE790 (no-pass/ellipsis), PIE800 (unnecessary spread)
  "ARG",        # unused function arguments
  "C901",       # cyclomatic complexity
  "PLR0911",    # too many return statements
  "PLR0912",    # too many branches
  "PLR0913",    # too many arguments
  "PLR0915",    # too many statements
  "S",          # security (bandit subset)
  "TCH",        # type-checking imports (move to TYPE_CHECKING block)
  "D",          # pydocstyle
  "RET",        # return statement simplification
  "ERA",        # eradicate commented-out code
  "FIX",        # FIXME/TODO detection
  "TD",         # TODO comment policy
]
ignore = [
  "D100",  # missing docstring in public module (covered by interrogate)
  "D104",  # missing docstring in public package
  "D107",  # missing docstring in __init__
  "S101",  # use of assert (acceptable in test files; see per-file-ignores)
]

[tool.ruff.lint.pydocstyle]
convention = "google"   # REQUIRED -- omitting this causes conflicting D-rule violations
# Without this setting, ruff selects D rules from multiple conflicting conventions
# simultaneously (google, numpy, pep257), producing thousands of contradictory errors

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-returns = 6
max-branches = 12
max-statements = 50

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
  "S101",    # assert is OK in tests
  "D",       # docstrings optional in test files
  "ARG001",  # unused function argument (common in fixtures)
]
"src/**/migrations/**/*.py" = [
  "ERA001",  # commented-out code (Alembic generates these)
]
```

**Critical bug in the slim rules doc -- missing `[tool.ruff.lint.pydocstyle] convention`.** Without specifying `convention = "google"`, ruff simultaneously enforces rules from the google, numpy, and pep257 conventions. These conventions have contradictory requirements (D200 says one-line docstrings must fit on one line; D205 says there must be a blank line after the summary). The result is thousands of conflicting violations on a file with perfectly good docstrings. `convention = "google"` or `"numpy"` must be specified.

### 21.5 mypy Configuration {#mypy-config}

```toml
# pyproject.toml

[tool.mypy]
python_version = "3.12"
strict = true                           # REQUIRED -- enables all optional checks

# strict = true implies all of these, but listed explicitly for documentation:
disallow_untyped_defs = true            # all functions must have type annotations
disallow_any_generics = true            # no bare List, Dict (use list[str], etc.)
disallow_incomplete_defs = true         # no partially-typed functions
check_untyped_defs = true               # check bodies of unannotated functions
disallow_untyped_decorators = true      # decorators must be typed
warn_return_any = true                  # warn if function returns Any
warn_unused_configs = true              # warn on unused mypy config options
warn_unused_ignores = true              # warn on unnecessary # type: ignore comments
warn_redundant_casts = true
no_implicit_optional = true             # Optional[X] must be written X | None
strict_optional = true
show_error_codes = true

# Per-module overrides for third-party libraries without stubs
[[tool.mypy.overrides]]
module = [
    "yaml.*",
    "orjson.*",
]
ignore_missing_imports = true
```

**Why `strict = true` must be explicit.** Without it, mypy's default behavior is to ignore unannotated functions entirely (`disallow_untyped_defs = false`). This means a function like:

```python
def process_payment(payment):  # no annotations
    return payment.amount * 1.1  # multiplied by float -- no type checking here
```

...passes mypy completely with no warnings. The entire purpose of mypy is nullified for any function that lacks annotations. `strict = true` is what makes mypy meaningful.

### 21.6 Pruned Tools (Redundancy Rationale) {#pruned-tools}

The following tools appeared in earlier versions of the quality gate and have been removed. The rationale for each removal is documented here to prevent re-introduction without justification.

| Tool | Reason for Removal |
|------|--------------------|
| `refurb` | ruff's `FURB` ruleset (already in `[tool.ruff.lint] select`) covers all substantive refurb checks. Running both produces duplicate diagnostics with no new signal. |
| `xenon` | ruff `C901` + radon `cc` cover cyclomatic complexity. Adding a third complexity enforcement tool (xenon) without adding new signal triples the friction for every complexity-limit violation without catching additional bugs. |
| `pylint` | ruff's `PL*` ruleset covers the relevant pylint checks (`PLR0911`, `PLR0912`, `PLR0913`, `PLR0915`). Running both pylint and ruff produces overlapping diagnostics with differing message text, creating noise. Ruff is faster by 10-100x. |
| `dodgy` | Superseded by `detect-secrets` (working-tree scan with baseline) and `gitleaks` (full git history scan). dodgy has no significant releases since 2020 and its pattern coverage is a strict subset of detect-secrets. |
| `cohesion` | High false-positive rate on valid patterns (thin facade classes, data classes, repository classes). The heuristic is too brittle for a blocking gate. God-class detection via radon's maintainability index (`radon mi`) is more reliable. |
| `vulture` | High false-positive rate without a curated `--ignore` list. Public API symbols, Pydantic model fields, SQLAlchemy column attributes, and pytest fixtures all appear as "dead code" to vulture. ruff `F401` (unused imports) and `F841` (unused variables) handle the safe subset with zero false positives. |
| `jscpd` | Node.js tool requiring a Node.js toolchain install. Wrong ecosystem for a Python-only project. The Python-native alternative for copy-paste detection is pylint R0801 (but pylint is also removed -- see above) or `detect-clone-python`. For the small set of cases where copy-paste is worth detecting, ruff `FURB` catches reimplemented stdlib patterns, and code review catches the rest. |
| `beartype` AND `typeguard` together | Both provide O(1)/decorator runtime type checking. Running both in the same project means every type violation is reported twice from two different tools in two different formats. Pick one: beartype for performance-critical code (O(1) checks), typeguard for development/staging validation (recursive checks). |

---

## 22. Operational Patterns {#operational}

### 22.1 Container / Docker Patterns {#docker}

The mandated Dockerfile pattern uses a multi-stage build: a `builder` stage installs uv and resolves dependencies, and a `runtime` stage copies only the `.venv` and source code -- no build tooling. This produces the smallest possible runtime image.

```dockerfile
# ---- Builder stage ----
FROM python:3.12-slim-bookworm AS builder

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (layer-cache optimization)
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev deps, no project source yet)
RUN uv sync --frozen --no-dev --no-install-project

# Now copy source and install the project itself
COPY src/ src/
RUN uv sync --frozen --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim-bookworm AS runtime

# Minimal runtime: only the venv and source
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Non-root user for security
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --no-create-home appuser
USER appuser

ENTRYPOINT ["python", "-m", "myapp.main"]
```

**Why `--frozen`?** The `uv sync --frozen` flag fails if `uv.lock` does not match `pyproject.toml`. Without it, uv would silently re-resolve dependencies during the Docker build, potentially producing a different environment than what was tested. `--frozen` enforces the exact lockfile.

**Why copy `.venv` not `site-packages`?** Copying the entire `.venv` from the builder preserves all entry points, scripts, and package metadata. Copying only `site-packages` misses executables installed in `.venv/bin/`.

**Security hardening.** Run as a non-root user. Never use `ENV` for secrets (visible in `docker history`). Mount secrets at runtime via Docker secrets or environment injection from a secrets manager.

### 22.2 CI/CD with GitHub Actions {#ci-cd}

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
      fail-fast: false

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies (locked)
        run: uv sync --frozen --all-extras

      - name: Ruff -- lint
        run: uv run ruff check src/ tests/

      - name: Ruff -- format
        run: uv run ruff format --check src/ tests/

      - name: mypy -- strict type check
        run: uv run mypy --strict src/

      - name: pytest -- tests with coverage
        run: uv run pytest tests/ --cov=src --cov-fail-under=100 --cov-report=xml

      - name: deptry -- dependency analysis
        run: uv run deptry src/

      - name: bandit -- security scan
        run: uv run bandit -r src/ -ll

      - name: pip-audit -- CVE scan
        run: uv run pip-audit

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

  publish:
    name: Publish to PyPI
    runs-on: ubuntu-latest
    needs: [test]
    if: startsWith(github.ref, 'refs/tags/v')
    environment: pypi
    permissions:
      id-token: write  # Required for OIDC publishing

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Build package
        run: uv build

      - name: Publish to PyPI (OIDC -- no token required)
        uses: pypa/gh-action-pypi-publish@release/v1
        # OIDC: no API token needed; GitHub proves identity to PyPI directly
```

**OIDC publishing.** The `pypa/gh-action-pypi-publish` action with `permissions: id-token: write` uses OpenID Connect to authenticate to PyPI without a stored API token. This eliminates the secret rotation burden and removes PyPI tokens from GitHub secrets.

**uv cache.** The `astral-sh/setup-uv@v5` action with `enable-cache: true` and `cache-dependency-glob: "uv.lock"` caches the uv download cache, typically reducing install times by 60-80% on cache hit.

**`uv sync --frozen`.** This is the most important CI flag. It verifies that `uv.lock` matches `pyproject.toml` exactly and fails if any dependency has drifted. Without it, CI might silently install a different dependency graph than what developers use locally.

### 22.3 SBOM and Supply Chain Security {#sbom}

A Software Bill of Materials (SBOM) documents every component in your software supply chain -- package name, version, and hash. It is required for SOC 2 compliance, required by some enterprise customers, and essential for rapid CVE impact assessment.

Generate a CycloneDX SBOM with:

```bash
# Install cyclonedx-py
uv add --dev cyclonedx-bom

# Generate SBOM from the installed environment
uv run cyclonedx-py environment -o sbom.json --format json

# Or from pyproject.toml (lockfile-based, faster)
uv run cyclonedx-py poetry --of JSON -o sbom.json
```

**Sigstore attestation.** For libraries published to PyPI, use sigstore to sign release artifacts. The `pypa/gh-action-pypi-publish` action generates sigstore signatures automatically when OIDC publishing is enabled.

**Supply chain security checklist:**

1. Commit `uv.lock` with `--universal` (section 3.2)
2. Run `pip-audit` + `osv-scanner` in CI (Tier 1 + Tier 2)
3. Generate SBOM on every release
4. Use `detect-secrets` + `gitleaks` pre-commit hooks (section 9.4)
5. Enable Dependabot or Renovate for automated dependency updates
6. Pin Docker base image SHA, not just tag (tags are mutable): `FROM python:3.12-slim-bookworm@sha256:abc123...`

### 22.4 Dependency Update Policy {#dependency-updates}

| Category | Cadence | Process |
|----------|---------|---------|
| Security patches (CVE) | Within 48 hours of disclosure | Manual PR with expedited review |
| Minor and patch versions | Weekly | Automated PR via Renovate/Dependabot |
| Major versions | Monthly review cycle | Manual with changelog audit and test run |
| Python version | Track latest stable + 1 prior | Scheduled quarterly test run |

```toml
# renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:base"],
  "schedule": ["every weekend"],
  "packageRules": [
    {
      "matchDepTypes": ["devDependencies"],
      "automerge": true,
      "automergeType": "pr",
      "requiredStatusChecks": ["Test (Python 3.12)"]
    },
    {
      "matchUpdateTypes": ["major"],
      "automerge": false,
      "labels": ["major-update", "needs-review"]
    }
  ]
}
```

**Lockfile regeneration.** After any dependency update, regenerate `uv.lock`:

```bash
uv lock --universal
git add uv.lock
git commit -m "chore: update uv.lock"
```

### 22.5 Datetime and Timezone Policy {#datetime-policy}

Naive datetimes (datetimes without timezone info) are forbidden in all application code. They are the root cause of an entire class of bugs: DST transitions, UTC vs local time confusion, and inconsistent ordering of timestamps across time zones.

**The rules:**

1. All datetimes created in application code must be timezone-aware.
2. The canonical internal representation is UTC.
3. `datetime.utcnow()` is deprecated in Python 3.12 and removed in a future version. Do not use it. Use `datetime.now(tz=datetime.timezone.utc)`.
4. For local time zone representation, use `zoneinfo.ZoneInfo` -- not the deprecated `pytz`.

```python
# ANTIPATTERN -- naive datetime (no timezone)
from datetime import datetime
now = datetime.now()         # naive -- no timezone
utc = datetime.utcnow()      # deprecated in 3.12, creates naive datetime

# MODERN PATTERN -- always timezone-aware
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# UTC (recommended for storage and internal representation)
now_utc = datetime.now(tz=timezone.utc)

# Specific timezone (for display or user-facing output)
eastern = ZoneInfo("America/New_York")
now_eastern = datetime.now(tz=eastern)

# Convert between zones
now_pacific = now_utc.astimezone(ZoneInfo("US/Pacific"))

# Parse ISO 8601 string with timezone
from datetime import datetime
parsed = datetime.fromisoformat("2026-01-15T14:30:00+00:00")
assert parsed.tzinfo is not None  # verify it parsed as timezone-aware
```

**Database storage.** Store all timestamps as UTC in the database. Apply `TIMESTAMP WITH TIME ZONE` (not `TIMESTAMP`) in PostgreSQL schemas. SQLAlchemy's `DateTime(timezone=True)` maps to this correctly.

**Serialization.** orjson serializes `datetime` objects as ISO 8601 with UTC offset when given `option=orjson.OPT_UTC_Z`:

```python
import orjson
from datetime import datetime, timezone

dt = datetime.now(tz=timezone.utc)
serialized = orjson.dumps({"ts": dt}, option=orjson.OPT_UTC_Z)
# b'{"ts":"2026-04-26T14:30:00Z"}' -- "Z" suffix for UTC
```

---

## 23. Python 3.12 / 3.13 Features Reference {#python-features}

### PEP 695: Type Parameter Syntax (3.12)

Covered in detail in section 6.1. Summary of the four forms:

```python
type Alias = tuple[int, str]        # type alias -- scoped, explicit
type Generic[T] = list[T]           # generic alias
class Container[T]: ...             # generic class
def first[T](items: list[T]) -> T:  # generic function
```

### PEP 701: F-String Improvements (3.12)

```python
# Nested same-quote characters -- no longer requires alternating quotes
items = ["a", "b", "c"]
result = f"items: {', '.join(items)}"   # works in 3.12

# Backslashes in f-string expressions (banned before 3.12)
lines = ["line1", "line2"]
joined = f"{'\n'.join(lines)}"

# Multi-line expressions with comments inside f-strings
query = f"""
SELECT *
FROM users
WHERE id = {
    user_id  # this comment is valid in 3.12
}
"""
```

### Standard Library Additions

| Feature | Usage | Min Version |
|---------|-------|-------------|
| `itertools.batched(it, n)` | Yield size-n tuples from iterable (last may be smaller) | 3.12 |
| `pathlib.Path.walk()` | `os.walk()` variant returning `Path` objects | 3.12 |
| `Path.relative_to(walk_up=True)` | Allows `..` in relative paths | 3.12 |
| `Path.glob(case_sensitive=False)` | Explicit case sensitivity control | 3.12 |
| `sys.monitoring` | Low-overhead debugger/profiler API (replaces `sys.settrace`) | 3.12 |
| `tomllib` | TOML parsing (stdlib) | 3.11 |
| `match`/`case` | Structural pattern matching | 3.10 |
| `except*` | Exception groups for concurrent error handling | 3.11 |
| `Self` type | Correct return type for methods returning `self` | 3.11 |
| `@dataclass(slots=True)` | Memory-efficient dataclasses via `__slots__` | 3.10 |
| `contextlib.chdir(path)` | Context manager for temporary directory changes | 3.11 |
| `datetime.UTC` | Alias for `datetime.timezone.utc` | 3.11 |
| `zoneinfo.ZoneInfo` | IANA timezone database (replaces pytz) | 3.9 |

### Python 3.13 Changes Affecting 3.12 Code

Python 3.13 (GA October 2024) introduces free-threading (PEP 703) and an experimental JIT compiler. Neither affects 3.12-targeting code that follows the patterns in this document. The changes to be aware of for forward compatibility:

| Change | Impact |
|--------|--------|
| Free-threading (`--disable-gil`) | Code with hidden global state may have data races. The patterns here use dependency injection and module-level singletons initialized once -- compatible. |
| Removed `distutils` | No impact (uv manages packaging; `distutils` was deprecated since 3.10). |
| `typing.Optional`, `typing.Union` generate `DeprecationWarning` | Already banned in section 2.1.2. `-W error::DeprecationWarning` in tests (section 10.1) surfaces this. |
| `datetime.utcnow()` deprecated (3.12), scheduled for removal | Already banned in section 22.5. |
| `ssl.wrap_socket()` removed | Use `ssl.SSLContext.wrap_socket()`. HTTPX with `verify=True` handles this internally. |

### exception groups and `except*`

Exception groups, introduced in Python 3.11, allow a single `raise` to carry multiple independent exceptions. They are the correct mechanism for async code that fans out to multiple concurrent operations and needs to report all failures.

```python
import asyncio

async def fetch_all(urls: list[str]) -> list[dict]:
    """Fetch all URLs concurrently, collecting all errors."""
    tasks = [asyncio.create_task(fetch_one(url)) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        raise ExceptionGroup("fetch_all failed", errors)
    return [r for r in results if not isinstance(r, Exception)]


# Consuming code can handle specific exception types within the group
try:
    data = await fetch_all(urls)
except* httpx.TimeoutException as eg:
    log.warning("fetch_all.timeout", count=len(eg.exceptions))
except* httpx.HTTPStatusError as eg:
    log.error("fetch_all.http_error", count=len(eg.exceptions))
```

### Performance Profiling Reference

For identifying hot paths before reaching for msgspec or beartype:

```bash
# CPU profiling -- record a flame graph
uv run py-spy record -o profile.svg --pid $(pgrep -f "myproject.main")

# Or for a subprocess
uv run py-spy record -o profile.svg -- python -m myproject.main --benchmark

# Complexity trend tracking
uv run wily build src/
uv run wily report src/myproject/services/payment.py
```

---

*Core sections complete. See companion document for sections 11-20 (web frameworks, async, data science, observability, UI patterns).*
