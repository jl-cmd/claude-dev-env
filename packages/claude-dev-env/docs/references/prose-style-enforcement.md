# Prose-style enforcement

Two opinionated prose gates (heavy-word swaps in `plain_language_blocker.py`, hook prose-detector consistency in `hook_prose_detector_consistency.py`) are **off by default**.

## Opt-in

Set `CLAUDE_PROSE_STYLE_ENFORCEMENT` to `1`, `true`, `yes`, or `on` (case and spaces ignored). Any other value, and an unset variable, leave those two gates off.

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in `hooks/blocking/config/prose_style_enforcement_constants.py`.

## Always on

Structural AskUserQuestion lean-block validation in `ask_user_question_shape_blocker` (chat detail, length caps on question blocks) stays active regardless of the flag. Historical/comparative language detection in `state_description_blocker.py` runs unconditionally and does not read this flag. Apply `rules/asd-ste100-language.md` for user-facing word choice and sentence style. Code-rules and security blockers are out of scope for this switch.

## Hedging claims

Hedge-word discipline is prose guidance, not a hook: `rules/hedging-claims.md`. State a claim with its evidence, or label it unverified in the same sentence as the hedge word.
