# 5P Analysis Framework for Prompt-to-Skill Conversion

Run this analysis against the source prompt. Extract concrete answers for every
field — do not leave blanks. If the prompt does not contain enough information
to answer a field, mark it `[INFER]` and provide your best inference, or
`[ASK]` if you must ask the user.

Write the completed analysis to `{workspace}/5p-analysis.md`.

---

## P1: Purpose

Extract:

| Field | How to Extract | Output |
|---|---|---|
| **Problem statement** | What does the prompt solve? What goes wrong without it? | One sentence: "Without this skill, {user} has to {painful thing} every time they {action}." |
| **Core action** | What is the single most important thing the prompt does? | One verb phrase: "generates branded reports" / "orchestrates sprint planning" / "validates data pipelines" |
| **Frequency** | How often would someone use this? | Daily / Weekly / Per-project / Ad-hoc |
| **Skill category** | What type of output does it produce? | `document-creation` / `workflow-automation` / `mcp-enhancement` |
| **Justification** | Why does this need to be a skill instead of a one-off prompt? | At least one of: repeated use, domain knowledge required, format consistency needed, multi-step sequence, team standardization |

### Decision: Is This Worth Skillifying?

A prompt should become a skill if **2+ of these are true**:

- [ ] Used more than twice per week
- [ ] Requires domain knowledge Claude doesn't have by default
- [ ] Output must follow specific format, brand, or compliance rules
- [ ] A new user couldn't replicate the result without the exact prompt
- [ ] Involves 3+ steps that must happen in a specific order
- [ ] Multiple people need the same workflow

If 0-1 are true, the prompt may not benefit from being a skill. Note this in the
analysis but proceed if the user wants to build it anyway.

---

## P2: People

Extract:

### The User (who triggers the skill)

| Field | How to Extract | Output |
|---|---|---|
| **Role** | Who writes this prompt? What's their job? | e.g., "marketing manager", "developer", "founder" |
| **Technical level** | How much can you assume they know? | `technical` / `semi-technical` / `non-technical` |
| **Trigger phrases** | What would they naturally type to invoke this? | List 5+ phrases, mixing formal and casual. Include: exact phrases from the prompt, paraphrased versions, casual/shorthand versions, edge cases |
| **Context at invocation** | What do they typically have ready when they ask? | e.g., "file already uploaded", "project name known", "data in Google Sheet" |
| **Anti-triggers** | What similar-sounding requests should NOT trigger this skill? | List 3+ near-miss queries that share keywords but need something different |

### How to Generate Trigger Phrases

Read the source prompt and identify:
1. **Action verbs** the user would say: "create", "generate", "build", "make", "write", "set up"
2. **Object nouns** they'd reference: "report", "presentation", "social post", "sprint plan"
3. **Context words** that signal this workflow: file types, tool names, domain terms
4. **Casual variants**: "whip up a", "put together a", "I need a quick"

Combine these into realistic phrases a user would actually type:
```
Formal:  "Create a quarterly performance report using the sales data"
Casual:  "make me a report from this quarter's numbers"
Minimal: "q3 report from the attached csv"
Edge:    "can you turn this spreadsheet into something I can show my boss"
```

### The Audience (who consumes the output)

| Field | How to Extract | Output |
|---|---|---|
| **Role** | Who reads/uses the output? | e.g., "executive team", "client", "engineering team" |
| **Format expectations** | What do they expect to receive? | e.g., "polished .pptx", "markdown in Slack", "formatted email" |
| **Quality bar** | What would make them reject it? | e.g., "off-brand colors", "missing data source", "too informal" |
| **Tone** | How should the output read? | `executive` / `technical` / `casual` / `formal` |

---

## P3: Process

This is the longest section. It becomes the SKILL.md body.

### Step-by-Step Decomposition

Break the prompt into discrete phases. For each phase, extract:

```
Phase {N}: {Name}
  Action:     What happens in this phase
  Input:      What this phase needs (from user, previous phase, or environment)
  Output:     What this phase produces
  Tools:      What tools/commands are used
  Validation: How to verify this phase succeeded
  Errors:     What can go wrong and how to recover
```

### Identify Decision Points

Where does the process branch? Extract as explicit if/then:

```
Decision: {What is being decided}
  If {condition A} → {action A}
  If {condition B} → {action B}
  Default → {fallback action}
```

### Identify Repetitive Operations

Look for operations that happen identically every invocation:

| Operation | Same Every Time? | Candidate For |
|---|---|---|
| Data validation | Yes → exact same checks | Script in `scripts/` |
| Template application | Yes → same structure | Template in `assets/` |
| Style/brand rules | Yes → same standards | Reference in `references/` |
| API calls | Yes → same parameters | Script in `scripts/` |
| Output formatting | Yes → same format | Script or template |

### Identify Implicit Knowledge

What does the prompt assume the user/Claude already knows? This implicit
knowledge must become explicit in the skill. Common examples:

- Brand guidelines (colors, fonts, tone) → `references/brand-guide.md`
- API patterns and limits → `references/api-guide.md`
- Domain terminology → glossary in SKILL.md or `references/`
- File format requirements → validation script in `scripts/`
- Approval criteria → quality checklist in SKILL.md

### Convert Conversational Instructions to Imperative

For each instruction in the source prompt, transform:

| Source Prompt Says | Skill Should Say |
|---|---|
| "Try to make it look professional" | "Apply heading style: Barlow Condensed Bold 700, 36px. Body: Barlow Medium 400, 16px. Colors from `references/brand-guide.md`." |
| "Check if the data looks right" | "Run `python scripts/validate.py --input {file}`. If exit code ≠ 0, report the specific validation errors to the user." |
| "You might want to include a summary" | "Write a 3-sentence executive summary as the first section. Sentence 1: key finding. Sentence 2: supporting evidence. Sentence 3: recommended action." |
| "Keep it concise" | "Maximum 500 words for the full document. Maximum 2 paragraphs per section." |
| "Use the right format" | "Output as .docx using `scripts/create_doc.py`. Structure: title page → executive summary → findings → recommendations → appendix." |

---

## P4: Platform

Extract all technical dependencies:

### Tools and Infrastructure

| Field | How to Extract | Output |
|---|---|---|
| **Built-in tools** | Does the prompt use file creation, code execution, web search? | List: `bash_tool`, `create_file`, `web_search`, `show_widget`, etc. |
| **MCP servers** | Does the prompt reference external services? | List with server URLs if known |
| **Python packages** | Does any script need non-standard packages? | List with install commands: `pip install pandas --break-system-packages` |
| **File types read** | What input formats does the skill accept? | List: `.csv`, `.xlsx`, `.pdf`, `.json`, etc. |
| **File types written** | What output formats does the skill produce? | List: `.docx`, `.pptx`, `.html`, `.md`, etc. |

### Folder Structure Decision

Based on the Process analysis, determine what goes in the skill folder:

```
{skill-name}/
├── SKILL.md                          ← Always required
├── scripts/                          ← If any deterministic operations found
│   └── {extracted scripts}
├── references/                       ← If domain knowledge exceeds SKILL.md budget
│   └── {extracted reference docs}
├── assets/                           ← If templates or binary resources needed
│   └── {extracted templates/assets}
└── evals/                            ← Always include
    └── evals.json
```

If the Process analysis found no scripts, references, or assets needed, the
skill is SKILL.md-only. That's fine — not every skill needs bundled resources.

---

## P5: Performance

Extract success criteria and test material:

### Success Criteria

| Metric | Target | Measurement |
|---|---|---|
| **Trigger accuracy** | 90%+ of relevant queries load the skill | Test with trigger phrases from P2 |
| **False trigger rate** | <10% of near-miss queries load the skill | Test with anti-triggers from P2 |
| **Output correctness** | Meets all quality checklist items | Run functional test cases |
| **Consistency** | Same input → structurally identical output | Run same test 3x, compare |
| **Efficiency** | Fewer tool calls than without the skill | Compare with/without |

### Generate Test Queries

From the People analysis, produce:

**Should-trigger queries (minimum 3):**
Write realistic queries a user would actually type. Include context, file
references, casual language. Vary the phrasing significantly.

**Should-NOT-trigger queries (minimum 3):**
Write near-miss queries that share keywords with the skill but actually need
something different. These test the boundaries of the description.

### Generate Quality Checklist Items

From the Process analysis, extract every verifiable criterion. Each item must be
answerable as pass/fail:

```
- [ ] Output file exists and is non-empty
- [ ] All required sections present
- [ ] Brand colors match specification
- [ ] No placeholder text remaining
- [ ] Data validated before processing
```

### Identify Edge Cases

What unusual inputs or conditions could break the skill?

```
Edge case: {description}
  Expected behavior: {what should happen}
  Handling: {instruction added to SKILL.md}
```

---

## Output Format

After completing the analysis, you have all inputs needed for Steps 3-10 of the
main SKILL.md. The analysis document should be structured exactly as above with
all fields filled. If you marked anything `[ASK]`, pause and ask the user before
proceeding to skill construction.
