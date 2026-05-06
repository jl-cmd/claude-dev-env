# Run setup and loop state

## Step 0 — Grant project permissions (detail)

Before spawning any subagents, grant the session write access to the project’s `.claude/**` tree. Command in `SKILL.md`.

`${CLAUDE_SKILL_DIR}` is a Claude Code host-managed token, pre-substituted by the runtime before any shell sees it. Unlike `${TMPDIR}` and similar shell parameter expansions, it does not depend on the shell’s expansion semantics, so it behaves the same on Unix and Windows shells.

The script reads `Path.cwd()` and writes idempotent allow rules into `~/.claude/settings.json`. Run from the project root. If it fails (non-zero exit), surface the error and stop — do not proceed without the grant.

This is the **first** action of every `/bugteam` invocation, before any subagent spawn. The corresponding revoke runs at Step 5 regardless of how the cycle exits.

## Step 1 — Resolve PR scope (detail)

Same resolution path as `/findbugs`:

1. `gh pr view --json number,baseRefName,headRefName,url` from the working directory.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → refuse per refusal cases in `SKILL.md`.

Capture `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` runs to completion from the single up-front confirmation.

## Step 2 — Run name and temp directory (detail)

### Run specification

- **Run name:** `bugteam-pr-<number>-<YYYYMMDDHHMMSS>` for single-PR invocations, `bugteam-<YYYYMMDDHHMMSS>` for multi-PR invocations (or `bugteam-<sanitized-head-branch>-<YYYYMMDDHHMMSS>` if no PR). The timestamp is captured once at invocation start and prevents two concurrent invocations on the same PR from colliding.

- **Branch-name sanitization (no-PR fallback only):** Before substituting `<head-branch>` into the `run_name` template, replace every character outside `[A-Za-z0-9._-]` with `-`. The whitelist keeps safe portable filename characters only; OS-reserved and shell-special characters (`/ \ : * ? < > | "` plus ASCII control characters `0x00`–`0x1F`) fall outside the whitelist and become `-`. Example: `feat/foo*bar` → `feat-foo-bar`; `run_name` becomes `bugteam-feat-foo-bar-<YYYYMMDDHHMMSS>`. Apply sanitization when `run_name` is first assembled so every downstream use (temp dir, cleanup) sees the safe form.

- **Per-run temp directory (resolved once, reused everywhere):** After `run_name` is captured, resolve a portable absolute path: `Path(tempfile.gettempdir()) / run_name` (requires `import tempfile`). `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, and `TMP` in platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix. Capture the resolved absolute path as `<run_temp_dir>` and pass that literal path to every shell command that follows.

- **Subagent roles (spawned per loop, not at invocation start):**
  - `bugfind` — `code-quality-agent`, model opus (Opus 4.7 at default xhigh effort)
  - `bugfix` — `clean-coder`, model opus (Opus 4.7 at default xhigh effort)

### Loop state block

The block in `SKILL.md` mixes lead-internal variables and one shell command (`starting_sha`). Read it as instructions, not a single runnable script.

**`loop_comment_index` scope (per-loop, not cross-loop):** Reset at the start of every AUDIT action, populated as finding comments are posted during AUDIT, consumed by the matching FIX action when it posts fix replies, and discarded after FIX completes. It does not persist across loops; each loop starts with an empty index and its own fresh set of comment URLs.

Each entry: `{loop, finding_id, finding_comment_id, finding_comment_url, used_fallback, fix_status}`. Populated by AUDIT, consumed by FIX.
