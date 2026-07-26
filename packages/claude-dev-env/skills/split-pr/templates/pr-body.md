# Draft PR body — illustration only

`execute_split.py` writes this body itself in `_create_draft_pr` and passes it to `gh pr create --body-file`. The f-string in that function is the source of truth. This page shows the shape for reading; hand-posting it is never part of the flow.

Placeholders: `<story>` is the slice story, `<source_pr>` the source PR number, `<base_branch>` the slice base.

```markdown
## Summary

<story>

## Split source

Excised from pull request #<source_pr> via `/split-pr`.

## Dependencies

Base branch: `<base_branch>`. Merge earlier slices first.

## Testing

File-partitioned from the parent pull request. Project-wide CI on this slice alone is not claimed by `/split-pr` unless verified separately.
```
