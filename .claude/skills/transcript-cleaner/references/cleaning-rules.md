# Transcript Cleaning Rules

## Preservation Rules

- Maintain the speaker's original wording and sentence structure
- Keep contractions and slang exactly as delivered by the speaker
- Keep acronyms exactly as delivered by the speaker
- Preserve any speaker names and timestamps that appear in the transcript
- Do not include non-verbal cues (like [laughter], [pause], etc.)
- Do not make lists out of text unless the speaker explicitly declares that it is a list

## Grammar and Punctuation Rules

- Fix grammatical errors
- Correct punctuation errors
- Use em dashes (—) for interruptions or emphasis
- Break apart run-on sentences into discrete, properly punctuated sentences
- Break apart paragraphs longer than 5 sentences into multiple paragraphs
- Spell out numbers at the beginning of sentences; use numerals in the middle and end of sentences

## Removal Rules

Remove the following speech artifacts:

- **Filler words**: "uh", "um", "like" (when used as filler, not as a meaningful word)
- **False starts and speech interruptions**: incomplete sentence fragments where the speaker restarts a thought
- **"You know" and variations**: remove this phrase and its variants when used as filler
  - Example: "This is, you know, how we do it." → "This is how we do it."
- **Trailing "right?" as filler**: remove sentences ending with "right?" when it's used as a discourse marker, not a genuine question
  - Example: "This was the way things were, right?" → "This was the way things were."

## Deduplication Rules

- **Duplicate words**: remove duplicate words appearing next to each other
  - Example: "This is the focus focus of the system" → "This is the focus of the system"
- **Duplicate sentences**: remove duplicate sentences appearing next to each other
- **Duplicate phrases**: remove duplicate phrases appearing next to each other
  - Example: "It's marketing speak, it's marketing speak, it's a way, it's a way to understand" → "It's marketing speak, it's a way to understand"

## Context-Specific Terms

Preserve and spell these terms correctly:

**People and companies:**
- Christopher Penn (speaker name)
- Trust Insights, Trust Insights Inc., TrustInsights.ai

**AI and technology terms:**
- large language models
- ChatGPT
- LLMs
- Google Gemini
- IBM WatsonX

**Business terms:**
- 5P Framework
- In-Ear Insights

**General terms:**
- data, AI, artificial intelligence, analytics, consulting, management
