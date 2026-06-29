#!/usr/bin/env bash
# start checkpython.sh
#
# SupoClip mandatory quality gate.
#
# Runs the union of the documented quality tools and FAILS NON-ZERO on any
# error. The pytest stage runs the FULL suite -- including the real-output
# integration tests (tests/integration) that actually invoke ffmpeg -- because
# a gate that runs only lint + coverage passes green on a non-functional app
# (coverage can be 100% over mocks). Real artifacts are the point.
#
# Usage: ./checkpython.sh
set -uo pipefail

cd "$(dirname "$0")"

FAILED=0
run() {
    local name="$1"
    shift
    echo ""
    echo "=================================================================="
    echo ">>> ${name}"
    echo "=================================================================="
    if "$@"; then
        echo "--- ${name}: PASS"
    else
        echo "!!! ${name}: FAIL"
        FAILED=1
    fi
}

# --- Lint & format -------------------------------------------------------
run "ruff check"        uv run ruff check src tests
run "ruff format"       uv run ruff format --check src tests

# --- Type checking -------------------------------------------------------
run "mypy"              uv run mypy src
run "pyright"           uv run pyright src

# --- Security ------------------------------------------------------------
run "bandit"            uv run bandit -r src -q -c pyproject.toml

# --- Complexity ----------------------------------------------------------
# radon: fail if ANY function is grade C or worse.
echo ""
echo "=================================================================="
echo ">>> radon (no grade C+)"
echo "=================================================================="
RADON_OUT="$(uv run radon cc src -n C 2>/dev/null)"
if [ -n "${RADON_OUT}" ]; then
    echo "${RADON_OUT}"
    echo "!!! radon: FAIL (grade C or worse found)"
    FAILED=1
else
    echo "--- radon: PASS (all functions grade A/B)"
fi

run "xenon"             uv run xenon --max-absolute B --max-modules B --max-average A src

# --- Dependency hygiene --------------------------------------------------
run "deptry"            uv run deptry .

# --- Import-graph cycle check (grimp) ------------------------------------
run "grimp (no import cycles)" uv run python - <<'PY'
import sys
import grimp

graph = grimp.build_graph("src")
visiting, visited, cycle = set(), set(), []


def dfs(module, stack):
    if module in cycle:
        return
    visiting.add(module)
    for imported in sorted(graph.find_modules_directly_imported_by(module)):
        if not imported.startswith("src"):
            continue
        if imported in stack:
            cycle.extend(stack[stack.index(imported):] + [imported])
            return
        if imported not in visited:
            dfs(imported, stack + [imported])
            if cycle:
                return
    visiting.discard(module)
    visited.add(module)


for mod in sorted(graph.modules):
    if mod not in visited and not cycle:
        dfs(mod, [mod])

if cycle:
    print("Import cycle detected: " + " -> ".join(cycle))
    sys.exit(1)
print("No import cycles in src.")
PY

# --- Tests + coverage (line AND branch, 100% floor over REAL output) -----
run "pytest (full suite incl. integration)" \
    uv run pytest tests/ --cov=src --cov-branch \
        --cov-report=term-missing --cov-fail-under=100

echo ""
echo "=================================================================="
if [ "${FAILED}" -ne 0 ]; then
    echo "RESULT: FAIL -- quality gate did not pass."
    exit 1
fi
echo "RESULT: PASS -- all quality checks green."
