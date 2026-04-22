# Team setup and loop state

## Step 0 — Grant project permissions (detail)

Before spawning any teammates, grant the team session write access to the project’s `.claude/**` tree. Command in `SKILL.md`.

`${CLAUDE_SKILL_DIR}` is a Claude Code host-managed token, pre-substituted by the runtime before any shell sees it. Unlike `${TMPDIR}` and similar shell parameter expansions, it does not depend on the shell’s expansion semantics, so it behaves the same on Unix and Windows shells.

The script reads `Path.cwd()` and writes idempotent allow rules into `~/.claude/settings.json`. Run from the project root. If it fails (non-zero exit), surface the error and stop — do not proceed without the grant.

This is the **first** action of every `/bugteam` invocation, before any team creation or agent spawn. The corresponding revoke runs at Step 5 regardless of how the cycle exits.

## Step 1 — Resolve PR scope (detail)

Same resolution path as `/findbugs`:

1. `gh pr view --json number,baseRefName,headRefName,url` from the working directory.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → refuse per refusal cases in `SKILL.md`.

Capture `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` runs to completion from the single up-front confirmation.

## Step 2 — Create the agent team (detail)

This session is the **team lead**. Create the team with `TeamCreate` using the exact argument shape in `SKILL.md`.

`<team_name>` is built under **Team name** below (sanitization + timestamp already applied). `TeamCreate` matches natural-language team creation in the product docs; quote in [`../sources.md`](../sources.md).

### Team specification

- **Team name:** `bugteam-pr-<number>-<YYYYMMDDHHMMSS>` (or `bugteam-<sanitized-head-branch>-<YYYYMMDDHHMMSS>` if no PR). The timestamp is captured at team-creation time from the lead session and prevents two concurrent invocations on the same PR from colliding.

- **Branch-name sanitization (no-PR fallback only):** Before substituting `<head-branch>` into the `team_name` template, replace every character outside `[A-Za-z0-9._-]` with `-`. The whitelist keeps safe portable filename characters only; OS-reserved and shell-special characters (`/ \ : * ? < > | "` plus ASCII control characters `0x00`–`0x1F`) fall outside the whitelist and become `-`. Example: `feat/foo*bar` → `feat-foo-bar`; `team_name` becomes `bugteam-feat-foo-bar-<YYYYMMDDHHMMSS>`. Apply sanitization when `team_name` is first assembled so every downstream use (team creation, scoped temp dir, cleanup) sees the safe form.

- **Per-team temp directory (resolved once, reused everywhere):** After `team_name` is captured, resolve a portable absolute path with a Claude-side lookup using Python’s `tempfile.gettempdir()`, which honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix: `Path(tempfile.gettempdir()) / team_name` (requires `import tempfile`). The `team_name` value already carries the `bugteam-` prefix; keep it as-is here. Let `tempfile.gettempdir()` perform the lookup; use its result directly. Capture the resolved absolute path as `<team_temp_dir>` and pass that literal path to every shell command that follows. Claude performs all temp-root resolution so every shell (bash, cmd.exe, PowerShell) receives the same literal absolute value.

- **Roles defined up front (spawned per loop, not at team creation):**
  - `bugfind` — teammate role `code-quality-agent`, model opus (Opus 4.7 at default xhigh effort)
  - `bugfix` — teammate role `clean-coder`, model opus (Opus 4.7 at default xhigh effort)

- **Display mode:** inherit the user’s default (`teammateMode` in `~/.claude.json`); do not override.

Reference teammate role definitions by name when spawning. Doc quote on subagent scopes: [`../sources.md`](../sources.md).

### Loop state block

The block in `SKILL.md` mixes lead-internal variables and one shell command (`starting_sha`). Read it as instructions, not a single runnable script.

**`loop_comment_index` scope (per-loop, not cross-loop):** Reset at the start of every AUDIT action, populated as finding comments are posted during AUDIT, consumed by the matching FIX action when it posts fix replies, and discarded after FIX completes. It does not persist across loops; each loop starts with an empty index and its own fresh set of comment URLs.

Each entry: `{loop, finding_id, finding_comment_id, finding_comment_url, used_fallback, fix_status}`. Populated by AUDIT, consumed by FIX.
