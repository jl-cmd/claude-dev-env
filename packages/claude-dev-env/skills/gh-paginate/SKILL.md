---
name: gh-paginate
description: Safe pagination for gh api reads of paginated GitHub list endpoints (PR reviews/comments/files, issue comments, pulls, issues) — --paginate --slurp piped to external jq, single-page bounds, newest-first walks. Use before composing any gh api list-endpoint call or any cross-page jq operation (sort_by | last, reverse).
---

# gh API Pagination Rule

**Root cause:** GitHub REST API list endpoints paginate by default. Without `--paginate --slurp`, callers see only the oldest page, and cross-page jq operations (e.g., `sort_by | last`) operate within a single page — producing wrong-but-confident results.

**Rule:** All `gh api` calls that read `pulls/<number>/reviews`, `pulls/<number>/comments`, `issues/<number>/comments`, or any other paginated GitHub list endpoint **must** request the full set of pages AND apply any cross-page jq operation through external `jq`, not through `gh`'s built-in `--jq`. Use `--paginate --slurp | jq` (preferred — see [Safe patterns](#safe-patterns)). Never call these endpoints with their default pagination, and never use `gh`'s `--jq` for cross-page operations like `sort_by | last` or `| reverse | .[0]`.

## Two defects, one rule

This rule guards against two distinct silent-truncation defects that compound:

1. **Default page truncation.** Without `--paginate`, only the first page is fetched.
2. **`--jq` runs per-page, not on the concatenated result.** Per [GitHub CLI #10459](https://github.com/cli/cli/issues/10459), `gh api --paginate --jq '<filter>'` applies `<filter>` to each page **separately** and emits one output per page. Cross-page operations like `sort_by(.submitted_at) | last` therefore operate within each page independently, not across the merged result set.

The safe patterns below fix both defects together: `--paginate --slurp` walks every page AND emits a single merged structure, and an **external** `jq` then runs cross-page operations on that merged structure.

## Affected endpoints

The rule applies to every paginated read from the GitHub REST API. Common offenders in PR-loop skills:

- `gh api repos/<owner>/<repo>/pulls/<number>/reviews`
- `gh api repos/<owner>/<repo>/pulls/<number>/comments`
- `gh api repos/<owner>/<repo>/pulls/<number>/files`
- `gh api repos/<owner>/<repo>/issues/<number>/comments`
- `gh api repos/<owner>/<repo>/pulls`
- `gh api repos/<owner>/<repo>/issues`

The same rule applies to any other endpoint documented as paginated by GitHub (see [GitHub REST API pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)).

Single-object endpoints (e.g., `repos/<owner>/<repo>/pulls/<number>` returning one PR object) are not paginated — `?per_page=...` is silently ignored, and neither `--paginate` nor external `jq` is required. Use `gh`'s `--jq` directly on those endpoints.

## Safe patterns

### Preferred — `--paginate --slurp` piped to external `jq`

`gh api ... --paginate --slurp` walks every page and emits a single merged JSON array of page-arrays (`[[page1_items...], [page2_items...], ...]`). Pipe to external `jq` to flatten and filter across the full result set:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'
```

The `.[][]` flattens the array-of-pages into one stream of items before the cross-page operators (`sort_by`, `last`, `reverse`) run. Combine with `?per_page=100` to reduce round-trips on long PRs.

`gh`'s `--jq` flag and `--slurp` flag are mutually exclusive (gh CLI rejects `--paginate --slurp --jq` with `the --slurp option is not supported with --jq or --template`), which is why the filter must run in an external `jq` invocation.

### Acceptable — single-page bound on a paginated list endpoint when result fits

When you have an explicit reason to read at most one page from a **paginated** list endpoint (e.g., a known-small list), document the bound in a comment and use `?per_page=100` without `--paginate`. Cross-page operators are not in play here, so `gh`'s `--jq` is safe:

```bash
# Bound: a freshly created issue is expected to have <= 100 comments.
gh api 'repos/<owner>/<repo>/issues/<number>/comments?per_page=100' \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | length'
```

This pattern is only safe when the endpoint is confirmed to return a list smaller than 100 entries. Lists that grow over the PR's lifetime (reviews, comments) must use `--paginate --slurp` plus external `jq`.

### Single-object endpoints — no pagination needed

Endpoints that return a single object (e.g., `pulls/<number>`, `issues/<number>`) are not paginated. `?per_page=...`, `--paginate`, and `--slurp` are all unnecessary. Use `gh`'s built-in `--jq` directly:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>' --jq '.head.sha'
```

### Newest-first walk

Pair pagination with explicit reverse-sort so the consumer reads newest-first regardless of the API's internal order:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | reverse'
```

This is the canonical pattern for the bugbot <-> bugteam convergence loop: walk newest-first, stop at the first clean review.

## Enforcement

This rule is documentation-only at present. A future PreToolUse hook may pattern-match `Bash` invocations of `gh api repos/.../pulls/<n>/(reviews|comments)` without `--paginate --slurp` (or with `--paginate --jq` doing cross-page operations) and return a corrective message. Until that hook lands, treat this rule as binding by review and rely on it during skill authoring.
