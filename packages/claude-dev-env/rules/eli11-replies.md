# ELI11 Replies

Every chat reply the user reads follows one shape: action first, detail last, few words.

## Reply shape

1. **What I need from you** — when the user must act, open with "Do N things" and numbered click-by-click steps, one short line each, the action in bold. When nothing is needed, open with the outcome in one sentence.
2. **Findings** — at most 3 short bullets.
3. **Detail** — only when the user asks.

## Rules

- Short active sentences. One idea per sentence.
- Say what is, and what to do. Skip background, history, and options you are not recommending.
- A command the user should run goes in its own `bash`-tagged fenced block so the Run button appears — one command per block.
- Status updates on background work: one line each.
- Long reports overwhelm the user. When a reply grows past ~10 lines, cut findings before cutting the action steps.

## Relationship to other rules

- [`plain-language`](plain-language.md) governs word choice; this rule governs reply length and shape.
- `AskUserQuestion` still carries every question to the user, with the same short style in its options.
