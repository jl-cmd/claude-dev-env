# Splitting principles — vertical slices

A split plan groups changed paths into **semantic vertical slices**, not layer
silos. Each slice tells one reviewable story and keeps related tests beside the
behavior they cover.

## Invariants

1. **Test co-location.** A behavior change and its related tests share one
   slice. Tests do not land in a later dedicated-test slice by default.
2. **One story per slice.** Each slice has a single review focus (one vertical
   ability or one coherent subsystem story).
3. **Unique path ownership.** Every changed path appears in exactly one slice.
4. **Green intermediate.** Each stacked intermediate must collect and run the
   tests that belong to that slice and its bases.
5. **Preparatory refactors first.** Large refactors that do not change
   product behavior occupy earlier preparatory slices, not mixed with behavior.
6. **Dependency bases encode merge order.** Slice N+1 bases on slice N when it
   depends on N's definitions.

## Fable gates

Standing Fable approval is required for:

- a semantic re-bucket that moves paths across slices after the first plan
- an oversized atomic exception that keeps an unsplittable surface as one PR
