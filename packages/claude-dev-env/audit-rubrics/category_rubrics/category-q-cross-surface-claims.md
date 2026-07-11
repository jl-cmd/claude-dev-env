# Category Q — Cross-surface claim consistency (terminology, PR-description claims, message-vs-guard)

**What this category audits:** claims a change makes on one surface that a second surface contradicts. A code field carries one spelling while the prose that names it uses a near-miss variant. A PR description states a fact that the diff or the repo does not bear out. A log or error string asserts a condition that the branch gating it does not guarantee. Each defect lives in the gap between two surfaces that must agree: the code and the prose about it, the PR body and the diff, the message text and the guard that fires it.

**Why this category is its own bucket:** each surface reads as correct on its own. The code field is a valid identifier. The PR sentence is a well-formed claim. The log line is grammatical. The defect surfaces only when a reader holds two surfaces side by side and finds that one says a thing the other denies. Categories that read a single surface miss this; Q forces the reader to pair every claim with the surface that must back it.

## Canonical examples

- **PR #810 (Q1).** Eleven prose surfaces name the term one way while the code field reads `premium_interactions`. One divergent term spreads across README text, doc tables, and inline prose, so a reader who trusts any of the eleven surfaces reaches for a field name the code does not define.
- **PR #808 (Q2).** The PR description claims zero remaining gate subjects while `converge.mjs` still holds them. The body asserts a cleanup the diff does not finish, so a reviewer who trusts the description approves a state the code contradicts.
- **PR #823 (Q3).** A skip-branch log asserts a hardening PR opened, yet `spawnStandardsFollowUp` can return `hardeningPrOpened: false`. The message states an outcome the guard that reaches it does not guarantee, so the log reads as a success the run did not achieve.

## Other typical patterns

- A config key the diff adds reads `retry_budget`; a doc table row names it `retry-budget`, and a runbook names it `retry budget`.
- An API field the diff introduces is `itemCount` (singular tail); a client doc calls it `itemCounts`.
- A PR body says "this removes the last caller of `legacy_resolve`"; a reference search still finds a caller in a sibling module.
- A PR body claims a 30-second ceiling; the config value the diff sets reads 60 seconds.
- An error string says "config file is missing" while the branch that raises it fires on a parse failure, not an absent file.
- A log line says "retry limit reached this run" while the counter it reads resets each round, so the wording overstates the lifetime of the state it names.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category Q)

Decomposition is by the **pair of surfaces** that must agree.

| ID | Axis name | Concrete checks |
|---|---|---|
| Q1 | Term sweep | Pull out every identifier, API field, and config key the diff introduces or reads. Sweep all changed prose surfaces for near-miss variants — hyphen or space in place of an underscore, singular where the code is plural (or the reverse), a shared prefix with a divergent tail. Run `packages/claude-dev-env/_shared/pr-loop/scripts/terminology_sweep.py` for mechanical recall — it reads a unified diff on stdin or via `--diff-file`, prints one `file:line` finding per near-miss, exits 1 when findings exist and 0 when clean — then adjudicate each finding, since a near-miss can be an intentional distinct term. |
| Q2 | PR-description claim verification | Fetch the PR body. For each falsifiable claim, verify it two ways against the diff and the repo. A dead-code claim ("removes the last caller of X") gets a reference search across the repo. A performance or ceiling claim ("caps at 30 seconds", "cuts calls in half") gets checked against the actual config values and call sites the diff sets. |
| Q3 | Message-vs-guard consistency | For every log, error, and evidence string the diff adds or edits, read the condition that gates it. The message text matches what the guard guarantees — a string that asserts an outcome fires only on a branch that reaches that outcome. Temporal wording matches the lifetime of the state variable it names: "this run" versus "this round", "is open" versus "was opened", "reached" versus "attempted". |

Customize per-artifact: a change that adds no new identifier and no PR-body claim reduces Q to "verify every message the diff touches still matches its guard." A rename that spreads a term across many docs may need Q1 alone to list every prose surface.

---

## Sample prompt

The reusable template for Category Q is in [`../prompts/category-q-cross-surface-claims.md`](../prompts/category-q-cross-surface-claims.md). The Category Q source-material block needs the diff, the PR body text, and the changed prose surfaces the agent must cross-reference against the code.

## Why Category Q matters as its own bucket

A reviewer walking a single surface at a time — the code alone, the docs alone, the PR body alone — judges each on its own merits and misses Q. The code field is a valid name; the PR sentence is a plausible claim; the log line is grammatical. Only pairing each claim with the surface that must back it surfaces the gap. Q forces that pairing: every identifier the diff touches is swept against the prose, every PR-body claim is checked against the diff and the repo, and every message is read against the guard that fires it.
