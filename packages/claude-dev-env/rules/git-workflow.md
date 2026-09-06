# Git workflow

User-level rule: applies to **every** git repo that uses GitHub with `gh`. Small or non-primary repos follow the same rule unless the user says otherwise in the session.

## Workflow decision tree

**When to use stacked PRs:** Feature B depends on Feature A's implementation

**When to extract shared infrastructure first:** Multiple features need same utilities/helpers

**Extract Shared Infrastructure Pattern:**
1. Create infrastructure PR with only shared code
2. Get reviewed and MERGE infrastructure first
3. Launch parallel feature PRs that use merged infrastructure

## Pull request submission rules

**ALWAYS create PRs as DRAFT:** Use `gh pr create --draft` for ALL PRs

**A release bot's PR body is machine input. Leave it alone.** Release automation reads
back the body of its own merged pull request to decide it owns that merge. Rewriting the
body, or trimming its header or footer, makes the bot treat the merge as somebody else's
work: it cuts no tag, the publish job skips, and it opens one more release pull request on
the next run. Every release lands in the repository and reaches no user.

Spot one by its head branch, which starts `release-please--branches--`, or by a body that
opens with the bot's own marker line. The description rules in this file, the
`pr-description-writer` agent, and the house wording style all step aside for it. The
failure signature in the release job log reads
`could not parse pull request body as a release PR`.

Use the `pr-description-writer` agent before creating a pull request or
rewriting its full description. Publish its title and body file through
`.agents/skills/pull-request/scripts/pull_request.py`.

Resolve the active managed root (`CLAUDE_CONFIG_DIR` when set, `~/.claude`
otherwise), then run `<managed-root>/scripts/durable_post_lint.py` before any
pull request, issue, or GitHub MCP post. The linter checks the action-specific
title, body, and volatile-path rules before credential lookup or network
access.

Use `.agents/skills/pull-request/scripts/recover_legacy_author.py
<exact-state-file> --confirm-inactive` only for one explicitly selected legacy
author record. Do not infer a record from age alone. Keep every other record
untouched.

## Git golden rules

1. **DRAFT BEFORE PUSH**: When pushing ANYTHING to a PR, it MUST be in draft state first
   - Before push: `gh pr ready --undo`
   - After review approved: `gh pr ready`

## Never commit working documents or images

**NEVER commit these files to the repo:**

| Pattern | Reason |
|---------|--------|
| `docs/plans/*.md` | Working documents for planning, not repo content |
| `*.plan.md` | Temporary planning files |
| `SESSION_STATE.md` | Local session state |
| `*.png *.jpg *.jpeg *.gif *.webp *.avif *.svg *.ico` | Images go to external storage, not GitHub |

An image a PR needs as visual evidence is not an exception to that row. Upload it to the repository's durable `artifacts` release with `python3 ~/.claude/scripts/gh_artifact_upload.py <file> <owner/repo>` and embed the permanent URL in the PR comment. The image lives on GitHub without entering the repository tree.

## Responding to review feedback

**When this applies:** GitHub PR review feedback on a branch you are fixing.

1. Fetch every reviewer comment before making any fix.
2. Create a TodoWrite checklist with one item per comment.
3. Fix systematically, marking each todo complete.
4. Reply to each comment inline.

Repair only reported findings, then re-verify after every repair.

Every `gh` post in this workflow uses `--body-file` per `gh-cli-conventions.md` and keeps volatile scratch paths out per `durable-post-artifacts.md`. Stage session edits per `re-stage-before-commit.md` before each commit.
