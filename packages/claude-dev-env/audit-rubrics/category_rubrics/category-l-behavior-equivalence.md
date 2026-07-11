# Category L — Behavior-equivalence for refactors

**What this category audits:** rewrites of an existing function (especially an enforcement check, parser, classifier, or normalizer) where the new implementation must accept every input the old implementation accepted and reject every input the old implementation rejected. Common when a regex-based check is rewritten as a tokenize-based check, when a `str.startswith` chain is consolidated into a single regex, when a hand-rolled split is replaced with a library call, or when a multi-step pipeline is collapsed into one pass.

**Why this category is its own bucket:** Categories A–K catch failure modes inside the rewrite itself (wrong signature, dead code, missed branch). Category L catches the failure mode that emerges between the rewrite and the *historically valid inputs* the original code accepted. The diff looks internally consistent and the new unit tests pass — but inputs the prior code accepted fall through under the new implementation, or inputs the prior code rejected slip past. The bug only surfaces against the corpus of canonical inputs the original implementation was tuned for.

**Examples of Category L findings:**
- A tokenize-based exempt-marker check drops `#noqa` (no space after `#`) when the original normalization-based check accepted it. (ccc#479 F1)
- A new comment classifier misreads a bare `#` lookalike that the original regex correctly rejected. (ccc#479 F4)
- A refactored shebang detector drops the inline `#!` variant the original handled. (ccc#479 F5)
- An invariant the original loop enforced at the first match (early-exit) is dropped in the rewrite. (ccc#479 F6)
- A `startswith('## Problem')` shape is too loose compared to the sibling regex shape, accepting `## Problems and Pitfalls`. (ccc#472 F44)

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category L)

Decomposition is by the **kind of historically valid input** the rewrite must continue to accept (or reject) without behavior drift.

| ID | Axis name | Concrete checks |
|---|---|---|
| L1 | KNOWN_GOOD_INPUTS table presence | The rewrite ships a fixture (parametric test, table-driven inputs, or sibling-implementation comparison) enumerating the canonical historically-valid inputs the original accepted. |
| L2 | Whitespace / separator variants | Inputs with no space, leading whitespace, trailing whitespace, multiple internal spaces, tabs, or CRLF line endings retain their original accept/reject classification. |
| L3 | Adjacent-form regressions | A looser pattern in the rewrite (`startswith` where the original used a regex) accepts inputs the original rejected; OR a tighter pattern rejects inputs the original accepted. |
| L4 | Empty / boundary inputs | Empty string, single character, single-line vs multi-line, EOF without newline retain their original classification. |
| L5 | Invariant preservation | Early-exit guarantees, idempotence, ordering, stable iteration, "first match wins" semantics carry over. |
| L6 | Implementation-tag parity | Token-based vs regex-based vs str-method-based: the new tag accepts every input shape the old tag accepted (no shape silently dropped). |
| L7 | Skipped-category exhaustion | Inputs that the original explicitly skipped (e.g., shebang on line 1 only, exempt markers without trailing prose, `# type:` with a trailing justification) remain skipped. |
| L8 | Sibling-implementation comparison | When two parallel implementations exist (e.g., Python + PowerShell, regex + tokenize), the rewrite of one must still produce the same accept/reject decisions as the sibling for shared inputs. |

Customize per-artifact: a parser refactor without an explicit sibling implementation reduces L8 to "verified clean — no parallel implementation"; a single-axis rewrite (whitespace handling only) may exhaust the per-sub-bucket checks against just L2 and L7.

---

## Sample prompt

The reusable Variant C template for Category L is in [`../prompts/category-l-behavior-equivalence.md`](../prompts/category-l-behavior-equivalence.md). Inline the BEFORE state of the rewritten function, the AFTER state, and the KNOWN_GOOD_INPUTS the original accepted under `## Source material`.

## Why Category L matters as its own bucket

Categories A–K describe failure modes that show up in the rewrite's own surface. Category L describes the failure mode that shows up only when the rewrite is compared against the inputs the original was tuned for. A reviewer walking only A–K reads the rewrite, finds it clean, and approves it — without re-running the original test inputs through the new code path. L forces the reviewer to pin the original's known-good inputs in a table and assert each still passes against the rewrite.

The ccc#479 F1 case illustrates the cost of not running L. The refactor of `_is_exempt_python_comment` replaced a `comment_string[1:].lstrip()` normalization (which reduced both `# noqa` and `#noqa` to the body `noqa` before the membership test) with a tokenize-based recognizer that tested the raw `tokenize.COMMENT` token text against `startswith("# noqa")`. Production code carrying `#noqa: F401` (no space) silently stopped matching the exempt marker after the refactor, and the no-new-comments gate began blocking writes that the original implementation passed. The dropped no-space variant only surfaces under a KNOWN_GOOD_INPUTS table that enumerates spaced, no-space, tab-separated, and multi-space inputs — fixtures the rewrite's own tests would otherwise miss.
