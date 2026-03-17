---
name: qa-python
description: Run code quality audit when user asks to check code quality, run QA, verify code before commit, check for antipatterns, run linting/type checks, or assess code health. Executes tiered quality checks (ruff, mypy, pytest, deptry, radon, bandit, semgrep, pip-audit, pyright, jscpd) and scans for antipatterns, stubs, security violations, and duplicate code.
---

# Python Codebase Quality Assessment (8 Dimensions)

Comprehensive quality assessment of this Python codebase. Generate a detailed report evaluating 8 key dimensions.

## Setup

```bash
TIMESTAMP=$(date +%Y-%m-%d-%H-%M-%S)
BRANCH=$(git branch --show-current)
echo "Timestamp: $TIMESTAMP"
echo "Branch: $BRANCH"
```

## Step 1: Gather Context

### Project Structure
```bash
find src/ -name "*.py" | head -30
```

### Files Changed from Main
```bash
git diff main...HEAD --name-only -- '*.py' 2>/dev/null || echo "Unable to diff against main"
```

### Git Diff Summary
```bash
git diff main...HEAD --stat -- '*.py' 2>/dev/null || echo "No diff available"
```

## Step 2: Run Tier 1 — Gate Checks

### Ruff (Linting & Style)
```bash
ruff check src/ 2>&1 || true
```

### Ruff Statistics
```bash
ruff check src/ --statistics 2>&1 || true
```

### Ruff Format Check
```bash
ruff format src/ --check 2>&1 || true
```

### MyPy (Type Checking)
```bash
mypy src/ 2>&1 || true
```

### Pytest + Coverage
```bash
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80 -q 2>&1 || echo "Tests failed or pytest not configured"
```

### Deptry (Dependencies)
```bash
deptry . 2>&1 || echo "Deptry not installed"
```

## Step 3: Run Tier 2 — Quality Analysis

### Radon Cyclomatic Complexity
```bash
radon cc src/ -a -s 2>&1 || echo "Radon not installed"
```

### Radon Maintainability Index
```bash
radon mi src/ -s 2>&1 || echo "Radon not installed"
```

### Bandit (Security)
```bash
bandit -r src/ -f txt 2>&1 || true
```

### Dodgy (Hardcoded Secrets)
```bash
dodgy 2>&1 || echo "Dodgy not installed"
```

### Cohesion (God Class Detection)
```bash
cohesion --below=50 src/ 2>&1 || echo "Cohesion not installed"
```

### Refurb (Modernization)
```bash
refurb src/ 2>&1 || echo "Refurb not installed"
```

### Vulture (Dead Code)
```bash
vulture src/ --min-confidence 80 2>&1 || echo "Vulture not installed"
```

### Interrogate (Docstring Coverage)
```bash
interrogate src/ -v 2>&1 || echo "Interrogate not installed"
```

### Pylint (Deep Linting)
```bash
pylint src/ 2>&1 || echo "Pylint not installed"
```

## Step 4: Run Tier 3 — Advanced

### Xenon (Complexity Enforcement)
```bash
xenon src/ --max-absolute B --max-modules A --max-average A 2>&1 || echo "Xenon not installed"
```

### Semgrep (Security Patterns)
```bash
semgrep --config auto src/ --quiet 2>&1 || echo "Semgrep not installed"
```

### Pip-Audit (Dependency Vulnerabilities)
```bash
pip-audit 2>&1 || echo "Pip-audit not installed"
```

### Pyright (Additional Type Checking)
```bash
pyright src/ 2>&1 || echo "Pyright not installed"
```

### jscpd (Copy-Paste Detection)
```bash
jscpd --min-lines 4 --min-tokens 50 --languages python src/ 2>&1 || echo "jscpd not installed"
```

## Step 5: Security Anti-Pattern Detection

### Dangerous Deserialization
```bash
grep -rn "pickle\.loads\|pickle\.load\|yaml\.load(" src/ --include="*.py" 2>&1 || echo "None found"
```

### Code Injection Vectors
```bash
grep -rn "\beval(\|\bexec(\|\bcompile(" src/ --include="*.py" 2>&1 || echo "None found"
```

### Shell Injection
```bash
grep -rn "shell=True\|os\.system(\|os\.popen(" src/ --include="*.py" 2>&1 || echo "None found"
```

### Insecure Random
```bash
grep -rn "import random\|from random import" src/ --include="*.py" 2>&1 || echo "None found"
```

### Unsafe XML
```bash
grep -rn "xml\.etree\|xml\.sax\|xml\.dom" src/ --include="*.py" 2>&1 || echo "None found"
```

### TLS Verification Disabled
```bash
grep -rn "verify=False\|ssl.*unverified" src/ --include="*.py" 2>&1 || echo "None found"
```

## Step 6: Silent Error Detection

### Bare Except Clauses
```bash
grep -rn "except:" src/ --include="*.py" 2>&1 || echo "None found"
```

### Empty Exception Handlers
```bash
grep -rn -A1 "except" src/ --include="*.py" | grep -B1 "pass$" 2>&1 || echo "None found"
```

### TODO/FIXME/HACK Comments
```bash
grep -rn "TODO\|FIXME\|XXX\|HACK" src/ --include="*.py" 2>&1 || echo "None found"
```

### Print Statements
```bash
grep -rn "print(" src/ --include="*.py" 2>&1 || echo "None found"
```

### Unused Variables
```bash
ruff check src/ --select F841 2>&1 || true
```

## Step 7: Stub Detection

### Unimplemented Functions (pass body)
```bash
grep -rn -A2 "def " src/ --include="*.py" | grep -B1 "^\s*pass$" | grep "def " 2>&1 || echo "None found"
```

### Ellipsis-Only Bodies
```bash
grep -rn -A2 "def " src/ --include="*.py" | grep -B1 "^\s*\.\.\.$" | grep "def " 2>&1 || echo "None found"
```

### Unimplemented NotImplementedError (non-abstract)
```bash
grep -rn "raise NotImplementedError" src/ --include="*.py" 2>&1 || echo "None found"
```

### Placeholder Comments
```bash
grep -rn "# TODO.*implement\|# placeholder\|# fill in\|# stub" src/ --include="*.py" 2>&1 || echo "None found"
```

## Step 8: Duplicate Code Detection

### Pylint Duplicate Code
```bash
pylint src/ --enable=duplicate-code --disable=all --min-similarity-lines=4 2>&1 || echo "Pylint not installed"
```

### Ruff Simplification Opportunities
```bash
ruff check src/ --select SIM,FURB 2>&1 || true
```

## Step 9: Analysis Instructions

Based on all tool outputs above, create a comprehensive quality assessment report following the 8-dimension framework. For each dimension:
- Specific findings with file paths and line numbers when available
- Severity: Critical / High / Medium / Low / Info
- Concrete, actionable recommendations

### Dimension Analysis Framework

1. **What's Good**: Passing checks, good patterns, well-tested code, proper type hints, clean architecture, high coverage

2. **What's Bad**: All errors, violations, security issues, failures. Categorize by severity.

3. **What's Missing**: Missing docstrings, tests, type hints, error handling, coverage gaps

4. **What's Unnecessary**: Dead code (vulture), unused imports, unused dependencies (deptry), redundant patterns

5. **What's Fixed (vs main)**: Issues resolved on this branch vs main

6. **What's Newly Broken (vs main)**: New issues introduced since diverging from main

7. **Silent Errors**: Bare excepts, swallowed exceptions, ignored return values, stubs, placeholder code, security anti-patterns

8. **Overengineered**: High complexity (C/D/E/F grades), God classes (low cohesion), unnecessary abstractions, duplicated code (jscpd), wrapper functions, deep inheritance

## Step 10: Generate and Save Report

Create the report and save to `docs/reports/qa-{TIMESTAMP}.md`:

```markdown
# Quality Assessment Report

**Project:** {project-name}
**Date:** {TIMESTAMP}
**Branch:** {BRANCH}
**Compared Against:** main

---

## Executive Summary

[2-3 sentence overall assessment]

**Overall Health Score:** [A/B/C/D/F] — [Brief justification]

| Dimension | Status | Issues Found |
|-----------|--------|--------------|
| Good | ✅/⚠️/❌ | [summary] |
| Bad | ✅/⚠️/❌ | [count] |
| Missing | ✅/⚠️/❌ | [count] |
| Unnecessary | ✅/⚠️/❌ | [count] |
| Fixed | ✅/⚠️/❌ | [count] |
| Newly Broken | ✅/⚠️/❌ | [count] |
| Silent Errors | ✅/⚠️/❌ | [count] |
| Overengineered | ✅/⚠️/❌ | [count] |

---

## 1. What's Good
[Passing checks, good patterns, well-documented code, high test coverage]

## 2. What's Bad

### Critical
[Critical issues]

### High
[High severity]

### Medium
[Medium severity]

### Low
[Low severity]

## 3. What's Missing
[Missing documentation, tests, type hints, error handling]

## 4. What's Unnecessary
[Dead code, unused imports, unused dependencies, duplicates]

## 5. What's Fixed (since main)
[Issues resolved — or "No comparison available" if on main]

## 6. What's Newly Broken (since main)
[New issues introduced — or "No comparison available" if on main]

## 7. Silent Errors
[Bare excepts, swallowed exceptions, stubs, security anti-patterns]

## 8. Overengineered
[High complexity, God classes, duplicated code, unnecessary abstractions]

---

## Security Findings

### Critical Security Issues
[OWASP-mapped issues requiring immediate remediation]

### Security Anti-Patterns Detected
[Instances of pickle, eval, shell=True, yaml.load, verify=False, etc.]

---

## Stub & Implementation Completeness

[Functions with pass/ellipsis bodies, placeholder comments, unimplemented NotImplementedError]

---

## Duplicate Code

[jscpd/pylint R0801 findings; functions sharing 4+ identical lines]

---

## Recommendations

### High Priority
1. [Most critical fixes]

### Medium Priority
1. [Important improvements]

### Low Priority
1. [Nice-to-have]

---

## Tool Output Summary

| Tool | Status | Issues/Notes |
|------|--------|--------------|
| ruff | [pass/fail] | [issue count] |
| mypy | [pass/fail] | [issue count] |
| pytest | [pass/fail] | [test count, coverage %] |
| deptry | [pass/fail] | [issue count] |
| radon cc | [pass/fail/skipped] | [avg grade] |
| radon mi | [pass/fail/skipped] | [avg score] |
| bandit | [pass/fail] | [issue count] |
| dodgy | [pass/fail/skipped] | [issue count] |
| cohesion | [pass/fail/skipped] | [issue count] |
| refurb | [pass/fail/skipped] | [issue count] |
| vulture | [pass/fail/skipped] | [issue count] |
| interrogate | [pass/fail/skipped] | [coverage %] |
| pylint | [pass/fail/skipped] | [issue count] |
| xenon | [pass/fail/skipped] | [grade] |
| semgrep | [pass/fail/skipped] | [issue count] |
| pip-audit | [pass/fail/skipped] | [vuln count] |
| pyright | [pass/fail/skipped] | [issue count] |
| jscpd | [pass/fail/skipped] | [duplicate count] |

---

*Generated by /qa-python skill on {TIMESTAMP}*
```

After generating the report, save it to the file path above.

$ARGUMENTS
