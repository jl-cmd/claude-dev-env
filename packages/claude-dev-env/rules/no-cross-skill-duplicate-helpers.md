---
paths: "**/skills/*/scripts/**/*.py"
---

# Cross-Skill Duplicate Helpers

**When this applies:** Any Write or Edit to a `.py` file under a skill's `scripts/` directory (`**/skills/<skill-name>/scripts/**/*.py`) that copies a top-level helper from another skill's `scripts/` directory.

## The two duplication cases differ

CODE_RULES "Reuse before create" / DRY says one helper lives in one home and both call sites import it. That rule is enforced **within one skill**. Two `.py` modules in the same skill's `scripts/` directory that carry the same top-level function body fail the `code_rules_duplicate_body` check, which the staged policy lint runs through `code_rules_enforcer.py`. The fix is a shared module both import.

Across **two skill folders** the same copy is a different call. Each skill folder installs on its own, so a shared module would couple two skills the install model keeps separate: deleting or reinstalling one skill would break a helper the other depends on. A small launch helper copied into each skill (for example a Chrome-open helper that reads the registry and runs `chrome.exe`) is a defensible skill-isolation tradeoff, not a regression.

## Decision

Before you copy a top-level helper from one skill's `scripts/` directory into another:

- **Same skill, two modules.** Extract one shared module in that skill and import it from both. The `code_rules_duplicate_body` check reports the copy.
- **Two skill folders, a small self-contained helper.** Copy it, and the skill-isolation tradeoff stands. An advisory `[CODE_RULES advisory]` line names the source skill when the lint runs, so the copy is a deliberate choice on record, not an oversight.
- **Two skill folders, a large or behavior-bearing body** — when the copied body is large, holds business logic, or would drift in a way that changes behavior, raise the choice through `AskUserQuestion`: copy and accept drift, or stand up a shared dependency both skills declare (for example a published package both `requirements` files name, or a `_shared` module the install step writes into each skill). A shared dependency that survives independent install is the only shared-home path that does not break the install model.

## What the advisory tells you

The `advise_cross_skill_duplicate_helper` check in `code_rules_duplicate_body` prints to stderr (never fails the lint) when a top-level function in a changed file has the same normalized body as a top-level function in another skill's `scripts/` directory. The message names the source skill and function so a reviewer can confirm the copy was intentional. It fires only across skill folders. Within one skill the reporting check already covers the copy.

## Why this is a rule, not a wider check

Extending the duplicate-body check to span skill folders would report the exact skill-isolation copy that keeps skills independently installable, a false positive on a sanctioned pattern. The boundary between "same skill, report" and "two skills, signal" is a judgment the writer makes with the source skill named in front of them. The rule states the judgment, and the `[CODE_RULES advisory]` line surfaces the signal. Neither one fails the defensible copy.
