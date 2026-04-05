---
description: Fetch and display all comments from a GitHub PR (fetches comments from the current repo)
---

You are an AI assistant integrated into a git-based version control system. Your task is to fetch and display comments from a GitHub pull request.

**CRITICAL: Detect the repository from the current git remote (upstream preferred, then origin).**

Follow these steps:

1. Detect `{owner}/{repo}` from `gh repo view --json nameWithOwner -q .nameWithOwner`
2. Extract PR number from the argument (e.g., "PR44" → 44, "44" → 44)
3. Use `gh api repos/{owner}/{repo}/issues/{number}/comments` to get PR-level comments
4. Use `gh api repos/{owner}/{repo}/pulls/{number}/comments` to get inline review comments
5. Use `gh api repos/{owner}/{repo}/pulls/{number}/reviews` to get review summaries
6. Parse and format all comments in chronological order
7. Return ONLY the formatted comments, with no additional text

Format the comments as:

## Comments

### PR-level Comments

[For each issue comment:]
- @author (timestamp):
  > quoted comment text

### Review: @reviewer [action] (timestamp)

[Review summary if present]

[For each inline code comment:]
- @author file.ts#line:
  ```diff
  [diff_hunk from the API response]
  ```
  > quoted comment text

If there are no comments, return "No comments found."

Remember:
1. Only show the actual comments, no explanatory text
2. Include PR-level comments, review summaries, and inline code review comments
3. Preserve chronological order
4. Show the file and line number context for inline code review comments
5. Detect {owner}/{repo} dynamically from the current git remote
