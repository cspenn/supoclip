# PYTHON 3.11 BEST PRACTICES

1. **Core Mastery**:  
   - Data types, control flow, functions, OOP, functional paradigms (decorators, generators, comprehensions).  
   - Context managers (`with`), exception handling, algorithmic efficiency (time/space complexity).  
   - Standard libraries: `os`, `subprocess`, `re`, `tomllib`, `contextlib.chdir`, `collections.abc`.

2. **Performance Optimization**:  
   - Profiling (cProfile, line_profiler), Cython/Numba acceleration, memory-efficient structures (`dataclass(slots=True)`).  
   - Lazy loading, connection caching (`lru_cache`), recursion inlining (Python 3.11 zero-cost exceptions).

3. **Code Quality**:  
   - PEP 8 compliance, type hints (mandatory), linters (Ruff, pylint), formatters (black).  
   - Pre-commit hooks, docstrings, DRY refactoring, dead code removal.

4. **Frameworks & Libraries**:  
   - Web: FastAPI (async, type-driven), Django (ORM), Flask (microservices).  
   - Data Science: NumPy (NDArray typing), Pandas, TensorFlow/Keras, Scikit-learn.  
   - Async I/O: HTTPX, asyncio (TaskGroup, timeout).

5. **Domain-Specific Practices**:  
   - Serverless: AWS Lambda (layers, memory config, async I/O), least-privilege IAM.  
   - ML Pipelines: Tensor shape annotations, GPU memory isolation, reproducible environments (Poetry, Conda-lock).  
   - Security: HTTPS enforcement, input sanitization, FIPS crypto, SAST scanning (Bandit).

6. **Python 3.11+ Features**:  
   - Structural pattern matching (`match-case`), exception groups (`except*`), TOML parsing.  
   - Faster CPython (inlined calls, adaptive interpreter), frozen imports, strict var typing.

7. **Anti-Patterns**:  
   - Mutable defaults, bare `except`, circular imports, global overuse, magic numbers.  
   - Spaghetti code, hardcoded secrets, unvalidated inputs, debugger remnants in prod.

8. **Tooling**:  
   - IDE: VS Code + Pylance (type-checking, isort).  
   - CI/CD: GitHub Actions matrix builds, Poetry/PDM dependency isolation.  
   - Static Analysis: mypy (type), Bandit (security), pytest coverage.

9. **Design Principles**:  
   - Resource safety (`with`, `finally`), lazy evaluation, stateless serverless functions.  
   - Least surprise (explicit over implicit), reproducibility (dependency pinning).

10. **Evolution**:  
    - Migrate from "dead batteries" (deprecated modules), adopt C11 toolchains for extensions.  
    - Leverage adaptive interpreter (PEP 659), specialize bytecode optimizations.

**Associations**:  
- Type hints → robustness, static analysis, FastAPI auto-docs.  
- Asyncio → serverless cost reduction, parallel I/O.  
- Dataclasses → memory efficiency → high-throughput systems.  
- Structural pattern matching → cleaner state machines.  
- Zero-cost exceptions → performance-critical error handling.

# CODINGSTANDARDS

This document outlines the development standards for Python 3.11+ projects. It blends established principles with modern tooling to enhance robustness and maintainability.

## **1. Project Structure & File Conventions**

* We always start and end files with the path of the file as a comment (e.g., # start src/example/file.py).  
* All imports should be absolute from the project's source root. No relative imports.  
* Keep functionality in the main.py entry point to a minimum; it should orchestrate the application, not implement core logic.  
* The standard invocation for the app is python -m src.main.  
* No file should ever exceed 750 lines; refactor if necessary.  
* The following files and directories are always required:  
  * docs/prd.md  
  * docs/workplan.md  
  * docs/polish.md  
  * checkpython.sh  
  * .pre-commit-config.yaml - Configuration for the pre-commit framework.  
  * migrations/ - This directory, managed by Alembic, will contain all database schema migration scripts.  
* Never modify the contents of checkpython.sh.

## **2. Configuration & Runtime Validation**

* **CORE RULE:** Never use environment variables for configuration. Always use config.yml for general settings and credentials.yml for secure items. credentials.yml must always be in .gitignore. A placeholder credentials.yml.dist should exist in the repository.  
* The application must never remove or overwrite tokens, keys, and passwords set by the user in credentials.yml. Always preserve user-added configuration details to prevent breaking the application's setup.  
* **Runtime Validation with Pydantic:** To prevent errors from malformed configuration, we will use Pydantic for runtime validation. All configuration loaded from YAML files must be parsed into a Pydantic model at application startup. This ensures all settings are of the correct type and format before any logic is executed.  
* Never hard code variables or data within code; always use configuration files.

## **3. Command-Line Interface**

* **Flexible Overrides with Typer:** The primary source of configuration remains config.yml. However, for convenience and one-off runs, we will use Typer to provide command-line flags that can **override** settings from the YAML file (e.g., --dry-run).  
  * The application should first load settings from config.yml, then apply any overrides provided via CLI flags.  
  * All other forms of command-line arguments for configuration are still forbidden.

## **4. Code Quality & Design Principles**

* Adhere to coding principles like DRY, SPOT, SOLID, GRASP, and YAGNI.  
* Use Google Python Style for docstrings (PEP 257).  
* Avoid deeply nested logic (max two levels).  
* Use clear, descriptive, and unambiguous names.  
* Functions and methods must have a single responsibility.  
* In-line code comments must not exceed two lines.

## **5. Environment & Tooling**

* Write for Python 3.11+.  
* Manage virtual environments and dependencies with poetry and pyproject.toml.  
  * poetry is to be used for dependency management only, not for application builds.  
* **Automated Quality Checks with pre-commit:** To enforce code quality standards automatically, we will use the pre-commit framework. It must be configured in .pre-commit-config.yaml to run the checkpython.sh script on every commit. This prevents code that fails quality checks from being committed to the repository.  
* Use checkpython.sh (Ruff, mypy, Bandit, pytest) for the actual quality checks.

## **6. Core Libraries**

* **Database Interaction with SQLAlchemy:** All application-level database operations (reads, writes, updates) **must** be performed using the SQLAlchemy Core or ORM. This ensures type safety, prevents SQL injection vulnerabilities, and works seamlessly with Alembic for migrations. Raw SQL strings are forbidden in application code.  
* **API Communication with HTTPX:** All external HTTP requests (e.g., to REST APIs) **must** be made using the httpx library. Its modern feature set, strict timeouts, and superior testability make it the standard for both synchronous and asynchronous contexts (though we will only use the sync client).

## **7. Database Schema Management**

* **Migrations with Alembic:** All changes to the SQLite database schema (e.g., adding a table or a column) **must** be managed through Alembic. This creates a version-controlled, repeatable history of the database structure. Manual changes to the database schema are strictly forbidden.

## **8. Logging & Error Handling**

* Use the logging module to log to a timestamped file in the logs/ folder and to the console.  
* Use emoji indicators: 🟢 (INFO), 🟡 (WARN), and 🛑 (ERROR).  
* Log level must be configurable in config.yml and validated by the Pydantic settings model.  
* Define custom, project-specific exceptions.  
* Employ exponential backoff for network calls where appropriate.

## **9. Testing**

* Use pytest for all unit tests.  
* Tests should include cases for:  
  * Pydantic model validation.  
  * SQLAlchemy database logic (using a test database).  
  * httpx API interactions (using mocking libraries like pytest-httpx).  
  * Alembic migrations.  
  * Typer CLI overrides.  
* Always update tests to match code changes.  
* When tests fail to produce any output, assume a complete failure in the code that prevents the test from running at all; never assume success in this scenario.

## **10. Specific Implementation Rules**

* **Progress Monitoring:** Use tqdm for progress monitoring for loops expected to have more than 5 steps or take longer than 10 seconds to provide clear user feedback.  
* **Report Generation:** When producing reports, use HTML, CSS, Tailwind, and d3.js. All rendering logic must be client-side ONLY. Never use server-side technologies or external API calls for report rendering.

# DEBUGGING STANDARDS : THE VUW

## How to Debug: "Verifiable Units of Work"

We will no longer provide large, multi-step "plans." Instead, we will provide a sequence of small, isolated **"Verifiable Units of Work" (VUWs)**. Each VUW_ is a micro-plan for a single, contained task to break work down into small, bite-sized chunks. Our developer is inexperienced and unskilled, so we must provide tiny work units and frequent validation.

The core principles of this approach are:

1.  **Extreme Granularity:** Each VUW_will target a single file or a single, specific error across a few files. This minimizes cognitive load and prevents the "tunnel-vision" refactoring problem. No VUW should ever have a diff longer than a single function or class.
2.  **Verification is the Definition of "Done":** Every VUW_ will have a mandatory, non-negotiable **Verification Checklist**. The task is not complete until that checklist is passed. This moves verification from an assumed skill to an explicit task requirement.
3.  **Sequential, Not Parallel:** The developer will be given **one VUW_ at a time**. They cannot start the next one until the previous one is submitted and passes a QA check. This prevents them from getting lost or working on unverified code.
4.  **Repetition Builds Discipline:** The constant repetition of the Verification Checklist on every single task is designed to build the muscle memory of a disciplined workflow.
5.  **Clarity over Conciseness:** The instructions will be painfully literal, assuming nothing. If an import is needed, the plan will state, "Add this exact import statement to the top of the file." We will use git diffs to show exact changes needed so the developer knows exactly what to type.

---

### The Structure of a "Verifiable Unit of Work" (VUW_)

Every work plan will now follow this exact template:

---
**VUW_ID:** [A unique identifier, e.g., `BUGFIX-001`]

**Objective:** [A one-sentence explanation of *why* this task is important.]
*   *Example: "To fix the fatal `ModuleNotFoundError` that prevents the application from starting."*

**Files to Modify:**
*   `[List of file paths]`

***Mandatory Pre-Work Checkpoint:***

Use git to make a checkpoint in advance of making ANY changes to a file. This is for backup and rollback, and must not be skipped. If you cannot make a checkpoint, stop.

**Step-by-Step Instructions:**

You are not done with this task until you run these commands and they succeed. Check the box only when the command passes.

1.  **[Literal instruction 1]**: *Example: "Open the file `src/crawler/extractor.py`."*
2.  **[Literal instruction 2]**: *Example: "Find the line: `import pdfplumber.errors`."*
3.  **[Literal instruction 3]**: *Example: "Delete that line and replace it with: `from pdfplumber.exceptions import PDFSyntaxError`."*
4.  **[Literal instruction 4]**: *Example: "In the `_extract_from_pdf` method, find the `except` block and change `except (pdfplumber.errors.PDFSyntaxError, ...)` to `except (PDFSyntaxError, ...)`."* - show this as a git diff exactly.

**Mandatory Verification Checklist:**

You are not done with this task until you run these commands and they succeed. Check the box only when the command passes.

*   `[ ]` **Run `./checkpython.sh`**: Must report **zero errors** for tests  **"Success: no issues found"**, **100% passing tests**.

**Self-Attestation:**

*   `[ ]` I attest that I have run checkpython.sh and tests have all passed.

***Mandatory Post-Work Checkpoint:***

Use git to make a checkpoint after a VUW passes all tests. This is for backup and rollback, and must not be skipped. If you cannot make a checkpoint, stop.

---

### The Grand Strategy: Sequencing the VUWs

We will organize the overall repair effort into a series of "Campaigns," where each campaign is a sequence of related VUWs.

**Campaign 1: Application Stability (The Blockers)**
*   **Goal:** Make the application runnable and the tests executable.
*   **Sequence of VUWs:**
    1.  **VUW_BUGFIX-001:** {explanation}
    2.  **VUW_BUGFIX-002:**  {explanation}
    3.  ... and so on for every error that prevents `pytest` from running successfully.

**Campaign 2: Type Safety (`mypy` Errors)**
*   **Goal:** Achieve zero `mypy` errors project-wide.
*   **Sequence of VUWs:**
    1.  **VUW_MYPY-001:** {explanation}
    2.  **VUW_MYPY-002:** {explanation}
    3.  ... one VUW_for each of the remaining `mypy` errors.

**Campaign 3: Code Quality (`ruff` Errors)**
*   **Goal:** Achieve zero `ruff` errors project-wide.
*   **Sequence of VUWs:**
    *   This will be the longest campaign, with one VUW_for each file that has `ruff` errors, starting with the files that have the most severe violations (like `BLE001` blind exceptions).

By breaking the work down this way, we are building a rigid "scaffolding" of process around the developer. We are not just giving them a map; we are giving them turn-by-turn directions with mandatory checkpoints. This approach directly targets their specific weaknesses—lack of verification, incomplete changes, and getting lost—and forces the adoption of a more disciplined, robust, and successful development workflow.

Build VUW Campaign Workplans with the individual VUWs. Arrange the work plan in order of importance, most important to least important.