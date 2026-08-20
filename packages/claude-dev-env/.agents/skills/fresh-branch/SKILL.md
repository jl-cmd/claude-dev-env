---
name: fresh-branch
description: >-
  Fresh git branch from origin/main in an isolated worktree under a configured root (default: <repo>/.claude/worktrees/<agent>/; never checkout -b in the caller tree).
  Triggers: fresh branch, new branch from main, /fresh-branch, start fresh, clean branch off main,
  worktree branch, branch in temp.
---

# fresh-branch

Creates a new branch from a fresh-fetched `origin/main` inside an isolated git worktree under a **configured isolated root**. Default root is the repository's `.claude/worktrees/`; pass `--worktree-root` for an absolute alternate root (including outside the repo). Every worktree path must resolve under that root. Shared primitive: other skills invoke `/fresh-branch` when they need a clean branch without touching the caller's dirty tree.

**Announce at start:** "Creating a fresh branch from origin/main."

## When this applies

- User or caller wants a **new** branch based on current `origin/main`.
- Caller needs the branch path/name as a return value for a later PR step.

**Does not apply (refuse with the quoted line):**

- Switch to an existing branch → `Use git switch / checkout for an existing branch; /fresh-branch only creates new ones.`
- Push or open a PR → `This skill only creates the branch worktree; push and PR are separate.`

## Checklist

```
- [ ] Phase 1 — confirm repo context (cwd or --repo)
- [ ] Phase 2 — resolve branch name (AskUserQuestion when needed)
- [ ] Phase 3 — execute the create script; parse JSON
- [ ] Phase 4 — report branch, worktree_path, base_commit; return to caller
```

## Phase 1 — Repo context

Work against the repository the user has open (or the path the caller names). The script resolves the git toplevel from `--repo` (default `.`). Do not invent a different clone.

## Phase 2 — Branch name (high freedom)

Branch names: lowercase, hyphen-separated, optional `prefix/description`.

**When a topic is available:** suggest 2–4 names via `AskUserQuestion`. Poll recent remote names for local convention:

```
git branch -r --sort=-committerdate
```

(Take a short head of that list in the shell you use; do not require Unix `head`.)

**When no topic:** ask for a name via `AskUserQuestion` (`multiSelect: false`, free-text option).

## Phase 3 — Create branch (execute the script)

**Execute** the bundled CLI (do not reimplement with ad-hoc `git checkout -b`):

```
python "${CLAUDE_SKILL_DIR}/scripts/create_fresh_branch.py" --branch-name "<name>"
```

Optional flags:

| Flag | Role |
|------|------|
| `--repo <path>` | Source repo (default: current directory) |
| `--agent <slug>` | Agent segment under the configured root: `claude`, `grok`, `cursor`, `codex`, … |
| `--base <ref>` | Base ref (default: `origin/main`) |
| `--worktree-root <abs-path>` | Absolute isolated root for all worktrees (default: `<repo-root>/.claude/worktrees`) |

Agent resolution inside the script: `--agent` → `FRESH_BRANCH_AGENT` env → host markers → `claude`.

Configured-root contract:

- Default configured root: `<repo-root>/.claude/worktrees`
- Explicit `--worktree-root` must be absolute; a relative value fails closed with a deterministic error before any git fetch
- Absolute roots outside the repository are legal; the agent and branch still nest under that root
- Worktree path: `<configured-root>/<agent>/<branch-name>`, on every platform
- Every allocated path must resolve under the configured root; traversal that escapes fails closed
- If the path exists, the script suffixes `-2`, `-3`, …
- Permission-rule cleanup (`stale_worktree_rule_sweep`) only walks `~/.claude/worktrees`; external `--worktree-root` trees are outside that sweep until a follow-up ships

On exit 0, stdout is one JSON object:

| Field | Meaning |
|-------|---------|
| `branch` | Created branch name |
| `worktree_path` | Absolute path of the new worktree |
| `base_ref` | Base ref used |
| `base_commit` | SHA at that ref after fetch |
| `agent` | Host slug used in the path |
| `repo_root` | Source repository root |

On non-zero exit, stdout is `{"error": "..."}`. Report the error and stop. Do not fall back to `git checkout -b` in the caller tree.

## Phase 4 — Report

State `branch`, `worktree_path`, and `base_commit`. When invoked as a subroutine, return those fields so the caller can continue (for example open a PR from that worktree).

Further edits for the new branch belong in `worktree_path`, not in the caller's original cwd.

## Constraints

- Never `git checkout -b` (or equivalent) in the caller's working tree.
- Always fetch the base ref through the script (default `origin/main`).
- Do not push. Do not open a PR.
- Do not switch an existing branch; only create.

## Gotchas

- **Dirty caller cwd blocks `checkout -b` and pollutes the tree.** Phase 3 always uses `git worktree add -b` into `<configured-root>/<agent>/…`. If you reconstruct Phase 3 by hand with `checkout -b` in the session cwd, local modifications block the checkout and leave the user on a half-switched branch.
- **Caller HEAD must stay put.** After success, the original repo's checked-out branch and dirty files are unchanged; only the new worktree has the new branch.
- **Branch name collision.** If the branch already exists, the script exits non-zero with `{"error":...}`. Pick a new name; do not delete remote branches unless the user asks.
- **Path already occupied.** A leftover folder at the preferred worktree path gets a numeric suffix (`-2`, …); report the path from JSON, not the path you assumed.
- **Relative `--worktree-root` is refused before fetch.** Only an absolute path is accepted; the default root applies when the flag is omitted. Validation runs before `git fetch`, so a bad root never touches the network or remote-tracking refs.
- **External roots and stale permission rules.** `stale_worktree_rule_sweep` only walks `~/.claude/worktrees`. Edit rules granted under an external `--worktree-root` are not swept when that tree is deleted.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub: phases, checklist, constraints, gotchas |
| `CLAUDE.md` | Package map for agents browsing the skill folder |
| `scripts/create_fresh_branch.py` | **Execute** — deterministic fetch + worktree branch CLI |
| `scripts/fresh_branch_git_commands.py` | Git command helpers behind the CLI (fetch, ref checks, worktree add) |
| `scripts/test_create_fresh_branch.py` | Real-repo tests for agent/path/CLI behavior |
| `scripts/test_fresh_branch_git_commands.py` | Real-repo tests for the git command helpers |
| `scripts/fresh_branch_scripts_constants/` | Named constants for the CLI |

## Folder map

- `scripts/` — executable CLI, tests, constants package
- `scripts/fresh_branch_scripts_constants/` — importable `UPPER_SNAKE` values
