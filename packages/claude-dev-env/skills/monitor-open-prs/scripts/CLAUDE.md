# monitor-open-prs/scripts

Discovery helper for the `monitor-open-prs` skill.

## Key files

| File | Purpose |
|---|---|
| `discover_open_prs.py` | Queries `gh search prs` for each owner scope and flattens results to a uniform list of dicts |
| `test_discover_open_prs.py` | Tests for the discovery helper |

## Conventions

- `discover_open_prs(all_owners: list[str]) -> list[dict]` is the single entry point. It shells out to `gh search prs --owner <owner> --state open --json number,repository,url,headRefName,baseRefName` once per owner and merges the results.
- Each returned dict has keys: `number`, `owner`, `repo`, `head_ref`, `base_ref`, `url`.
- An empty scope or an empty sweep returns an empty list and exits cleanly with no errors.
- The module is stateless and has no filesystem side effects.
