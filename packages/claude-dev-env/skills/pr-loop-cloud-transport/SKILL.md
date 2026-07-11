---
name: pr-loop-cloud-transport
description: Runs any PR-loop skill in a Claude Code session whose gh CLI cannot act on the PR — the binary is absent, gh auth status fails, or the active login cannot act on the PR's owner. A six-step transport workflow loads the GitHub MCP schemas, fixes origin/HEAD before pushes, keys review rules to the live MCP identity, routes every GitHub operation through the gh-to-MCP substitution matrix, reads Copilot status from what lands on the PR, and self-checks the posts the gh-text hooks cannot gate. Use at run start when pr-converge, autoconverge, bugteam, qbug, findbugs, fixbugs, monitor-open-prs, or copilot-review runs in a cloud session, when `command -v gh` or `gh auth status` fails, or when an MCP tool call fails with InputValidationError.
---

# PR-loop cloud transport

One workflow that makes a cloud session able to run the PR-loop skill family. A cloud session ships no `gh` binary and cannot fetch one, so every `gh` step in a PR-loop skill routes through the GitHub MCP tools; this skill is the setup and routing contract for that substitution. The same routing serves a session whose `gh` is present but unauthenticated, or authenticated as an account that cannot act on the PR's owner — a binary that cannot act on the PR is as unusable as a binary that is not there. The evidence base is `docs/references/cloud-pr-loop-compatibility.md` in the source repo — every rule here traces to a live probe, the operation inventory recorded there, or the auth rule the calling skills state.

## Decide the transport first

Three checks, in order; the first failure routes to the cloud transport:

1. `command -v gh` — the binary exists.
2. `gh auth status` — an active authenticated account exists; a non-zero exit fails the check.
3. Once the PR scope is resolved (owner and repo known): `gh api repos/<owner>/<repo> --jq .permissions.push` must print `true`. The `permissions` object in that response reports the authenticated account's own rights on the repo, `push` included (live probe: the Section 7 appendix row in the runbook), so one command proves the binary, the auth, and the account's write access together. An error, a 404, or `false` fails the check.

- **All three pass** → local session. Stop here; follow the calling skill's own steps unchanged.
- **Any check fails** → cloud transport. Run the workflow below, then follow the calling skill's steps with every `gh` operation swapped for its cloud path.

A read-scoped account passes checks 1 and 2 and fails check 3 — the PR-loop skills push fix commits, so `push: false` means the local path stalls at its first push while the MCP transport carries the run.

## Cloud transport workflow

Copy this checklist and check off items as you complete them:

```
Cloud transport setup:
- [ ] Step 1: Load MCP schemas (once per session)
- [ ] Step 2: Fix origin/HEAD in every repo root
- [ ] Step 3: Read the MCP identity and key the review rules to it
- [ ] Step 4: Route every GitHub operation through the substitution matrix
- [ ] Step 5: Read Copilot status from what lands on the PR
- [ ] Step 6: Self-check the posts the quiet hooks would have gated
```

**Step 1: Load MCP schemas (once per session)**

MCP tool schemas are deferred: a call before its schema loads fails with `InputValidationError`. Run exactly:

```
ToolSearch "select:mcp__github__pull_request_read,mcp__github__pull_request_review_write,mcp__github__add_comment_to_pending_review,mcp__github__add_reply_to_pull_request_comment,mcp__github__add_issue_comment,mcp__github__request_copilot_review,mcp__github__update_pull_request,mcp__github__create_pull_request,mcp__github__issue_write,mcp__github__search_pull_requests,mcp__github__get_me,mcp__github__actions_list,mcp__github__actions_get,mcp__github__get_job_logs,mcp__Claude_Code_Remote__add_repo"
```

Every name carries its full `mcp__` prefix — a bare name matches nothing and loads no schema. The list mixes servers on purpose: the `mcp__github__*` tools plus `mcp__Claude_Code_Remote__add_repo` for cross-repo checkout.

Verify: call `mcp__github__get_me`. A returned login confirms the load; an `InputValidationError` means a schema is missing — re-run the load with the failing tool named, then verify again.

**Step 2: Fix origin/HEAD in every repo root**

Cloud clones do not set `origin/HEAD`, and the global pre-push hook resolves its base ref from it, so every `git push` fails with `fatal: Not a valid object name origin/HEAD` until the ref exists. For each repo root the run touches:

```
git -C <repo-root> remote set-head origin -a
```

Feedback loop: a push that fails with the `origin/HEAD` message means this step has not run in that repo — run it there and push again. Never route around the hook with `--no-verify`.

**Step 3: Read the MCP identity and key the review rules to it**

Call `mcp__github__get_me` and record the login. Key every identity rule to that live login, not to a fixed account name:

- On a PR the MCP login authored, post `COMMENT` reviews only — GitHub blocks `APPROVE` and `REQUEST_CHANGES` on one's own PR. On a PR another account authored, any review type works.
- Leave `BUGTEAM_REVIEWER_ACCOUNT` unset and skip every account-swap step; the swap path has no cloud form.
- A second identity rides raw REST: a body posted with `GH_TOKEN` lands as the `claude[bot]` GitHub App. Self-PR checks and bot filters account for the split.

Full identity rules, the REST fallback scope, and the two-identity model: see [reference/identity-and-hooks.md](reference/identity-and-hooks.md).

**Step 4: Route every GitHub operation through the substitution matrix**

Every `gh` operation in the calling skill has one cloud path. The full operation-by-operation table: see [reference/substitution-matrix.md](reference/substitution-matrix.md). The rules that carry the most weight:

- Read review threads with `mcp__github__pull_request_read(method="get_review_comments")` and resolve them with `mcp__github__pull_request_review_write(method="resolve_thread", threadId="PRRT_...")`. Custom GraphQL is pinned to a served set, so hand-written `gh api graphql` queries have no cloud path.
- Reply to an inline comment with `mcp__github__add_reply_to_pull_request_comment` using the numeric id from the comment's `discussion_r` anchor.
- Always pass `perPage` on `mcp__github__search_pull_requests` — an unpaginated owner-wide search overflows the tool-result limit.
- Helper scripts that spawn `gh` subprocesses fail in cloud; run their steps through the matrix and keep their decision rules.

**Step 5: Read Copilot status from what lands on the PR**

Skip the `gh api copilot_internal/user` quota read; treat Copilot quota as unknown. Call `mcp__github__request_copilot_review` — its silent completion confirms nothing either way. Status comes from the PR afterward:

- A Copilot review on the HEAD, clean or with findings, means Copilot is up.
- An out-of-usage notice on the HEAD, or no review within the caller's poll budget, means Copilot is down — bypass the gate and say plainly in the run report that the status is an environment limit.

**Step 6: Self-check the posts the quiet hooks would have gated**

The `gh`-text hooks read risk from literal `gh ...` command text, and an MCP post carries none, so those checks go quiet in cloud. Before each MCP post, check by hand:

- No volatile scratch path in a post body (job dirs, temp roots, worktrees).
- A proof-of-work comment carries all five parts the proof standard names.
- A PR title follows Conventional Commits.
- Markdown bodies go through the structured `body` parameter so backticks show as formatting.

The commit and push gates still fire on cloud Bash git commands — follow them normally. The full hook roster and which side of the split each hook sits on: see [reference/identity-and-hooks.md](reference/identity-and-hooks.md).

## Layout

| File | Role |
|---|---|
| `SKILL.md` | This workflow: the transport decision, the six setup and routing steps, and the progress checklist |
| `reference/substitution-matrix.md` | The gh-to-MCP operation substitution matrix, pagination rules, and the REST fallback scope |
| `reference/identity-and-hooks.md` | The two-identity model, self-PR review rules, and the hook-coverage split in cloud sessions |
