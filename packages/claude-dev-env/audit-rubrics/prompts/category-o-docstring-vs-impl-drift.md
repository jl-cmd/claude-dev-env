# Category O audit prompt (Variant C)

**Judgment standard (thick source):** `packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md`

This file is the audit **template** only: source-material slots, forced-exhaustion protocol, adversarial probes, cross-bucket questions, output shape, and a worked example. For every sub-bucket's judgment standard, gate inventory, and free-form checklist, read the thick rubric above. Do not treat this prompt as a second full copy of the standard.

## Division of labor

| Surface | Role |
|---|---|
| Category O rubric | Single thick judgment source (O1–O9, gates, checklists, examples). |
| **This prompt** | Variant C protocol shell that points at the rubric for judgment. |
| `packages/claude-dev-env/rules/docstring-prose-matches-implementation.md` | Always-on write-time policy + compact checklist. |

---

Audit [REPO/ARTIFACT] [TARGET_ID] for **Category O only** (docstring / fixture-prose vs implementation drift). Skip A–N, P. Sub-bucket forced-exhaustion mode: Category O is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

Apply each sub-bucket's **judgment standard** from the thick rubric. The bullets under each sub-bucket here are protocol probes only.

[ARTIFACT METADATA — include every changed module's docstring AND the exported symbols of that module so the audit can compare claim vs body]

- Title / one-line summary: [TITLE]
- Head ref / SHA at audit time: [HEAD_SHA]
- Changed modules (file + module-level docstring verbatim + exported symbol list): [CHANGED_MODULES]
- Changed fixtures (file + fixture-function docstring verbatim + sibling-test names in the same file): [CHANGED_FIXTURES]
- Changed helper functions whose body was edited (file:line + function docstring verbatim + signature): [CHANGED_HELPERS]
- Stated intent of the change: [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: list every changed module / fixture / helper. State the audit goal: for each docstring claim, verify the body delivers exactly what the claim promises — no broader, no narrower, no different ordering, no references to sentinels/filenames the body and repo do not use.]

## Source material ([N] files/sections, all lines in scope)

[INLINE each changed module's docstring + the symbols defined in that module. INLINE each changed fixture's docstring + the names of sibling tests in the same file. INLINE each changed helper-function docstring + the verbatim function body.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**O1. Module-level responsibility verbs** ⭐ canonical O case
- Judgment: thick rubric O1 (responsibility verbs + user-facing-text vs data-schema scope).
- Adversarial probes: (a) grep for the verb's noun-form in sibling modules — did a refactor place the responsibility elsewhere; (b) inspect the module's `__all__` (if present) — does every claimed responsibility appear; (c) check git log for recent splits — does the docstring still describe the pre-split scope.

**O2. Fixture docstring vs sibling-test behavior**
- Judgment: thick rubric O2.
- Adversarial probes: (a) grep for the fixture's invariant-setting call in test bodies — does any test re-call it with a different argument; (b) check for `pytest.mark.parametrize` arguments that reach a code path the fixture claim says is disabled; (c) check for explicit teardown / reset calls inside tests that contradict the fixture's blanket scope.

**O3. Predicate-name and -docstring vs body breadth**
- Judgment: thick rubric O3.
- Adversarial probes: (a) walk each `return True` branch and ask whether the input that reached it satisfies the name's promise; (b) construct an input class outside the named promise that still returns True — that is an O3 finding; (c) check the name against neighboring helpers — is one of them the better home for the broader case.

**O4. Step-ordering narrative**
- Judgment: thick rubric O4 (includes branch-guarded dispatch; gated form `check_docstring_step_enumeration_dispatch_coverage`).
- Adversarial probes: (a) read the body strictly top-to-bottom and label each call A/B/C against the docstring's named steps; (b) check for early returns that reorder visible steps; (c) check for `try/finally` blocks where the finally clause is itself one of the named steps and runs out of declared order.

**O5. Named-sentinel / filename references**
- Judgment: thick rubric O5.
- Adversarial probes: (a) grep the exact sentinel string in this module and sibling modules; (b) grep the named filename against the repo's naming convention (underscore vs hyphen); (c) check for case-sensitivity mismatches between the docstring and the body.

**O6. Free-form `Args:`-adjacent claims**
- Judgment: thick rubric O6 (unions, suppressors, exclusion axis, delegation summaries, Returns/Raises/Note claims, run-mode field meaning). Gate inventory and free-form checklist live in the rubric.
- Adversarial probes: (a) check `Returns:` claims against every `return` statement in the body — is the documented return shape the actual return shape; (b) check `Raises:` claims against every `raise` and propagating callee — is every documented raise reachable; (c) check `Example:` snippets — does the snippet actually compile against the signature.

**O7. Module-doc-vs-split-module after refactor**
- Judgment: thick rubric O7.
- Adversarial probes: (a) for each module in the split, list its exported symbols and compare to the docstring's claimed responsibilities; (b) grep the responsibility's verb against the originating module — does the originating docstring still claim what left; (c) check for cross-module imports that reveal which file hosts each responsibility.

**O8. Companion-doc ordering/content vs producer**
- Judgment: thick rubric O8 (order/content claims vs producer; `check_docstring_no_consumer_claim` for the producer-only assertion slice).
- Adversarial probes: (a) for each changed producer, name the artifact it builds and grep the skill's `SKILL.md` and sibling `.md` files for any sentence naming that artifact; (b) walk the producer body's build step — does it sort, or does it merge stored names and append in file order — and compare against the doc's order word (`sorted`, `alphabetical`); (c) check whether the doc's content claim (`just the at-risk names`, `only the current set`) hides merged-in prior entries the producer carries over from the stored file.

**O9. Python docstring plainness for a general developer**
- Judgment: thick rubric O9 (and `packages/claude-dev-env/rules/plain-illustrative-docstrings.md`). Run-on and prose-wall gates backstop the deterministic marks.
- Adversarial probes: (a) read each changed narrative and name the concrete moment, input, and outcome it paints — a narrative that names none is an O9 finding; (b) count the longest sentence's words and check for an em-dash or semicolon join — over the limit with a join is the wall mark the gate also catches; (c) rewrite each "is not" clause as a positive statement — a clause that resists rewriting because the body offers no positive description is an O9 finding.

## Cross-bucket questions to answer at the end

Q1: Across all 9 sub-buckets, which docstring claim is the most misleading — i.e., a future maintainer reading only the docstring would write or change code that contradicts the body? Cite file:line of the docstring AND the body line(s) that contradict it.

Q2: Which docstring claim is at highest risk of becoming load-bearing — i.e., a future caller or test author would rely on the claim to skip reading the body? Cite the claim and the use case.

Q3: Of the changed docstrings, which one most clearly shows a refactor was incomplete (i.e., the body changed but the docstring did not)? Cite both the docstring and the body change that orphaned it.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket O1-O9, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite (a) the docstring file:line, (b) the body file:line that contradicts it, and (c) one sentence describing the contradiction in concrete terms. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 module-level docstring claims whose implementation left during a refactor — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-dev-env PR #522

Audit jl-cmd/claude-dev-env PR #522 for **Category O only** (docstring / fixture-prose vs implementation drift). Skip A-N, P. Sub-bucket forced-exhaustion mode: Category O is decomposed into 9 sub-buckets below.

PR #522 split `pr_description_command_parser.py` into two modules — the original parser and a new `pr_description_pr_number.py` — but the originating module's docstring still claims the PR-number recovery responsibility. A sibling change to `pr_description_body_audit.py` introduced a module docstring whose verb (`detects vague language`) overstates the module's actual responsibility (it only exposes `_extract_vague_scan_text()`; detection runs elsewhere).

Expected findings on PR #522:
- **O1 finding:** `pr_description_body_audit.py:8` docstring uses verb `detects`, but the only exported symbol prepares input for a regex scan that fires in a different module. Body line(s) showing `_extract_vague_scan_text` returning normalized text without a detection call.
- **O7 finding:** `pr_description_command_parser.py` module docstring still names PR-number recovery as a responsibility; the split placed that in `pr_description_pr_number.py`. The originating docstring needs an O7-shaped rewrite to drop the claim that left.
- **O2 finding:** `test_pr_description_enforcer_readability.py` autouse fixture docstring claims readability is globally disabled `for these tests`; sibling tests in the same module explicitly re-enable readability through a different state path.
- **O5 finding:** `code_rules_magic_values.py` docstring references a `# pragma: no-tdd-gate` sentinel and a hyphenated `test_code-rules-enforcer.py` filename; neither token exists in the module body or matches the repo's underscore-only test-file naming convention.
