# Fetch PR naming surface

**Execute** these commands (pwsh). Replace `<N>` with the PR number. Parse the PR number from a URL (`…/pull/2153` → `2153`) when the user pastes a link.

Prefer this recipe so the user’s worktree stays as-is. Do not `gh pr checkout` for naming audits.

## Metadata

```powershell
gh pr view <N> --json number,title,body,baseRefName,headRefName,url
```

## Paths and renames

One paginated files list covers added, modified, and renamed paths (`status`, `previous_filename`). Use `--paginate --slurp` per `gh-cli-conventions` (not built-in `--jq` across pages):

```powershell
gh api repos/:owner/:repo/pulls/<N>/files --paginate --slurp
```

When `:owner` / `:repo` are unknown, resolve them from `gh pr view <N> --json headRepository,url` or the PR URL, then re-run the files call.

## What to keep from the fetch

- PR title and first paragraph of body (scope wording)
- Every added or renamed path under package roots and `.claude/skills/`
- New Python module stems whose names carry driver words

Scoring rules for those signals live in `reference/rule-checklist.md` — this file only fetches.
