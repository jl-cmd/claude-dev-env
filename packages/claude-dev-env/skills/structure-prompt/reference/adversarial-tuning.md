# Sharpen the adversarial-pass phrasing

The output spec usually closes with an adversarial second-pass instruction like *assume your first pass missed at least 3 P1 bugs across these N sub-buckets — find them*. When that phrase uses a generic noun (`bugs`, `findings`, `issues`, `problems`), the skill replaces the noun with one that names the category's specific failure mode.

## Detection

The fix fires when the output spec contains a phrase matching this shape, with a generic noun:

- "missed at least `<number>` [bugs / findings / issues / problems]" — optionally preceded by a severity tier (`P0` or `P1`) when the framework uses tiered findings.

A noun is "generic" when it could apply to any audit category. A noun is "specific" when it names the failure mode of the category.

## How to derive the specific noun

Read the mission line and the framework header. Pull the category's domain from there. Match against this lookup:

| Category domain | Specific failure-mode noun |
|---|---|
| API contracts (signatures, return types, callback shape) | contract drifts |
| Selector / query / engine compatibility | engine-version incompatibilities |
| Resource cleanup (handles, locks, subscriptions) | leaked resources |
| Scoping and ordering | scope or ordering bugs |
| Dead code | dead code paths |
| Silent failures (swallowed exceptions, dropped errors) | silent failures |
| Bounds and overflow | bounds or overflow bugs |
| Security boundaries | trust-boundary violations |
| Concurrency | concurrency hazards |
| Code rules compliance | rule violations |
| Codebase conflicts (incomplete propagation) | parallel sites that should have been updated alongside the diff |

When the category sits outside this list, derive the noun from the framework's most prominent axis name (e.g., a framework whose axes all name "selectors" → "selector incompatibilities").

## Procedure

1. Find the adversarial-pass sentence in the output spec.
2. Identify the generic noun in that sentence.
3. Replace it with the specific noun from the table or framework.
4. Keep the rest of the sentence intact: count (e.g., "3"), severity tier (e.g., "P1") when the original phrase carries one, and the closing "find them".

## Examples

Before (generic):
> "assume your first pass missed at least 3 P1 bugs across these 7 sub-buckets — find them"

After (Category B):
> "assume your first pass missed at least 3 P1 engine-version incompatibilities across these 7 sub-buckets — find them"

After (Category K):
> "assume your first pass missed at least 3 P1 parallel sites that should have been updated alongside the diff across these 7 sub-buckets — find them"

After (Category C):
> "assume your first pass missed at least 3 P1 leaked resources across these 7 sub-buckets — find them"

## What stays put

When the adversarial phrase already names a specific failure mode, the noun stays. The skill changes only generic nouns.

The count (e.g., 3) and severity tier (e.g., P1) stay intact when the original phrase carries them. Some categories name a noun that doesn't fit the P-tier model — Codebase Conflicts ("parallel sites that should have been updated alongside the diff") is the canonical example — but preservation still applies: if the original phrase includes a tier, the rewritten phrase includes it too. The rule is preservation, not insertion or removal.

## Disposition reporting

Every outcome emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines. When the noun was replaced: `> Gap: Adversarial-pass noun sharpened — "bugs" → "<specific noun>".` When the phrase already carries a specific noun: `> Gap: Adversarial-pass noun verified — "<specific noun>" already specific.` Silent pass is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
