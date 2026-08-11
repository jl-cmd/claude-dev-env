# Prose-style enforcement

Opinionated prose gates (heavy-word swaps, hedging, historical state phrasing, intent-only endings, hook prose-detector consistency) are **off by default**.

## Opt-in

Set `CLAUDE_PROSE_STYLE_ENFORCEMENT` to `1`, `true`, `yes`, or `on` (case and spaces ignored). Any other value, and an unset variable, leave those gates off.

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in `hooks/blocking/config/prose_style_enforcement_constants.py`.

## Always on

Structural AskUserQuestion lean-block validation in `plain_language_blocker` (chat detail, length caps on question blocks) stays active regardless of the flag. Code-rules and security blockers are out of scope for this switch.

## Advisory precision measurement (OP-07B)

When the flag is off, heavy-word and hedging hits still emit privacy-safe advisory candidates to `~/.claude/logs/prose-matcher-advisory.jsonl` (matcher id, surface, hashed context fingerprint, optional label). Classification (`keep` / `narrow` / `drop` / `advisory`) uses a labeled sample floor of 30 and precision floors 0.7 / 0.4. Matchers below the floor stay advisory. No matcher becomes hard-blocking from historical labels alone. See `hooks/observability/prose_matcher_advisory.py`.

## Explicit uncertainty (OP-07C)

With enforcement on, a hedge word in a sentence that also labels the claim (`unverified`, `I don't know`, `no source for this claim`, …) passes. A bare hedge in a different sentence still blocks. Detail: `rules/hedging-claims.md`.

## Plain-language advisory (OP-07D)

Heavy-word matches never hard-deny a Write/Edit or AskUserQuestion. With enforcement on, the hook allows the call and returns a `systemMessage` that names everyday swaps for both AskUserQuestion and `.md` writes. Lean-block structure denials stay hard. Detail: `rules/plain-language.md`.
