# Prose-style enforcement

Five hooks read the writing rules and block work that breaks them. One shared
switch turns all five on or off together.

## The five checks

| Hook | Fires on | What it blocks |
|---|---|---|
| `hedging_language_blocker.py` | Stop | A reply carrying hedging words such as `likely`, `probably`, `appears to be` |
| `question_to_user_enforcer.py` | Stop | A reply that asks the user a question in prose instead of through the AskUserQuestion tool |
| `intent_only_ending_blocker.py` | Stop | A reply that ends on a promise about work that is still undone |
| `plain_language_blocker.py` | PreToolUse (AskUserQuestion, Write/Edit/MultiEdit on `.md`) | Heavy words with an everyday swap, such as `utilize` for `use` |
| `state_description_blocker.py` | PreToolUse (Write/Edit) | Historical and comparative wording in comments, Python docstrings, and `.md` files |

## The switch

The flag is `PROSE_STYLE_ENFORCEMENT_ENABLED` in
`hooks/hooks_constants/prose_style_enforcement_constants.py`. It ships as
`False`.

Set it to `True` to turn all five checks back on:

```python
PROSE_STYLE_ENFORCEMENT_ENABLED = True
```

## What off means

Off means silent. Each hook reads the flag before it looks at any text, and
returns straight away when the flag is `False`. It writes no output, records no
block, and adds no note to the transcript, matching the `verified_commit` and
`code-review` gate families.

The writing rules themselves stay in place. `~/.claude/rules/` still carries
plain-language, no-historical-clutter, ask-user-question-required, and
long-horizon-autonomy, and agents still follow them. The flag governs
mechanical enforcement alone.

## Coverage

The two PreToolUse hooks read the flag inside `evaluate()`, so both their
standalone-script and in-process dispatcher paths obey it.

`ALL_PROSE_STYLE_HOOK_MODULE_NAMES` in the constants module lists the five, and
`test_prose_style_enforcement_constants.py` walks that roster: it runs each hook
on one violating payload with the flag forced on, asserts the block, then runs
the same payload with the flag forced off and asserts silence.

## Hooks outside the switch

`session_handoff_blocker` runs on the same Stop dispatcher and enforces the same
long-horizon-autonomy rule on reply prose, and it sits outside this switch by
design: it protects run continuity rather than word choice.
