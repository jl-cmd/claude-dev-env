# Honest limitations of a promoted prototype

State both of these to the user, in these terms, whenever a proof-of-concept is promoted. Do not soften or drop them. They are the price of building without standards gates.

## 1. Write-time code rules never ran on this code

`code_rules_enforcer` is a Write/Edit gate: it checks content as it is written. Prototype code is built under `--bare`, so that gate never fired, and content brought into promotion as a git diff (apply, checkout, cherry-pick) does not pass through it either.

Promotion records the controls applied to the real diff:

- review and verification under the [review guide](../../reviews/SKILL.md#review-workflow);
- the `privacy-hygiene` sweep for personal data and secrets;
- the pull-request review (AGENTS.md criteria and any PR-loop reviewers).

Say plainly: the write-time rule engine did not see this code; the verifier and review are what cover it.

## 2. TDD ordering is waived on promoted prototype lines

The sandbox agent wrote code first and tests, if any, after. Red-green-refactor ordering did not happen. So the honest claim on promoted prototype code is exactly this, and nothing more:

> Review and verification completed, privacy swept — TDD ordering waived.

Do not claim red-green compliance on these lines. A prototype is a reference build, not a test-first build. Promotion reviews and verifies the code against the current standards.
