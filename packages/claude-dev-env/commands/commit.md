---
description: Commit and push changes to GitHub (use instead of git commit)
allowed-tools: Bash, Read, Glob, Grep
---

## Step 1: Analyze Changes

Run these in parallel:
- `git status` (never use -uall flag)
- `git diff` and `git diff --staged` to see all changes
- `git log --oneline -5` to match the repo's commit message style

If there are no changes to commit, tell the user and stop.

## Step 2: Commit

- Stage relevant files by name (not `git add -A` or `git add .`)
- Do NOT stage files that look like secrets (.env, credentials, etc.)
- Create a single commit with a conventional commit message (feat:, fix:, chore:, etc.)
- Focus the message on "why" not "what"
- End the commit message with: `Co-Authored-By: Claude <noreply@anthropic.com>`
- Use a HEREDOC for the commit message

## Step 3: Push to GitHub

- Run `git push` to push the commit to the remote
- If the branch has no upstream, use `git push -u origin <branch-name>`
- Report the result to the user (success or any errors)