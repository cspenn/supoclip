---
name: qa-react
description: Run comprehensive React/TypeScript code quality audit. Executes tiered quality checks (Biome, TypeScript, Vitest, Knip) and scans for React-specific anti-patterns (dangerouslySetInnerHTML, floating promises, console logs, `any` types). Generates an 8-dimension health report.
---

# React/TypeScript Codebase Quality Assessment (8 Dimensions)

You are performing a comprehensive quality assessment of this React/TypeScript codebase. Generate a detailed report evaluating 8 key dimensions, specifically focusing on the unique constraints of React applications (Server/Client component boundaries, hydration, state management, and accessibility).

## Setup

Capture timestamp and branch info:

```bash
TIMESTAMP=$(date +%Y-%m-%d-%H-%M-%S)
BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
NODE_VERSION=$(node -v 2>/dev/null || echo "unknown")
echo "Timestamp: $TIMESTAMP"
echo "Branch: $BRANCH"
echo "Node Version: $NODE_VERSION"
```

## Step 1: Gather Context

### Project Structure
```bash
find src/ -name "*.ts" -o -name "*.tsx" 2>/dev/null | head -40 || echo "No src/ directory found"
```

### Files Changed from Main
```bash
git diff main...HEAD --name-only -- '*.ts' '*.tsx' '*.json' 2>/dev/null || echo "Unable to diff against main"
```

### Git Diff Summary
```bash
git diff main...HEAD --stat -- '*.ts' '*.tsx' 2>/dev/null || echo "No diff available"
```

## Step 2: Run Quality Tools

Run each tool and capture output. Tools that aren't installed will be skipped gracefully.

### Biome (Linting, Formatting & Import Sorting)
```bash
pnpm biome check src/ --reporter=summary 2>&1 || npx biome check src/ --reporter=summary 2>&1 || echo "Biome not installed"
```

### Biome Diagnostics (Detailed)
```bash
pnpm biome check src/ 2>&1 | head -50 || echo "Biome not available"
```

### ESLint (Alternative Linting)
```bash
pnpm eslint src/ --max-warnings=0 2>&1 || npx eslint src/ --max-warnings=0 2>&1 || echo "ESLint not configured"
```

### TypeScript Compiler (Strict Type Checking)
```bash
pnpm tsc --noEmit --pretty 2>&1 || npx tsc --noEmit --pretty 2>&1 || true
```

### Knip (Dead Code & Unused Dependencies)
```bash
pnpm knip --no-exit-code 2>&1 || npx knip --no-exit-code 2>&1 || echo "Knip not installed"
```

### Vitest (Unit Testing & Coverage)
```bash
pnpm vitest run --coverage --reporter=verbose 2>&1 || npx vitest run --coverage --reporter=verbose 2>&1 || echo "Tests failed or Vitest not configured"
```

### Dependency Audit (Security)
```bash
pnpm audit --audit-level=high 2>&1 || npm audit --audit-level=high 2>&1 || true
```

## Step 3: React Anti-Pattern Detection (Grepping)

### dangerouslySetInnerHTML Usage (XSS Risk)
```bash
echo "=== dangerouslySetInnerHTML without DOMPurify ==="
grep -rn "dangerouslySetInnerHTML" src/ --include="*.tsx" --include="*.ts" 2>&1 || echo "None found"
```

### Explicit `any` Type Usage
```bash
echo "=== Explicit 'any' types ==="
grep -rn ": any" src/ --include="*.ts" --include="*.tsx" 2>&1 || echo "None found"
grep -rn "as any" src/ --include="*.ts" --include="*.tsx" 2>&1 || echo "None found"
```

### Type Assertions on API Responses
```bash
echo "=== 'as' type assertions (should use Zod.parse) ==="
grep -rn "as [A-Z]" src/ --include="*.ts" --include="*.tsx" 2>&1 | grep -v "as const" | grep -v "as unknown" | head -20 || echo "None found"
```

### Console Statements
```bash
echo "=== Console statements (remove for production) ==="
grep -rn "console\.\(log\|warn\|error\|debug\|info\)" src/ --include="*.ts" --include="*.tsx" 2>&1 || echo "None found"
```

### Floating Promises (Missing Error Handling)
```bash
echo "=== .then() without .catch() (floating promises) ==="
grep -rn "\.then(" src/ --include="*.ts" --include="*.tsx" 2>&1 | grep -v "\.catch(" || echo "None found"
```

### localStorage for Auth Tokens
```bash
echo "=== localStorage usage (auth tokens should use httpOnly cookies) ==="
grep -rn "localStorage\.\(set\|get\)Item.*\(token\|auth\|session\|jwt\)" src/ --include="*.ts" --include="*.tsx" -i 2>&1 || echo "None found"
```

### NEXT_PUBLIC_ Secrets Leak
```bash
echo "=== NEXT_PUBLIC_ variables (verify none are secrets) ==="
grep -rn "NEXT_PUBLIC_" .env* 2>/dev/null | grep -i "secret\|password\|key\|token\|database\|private" || echo "None found"
```

### useEffect Data Fetching (Should Use React Query)
```bash
echo "=== useEffect with fetch (should use TanStack Query or Server Components) ==="
grep -rn "useEffect.*fetch\|useEffect.*axios\|useEffect.*get(" src/ --include="*.tsx" --include="*.ts" 2>&1 || echo "None found"
```

### Missing Error Boundaries
```bash
echo "=== error.tsx files (should exist for major route segments) ==="
find src/ -name "error.tsx" 2>/dev/null || echo "No error.tsx files found (missing error boundaries)"
```

### TODO/FIXME/HACK Comments
```bash
echo "=== TODO/FIXME/HACK comments ==="
grep -rn "TODO\|FIXME\|XXX\|HACK" src/ --include="*.ts" --include="*.tsx" 2>&1 || echo "None found"
```

### @ts-ignore / @ts-expect-error Suppressions
```bash
echo "=== TypeScript suppressions ==="
grep -rn "@ts-ignore\|@ts-expect-error\|@ts-nocheck" src/ --include="*.ts" --include="*.tsx" 2>&1 || echo "None found"
```

### Unused Variables
```bash
echo "=== Unused variables (underscore convention) ==="
grep -rn "const [a-z].*= .*;\s*$" src/ --include="*.ts" --include="*.tsx" 2>&1 | head -10 || echo "Check via TypeScript/Biome instead"
```

## Step 4: Analysis Instructions

Based on all the tool outputs above, create a comprehensive quality assessment report following the 8-dimension framework below. For each dimension:

- Provide specific findings with file paths and line numbers when available
- Assess severity (Critical/High/Medium/Low/Info)
- Give concrete, actionable recommendations

### Dimension Analysis Framework

1. **What's Good**: Passing Biome/ESLint checks, zero `any` types, high Vitest coverage, proper Server/Client component split, Zod validation on server actions, good accessibility, clean TypeScript with strict flags, well-structured state management.

2. **What's Bad**: TypeScript errors, Linter violations, Failed tests, High severity dependency vulnerabilities, Missing strict tsconfig flags.

3. **What's Missing**: Missing tests (components, hooks, server actions), Missing error boundaries, Missing loading/error states on data-fetching components, Missing `alt` text on images, Missing `aria-label` on icon buttons, Missing Zod validation on API routes, Missing `server-only` imports.

4. **What's Unnecessary**: Dead code and unused exports (Knip results), `console.log` statements, Commented-out code, Unused dependencies, Premature `useMemo`/`useCallback`, Unnecessary global state for local concerns.

5. **What's Fixed (vs main)**: Based on git diff, identify what issues were resolved on this branch compared to main.

6. **What's Newly Broken (vs main)**: Based on git diff, identify new issues introduced since diverging from main.

7. **Silent Errors**: Swallowed promise rejections (`.then()` without `.catch()`), Empty `catch (e) {}` blocks, `as Type` assertions masking runtime mismatches, Hydration mismatches (browser API in initial render), Stale closures in event handlers (missing functional setState), Missing useEffect dependency array items, Unhandled async errors in useEffect, Environment variable leakage (`NEXT_PUBLIC_` on secrets).

8. **Overengineered**: Components exceeding 250 lines, God hooks managing many unrelated state values, Premature memoization without profiling, Complex recursive TypeScript types (use simple utilities), `'use client'` too high in the tree, Global state (Zustand/Jotai) for concerns that belong in `useState`, Unnecessary custom hooks wrapping single-line operations.

## Step 5: Generate and Save Report

Create the report in `docs/reports/qa-react-{TIMESTAMP}.md`:

```markdown
# QA Report: React/TypeScript Application

**Project:** {PROJECT_NAME}
**Date:** {TIMESTAMP}
**Branch:** {BRANCH}
**Node Version:** {NODE_VERSION}
**Target:** React 18+ / Next.js 14+ / TypeScript 5.x
**Compared Against:** main

---

## Executive Summary

[2-3 sentence assessment. Is this production-ready? Are there type safety or security concerns?]

**Overall Health Score:** [A/B/C/D/F] - [Brief justification]

| Dimension | Status | Issues Found |
|-----------|--------|--------------|
| Good | [emoji] | [summary] |
| Bad | [emoji] | [count] |
| Missing | [emoji] | [count] |
| Unnecessary | [emoji] | [count] |
| Fixed | [emoji] | [count] |
| Newly Broken | [emoji] | [count] |
| Silent Errors | [emoji] | [count] |
| Overengineered | [emoji] | [count] |

---

## 1. What's Good

[Passing type checks, clean Biome/ESLint run, good test coverage, proper Server/Client component separation, Zod validation, accessible components]

## 2. What's Bad

### Critical (Security / Data Loss Risks)
[XSS vectors, auth token leakage, unvalidated server actions, NEXT_PUBLIC_ secrets]

### High (Runtime Crashes)
[TypeScript errors, missing error boundaries, unhandled promise rejections]

### Medium
[Linter warnings, missing loading/error states, accessibility gaps]

### Low
[Code style issues, minor type improvements]

## 3. What's Missing

[Missing tests, missing error boundaries, missing loading/error states, missing accessibility attributes, missing Zod validation on server actions]

## 4. What's Unnecessary

[Dead code found by Knip, console.log statements, commented-out code, unused dependencies, premature optimizations]

## 5. What's Fixed (since main)

[Issues resolved on this branch - or "No comparison available" if on main]

## 6. What's Newly Broken (since main)

[New issues introduced - or "No comparison available" if on main]

## 7. Silent Errors

[Swallowed promises, empty catch blocks, type assertions, hydration mismatches, stale closures, missing useEffect deps]

## 8. Overengineered

[God components, god hooks, premature memoization, complex TypeScript gymnastics, misplaced 'use client']

---

## Security Checklist

| Check | Status | Notes |
|-------|--------|-------|
| No `dangerouslySetInnerHTML` without DOMPurify | [pass/fail] | |
| No `NEXT_PUBLIC_` on secrets | [pass/fail] | |
| No `localStorage` for auth tokens | [pass/fail] | |
| Zod validation on all server actions | [pass/fail] | |
| httpOnly cookies for sessions | [pass/fail] | |
| `server-only` on GCP/DB files | [pass/fail] | |
| No `javascript:` URLs in href | [pass/fail] | |
| CSP headers configured | [pass/fail] | |

---

## Accessibility Checklist

| Check | Status | Notes |
|-------|--------|-------|
| Semantic HTML (button, a, h1-h6) | [pass/fail] | |
| All images have alt text | [pass/fail] | |
| All form inputs have labels | [pass/fail] | |
| Focus trapped in modals | [pass/fail] | |
| Color contrast 4.5:1 (text) | [pass/fail] | |
| Keyboard navigable | [pass/fail] | |
| error.tsx for route segments | [pass/fail] | |

---

## Tool Output Summary

| Tool | Status | Issues/Notes |
|------|--------|--------------|
| Biome | [pass/fail/skipped] | [Lint/Format errors] |
| ESLint | [pass/fail/skipped] | [Rule violations] |
| TypeScript | [pass/fail] | [Type errors] |
| Vitest | [pass/fail] | [Test count, coverage %] |
| Knip | [pass/fail/skipped] | [Unused files/exports/deps] |
| Dependency Audit | [pass/fail] | [Vulnerability count] |
| Anti-pattern Grep | [pass/fail] | [Patterns found] |

---

## Recommendations

### Immediate (Before Deploy)
1. [Critical security or runtime fixes]

### Short-term (This Sprint)
1. [Type safety improvements, missing tests]

### Long-term (Tech Debt)
1. [Refactor oversized components, improve coverage]

---

*Generated by /qa-react on {TIMESTAMP}*
```

After generating the report content, save it to the file path shown above.

$ARGUMENTS
