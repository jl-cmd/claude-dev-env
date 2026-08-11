# update

Fast-forwards a local git repository's `main` branch to a chosen remote's `main`.

**Trigger:** `/update`, "update main", "fast-forward main", "sync main from origin", "pull latest main into <path>", "bring main up to date".

## Purpose

Advances the `main` ref in a safe, confirmed, fast-forward-only way. Never forces, never merges. Confirms the repo path and source remote before any write. Offers to switch the checkout to `main` after the ref moves, with a clean-tree safety check.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — five phases, refusals, gotchas. Flat by design; no companion files. |

## Five phases

| Phase | Key action |
|---|---|
| 1 — Resolve path | `git -C "<path>" rev-parse --show-toplevel` |
| 2 — Confirm path + remote | One `AskUserQuestion` listing remote/URL pairs; recommends `origin/main` first |
| 3 — Fetch + fast-forward | Fetch, check ancestry with `merge-base --is-ancestor`, apply via `merge --ff-only` (on main) or `fetch main:main` (off main) |
| 4 — Report | Old SHA → new SHA, checkout state, dirty tracked files |
| 5 — Offer to land on disk | `AskUserQuestion` to switch checkout to `main` (only when tree is clean and `main` is not held by another worktree) |

## Refusals (first match wins)

- Path is not a git repository → stated error, stop.
- Remote has no `main` → stated error, stop.
- Local `main` has diverged (not a fast-forward) → stated error, stop. Use `/rebase` to reconcile.

## Conventions

- Every command uses `git -C "<path>"` — never `cd` into the repo.
- Path confirmation is mandatory even when the path comes from the argument.
- The skill never switches to any branch other than `main`, and only in Phase 5 with operator approval.
- `origin` is not always the source of truth; the confirmed remote may be `upstream` or another name.
