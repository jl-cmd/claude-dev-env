# gh API Pagination

Every `gh api` read of a paginated GitHub list endpoint (PR `reviews`/`comments`/`files`, issue `comments`, `pulls`, `issues`) uses `--paginate --slurp` piped to **external** `jq` — `gh`'s built-in `--jq` runs per page, so cross-page operations like `sort_by | last` give wrong-but-confident results. Single-object endpoints (`pulls/<n>`, `issues/<n>`) skip pagination and may use `--jq` directly. For a newest-first walk, sort the slurped array and take the last element; for single-page bounds, cap with a `per_page` query parameter.
