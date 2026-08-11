# Operation matrix

Each issue op maps to a GitHub MCP tool and a `gh` fallback that reaches the same REST endpoint. Prefer the MCP tool; fall back to `gh` when the MCP server is unreachable. The REST endpoint column names the authoritative contract both surfaces call, so a session with neither surface can still drive the raw API.

The MCP tool names below match the connected GitHub MCP server's issue toolset. When a server exposes a tool under a different name, pick the tool by what the row describes, and the REST endpoint tells you what it must call.

| Operation | GitHub MCP tool | REST endpoint | `gh` fallback |
|-----------|-----------------|---------------|---------------|
| Search open + closed | `mcp__github__search_issues` | `GET /search/issues?q=<terms>+repo:{owner}/{repo}` | `gh issue list --search "<terms>" --state all` |
| Create epic / sub-issue | `mcp__github__issue_write` (create) | `POST /repos/{owner}/{repo}/issues` | `gh issue create --title "<t>" --body-file <path> --label <label>` |
| Read issue body | `mcp__github__issue_read` | `GET /repos/{owner}/{repo}/issues/{number}` | `gh issue view <number> --json body` |
| Update body / labels | `mcp__github__issue_write` (update) | `PATCH /repos/{owner}/{repo}/issues/{number}` | `gh issue edit <number> --body-file <path> --add-label <label>` |
| Attach native sub-issue | `mcp__github__sub_issue_write` | `POST /repos/{owner}/{repo}/issues/{number}/sub_issues` | `gh api repos/{owner}/{repo}/issues/{number}/sub_issues -F sub_issue_id=<int>` |
| Add cross-reference comment | `mcp__github__add_issue_comment` | `POST /repos/{owner}/{repo}/issues/{number}/comments` | `gh issue comment <number> --body-file <path>` |
| Create label | `mcp__github__` label-create tool | `POST /repos/{owner}/{repo}/labels` | `gh label create <name> --color <hex> --description "<text>"` |

## The sub-issue `.id` rule (read this before every attach)

The sub-issues endpoint identifies the child by its REST **database `.id`** — a large integer such as `2138472019` — not by its display number (`#42`). The two are different values. Passing the display number attaches nothing.

Read the child's `.id` from the create op's response, or fetch it:

```
gh api repos/{owner}/{repo}/issues/{number} --jq .id
```

`gh issue view <number> --json id` returns the GraphQL node id, a base64 string — the wrong value for this endpoint. Use `gh api ... --jq .id` for the REST database id.

The gh attach uses `-F` (typed field), which sends the id as a JSON integer. `-f` sends a string, and the endpoint rejects a string sub-issue id.

```
gh api repos/{owner}/{repo}/issues/{parent}/sub_issues -F sub_issue_id=2138472019
```

## Body content through `--body-file`

Every `gh issue create`, `gh issue edit`, and `gh issue comment` passes body content with `--body-file <path>`, never `--body "<text>"`. A `--body` string mangles backticks on GitHub — they land as literal `\``. Write the body to a temp file and point `--body-file` at it.

## Paginated reads

`gh issue list` needs no pagination flags. For a `gh api` read of a paginated list endpoint (an issue's comments, a repository's issues), pass `--paginate --slurp` and pipe to external `jq` — `gh`'s built-in `--jq` runs per page and gives wrong cross-page results.
