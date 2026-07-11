# Per-category disposition

Every multi-category framework requires each category to emit exactly one disposition:
- At least one positive finding with a locator (file:line, section ID, line number, or equivalent) per category
- Exactly one explicit proof-of-absence with at least 3 adversarial probes specific to that category

## Detection

The framework names 2+ categories, surfaces, sub-buckets, items, checks, or criteria the agent processes.

## Insertion

Insert this exact line directly under the category list header, substituting `<category-noun>` with whatever the prompt calls them (sub-bucket, surface, item, category, check, criterion):

> Each `<category-noun>` returns either at least one finding with a locator OR exactly one proof-of-absence with at least 3 adversarial probes specific to that `<category-noun>`. A `<category-noun>` returning neither is a protocol gap.

## Idempotency

When the framework already states an equivalent requirement (positive finding OR proof-of-absence with ≥3 probes), leave it intact. Insert only when the requirement is absent or weaker than the canonical form.

## Disposition reporting

Every outcome emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines. When the disposition line was inserted: `> Gap: Per-category disposition line inserted under category list header.` When the framework already carries the canonical form: `> Gap: Per-category disposition verified — canonical form already present.` Silent omission is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
