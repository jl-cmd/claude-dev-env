# AskUserQuestion Required

Route every user-directed question through the `AskUserQuestion` tool — never a plain-text question in a response's final paragraph. Structure: concise `question`, `header` of 12 chars or fewer, 2-4 options (the UI adds the "Other" fallback), `multiSelect` only when choices genuinely combine.

## Context before the question

Each `question` field leads with a short fact, then asks. State what you found or what is at stake in one plain sentence, then put the decision on the next sentence (or after a colon). Bare questions without stakes fail the gate.

```
ok:   The gate blocks bare rm on worktrees. How should temp cleanup run?
flag: How should temp cleanup run?
```

Every option carries a short `description` so the user knows what choosing it does.

## Plain-brief wording

Write every question and option description in the `plain-brief` style (`output-styles/plain-brief.md`):

- Lead with the outcome or fact — never process narration ("I looked at...", "First, I...").
- One idea per short sentence.
- Everyday words; unpack jargon on first use.
- No arrow chains and no stacked-hyphen jargon stacks.
- Keep the question field to three sentences or fewer; keep each option description to two or fewer.
- Keep each sentence at 28 words or fewer.

The `plain_language_blocker` PreToolUse hook blocks heavy words. The `ask_user_question_style_blocker` PreToolUse hook blocks missing context, missing option descriptions, and plain-brief style breaks.

## Routing enforcer

The `question_to_user_enforcer` Stop hook blocks a response whose final paragraph (after stripping code fences, inline code, and blockquotes) ends in a question mark or contains ask-phrases ("would you like", "should I", "let me know if", ...). Rhetorical questions answered in the same paragraph, and questions inside code or blockquotes, pass. `verify-before-asking` gates whether the question belongs to the user at all.
