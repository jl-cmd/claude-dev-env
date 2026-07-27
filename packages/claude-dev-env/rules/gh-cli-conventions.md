# gh CLI Conventions

Two call shapes the `gh` CLI gets wrong by default.

## Body content goes in a file

Every `gh` command carrying markdown body content (`gh pr create/edit/comment/review`, `gh issue create/edit/comment`) uses `--body-file <path>` with a temp file — never a `--body` / `-b` string, where backticks land on GitHub as a literal `` \` ``. Write the temp file BOM-free:

```powershell
[IO.File]::WriteAllText($bodyPath, $body, [Text.UTF8Encoding]::new($false))
```

MCP GitHub tools take `body` as a structured parameter and are unaffected.

`gh_body_arg_blocker.py` (PreToolUse on Bash, hosted by `bash_pre_tool_use_dispatcher`) blocks `--body <arg>` and returns the corrective message.

## Paginated reads slurp before they filter

Every `gh api` read of a paginated GitHub list endpoint (PR `reviews` / `comments` / `files`, issue `comments`, `pulls`, `issues`) uses `--paginate --slurp` piped to **external** `jq`. The built-in `--jq` runs per page, so a cross-page operation like `sort_by | last` gives a wrong-but-confident result.

Single-object endpoints (`pulls/<n>`, `issues/<n>`) skip pagination and may use `--jq` directly. For a newest-first walk, sort the slurped array and take the last element; for single-page bounds, cap with a `per_page` query parameter.

## Sibling rules

- [`destructive-commands.md`](destructive-commands.md) — why a body describing `rm -rf` must travel by file path.
- [`durable-post-artifacts.md`](durable-post-artifacts.md) — what a post body may reference.
- [`proof-of-work-pr-comments.md`](proof-of-work-pr-comments.md) — what the proof comment must contain.
