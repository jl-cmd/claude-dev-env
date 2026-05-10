# Fill placeholders with real values

Some prompts ship as templates with placeholder tokens. The skill replaces those with concrete values pulled from the rubric, the companion artifact, or the user.

## Detection patterns

A placeholder is any bracketed token whose content reads as instructional rather than a literal name. Common shapes:

- `[REPO/ARTIFACT]`
- `[TARGET ID]`
- `[N]`
- `[ARTIFACT METADATA]`
- `[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]`
- `[List the supported …]`
- `[Declared minimum …]`
- `[file:line / paragraph]`
- `[A1]–[AN]`, `[B1]–[BN]`, etc.

## Procedure

1. Find every placeholder in the prompt.
2. For each placeholder, look up the value via [`research.md`](research.md).
3. Replace the placeholder with the real value.
4. For placeholders matching `[INLINE THE FULL ARTIFACT HERE …]` (any placeholder that opens with `INLINE THE FULL ARTIFACT`, including the long-form `[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]`), the artifact's text comes from one of the sources [`research.md`](research.md) enumerates — a local file the user named when invoking in file-path mode, a sibling artifact the rubric points at, content the user pasted alongside the prompt, or a path the user supplied via AskUserQuestion. Inline that text as fenced code blocks, using each file's path as a `###` heading above its fenced block. The skill never reaches outside those sources for retrieval; when none of them yields the artifact, the spoke leaves the placeholder in place and records a gap per [`output-contract.md`](output-contract.md).

## When the rubric points at a sibling prompt

Rubric files often say "use category-X.md as the canonical worked example." When that happens:

1. Read the sibling prompt.
2. Copy the sibling's data body — the inlined artifact — into this prompt's data body.
3. Sharpen this prompt's sub-bucket bullets so they cite the identifiers in the data body that match this category's axes.
4. Keep the category-specific phrasing intact. Only the data body and the per-bucket bullets that reference data-body content change.

## Sub-buckets that have nothing to find in the data body

When the data body holds nothing that fits a particular sub-bucket (e.g., a SQL sub-bucket and a diff with no SQL), that sub-bucket stays as a proof-of-absence shape. Spell out three adversarial probes the agent runs to confirm zero relevant content. Use the sub-bucket bullets to name the things the agent searches for.

## What stays put

These elements pass through untouched:

- The mission's category name (e.g., "Category B only") — derived from the file name, not the artifact
- The per-category disposition statement
- The cross-bucket question structure (Q1, Q2, Q3 by name)
- The output spec's lead format (`Total: N (P0=N, P1=N, P2=N)`)
- The adversarial-pass count and severity tier — handled by [`adversarial-tuning.md`](adversarial-tuning.md) when the noun needs sharpening; the count and tier values come from the original prompt's own adversarial phrase, not a fixed default

## Disposition reporting

Every outcome emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines. When placeholders were filled: `> Gap: Placeholders instantiated — <N> placeholders replaced with real values.` When no placeholders exist: `> Gap: Instantiation verified — no placeholder tokens found.` When a placeholder could not be resolved: `> Gap: Placeholder "<token>" left in place — no real value found in available sources.` Silent pass is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
