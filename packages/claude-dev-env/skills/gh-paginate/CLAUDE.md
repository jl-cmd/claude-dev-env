# gh-paginate skill

Provides the safe-pagination rule and patterns for `gh api` calls against paginated GitHub list endpoints (PR reviews, PR comments, issue comments, pulls, issues). The rule prevents two silent-truncation defects: default page truncation and per-page `--jq` evaluation.

**Trigger:** Loaded by the `gh-paginate` skill name or when any skill or rule references the pagination rule.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete rule: affected endpoints, safe `--paginate --slurp \| jq` pattern, single-page bound pattern, single-object pattern, newest-first walk pattern, and enforcement notes |

## Conventions

- The preferred pattern pipes `--paginate --slurp` to an **external** `jq` invocation so cross-page operations (`sort_by`, `last`, `reverse`) run on the merged array-of-pages. The built-in `--jq` flag is incompatible with `--slurp` and runs per-page, producing wrong cross-page results.
- Single-object endpoints (e.g., `pulls/<number>`) are not paginated; `--paginate` is unnecessary and `gh --jq` is safe.
- The single-page bound pattern (`?per_page=100` without `--paginate`) is acceptable only when the list is confirmed to stay under 100 entries.
- This skill ships as documentation only; enforcement via a future PreToolUse hook is noted in `SKILL.md`.
