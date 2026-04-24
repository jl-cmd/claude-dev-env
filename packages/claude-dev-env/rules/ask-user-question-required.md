# AskUserQuestion Required

**When this applies:** Any time you would ask the user a question during discovery, scoping, or implementation planning — after the `verify-before-asking` decision checklist confirms the question genuinely belongs to the user.

## Rule

Route every user-directed question through the `AskUserQuestion` tool. Embedded plain-text questions in the final paragraph of an assistant message are blocked by a Stop hook, and the response must be re-output with the ask moved into an `AskUserQuestion` tool call.

## Detection Criteria

The `question_to_user_enforcer` Stop hook inspects the last non-empty paragraph of the response after stripping fenced code blocks, inline code (backticks), and blockquoted lines (`> …`). The response is blocked when either signal is present:

- The final paragraph's last sentence ends with a question mark.
- The final paragraph contains any of these preamble phrases (case-insensitive, word-boundary matched): `would you like`, `should I`, `do you want`, `which would you prefer`, `let me know if`, `let me know which`, `let me know whether`, `please confirm`, `please let me know`, `want me to`.

## Acceptable Plain-Text Question Patterns

These remain allowed and do not trigger the hook:

- **Rhetorical questions answered in the same paragraph.** `"What happens if the queue is empty? The handler short-circuits cleanly."` The question frames its own answer; the reader never has to respond.
- **Questions inside code, diffs, or documentation excerpts.** Code fences, inline backticks, and `>` blockquotes are stripped before detection. Quoting a GitHub issue title, a user's prior message, or a log line inside a blockquote is fine.
- **Middle-paragraph questions when the closing paragraph is declarative.** Only the final paragraph is scanned.

## AskUserQuestion Structure

When a question is genuinely for the user, call the tool with:

- A concise `question` string stating what is needed.
- A `header` of twelve characters or fewer summarizing the decision.
- Two to four `options`, each with a short `label` the user can pick. An "Other" free-text fallback is already provided by the UI; do not add one manually.
- `multiSelect: false` unless the user can genuinely combine choices.

## Why

- **Structured options reduce re-reading friction.** The user sees labeled choices directly rather than scanning prose for the ask.
- **Transcript clarity.** Tool-use entries are easy to locate in the JSONL transcript; prose questions disappear into the response text.
- **Reduced drift.** Claude's next turn cannot move past an unanswered structured question; prose questions can be silently bypassed.

## Enforcement

- Hook: `packages/claude-dev-env/hooks/blocking/question_to_user_enforcer.py`, registered on the `Stop` matcher in `packages/claude-dev-env/hooks/hooks.json`.
- Loop prevention: the hook honors Claude Code's `stop_hook_active` flag and does not re-block on retry.
- User-facing notice: `USER_FACING_ASKUSERQUESTION_NOTICE` in `packages/claude-dev-env/hooks/config/messages.py`.
- Related rule: `packages/claude-dev-env/rules/verify-before-asking.md` gates whether the question belongs to the user in the first place.
