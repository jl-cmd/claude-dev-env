## Summary

<story>

## Split source

Excised from PR #<source_pr> via `/split-pr`.

## Dependencies

Base branch: `<base_branch>`. Merge earlier slices in the chain first.

## Testing

Slice membership is file-partitioned from the source PR. Full project CI on this slice alone is **not** claimed by `/split-pr` unless a human or follow-up run verifies it.

## Proof note

This PR is one link in a stacked split. Review focus is this slice’s story only; merge earlier bases first.
