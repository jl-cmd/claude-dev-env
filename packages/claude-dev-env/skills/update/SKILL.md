---
name: update
description: Fast-forwards a local git repository's main branch to a remote's main, after confirming both the local repo path and the source remote through AskUserQuestion. Fetches the chosen remote, checks that the move is a true fast-forward (never a force, never a merge commit), and updates main whether or not main is the checked-out branch. Use when the user says "/update", "update main", "fast-forward main", "sync main from origin", "pull latest main into <path>", or "bring main up to date". Triggers on "/update", "update main", "fast-forward main", "sync main".
---

# update

## Overview

Fast-forwards the local `main` branch of a given repository to a chosen remote's `main`. The move is always a true fast-forward: the skill fetches the remote, checks that local `main` is an ancestor of the remote's `main`, and advances the ref. It never forces, never creates a merge commit, and never touches any branch other than `main`.

The repository is whatever path the user gives as the `/update <path>` argument. With no argument, the default is the current repository's top level. Either way the path is confirmed before any write.

**Announce at start:** "Confirming the repo path and source remote, then fast-forwarding main."

## When this applies

Trigger on a request to bring a repo's `main` up to date from a remote: "/update", "update main", "fast-forward main", "sync main from origin", "pull latest main into <path>".

**Refusals — first match wins; respond with the quoted line exactly and stop:**

- Path is not a git repository → `<path> is not a git repository. Give me the path to a git working tree.`
- The chosen remote has no `main` → `<remote> has no main branch. Pick a remote whose main you want.`
- Local `main` has diverged from the remote's `main` (not a fast-forward) → `main has diverged from <remote>/main (ahead N, behind M). A fast-forward is not possible — use /rebase or reconcile manually.`

## Instructions

### Phase 1 — Resolve the local path

Take the path from the `/update <path>` argument. With no argument, use the current repo's top level:

```
git -C "<path>" rev-parse --show-toplevel
```

Confirm the path is a git working tree (`git -C "<path>" rev-parse --git-dir`). If not, give the first refusal line.

### Phase 2 — Confirm the path and the source remote

List the candidate repo's remotes and their URLs:

```
git -C "<path>" remote -v
```

Confirm both in **one** `AskUserQuestion` question — header "Target". Each choice pairs the resolved path with one remote, labelled `<path> ← <remote>/main` and described with that remote's fetch URL. Picking a choice confirms the path and the remote together.

Recommend `<path> ← origin/main` first; the source-of-truth remote is not always the one named `origin`. The user picks "Other" to name a different path or remote. If they switch to a different repository, re-list its remotes and ask once more — remote names are per-repo.

### Phase 3 — Fetch and fast-forward

Run every command with `git -C "<path>"`. Do not `cd` into the repo.

1. Fetch the chosen remote's `main`, which moves the remote-tracking ref:

   ```
   git -C "<path>" fetch <remote> main
   ```

   Stop and report on failure (no network, no remote). If the remote has no `main`, give the second refusal line.

2. Read the current branch and the two commits:

   ```
   git -C "<path>" branch --show-current
   git -C "<path>" rev-parse <remote>/main
   git -C "<path>" rev-parse --verify main   # may not exist yet
   ```

3. Decide the case:

   | Case | Condition | Action |
   |---|---|---|
   | Create | local `main` does not exist | `git -C "<path>" branch main <remote>/main` |
   | Up to date | local `main` == `<remote>/main` | report, done |
   | Diverged | `merge-base --is-ancestor main <remote>/main` is false | third refusal line, stop |
   | Fast-forward, on main | current branch is `main` | clean check, then `merge --ff-only` |
   | Fast-forward, off main | current branch is not `main` | `fetch <remote> main:main` |

   The fast-forward gate:

   ```
   git -C "<path>" merge-base --is-ancestor main <remote>/main
   ```

   Exit 0 means a fast-forward is possible. Non-zero means diverged — refuse, never force.

4. Apply the fast-forward for the matched case:

   - **On `main`:** the working tree must be clean first — `git -C "<path>" status --porcelain` must be empty. If dirty, stop and report; never stash or discard. Then:

     ```
     git -C "<path>" merge --ff-only <remote>/main
     ```

   - **Off `main`:** advance the ref without touching the working tree:

     ```
     git -C "<path>" fetch <remote> main:main
     ```

     This is fast-forward-only (no leading `+`) and leaves the checked-out branch alone.

### Phase 4 — Report

State the old and new `main` SHAs and the one-line subject of the new tip:

```
git -C "<path>" log --oneline -1 main
```

Report the move as `main <old> → <new>`, or "already up to date" when nothing changed.

## Constraints (non-negotiable)

- **Fast-forward only.** If the remote's `main` is not a descendant of local `main`, stop. Never `--force`, never `branch -f`, never a merge commit. Divergence is a job for `/rebase`.
- **Always confirm both** the path and the source remote first, even when the path is given as an argument. Skipping a confirmation is not allowed — the confirmation is the point of this skill.
- **Touch only `main`.** Never switch the repo's checked-out branch. The single exception is advancing `main` in place when `main` is already checked out.
- **Never discard local work.** A dirty tree blocks the in-place fast-forward; stop and report rather than stash or reset.

## Gotchas

- `git fetch <remote> main:main` refuses with "Refusing to fetch into branch ... checked out" when `main` is the current branch. That is why Phase 3 branches on `git branch --show-current` and uses `merge --ff-only` when on `main`.
- The same refusal fires when `main` is checked out in a **different worktree** of the same repo. Find it with `git -C "<path>" worktree list`, then run the fast-forward from that worktree's path, or report it and stop.
- `<remote>/main` only moves after an explicit `git fetch`. Fetch inside every run; never compare against a remote-tracking ref left over from an earlier fetch.
- `origin` is not always the source of truth. When a fork is `origin` and the canonical repo is another remote (often `upstream`), the confirmed remote should be the canonical one, not whichever is named `origin`.
- Quote the path on every command — `git -C "<path>"` — so paths with spaces or a NAS drive letter survive.

## What this skill does NOT do

- Does not push, open a PR, or change any branch other than `main`.
- Does not create or switch feature branches — that is `/fresh-branch`.
- Does not reconcile a diverged `main` — that is `/rebase`.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — the complete skill. |

## Folder map

- `SKILL.md` — the whole skill. Flat by design: the operation is a short, deterministic git sequence with no scripts or reference files to load.
