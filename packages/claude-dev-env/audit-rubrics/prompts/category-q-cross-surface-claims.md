Audit [REPO/ARTIFACT] [TARGET_ID] for **Category Q only** (cross-surface claim consistency — terminology, PR-description claims, message-vs-guard). Skip A–P. Sub-bucket forced-exhaustion mode: Category Q is decomposed into 3 sub-buckets below. Each sub-bucket needs at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]

- Title / one-line summary: [TITLE]
- Base ref / SHA (state before the change): [BASE_SHA]
- Head ref / SHA at audit time (state after the change): [HEAD_SHA]
- Changed surfaces (file + line range + symbol/region name): [CHANGED_SURFACES]
- New or read identifiers, API fields, and config keys the diff touches: [DIFF_TERMS]
- Changed prose surfaces (README, doc tables, inline prose, log and error strings): [CHANGED_PROSE_SURFACES]
- PR description body text: [PR_BODY]
- Stated intent of the change: [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: describe what the diff changed in plain English, naming the identifiers and config keys it introduces, the PR-body claims it makes, and the messages it adds or edits. State the audit goal: find any surface whose wording contradicts another surface that must agree with it — a prose term that misspells a code field, a PR-body claim the diff or repo does not bear out, or a message that asserts more than the guard gating it guarantees.]

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL DIFF — the changed lines and enough surrounding context to show each identifier's definition and each message's guard.]

[ALSO INLINE the PR description body text and every changed prose surface — README sections, doc tables, runbooks, log and error strings — so the agent can pair each claim with the code it names.]

## Sub-buckets (each needs a Shape A finding OR Shape B with ≥3 adversarial probes)

**Q1. Term sweep**
- Pull out every identifier, API field, and config key the diff introduces or reads. For each, sweep all changed prose surfaces for a near-miss variant — a hyphen or a space in place of an underscore, a singular where the code is plural (or the reverse), a shared prefix with a divergent tail.
- Run `packages/claude-dev-env/_shared/pr-loop/scripts/terminology_sweep.py` for mechanical recall. It reads a unified diff on stdin or via `--diff-file`, prints one `file:line` finding per near-miss, exits 1 when findings exist and 0 when clean. Feed it the PR diff, then adjudicate each finding: a near-miss can be an intentional distinct term, so cite the code definition and the prose line and judge whether they name the same thing.
- Adversarial probes when the sweep is clean: (a) check camelCase versus snake_case spellings of the same field across code and docs; (b) check singular/plural drift on collection field names; (c) check a shared-prefix family (`retry_budget`, `retry_count`, `retry_limit`) for a doc that names the wrong member.

**Q2. PR-description claim verification**
- Read the PR body. List each falsifiable claim — a dead-code removal, a performance or ceiling number, a "last caller" assertion, a "no remaining X" cleanup claim.
- Verify each claim two ways against the diff and the repo. A dead-code claim gets a reference search across the repo for the named symbol. A ceiling or performance claim gets checked against the actual config value the diff sets and the call sites it touches. Cite the PR-body line and the diff or repo line that confirms or contradicts it.
- Adversarial probes when the body looks correct: (a) search the repo for a surviving caller of any symbol the body calls dead; (b) compare each stated number against the config constant the diff sets; (c) check whether a "this finishes the cleanup" claim leaves a matching pattern in an unchanged sibling file.

**Q3. Message-vs-guard consistency**
- For every log, error, and evidence string the diff adds or edits, read the branch condition that gates it. The message text matches what that guard guarantees: a string asserting an outcome fires only on a branch that reaches the outcome.
- Check temporal wording against the lifetime of the state variable the message names: "this run" versus "this round", "is open" versus "was opened", "reached" versus "attempted". Cite the message line and the guard or state-variable line.
- Adversarial probes when messages look aligned: (a) trace each success message back to the return value or flag it claims and confirm the branch cannot reach it with the opposite value; (b) check every "missing" / "not found" error against the exception class the branch actually catches; (c) check every counter-based message against where the counter resets.

## Cross-bucket questions to answer at the end

Q-a: Which single claim in this change is most likely to mislead a reader at runtime — a prose term that names a field the code does not define, a PR-body fact the diff contradicts, or a message that overstates its guard? Cite both surfaces by `path:line`.

Q-b: Which surface is the strongest witness to the contradiction — the doc, PR body, or message a reader would trust while the code says otherwise?

Q-c: Is there a term the diff introduces that appears correct in the code yet drifts across two or more prose surfaces at once? Cite each prose line and the code definition.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket Q1-Q3, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding cites BOTH surfaces — the claim and the surface that contradicts it — by `path:line`. The `failure_mode` describes the contradiction between the two surfaces. Cross-bucket Q-a through Q-c answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 cross-surface contradictions — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
