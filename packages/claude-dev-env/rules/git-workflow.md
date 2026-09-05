# Git Workflow

User-level rule: applies to **every** git repo that uses GitHub with `gh` (no exceptions for “small” or non-primary repos unless the user says otherwise in the session).

## Workflow Decision Tree

**When to use stacked PRs:** Feature B depends on Feature A's implementation

**When to extract shared infrastructure first:** Multiple features need same utilities/helpers

**Extract Shared Infrastructure Pattern:**
1. Create infrastructure PR with only shared code
2. Get reviewed and MERGE infrastructure first
3. Launch parallel feature PRs that use merged infrastructure

## PR Submission Rules

**ALWAYS create PRs as DRAFT:** Use `gh pr create --draft` for ALL PRs

Use the `pr-description-writer` agent before creating a pull request or
rewriting its full description. Publish its title and body file through
`.agents/skills/pull-request/scripts/pull_request.py`. The
`pr-title-description` skill may review the writer's output but cannot replace
the required writer.

Run `_shared/pr-loop/scripts/durable_post_lint.py` before any pull request,
issue, or GitHub MCP post. The linter checks the action-specific title, body,
and volatile-path rules before credential lookup or network access.

Use `.agents/skills/pull-request/scripts/recover_legacy_author.py
<exact-state-file> --confirm-inactive` only for one explicitly selected legacy
author record. Do not infer a record from age alone. Keep every other record
untouched.

## Git Golden Rules (NON-NEGOTIABLE)

1. **DRAFT BEFORE PUSH**: When pushing ANYTHING to a PR, it MUST be in draft state first
   - Before push: `gh pr ready --undo`
   - After review approved: `gh pr ready`

## Never Commit Working Documents or Images

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

Every `gh` post in this workflow uses `--body-file` per `gh-cli-conventions.md` and keeps volatile scratch paths out per `durable-post-artifacts.md`; stage session edits per `re-stage-before-commit.md` before each commit.
