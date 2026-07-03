---
name: pr-scope-resolve
description: >-
  Resolves the audit/fix target for a PR-loop skill: owner, repo, PR number,
  head ref, base ref, PR URL, and starting head SHA — via
  pull_request_read(method="get"), a search_issues branch fallback, then a
  git merge-base upstream-diff fallback, ending in the canonical refusal line
  when no target exists. Invoked by PR-loop orchestrators (pr-converge,
  bugteam, qbug, findbugs, fixbugs) as their first step; not for general git
  questions or branch management.
---

# PR Scope Resolve

**Core principle:** every PR-loop skill agrees on what it is auditing before any other work. One resolution ladder, one refusal line.

## How callers invoke this

- **Skill-capable contexts** (a lead session with the `Skill` tool): `Skill({skill: "pr-scope-resolve", args: "--skill <caller> [PR URL if the user gave one]"})`.
- **Fallback** (a subagent or teammate without the `Skill` tool): the caller's spawn prompt says "Read `~/.claude/skills/pr-scope-resolve/SKILL.md` and apply the resolution ladder with the parameters below."

The caller identity fills the refusal template. The resolved scope hands back: `owner`, `repo`, `number`, `head_ref`, `base_ref`, `url`, and `head_sha` (the starting `current_head`).

## The resolution ladder

Match the first rung that holds:

1. **A PR URL was given.** Extract `owner`, `repo`, and `number` from the URL, then `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` for `head.sha`, `head.ref`, `base.ref`, and draft state.
2. **Open PR for the current branch.** Call `pull_request_read(method="get")` with the PR number from the caller's context. When the number is unknown, recover it with the `search_issues` MCP tool using the current branch name, then fetch as in rung 1.
3. **No PR, but a remote default branch exists.** The scope is the upstream diff: `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`. `head_sha` is `git rev-parse HEAD`; there is no PR number or URL, and steps that post to a PR are skipped by the caller.
4. **Neither.** Respond exactly with the refusal template and stop:

   `No PR or upstream diff. /<caller> needs a target.`

## Ground rules

- **The GitHub MCP is the primary transport** (`pull_request_read`, `search_issues`); raw `gh api` is the fallback. MCP calls behave the same from any worktree, so scope resolution never depends on the working directory.
- **Re-resolve `head_sha` after any push or external wait.** The scope tuple (`owner`, `repo`, `number`) is stable for a run; the head SHA is not.
- **Full-diff scope.** The resolved scope always means the full `origin/<base>...HEAD` diff — every file the PR touches. A caller that narrows to a file list, commit range, or flagged-path subset is out of contract with every convergence gate downstream.

## Gotchas

- **`search_issues` recovers PR numbers from branch names**, but a branch reused across repos returns several hits — filter by repo before trusting the number.
- **A draft-state read belongs to this step.** Callers that need a draft PR (convergence loops that mark ready at the end) check `isDraft` here, on the same `get` call, rather than paying a second fetch later.

## Folder map

- `SKILL.md` — this file; the ladder is MCP- and git-native, so the skill ships no scripts.
