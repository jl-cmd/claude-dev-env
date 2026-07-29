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

## Git Golden Rules (NON-NEGOTIABLE)

1. **DRAFT BEFORE PUSH**: When pushing ANYTHING to a PR, it MUST be in draft state first
   - Before push: `gh pr ready --undo`
   - After review approved: `gh pr ready`

2. **ONE COMMIT PER REVIEW STAGE**: Each review round gets exactly ONE commit
   - Initial feature: 1 commit
   - After review #1: 2 commits (initial + review #1 fixes)
   - After review #2: 3 commits (initial + review #1 fixes + review #2 fixes)
   - NEVER squash multiple review stages into one commit
   - NEVER have multiple commits for the same review stage

## Never Commit Working Documents or Images

**NEVER commit these files to the repo:**

| Pattern | Reason |
|---------|--------|
| `docs/plans/*.md` | Working documents for planning, not repo content |
| `*.plan.md` | Temporary planning files |
| `SESSION_STATE.md` | Local session state |
| `*.png *.jpg *.jpeg *.gif *.webp *.avif *.svg *.ico` | Images go to external storage, not GitHub |

An image a PR needs as visual evidence is not an exception to that row. Upload it to the repository's durable `artifacts` release with `python3 ~/.claude/scripts/gh_artifact_upload.py <file> <owner/repo>` and embed the permanent URL in the proof comment. The image lives on GitHub without entering the repository tree.

## Responding to review feedback

**When this applies:** GitHub PR review feedback on a branch you are fixing.

1. Fetch every reviewer comment before making any fix.
2. Create a TodoWrite checklist with one item per comment.
3. Fix systematically, marking each todo complete.
4. Reply to each comment inline.
5. Create one review-fix commit. Do not squash it with the original.

Repair only reported findings, then re-verify after every repair.

## See also

| Rule | Covers |
|---|---|
| [`gh-cli-conventions.md`](gh-cli-conventions.md) | `--body-file` for post bodies; `--paginate --slurp` for list reads |
| [`proof-of-work-pr-comments.md`](proof-of-work-pr-comments.md) | The five-part proof comment every PR carries before leaving draft |
| [`re-stage-before-commit.md`](re-stage-before-commit.md) | Staging session edits so a commit does not drop them |
| [`verified-commit-gate-skip.md`](verified-commit-gate-skip.md) | Optional code-verifier review guidance |
| [`durable-post-artifacts.md`](durable-post-artifacts.md) | Keeping volatile scratch paths out of a post body |
| [`destructive-commands.md`](destructive-commands.md) | Allowed removal forms; destructive literals in commit and post bodies |
| [`code-standards.md`](code-standards.md) | The code standards a PR's diff is reviewed against |
