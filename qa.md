
You are conducting a comprehensive code review and audit of a software project. Your goal is to assess the current state of the codebase, identify issues, validate functionality against requirements, and produce a detailed audit report and remediation plan.

<details>

Our software package has been plagued with formatting issues, output issues, and not fulfilling its fundamental mandate as an OpusClip replacement in pure Python.

Your remit today is to first research other similar packages and learn what you can from them, then perform the full QA audit, identifying things we can borrow from other FOSS packages for our software.

References:
https://github.com/samuraigpt/ai-youtube-shorts-generator
https://github.com/ClipsAI/clipsai

You are authorized for web search and any other tool use necessary to accomplish the audit.

</details>


## Core Methodology

You MUST use parallelism for every step of this audit. This is immutable and non-negotiable. You should evaluate whether dynamic workflows are a good fit, and if not, use traditional agent teams.

### Agent Team Requirements

Before dispatching each agent:
1. Verify the agent can access its required input files
2. Give each agent this instruction: "If you encounter an error or cannot access your inputs, immediately report the failure rather than retrying silently."
3. After all agents complete, verify each produced output before merging results
4. Re-dispatch any agents that failed
5. Set the appropriate model for the agent based on its purpose.

- Initial planning and final audit review: Opus 4.8
- Web research, documentation reading, and summarization: Haiku 4.5
- Analysis: Sonnet 4.6
- Audit details: Opus 4.8
- Fallback: Opus 4.8

### Agent Documentation Requirements

- Every agent must write down their work as they proceed
- No agent may think without documenting their work
- All notes must be saved to the output/notes/ folder
- Each agent should create clearly named note files indicating their task

### Agent Task Decomposition

- Every agent is permitted to start new tasks or spawn new instances of itself to avoid context window limits
- ANTIPATTERN: Tackling one big task in a single agent
- BEST PRACTICE: Break big tasks into small tasks, accomplish each small part, write down results, then have subsequent agents compile and synthesize findings
- This ensures efficiency, effectiveness, and no loss of data

### Parallel Execution

ALWAYS use parallel sub-agents for this project. Dispatch independent work items simultaneously — do NOT execute them sequentially. If there are dependencies:
1. Batch all independent items first
2. Wait for completion of the batch
3. Then dispatch the next batch that depends on those results

### Tool Usage

- Always use graphify if it's available (it's more efficient and effective than grep)
- Examine the dependency graph to identify dead code

## Review Process

### Phase 1: Documentation Review

Deploy agent teams to review the docs/ folder first to understand:
- Project scope and requirements
- Product Requirements Document (PRD) promises and specifications
- Architecture and design intentions
- Expected functionality

Have agents document their findings in output/notes/docs-review-*.md files.

### Phase 2: Codebase Audit

Deploy agent teams to conduct a comprehensive code review across all source files. Each team should assess their assigned portion of the codebase.

For each area reviewed, agents must evaluate and document:

**✅ What's good, if anything?**
- Identify well-implemented features, clean code, good patterns
- If there's nothing good, explicitly state so

**❌ What's bad, if anything?**
- Identify bugs, errors, poor implementations, anti-patterns
- If there's nothing bad, explicitly state so

**❓ What's missing, if anything?**
- Identify incomplete features, missing functionality, gaps in implementation
- If there's nothing missing, explicitly state so

**🗑️ What's unnecessary, if anything?**
- Identify redundant code, unused features, over-engineered solutions
- If there's nothing unnecessary, explicitly state so

**🛠️ What's fixed, if anything?**
- Identify recently fixed issues or improvements
- If nothing was fixed, explicitly state so

**💥 What's newly broken, if anything?**
- Identify regressions or new bugs introduced
- If nothing was newly broken, explicitly state so

**🤫 What are the silent errors, if any?**
- Identify lurking bugs, edge cases not handled, silent failures
- If there are no silent errors, explicitly state so

**🐷 What's overengineered or overcomplicated, if anything?**
- Identify unnecessarily complex code, premature abstractions, over-architected solutions
- If nothing is overcomplicated, explicitly state so

**🚮 What's technical debt or dead code, if anything?**
- Identify deprecated code, unused functions/modules, code that should be removed
- Use the dependency graph to identify dead code
- If there's no technical debt or dead code, explicitly state so

Have agents document their findings in output/notes/code-review-*.md files.

### Phase 3: PRD Validation (CRITICAL)

This is the most critical part of the investigation. Deploy agent teams to validate that the code and system deliver on the promises in the PRD.

Agents must answer:
- Does the software actually do what it is intended to do?
- Are there functional gaps between what's promised in the PRD and what's implemented?
- For each feature/requirement in the PRD, is it fully implemented, partially implemented, or missing?

Create a comprehensive mapping of PRD requirements to implementation status.

Have agents document their findings in output/notes/prd-validation-*.md files.

### Phase 4: Testing Audit

Deploy agent teams to assess the testing infrastructure and coverage.

Agents must evaluate:
- Current test coverage percentage
- Number of passing vs failing unit tests
- Number of passing vs failing end-to-end integration tests
- Quality of test cases
- Missing test scenarios

**Success Criteria:**
- 100% test coverage
- 100% passing unit tests
- 100% passing end-to-end integration tests

**Failure Criteria:**
- Test coverage < 100%
- Any failing tests
- Missing test categories

Have agents document their findings in output/notes/testing-audit-*.md files.

## First Principles Validation

Agents must validate the codebase against these first principles:

- **P1 Fix Over Create** — Is existing code being modified appropriately? Are new files only created when radon cc ≥ C or structure mandates? Is there any grade C or lower code?
- **P2 Reusable Testing** — Are there one-off test scripts? Are utilities properly located in src/scripts/? Are tests in tests/?
- **P3 Docs Location** — Are all docs in docs/? Is CLAUDE.md the only exception at root?
- **P4 Never Defer** — Is there evidence of deferred work, "fix later" comments, "out of scope" issues, or "unrelated" problems being ignored?
- **P5 Use Agents** — N/A for code review, but validate if the codebase itself uses parallel processing where appropriate
- **P6 Anti-Elision** — Are there stubs, truncations, ..., pass statements, or # TODO comments?
- **P7 Contextual Strictness** — Does code make assumptions about signatures/state without validation?
- **P8 Explicit Failure Propagation** — Are exceptions being swallowed? Are errors properly propagated? Does None signal absence vs failure correctly?
- **P9 Idempotent Mutation** — Are operations idempotent? Is existing state verified before mutation?
- **P10 Simplicity** — Is there unnecessary complexity? Premature abstraction? Patterns used without demonstrated need?
- **P11 Test Coverage** — Already covered in Testing Audit phase
- **P12 Never Reinvent the Wheel** — Is custom code being written where proven FOSS packages exist?

Have agents document their findings in output/notes/principles-validation-*.md files.

## Synthesis Phase

After all agent teams have completed their work and documented findings:

1. Deploy a synthesis agent team to compile all findings from output/notes/
2. The synthesis team should identify patterns, systemic issues, and root causes
3. Think in terms of QA: what are the underlying problems causing surface-level issues?

## Output Requirements

You must produce two final documents:

### 1. Audit Report: output/review/audit-{yyyy-mm-dd}.md

This comprehensive report must include:

- Executive summary of findings
- Documentation review summary
- Codebase audit organized by the emoji categories (✅❌❓🗑️🛠️💥🤫🐷🚮)
- PRD validation results with specific gaps identified
- Testing audit results with coverage metrics
- First principles validation results
- Systemic issues and root causes identified
- Overall assessment of project health

### 2. Remediation Plan: output/review/fixes-{yyyy-mm-dd}.md

This detailed plan must include:

- Prioritized list of issues to fix (critical, high, medium, low priority)
- For each issue:
  - Clear description of the problem
  - Root cause analysis
  - Specific remediation steps
  - Estimated effort/complexity
  - Dependencies on other fixes
- Testing requirements to achieve 100% coverage and 100% passing
- Technical debt removal plan
- Dead code removal plan
- Compliance plan for first principles violations

## Critical Constraints

**YOU WILL NOT IMPLEMENT THE PLAN. DO NOT IMPLEMENT. THIS IS AUDITING ONLY.**

Your role is to audit, analyze, document, and plan. Implementation is explicitly forbidden in this task.

**IT IS FAILURE TO IGNORE OR DEFER ANY ERROR, REGARDLESS OF SCOPE, SEVERITY, OR EFFORT.**

Every issue found must be documented and included in the remediation plan. No exceptions.

## Final Output Format

Your final response should contain:

1. A summary of the agent teams deployed and their completion status
2. Confirmation that all agent notes have been written to output/notes/
3. Confirmation that the audit report has been written to output/review/audit-{yyyy-mm-dd}.md
4. Confirmation that the remediation plan has been written to output/review/fixes-{yyyy-mm-dd}.md
5. A brief executive summary of the most critical findings

Do not include the full content of the reports in your response - only confirm their creation and provide the executive summary.