# Code-review enforcement

This feature ties two git actions to a clean run of the built-in
`/code-review --fix`:

- **`git push`** needs a clean review at effort **low** or higher.
- **Pull-request creation** (`gh pr create` and the MCP `create_pull_request`
  tool) needs a clean review at effort **xhigh** or higher.

The gates follow the same shape as the `verified_commit` gate family.

## Opt-in (default off)

Enforcement is **off by default**. The master flag is
`CODE_REVIEW_ENFORCEMENT_ENABLED` in
`hooks/blocking/config/code_review_enforcement_constants.py`. Set it to
`True` to enable the push gate, the PR-create gate, the native pre-push
backstop (via the shared deny decision), and the stamp-directory write
blocker. When the flag is `False`, every gate allows the action and the
write-blocker allows stamp-directory access.

## How a stamp works

A stamp is a small JSON file that records one fact: a clean `/code-review` pass
ran against an exact branch surface at a given effort. Each work tree keeps one
file under `~/.claude/code-review-stamps/`, named by a hash of the resolved
work-tree path.

The stamp binds to a **branch-surface hash** — the hash of every changed path
and untracked file, each bound by its content digest, measured against the
merge base. When any byte of the change surface moves, the live hash stops
matching the stored hash, so the stamp stops covering the surface and the gate
asks for a fresh review.

A gate allows the action only when a stored stamp matches the live hash exactly
and its effort ranks at or above the effort the action needs. A missing,
unreadable, or malformed stamp reads as no coverage, so the gate fails closed.

## The single sanctioned minter

Only `invoke_code_review.py --record-stamp` writes a stamp. It forces a headless
`/code-review <effort> --fix` run, then mints a stamp only when the review
returns a clean exit code and leaves the branch surface unchanged in the same
pass. A pass that applies fixes mints nothing; the run loops on the new surface
up to a capped number of passes and mints only on a stable clean pass.

## Two layers guard the stamp directory

The gates trust one rule: only the sanctioned minter writes stamp files. Two
layers hold that rule.

1. **File-tool deny in `settings.json`.** `Write`, `Edit`, and `MultiEdit`
   under `~/.claude/code-review-stamps/` are denied. This layer covers work
   inside the repository. The installer merges hook groups into a user's
   `settings.json` and does not ship this package's `permissions.deny`, so on a
   user's machine this layer protects contributor work, at parity with the
   `verified_commit` gate's own file-tool deny.
2. **`code_review_stamp_directory_write_blocker` hook.** This hook ships through
   `hooks.json`, so it reaches every install. It has two arms:
   - a shell arm that denies any Bash or PowerShell command naming the stamp
     directory, or importing the stamp store module, or calling its mint
     function — while it lets the sanctioned minter command through;
   - a file-tool arm that denies any `Write`, `Edit`, or `MultiEdit` whose path
     resolves under the stamp directory. This arm closes the plain file-tool
     forge on every shipped install, which the package `settings.json` deny
     cannot reach on its own.

## What the gates block

- **Casual and accidental forges.** A plain file-tool write to the stamp
  directory, and a casual shell write to it, are both denied.
- **Hidden-path and split-step shell forges.** A shell command that assembles
  the stamp path from hex, base64, or character math is decoded and denied. A
  command that splits the directory change across steps to walk into the stamp
  directory is traced and denied.
- **Lazy skips.** A push or a pull-request creation cannot go ahead without a
  stamp that matches the live surface at the needed effort.

## What the gates do not block

The chain-mode `/code-review` runs as a subprocess spawn of the `claude`
binary, not a harness-recorded subagent, so there is no signed sidecar to
anchor a forgery-proof mint. The stamp reaches the same posture the
`verified_commit` gate holds, and no further. These bypass surfaces stay open:

- **Pull requests that skip the tool paths.** A PR opened through
  `gh api -X POST .../pulls` or the GitHub web page never triggers the
  create-PR gate.
- **`git push --no-verify`.** This flag tells git to skip the native pre-push
  hook, so the native backstop does not run.
- **A rebuilt store.** A script that re-implements the stamp store in memory
  and writes a matching file can mint a stamp the gates accept.

In short: these gates stop casual forges and lazy skips. They do not stop a
determined attacker who sets out to defeat them.

## Where the pieces live

- Gates: `hooks/blocking/code_review_push_gate.py`,
  `hooks/blocking/code_review_pr_create_gate.py`.
- Stamp store: `hooks/blocking/code_review_stamp_store.py`.
- Directory guard: `hooks/blocking/code_review_stamp_directory_write_blocker.py`.
- Shared constants: `hooks/blocking/config/code_review_enforcement_constants.py`.
- Native backstop: `hooks/git-hooks/pre_push.py` reuses the push gate's
  `deny_reason_for_directory` so the native hook and the Claude gate share one
  decision source.
- Minter: `scripts/invoke_code_review.py --record-stamp`.
