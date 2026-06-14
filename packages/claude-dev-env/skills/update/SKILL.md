---
name: update
description: Fast-forwards a local git repository's main branch to a remote's main, after confirming both the local repo path and the source remote through AskUserQuestion. Fetches the chosen remote, checks that the move is a true fast-forward (never a force, never a merge commit), and updates main whether or not main is the checked-out branch. When main is not the checked-out branch, it then offers to switch the checkout to main so the update reaches the files on disk. Use when the user says "/update", "update main", "fast-forward main", "sync main from origin", "pull latest main into <path>", or "bring main up to date". Triggers on "/update", "update main", "fast-forward main", "sync main".
---

# update

## Overview

Fast-forwards the local `main` branch of a given repository to a chosen remote's `main`. The move is always a true fast-forward: the skill fetches the remote, checks that local `main` is an ancestor of the remote's `main`, and advances the ref. It never forces, never creates a merge commit, and never rewrites any branch other than `main`. When `main` is not the checked-out branch, a final confirmed step offers to switch the checkout to `main` so the new commits reach the files on disk — the only branch switch the skill makes, and only after the operator approves it.

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

Then report what the checkout runs — a move of the `main` ref says nothing about the files on disk:

```
git -C "<path>" branch --show-current
git -C "<path>" status --short
```

- **Checked-out branch.** When a branch other than `main` is checked out, say so plainly: the fast-forward moves a ref only and no file on disk changes. Code that runs from this checkout comes from the checked-out branch, not from `main`.
- **Dirty tracked files.** List every modified tracked file from `status --short`. Uncommitted edits sit on top of the checked-out branch and are what runs — flag them, because a ref update can neither see nor repair them. When the tree is clean, report "working tree clean".

### Phase 5 — Offer to land `main` on disk

A fast-forward of the `main` ref leaves the files on disk untouched when another branch is checked out. The new commits exist in the repo but not in the working tree — the gap Phase 4 reports. This phase offers to close it.

Skip this phase and finish when the checked-out branch is already `main`: the new commits are already on disk.

Otherwise, when the checked-out branch is not `main`, run two safety checks before offering a switch:

1. **Tree clean of tracked changes.** Read `git -C "<path>" status --porcelain` and treat any line that does not start with `??` as a change to a tracked file. If any exist, do not offer the switch: report that `main` moved in the ref only, that switching would risk the uncommitted work, and stop. Never stash, reset, or discard. Untracked files (lines starting with `??`) are fine — they carry across a switch.
2. **`main` free to check out.** Read `git -C "<path>" worktree list`. If another worktree holds `main`, an in-place switch is impossible; report that path and stop.

When both checks pass, ask **one** `AskUserQuestion` — header "Get on disk":

- Recommended first choice, "Switch checkout to main": `git -C "<path>" checkout main` puts the new commits on disk. The branch you were on keeps its commits and is left unchanged.
- Second choice, "Stay on `<branch>`": leave the checkout where it is. The update stays in the `main` ref only and reaches disk later.

On "Switch", run:

```
git -C "<path>" checkout main
```

If `checkout` reports it would overwrite untracked files, stop and report those paths — never pass `-f`, which would drop the operator's untracked file. On success, confirm the branch and the tip now on disk:

```
git -C "<path>" branch --show-current
git -C "<path>" log --oneline -1
```

On "Stay", report that `main` is current in the ref and the new content reaches disk only after a later switch.

## Constraints (non-negotiable)

- **Fast-forward only.** If the remote's `main` is not a descendant of local `main`, stop. Never `--force`, never `branch -f`, never a merge commit. Divergence is a job for `/rebase`.
- **Always confirm both** the path and the source remote first, even when the path is given as an argument. Skipping a confirmation is not allowed — the confirmation is the point of this skill.
- **Switch the checkout only with approval.** The fast-forward itself touches the `main` ref alone. Switching the checked-out branch to `main` happens only in Phase 5, only after the operator approves the `AskUserQuestion`, only with a tree clean of tracked changes, and never with `-f`. The skill never switches to any branch but `main`.
- **Never discard local work.** A dirty tree blocks the in-place fast-forward; stop and report rather than stash or reset.

## Gotchas

- `git fetch <remote> main:main` refuses with "Refusing to fetch into branch ... checked out" when `main` is the current branch. That is why Phase 3 branches on `git branch --show-current` and uses `merge --ff-only` when on `main`.
- The same refusal fires when `main` is checked out in a **different worktree** of the same repo. Find it with `git -C "<path>" worktree list`, then run the fast-forward from that worktree's path, or report it and stop.
- `<remote>/main` only moves after an explicit `git fetch`. Fetch inside every run; never compare against a remote-tracking ref left over from an earlier fetch.
- `origin` is not always the source of truth. When a fork is `origin` and the canonical repo is another remote (often `upstream`), the confirmed remote should be the canonical one, not whichever is named `origin`.
- Quote the path on every command — `git -C "<path>"` — so paths with spaces or a NAS drive letter survive.
- "Up to date" describes the `main` ref, not the running code. A checkout deployed on a feature branch, or carrying uncommitted edits, runs that branch plus those edits regardless of where `main` points. Phase 4's checkout-state report exists so the operator sees that gap on every run, and Phase 5 offers to close it.
- `git checkout main` carries untracked files across unchanged, but refuses with "untracked working tree files would be overwritten" when an untracked file sits at a path `main` tracks. Phase 5 reports those paths and stops rather than passing `-f`, which would drop the operator's untracked file.

## What this skill does NOT do

- Does not push, open a PR, or change any branch other than `main`.
- Does not create feature branches, and switches only to `main` (Phase 5, with approval) — creating or switching to any other branch is `/fresh-branch`.
- Does not reconcile a diverged `main` — that is `/rebase`.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — the complete skill. |

## Folder map

- `SKILL.md` — the whole skill. Flat by design: the operation is a short, deterministic git sequence with no scripts or reference files to load.
