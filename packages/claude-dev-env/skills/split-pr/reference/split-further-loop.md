# Split-further loop

After the first vertical plan lands as draft slices, re-check each leaf PR:

1. Run the hand-written line analyzer (`scripts/analyze_pr.py`).
2. If hand-written lines ≥ 200, record a split-analysis artifact.
3. If hand-written lines ≥ 600 and no atomic exception, propose a further
   vertical split (tests still co-located with behavior).
4. Stop when every leaf fits review or carries a Fable-approved atomic
   exception.
