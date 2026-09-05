# gh CLI conventions

Two `gh` call shapes need explicit handling.

## Put body content in a file

Every `gh` command that carries markdown body content uses
`--body-file <path>`. This applies to `gh pr create`, `gh pr edit`,
`gh pr comment`, `gh pr review`, `gh issue create`, `gh issue edit`, and
`gh issue comment`. Never pass a `--body` or `-b` string. Write the file as
BOM-free UTF-8:

```powershell
[IO.File]::WriteAllText($bodyPath, $body, [Text.UTF8Encoding]::new($false))
```

MCP GitHub tools take `body` as a structured parameter. Write the same body to
a UTF-8 file and run the shared linter before sending that parameter.

For pull requests, use
`.agents/skills/pull-request/scripts/pull_request.py`. It passes
`--body-file` to `gh` after the action-aware linter succeeds. For issues and
GitHub MCP posts, run the linter directly with `issue-create`, `issue-edit`,
`issue-comment`, or `github-mcp-post` as the action.

## Paginated reads slurp before they filter

Every `gh api` read of a paginated GitHub list endpoint uses
`--paginate --slurp` and pipes the result to external `jq`. This applies to PR
reviews, comments, and files, plus issue comments, pulls, and issues. The
built-in `--jq` runs once per page and can produce a wrong cross-page result.

Single-object endpoints such as `pulls/<n>` and `issues/<n>` do not need
pagination and may use `--jq` directly. For a newest-first walk, sort the
slurped array and take the last element. For one page, cap the request with a
`per_page` query parameter.
