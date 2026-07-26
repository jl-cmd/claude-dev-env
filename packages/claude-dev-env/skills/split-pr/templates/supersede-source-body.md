# Supersede comment — illustration only

`supersede_source_pr.py` builds this comment in `build_supersede_comment_body` from the `SUPERSEDE_HEADING`, `SUPERSEDE_INTRO`, `SUPERSEDE_MERGE_ORDER_LABEL`, and `SUPERSEDE_LIST_ITEM_TEMPLATE` constants in `scripts/split_pr_scripts_constants/config/execute_constants.py`, then posts it with `gh pr comment --body-file`. Those constants are the source of truth. This page shows the shape for reading.

**Post it by hand and the idempotency check breaks.** `_is_already_superseded` scans the source PR's comments for the exact `SUPERSEDE_HEADING` text, so wording that drifts from the shipped constants earns a duplicate comment or a skipped close.

Placeholders: `<n1>`, `<n2>` are child PR numbers in merge order.

```markdown
## Superseded by stacked split

This PR was file-split into a stacked draft chain. Review and merge the stack in order; this source PR is superseded by the slices listed below.

**Merge order:** #<n1> → #<n2>

1. #<n1> — https://github.com/<owner>/<repo>/pull/<n1>
2. #<n2> — https://github.com/<owner>/<repo>/pull/<n2>
```
