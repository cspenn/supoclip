---
name: transcript-cleaner
description: This skill should be used when the user asks to "clean a transcript",
  "edit a transcript", "fix a transcript", "clean up this transcript", "remove filler
  words", "polish a transcript", "clean up my transcript", or provides a raw transcript
  and asks for editing help. Applies copy-editing rules that preserve the speaker's
  original voice while fixing grammar, punctuation, and removing speech disfluencies.
---

# Transcript Cleaning

Act as a copy editor, not a summarizer or paraphraser. The goal is to clean up the mechanical aspects of a transcript—grammar, punctuation, filler words—while preserving the speaker's original voice, tone, and wording exactly as they delivered it.

## Core Principle

**Preserve voice. Fix mechanics.**

The speaker's wording, sentence structure, contractions, slang, and acronyms must remain intact. Only correct what is broken: grammar errors, punctuation issues, run-on sentences, and speech artifacts like filler words and false starts.

## Workflow

To clean a transcript:

1. Read the `references/cleaning-rules.md` file to load the complete rule set before beginning
2. Pass through the transcript once, applying all rules simultaneously
3. Output only the cleaned transcript — no commentary, no explanation of changes, no notes

## The Critical Distinction

The difference between correct and incorrect editing is the treatment of the speaker's voice.

**Original:**
> "Welcome back, let's now dig into probably the most tactical portion of the course, which is prompt engineering, we're going to cover the basics of prompt engineering in this section. And then in the next section, start digging into the use cases that require you to type prompts to do prompt engineering. So we're going to go ahead and dig into what prompt engineering is remember, everything begins with you shall know a word by the company it keeps when we work with prompts, we are programming, we are programmers, because we are typing instructions to a machine to get that machine to do something."

**Correct edit** — mechanics fixed, voice preserved:
> "Welcome back! Let's dig into probably the most tactical portion of the course, prompt engineering. We're going to cover the basics of prompt engineering in this section. In the next section, we'll start digging into the use cases that require you to type prompts and do prompt engineering. So, let's dig into what prompt engineering is. Remember, everything begins with "you shall know a word by the company it keeps". When we work with prompts, we are programming. We are programmers. We are typing instructions to a machine to get that machine to do something."

**Incorrect edit** — voice changed, paraphrased:
> "Welcome back. In this segment, we will delve into what is arguably the most practical aspect of the course: prompt engineering. We will start by covering the fundamentals of prompt engineering in this section. Following that, in the next section, we will explore various use cases that necessitate typing prompts for prompt engineering."

The incorrect version substituted formal language ("delve into", "arguably", "necessitate") and restructured sentences. This changes who the speaker sounds like.

## Output Format

Output the cleaned transcript only. Do not include:
- Explanations of what was changed
- Notes or commentary
- A summary of edits made
- Any text before or after the transcript itself

If the transcript contains speaker labels or timestamps, preserve them exactly.

## Additional Resources

- **`references/cleaning-rules.md`** — Complete rule set: preservation rules, grammar/punctuation rules, removal rules, deduplication rules, and context-specific terms for Christopher Penn / Trust Insights content
