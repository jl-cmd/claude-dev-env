# gh-to-MCP operation substitution matrix

Route every `gh` operation a PR-loop skill names through its cloud path. Load the MCP schemas first (SKILL.md Step 1) — a call before its schema loads fails with `InputValidationError`. Every row traces to a live probe or the operation inventory recorded in `docs/references/cloud-pr-loop-compatibility.md` in the source repo.

## Contents

- The operation matrix
- Pagination rules
- The REST fallback and its scope

## The operation matrix

| Operation | Local mechanism | Cloud path |
|---|---|---|
| Read PR / mergeability / draft state | `gh pr view`, `gh api pulls/N` | `mcp__github__pull_request_read(method="get")` |
| PR diff / files / commits / checks | `gh pr diff`, `gh api ...` | `mcp__github__pull_request_read(method="get_diff"/"get_files"/"get_commits"/"get_check_runs")` |
| List reviews / review threads | `gh api --paginate --slurp \| jq` | `mcp__github__pull_request_read(method="get_reviews"/"get_review_comments")` |
| Post / update / close issue | `gh issue create/edit/close` | `mcp__github__issue_write(method="create"/"update")`; close an issue with `method="update", state="closed"` |
| Post issue or PR comment | `gh issue comment`, `gh pr comment` | `mcp__github__add_issue_comment` |
| Post review with inline comments | `gh api pulls/N/reviews` POST | `mcp__github__pull_request_review_write(method="create")` → `mcp__github__add_comment_to_pending_review` per finding → `mcp__github__pull_request_review_write(method="submit_pending", event="COMMENT")` |
| Reply to a review comment | `gh api pulls/N/comments/ID/replies` | `mcp__github__add_reply_to_pull_request_comment` (numeric `discussion_r` id) |
| Resolve / unresolve a thread | `gh api graphql resolveReviewThread` | `mcp__github__pull_request_review_write(method="resolve_thread"/"unresolve_thread", threadId="PRRT_...")` |
| Request the Copilot reviewer | `gh api POST pulls/N/requested_reviewers` | `mcp__github__request_copilot_review`. The call completes with no output and no in-band confirmation either way; confirm by a Copilot review landing on the PR. |
| Mark ready / send to draft | `gh pr ready`, `gh pr ready --undo` | `mcp__github__update_pull_request(draft=false / draft=true)`, with a read-back confirming the draft state each way |
| Create a PR | `gh pr create --draft` | `mcp__github__create_pull_request(draft=true)` |
| Edit a PR body or title | `gh pr edit` | `mcp__github__update_pull_request(body=..., title=...)` |
| Cross-repo PR search | `gh search prs --owner X --state open` | `mcp__github__search_pull_requests(query="user:X is:open", perPage=30)` |
| Check runs on a SHA | `gh api commits/SHA/check-runs` | `mcp__github__pull_request_read(method="get_check_runs")`, or REST for owners the app connection covers |
| CI logs | `gh run view --log` | `mcp__github__actions_list` / `mcp__github__actions_get` / `mcp__github__get_job_logs` |
| Clone another repo | `gh repo clone` | `git clone https://github.com/owner/repo` (session-scoped), or `mcp__Claude_Code_Remote__add_repo` first |
| Copilot quota | `gh api copilot_internal/user` | None. Treat quota as unknown; call `mcp__github__request_copilot_review`, then read `copilot_down` from what lands on the PR (SKILL.md Step 5). |
| Second reviewer identity | `gh auth switch`, `BUGTEAM_REVIEWER_ACCOUNT` | None. One MCP identity — the `mcp__github__get_me` login. `COMMENT` reviews on own PRs work; `APPROVE`/`REQUEST_CHANGES` on own PRs are blocked by GitHub. |

## Pagination rules

- `mcp__github__pull_request_read(method="get_reviews")` paginates with `page` + `perPage`.
- `mcp__github__pull_request_read(method="get_review_comments")` paginates with `perPage` + an `after` cursor.
- Always pass `perPage` on `mcp__github__search_pull_requests`: an unpaginated owner-wide search overflows the tool-result limit.

## The REST fallback and its scope

Raw REST through the agent proxy works only for owners the Claude GitHub App connection covers; a repo outside that coverage answers 403. The client shape:

```
curl -H "Authorization: Bearer $GH_TOKEN" --cacert /root/.ccr/ca-bundle.crt https://api.github.com/repos/<owner>/<repo>/...
```

GraphQL through the proxy is pinned to a served set of PR-review operations, so a hand-written `gh api graphql` query has no cloud path — read review threads through `mcp__github__pull_request_read(method="get_review_comments")` and resolve them through `mcp__github__pull_request_review_write(method="resolve_thread", ...)`.
