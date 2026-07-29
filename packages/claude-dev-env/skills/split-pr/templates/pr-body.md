## Summary

<story>

## Split source

Excised from PR #<source_pr> via `/split-pr`.

## Dependencies

Base branch: `<base_branch>`. Merge earlier slices in the chain first.

## Testing

Slice membership is file-partitioned from the source PR. After each slice commit, `/split-pr` runs `pytest --collect-only` on cumulative stack test modules so a definition on the wrong side of the cut fails execute before push. Full project test execution on this slice alone is **not** claimed unless a human or follow-up run verifies it.

## Proof note

This PR is one link in a stacked split. Review focus is this slice’s story only; merge earlier bases first.
