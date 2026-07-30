# Split-further loop

After the first vertical plan lands as draft slices, re-check each leaf PR:

1. Run the hand-written line analyzer (`scripts/analyze_pr.py`).
2. When it reports `requires_split_analysis`, record a split-analysis artifact.
3. When it reports `default_split` and no atomic exception applies, propose a
   further vertical split (tests still co-located with behavior).
4. Stop when every leaf fits review or carries a Fable-approved atomic
   exception.
