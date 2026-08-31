# Prose-style enforcement

Opinionated prose gates (hedging, historical state phrasing, intent-only endings, hook prose-detector consistency) are **off by default**.

## Opt-in

Set `CLAUDE_PROSE_STYLE_ENFORCEMENT` to `1`, `true`, `yes`, or `on` (case and spaces ignored). Any other value, and an unset variable, leave those gates off.

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in `hooks/blocking/config/prose_style_enforcement_constants.py`.

## Always on

Structural AskUserQuestion lean-block validation in `ask_user_question_shape_blocker` (chat detail, length caps on question blocks) stays active regardless of the flag. Apply `rules/asd-ste100-language.md` for user-facing word choice and sentence style. Code-rules and security blockers are out of scope for this switch.

## Advisory precision measurement (OP-07B)

When the flag is off, hedging hits still emit privacy-safe advisory candidates to `~/.claude/logs/prose-matcher-advisory.jsonl` (matcher id, surface, hashed context fingerprint, optional label). Classification (`keep` / `narrow` / `drop` / `advisory`) uses a labeled sample floor of 30 and precision floors 0.7 / 0.4. Matchers below the floor stay advisory. See `hooks/observability/prose_matcher_advisory.py`.

## Explicit uncertainty (OP-07C)

With enforcement on, a hedge word in a sentence that also labels the claim (`unverified`, `I don't know`, `no source for this claim`, …) passes. A bare hedge in a different sentence still blocks. Detail: `rules/hedging-claims.md`.
