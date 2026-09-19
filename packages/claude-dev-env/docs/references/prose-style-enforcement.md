# Prose-style enforcement

Two opinionated prose gates (heavy-word swaps in `plain_language_blocker.py`, hook prose-detector consistency in `hook_prose_detector_consistency.py`) are **off by default**.

## Opt-in

Set `CLAUDE_PROSE_STYLE_ENFORCEMENT` to `1`, `true`, `yes`, or `on` (case and spaces ignored). Any other value, and an unset variable, leave those two gates off.

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in `hooks/blocking/config/prose_style_enforcement_constants.py`.

## Always on

Historical and comparative language detection lives in `state_description_blocker.py`, which the staged policy lint applies under its state-description rule whatever this flag holds. Apply `rules/asd-ste100-language.md` for user-facing word choice and sentence style. Code-rules and security blockers are out of scope for this switch.

## Hedging claims

Hedge-word discipline is prose guidance, not a hook. State a claim with its evidence, or label it unverified in the same sentence as the hedge word.
