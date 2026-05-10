# Output contract

The skill emits exactly one artifact: the rewritten prompt. The emission shape depends on how the input arrived.

## Emission modes

**Paste mode** — input arrives as the user's message body or as a fenced block within it. Emit one fenced block containing the rewritten prompt. Choose a fence length that is strictly longer than the longest consecutive backtick run anywhere in the rewritten prompt (i.e., `max_backtick_run + 1`, with a minimum of four backticks). This ensures no inner fence in the rewritten prompt can prematurely close the outer fence — including cases where the input already used a 4+ backtick wrapper:

``````
`````
<rewritten prompt, which may itself contain 4-backtick fences>
`````
``````

**File-path mode** — input arrives as a file path argument (e.g., `/structure-prompt path/to/file.md`). File-path mode targets Markdown prompt artifacts; rewriting non-Markdown files is not supported. Rewrite the file in place. Emit a confirmation that names the file, gives the line-count delta, and lists the spokes that fired. When gaps exist, the confirmation also lists them — the output may span multiple lines.

## Disposition invariants

**No silent action** (also referenced as "no silent no-op"). Every spoke that fires MUST record its action. Two cases use the same `> Gap:` mechanism:

- **Deferred.** The spoke elected not to apply its transformation — missing source, ambiguous detection, fallback to user input, carve-out match, or any other reason. The gap note records what was deferred and why.
- **Applied.** The spoke successfully applied its transformation. The gap note records what changed (e.g., persona transformed, directive replaced, citation added) so the reader can detect the change.

Silent omission is never the correct disposition in either case. The reader of the output must always be able to detect which spokes fired, which deferred, and why.

## Preservation invariants

Two clauses govern what the rewritten prompt may change.

**Existing input content is preserved byte-for-byte.** The rewrite must not alter any of these values when they already appear in the input:

- Identifiers (variable names, function names, file paths)
- IDs and SHAs
- ID prefixes
- Proper names (people, products, services)
- Numeric values (line numbers, thresholds, counts)
- URLs
- Code block contents

**New numeric criteria are additive content.** When a spoke introduces a new measurable threshold (e.g., the `≥3` adversarial probes from [`per-category.md`](per-category.md), the citation-occurrence cutoffs from [`citation-depth.md`](citation-depth.md), or any new word/probe/count limit), that number is sourced per the authorized-additions list below. New numeric criteria augment the prompt; they never overwrite a numeric value the input already carries.

## Idempotency

Output stabilizes by the second invocation: the second and all subsequent invocations produce identical output (i.e., `f(f(x)) == f(f(f(x)))`). On the first invocation, content-mutating spokes (persona, cleanup, directives, constraints, adversarial-tuning, instantiation, citation-depth, canonical-case) apply their transformations and emit "applied" gap notes alongside situation-dependent spokes (structure, per-category) that re-fire because their input conditions still hold. On the second invocation, those mutating spokes no longer match their detection conditions (placeholders substituted, identifiers cited, markers present, noun sharpened, canonical sub-bucket marked), so their gap notes disappear and situation-dependent notes shift to "verified" wording. Combined with the gap-report block's deterministic replacement, the second invocation's output is stable: a third invocation produces identical output.

## Authorized additions

The skill adds content only when a spoke explicitly authorizes it. Evidence-required additions (cited values from the rubric, placeholder values from the input or user) must also pass [`research.md`](research.md) confirmation that the new content matches a real source (rubric, sibling artifact, user-pasted context, or AskUserQuestion answer). Skill-defined additions (the per-category disposition line, surface-formatting cleanup, the failure-mode noun from the adversarial-tuning built-in lookup table) are authorized by their spoke firing alone. The authorized additions are:

- The mission line, when [`persona.md`](persona.md) replaces a role assignment
- The per-category disposition line, when [`per-category.md`](per-category.md) detects an unenforced framework
- Measurable criteria, when [`directives.md`](directives.md) or [`constraints.md`](constraints.md) replaces a soft directive
- Real values in place of placeholders, when [`instantiation.md`](instantiation.md) fires
- `file:line` citations on identifier mentions, when [`citation-depth.md`](citation-depth.md) fires
- The ⭐ canonical-case marker on one sub-bucket, when [`canonical-case.md`](canonical-case.md) fires
- A category-specific failure-mode noun in the adversarial-pass phrase, when [`adversarial-tuning.md`](adversarial-tuning.md) fires
- Surface-formatting normalization (typo correction, single bullet style, language tags on fenced blocks, trimmed trailing whitespace, collapsed blank-line runs, sequential heading levels), when [`cleanup.md`](cleanup.md) fires
- `(citation unavailable: <reason>)` inline markers adjacent to unciteable identifiers, when [`citation-depth.md`](citation-depth.md) fires

Skill-defined additions (the per-category disposition line, surface-formatting cleanup, the failure-mode noun from [`adversarial-tuning.md`](adversarial-tuning.md)'s built-in lookup table) are authorized by their spoke firing alone — they do not need an external source. For evidence-required additions (cited values from the rubric, placeholder values from the input or user), [`research.md`](research.md) confirms the new content matches a real source. When evidence is missing for an evidence-required addition, the spoke leaves the prompt as-is and reports the gap. For a skill-defined addition, once the spoke's detection conditions are met the transformation fires and always emits an action note recording what changed — the spoke does not need external evidence beyond its own rubric, unlike evidence-required additions. (Skill-defined additions are still situation-dependent per the routing table; "fires" here means when the spoke is active, not on every invocation.) The "No silent action" invariant applies to both applied and deferred outcomes. The gap-report shape depends on emission mode:

- **Paste mode.** The fenced block contains exactly the rewritten prompt — no footer follows it. Record gaps inside the fenced block as a final blockquoted note prefixed `> Gap:` (one line per gap). The note sits below the rewritten prompt's last block and remains inside the fence. On a second invocation, prior-run `> Gap:` lines are deterministically replaced (not accumulated): the current run's gap notes overwrite any prior-run gap notes, ensuring idempotent output across invocations. The passthrough rule in [`block-classification.md`](block-classification.md) step 3 still treats the prior-run gap region as inert during block tagging, but the current run's gap line emission replaces rather than appends.
- **File-path mode.** The rewritten file on disk MUST be self-describing for gaps. Append a final HTML comment block at the bottom of the file. The block opens with `<!-- gap-report:` on its own line, contains one `> Gap:` line per gap, and closes with `-->` on its own line. The `<!-- gap-report:` block is deterministically replaced (never accumulated) to reflect the current run's gap state. When the current run has gaps, a new `<!-- gap-report:` block containing the gap lines overwrites any prior block. When the current run has no gaps, any prior block is replaced with `<!-- gap-report: none -->` — the file always carries a self-describing gap-report block so a reader can determine the latest run's gap state without external context. Example for a run with two gaps:

  ```
  <!-- gap-report:
  > Gap: Persona transformed — original "You are an expert code reviewer" replaced with mission "Find bugs in this code."
  > Gap: canonical-case marker skipped — framework has 5+ sub-buckets but rubric match, bullet density, and identifier density found no clear canonical case
  -->
  ```

  The post-edit confirmation message that names the file and the spokes that fired ALSO lists the same gaps, but the file itself is now self-describing — a reader of the file alone can detect which spokes deferred and why.
