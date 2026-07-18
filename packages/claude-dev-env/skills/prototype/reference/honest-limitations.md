# Honest limitations of a promoted prototype

State both of these to the user, in these terms, whenever a proof-of-concept is promoted. Do not soften or drop them. They are the price of building without standards gates.

## 1. Write-time code rules never ran on this code

`code_rules_enforcer` is a Write/Edit gate: it checks content as it is written. Prototype code is built under `--bare`, so that gate never fired, and content brought into promotion as a git diff (apply, checkout, cherry-pick) does not pass through it either.

Standards re-engage on promotion through three surfaces that stand in for the write-time hook:

- the `code-verifier` agent, in a fresh context, deriving and running the named gates against the real diff;
- the `privacy-hygiene` sweep for personal data and secrets;
- the pull-request review (AGENTS.md criteria and any PR-loop reviewers).

Say plainly: the write-time rule engine did not see this code; the verifier and review are what cover it.

## 2. TDD ordering is waived on promoted prototype lines

The sandbox agent wrote code first and tests, if any, after. Red-green-refactor ordering did not happen. So the honest claim on promoted prototype code is exactly this, and nothing more:

> code-verifier passed, privacy swept, review passed — TDD ordering waived.

Do not claim red-green compliance on these lines. A prototype is a reference build, not a test-first build. Fred Brooks: plan to throw one away. Promotion re-verifies the code and often rewrites it to standard; expect real work in the verifier repair loop, not a rubber stamp.
