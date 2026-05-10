# Worked examples

Each example shows an input prompt and the rewritten output, with a note on which spokes fire.

## Example 1: Code-audit prompt with full diff

**Input shape**
- Mission, metadata, large 4-file diff, sub-bucket framework (A1-A7), cross-bucket questions, output spec — in that order.

**Spokes that fire**
- [`structure.md`](structure.md): the diff sits between metadata and framework; relocate to the end.

**Rewritten ordering**
1. Mission
2. Metadata
3. Framework (A1-A7)
4. Cross-bucket questions
5. Output spec
6. Diff (all four files contiguous at the end)

## Example 2: Persona-led generic prompt

**Input**
> You are a senior security engineer. Be thorough and review this code carefully. Try to find SQL injection, XSS, and auth issues.
>
> ```python
> # ... code block ...
> ```

**Spokes that fire**
- [`persona.md`](persona.md): "You are a senior security engineer" → mission line.
- [`directives.md`](directives.md): "Be thorough" → surface enumeration; "carefully" → locator requirement.
- [`constraints.md`](constraints.md): "Try to find" → measurable criteria.
- [`structure.md`](structure.md): code block present → verifies ordering, emits gap note.

**Rewritten output**
> Audit this code for security issues.
> Inspect: SQL injection, XSS, auth issues.
> Cite file:line for every finding.
> ```python
> # ... code block ...
> ```
>
> The rewritten prompt carries these `> Gap:` lines recording every spoke that fired (per the [no silent action](output-contract.md#disposition-invariants) invariant):
> `> Gap: Persona transformed — original "You are a senior security engineer" replaced with mission "Audit this code for security issues."`
> `> Gap: Directive "Be thorough" replaced with surface enumeration "Inspect: SQL injection, XSS, auth issues."`
> `> Gap: Directive "carefully" replaced with locator requirement "Cite file:line for every finding."`
> `> Gap: Narrative directive "Try to find" merged with directives output — both derived the same measurable criteria "Inspect: SQL injection, XSS, auth issues."`
> `> Gap: Structural ordering verified — input already in canonical sequence.`

## Example 3: Multi-category framework without disposition

**Input shape**
- Framework names 5 categories. No per-category requirement on emission.

**Spokes that fire**
- [`per-category.md`](per-category.md): insert canonical disposition line under the category list header.

**Inserted line**
> Each category returns either at least one finding with a locator OR exactly one proof-of-absence with at least 3 adversarial probes specific to that category. A category returning neither is a protocol gap.

## Example 4: Already-optimized prompt

**Input**
- Mission first, framework before data body, persona absent, multi-category disposition present, no soft directives, code block tagged.

**Spokes that fire**
- [`structure.md`](structure.md): code block present → verifies ordering, emits `> Gap:` note recording the check.
- [`per-category.md`](per-category.md): multi-category framework present → confirms disposition line exists, emits `> Gap:` note.

**Rewritten output**
- Identical to input save for the appended gap notes from structure and per-category.
