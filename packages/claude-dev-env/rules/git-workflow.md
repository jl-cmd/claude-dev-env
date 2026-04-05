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
