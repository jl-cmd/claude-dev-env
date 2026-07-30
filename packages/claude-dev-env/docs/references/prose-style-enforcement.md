# Prose-style enforcement

Opinionated prose gates (heavy-word swaps, hedging, historical state phrasing, intent-only endings, hook prose-detector consistency) are **off by default**.

## Opt-in

Set `CLAUDE_PROSE_STYLE_ENFORCEMENT` to `1`, `true`, `yes`, or `on` (case and spaces ignored). Any other value, and an unset variable, leave those gates off.

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in `hooks/blocking/config/prose_style_enforcement_constants.py`.

## Always on

Structural AskUserQuestion lean-block validation in `plain_language_blocker` (chat detail, length caps on question blocks) stays active regardless of the flag. Code-rules and security blockers are out of scope for this switch.
