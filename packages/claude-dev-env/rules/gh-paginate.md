# gh API Pagination Rule

**Root cause:** The GitHub REST API returns 30 items per page by default. `gh api repos/<owner>/<repo>/pulls/<number>/reviews` and `gh api repos/<owner>/<repo>/pulls/<number>/comments` silently truncate at 30 results without warning. PRs that have accumulated more than 30 reviews or inline comments — common on long PR-loop cycles where bugbot, copilot, or the in-house bugteam each post repeatedly — return only the **oldest** 30, hiding the most recent reviews and findings entirely. A `sort_by(.submitted_at) | last` (or `| reverse`) on a truncated array picks the latest entry **within the first 30**, not the actual latest, which produces a stale-but-confident report that then drives wrong decisions (e.g., re-triggering bugbot when it has already posted a CLEAN review on a later page).

**Rule:** All `gh api` calls that read `pulls/<number>/reviews`, `pulls/<number>/comments`, `issues/<number>/comments`, or any other paginated GitHub list endpoint **must** request the full set of pages AND apply any cross-page jq operation through external `jq`, not through `gh`'s built-in `--jq`. Use `--paginate --slurp | jq` (preferred — see [Safe patterns](#safe-patterns)). Never call these endpoints with their default pagination, and never use `gh`'s `--jq` for cross-page operations like `sort_by | last` or `| reverse | .[0]`.

## Two defects, one rule

This rule guards against two distinct silent-truncation defects that compound:

1. **Default 30-item page.** Without `--paginate`, only the first page is fetched. On long PRs this hides the most recent reviews entirely.
2. **`--jq` runs per-page, not on the concatenated result.** Per [GitHub CLI #10459](https://github.com/cli/cli/issues/10459), `gh api --paginate --jq '<filter>'` applies `<filter>` to each page **separately** and emits one output per page. Cross-page operations like `sort_by(.submitted_at) | last` therefore operate within each page independently, not across the merged result set. On PRs with more than 100 reviews this still produces a wrong-but-confident "latest" review even when `--paginate` is set.

The safe patterns below fix both defects together: `--paginate --slurp` walks every page AND emits a single merged structure, and an **external** `jq` then runs cross-page operations on that merged structure.

## Affected endpoints

The rule applies to every paginated read from the GitHub REST API. Common offenders in this repo's PR-loop skills:

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

`gh --paginate --slurp` walks every page and emits a single merged JSON array of page-arrays (`[[page1_items...], [page2_items...], ...]`). Pipe to external `jq` to flatten and filter across the full result set:

```bash
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'
```

The `.[][]` flattens the array-of-pages into one stream of items before the cross-page operators (`sort_by`, `last`, `reverse`) run. Combine with `?per_page=100` so each page fetches 100 items instead of 30, reducing round-trips on long PRs without changing correctness.

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

This is the canonical pattern for the bugbot ↔ bugteam convergence loop: walk newest-first, stop at the first clean review.

## What NOT to do

```bash
# BAD — default 30-item page silently truncates on long PRs
gh api repos/<owner>/<repo>/pulls/<number>/reviews \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'

# BAD — `?per_page=100` alone caps at 100 items; PRs with 100+ reviews still truncate
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'

# BAD — --paginate fetches every page, but `--jq` runs PER-PAGE (gh CLI #10459).
# `sort_by(.submitted_at) | last` operates within each page independently and
# emits one "latest" per page, not the actual latest across the full result set.
gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate \
  --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'

# BAD — taking `| last` on an unpaginated read returns the latest of the first 30,
# not the actual latest. Same defect for `| reverse | .[0]`.
```

## Why both defects matter

`gh api`'s default page is the FIRST page of results, ordered oldest-to-newest by the GitHub API. When the result set exceeds 30 items, page 1 contains the OLDEST 30 — not the newest. A jq `| last` after `sort_by(.submitted_at)` picks the latest entry within those 30 oldest items, producing output that looks correct but reports a state from days or weeks ago.

`--paginate` alone does NOT fix this when paired with `--jq`: gh applies the jq filter to each page separately and emits one result per page. A consumer reading "the last line of output" still gets the latest within a single page, not the latest across all pages. The skill that consumes this output then makes decisions (re-trigger bugbot, mark a finding stale, report convergence) against an obsolete view of the PR.

`--paginate --slurp | jq` fixes both defects: every page is fetched, every page is merged into one structure before any jq operator runs, and cross-page operations see the full result set.

## Consumers

Skills and scripts in this repo that read paginated endpoints and must therefore use `--paginate --slurp` plus external `jq`:

- `pr-converge` — bugbot review walk (BUGBOT phase, Step 2.a) and inline-comments fetch (Step 2.b).
- `bugteam` — review threads, inline comments, audit-loop history.
- `qbug` — same as bugteam, scoped to a single subagent loop.
- `pr-review-responder` — review comments fetch (already enforced; this rule extends the same constraint to reviews and other endpoints).
- `monitor-many` — open-PR enumeration and per-PR review/comment scans.
- `babysit-pr` — review-comment polling.

Updating any of these to read paginated endpoints requires `--paginate --slurp` plus external `jq` (or a documented single-page bound on a small list).

## Enforcement

This rule is documentation-only at present. A future PreToolUse hook may pattern-match `Bash` invocations of `gh api repos/.../pulls/<n>/(reviews|comments)` without `--paginate --slurp` (or with `--paginate --jq` doing cross-page operations) and return a corrective message. Until that hook lands, treat this rule as binding by review and rely on it during skill authoring.

## Precedent

The `pr-review-responder` skill predated this rule and forbids default pagination on `pulls/<n>/comments` reads (`packages/claude-dev-env/skills/pr-review-responder/SKILL.md` Rule 1). This file generalizes that constraint to every paginated GitHub endpoint, adds the `--jq` per-page defect (gh CLI #10459) discovered while reviewing this rule, and centralizes the safe patterns so additional skills inherit the rule by reference instead of restating it.
