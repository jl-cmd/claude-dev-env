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
the next run. The merge stays in the repository. No tag is cut and the package never publishes.

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

## Run the required checks locally before the first push

Read the branch ruleset for the required check contexts before you push a branch,
or any level of a stack: `gh api repos/<owner>/<repo>/rules/branches/<trunk>`.
Then run that exact gate command locally against that level's own base, on every
level. A required check that never fired is invisible debt at every level, and it
surfaces only after the whole stack is pushed, when the repair costs a second pass
over every branch.

A checks listing that reports nothing on the branch is a finding, not a neutral
state. Find out whether the workflow's event filters exclude the branch, or whether
the check simply never ran, before you treat that branch as clean.

## Each stack level stands on its own

A symbol belongs at the level that first **uses** it, not the level that first
mentions it. A bottom pull request that declares the imports its descendants will
need fails the linter on unused imports. A test helper that calls a function three
levels above it fails on an undefined name. Both defects stay invisible while you
read the finished tip, and both are obvious the moment you check one level alone.

Prove each level before you push it: import the modules that level changes, and run
the required linter against that level's own base. To repair a level, rebuild its
import header as the union of what that level actually references, let the linter's
autofix strip the rest, and move a premature helper up to the level that defines
what it calls.

## A force-push that moves content obliges a description refresh

Force-with-lease protects the ref. It protects nobody's understanding of what the
branch now holds. When a rewrite moves content between levels of a stack, or
otherwise changes what a branch contains, refresh that pull request's description
through the `pr-description-writer` agent before you ask anyone to read or merge it.

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
