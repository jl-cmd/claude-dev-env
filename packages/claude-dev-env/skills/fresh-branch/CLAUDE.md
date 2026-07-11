# fresh-branch

Creates a new branch from `origin/main` (always fresh-fetched). Triggered by `fresh branch`, `new branch from main`, `/fresh-branch`, or `start fresh`.

## Purpose

A shared primitive used by other skills and directly by the user. Fetches `origin/main`, suggests 2–4 branch names via `AskUserQuestion` when a topic is available (polling recent branch naming patterns from `git branch -r`), then creates and checks out the branch with `git checkout -b <name> origin/main`.

Does not push the branch. Does not create a PR. Does not switch an existing branch. Callers that need the new branch name (for example, to open a PR) receive it as a return value.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Four-phase instructions: fetch `origin/main`, pick branch name (suggest or prompt), create branch, report. Includes gotchas discovered during use. |
