# Run setup and loop state

## Pre-flight (before Step 0)

### Utility scripts

Bugteam-specific utilities (preflight, fix_hookspath, grant, revoke) live in
the skill-local [`scripts/`](../scripts/) directory. Shared utilities remain in
[`_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/) (run, do not paste
into context). Utility scripts are **executed**, not loaded as primary context
([`sources.md`](sources.md) § Progressive disclosure and utility scripts).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

Non-zero → fix before grant. `BUGTEAM_PREFLIGHT_SKIP=1` emergency only.
`--pre-commit` if `.pre-commit-config.yaml` exists.

**Self-heal for stale local-scope `core.hooksPath`:** preflight silently
unsets ALL local-scope `core.hooksPath` entries on the active repository when
two conditions both hold: at least one entry does not end in the canonical
`hooks/git-hooks` suffix, AND a canonical global `core.hooksPath` is already
configured. The check clears the `<repo>/.git/hooks` entry git can seed into a
worktree's local config when `extensions.worktreeConfig` is set or seeding
tooling is in use, so the canonical global setting takes effect without Claude
needing to surface a failure or invoke the fix script. When the global is
unset or non-canonical, the self-heal stands down so the downstream
`core.hooksPath is '<path>'` diagnostic stays informative.

**Auto-remediation for `core.hooksPath`:** when preflight reports stderr
containing `core.hooksPath` (the message starts with
`bugteam_preflight: core.hooksPath is`, or `Git-side CODE_RULES enforcement is
not active`) — which surfaces when the global setting is missing or points
elsewhere — Claude must auto-invoke the fix script. Do not fall through to
`AskUserQuestion`, do not punt to the user, do not ask for confirmation:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_fix_hookspath.py"
```

The fix script removes any non-canonical local-scope override on the active
repository, sets the global `core.hooksPath` to `~/.claude/hooks/git-hooks` if
missing or wrong, and re-runs `bugteam_preflight.py`. Its exit code becomes the
preflight outcome. Exit 0 → continue to Step 0. Non-zero only when the
canonical hooks directory is missing (run `npx claude-dev-env .` first) or
`git config --global` writes are blocked. Other preflight failures (pytest,
pre-commit) still require manual fixes —
the auto-remediation only applies to the `core.hooksPath` failure mode.

## Step 0 — Grant project permissions (detail)

Before spawning any subagents, grant the session write access to the project's `.claude/**` tree:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/grant_project_claude_permissions.py"
```

`${CLAUDE_SKILL_DIR}` is a Claude Code host-managed token, pre-substituted by the runtime before any shell sees it. Unlike `${TMPDIR}` and similar shell parameter expansions, it does not depend on the shell’s expansion semantics, so it behaves the same on Unix and Windows shells.

The script reads `Path.cwd()` and writes idempotent allow rules into `~/.claude/settings.json`. Run from the project root. If it fails (non-zero exit), surface the error and stop — do not proceed without the grant.

This is the **first** action of every `/bugteam` invocation, before any subagent spawn. The corresponding revoke runs at Step 5 regardless of how the cycle exits.

## Step 1 — Resolve PR scope (detail)

Same resolution path as `/findbugs`:

1. Call `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` to fetch PR metadata; capture `number`, `headRefName`, `baseRefName`, and `url` from the response. Falls back to the merge-base diff path when no PR exists.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → refuse per refusal cases in `SKILL.md`.

Capture `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` runs to completion from the single up-front confirmation.

For multi-PR invocations, capture `all_prs = [{number, owner, repo, baseRef, headRef, url}, ...]`. A single-PR invocation produces a one-element list and follows the same downstream rules.

### Per-PR workspace

For each PR in `all_prs`:

Canonical path functions live in
[`_shared/pr-loop/scripts/_path_resolver.py`](../../_shared/pr-loop/scripts/_path_resolver.py):
`per_pr_workspace(run_temp_dir, owner, repo, pr_number)` returns a frozen
`PerPrWorkspace` with fields `worktree` (a `Path`), `diff_patch_template`,
`outcome_xml_template`, and `fix_outcome_xml_template` (each a `str.format`
template).

1. Create `<run_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<run_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Background subagents for a PR operate inside that PR's worktree. Step 4 teardown
runs [`teardown_worktrees.py`](../../_shared/pr-loop/scripts/teardown_worktrees.py)
for each PR before the shared `rmtree`.

## Step 2 — Run name and temp directory (detail)

Canonical path resolution lives in
[`_shared/pr-loop/scripts/_path_resolver.py`](../../_shared/pr-loop/scripts/_path_resolver.py).
The functions below are its public API; the implementation is the single source of
truth.

- **Run name:** `build_run_name(pr_number, head_branch, *, is_multi_pr)` — returns
  `bugteam-pr-<number>` for single-PR, `bugteam-<sanitized-head-branch>` for multi-PR.
- **Branch-name sanitization:** `sanitize_branch_name(head_branch)` — maps every
  character outside `[A-Za-z0-9._-]` to `-`.
- **Per-run temp directory:** `resolve_run_temp_dir(run_name)` — returns
  `Path(tempfile.gettempdir()) / run_name`. Capture the resolved absolute path as
  `<run_temp_dir>` and pass that literal path to every shell command that follows.

- **Subagent roles (spawned per loop, not at invocation start):**
  - `bugfind` — `code-quality-agent`, model opus (Opus 4.7 at default xhigh effort)
  - `bugfix` — `clean-coder`, model fable

### Loop state block

Loop state (lead; not a single script; per-PR): the variables below are tracked
independently for each PR in `all_prs`. Each PR has its own cycle, state, and
exit reason.

Create the initial state file with
[`init_loop_state.py`](../../_shared/pr-loop/scripts/init_loop_state.py):

```
python scripts/init_loop_state.py --pr-number <N> --head-ref <ref> --starting-sha <SHA> [--is-multi-pr]
```

Outputs the path to `<run_temp_dir>/pr-<N>/loop-state.json` with keys
`loop_count`, `last_action`, `last_findings`, `starting_sha`, `loop_comment_index`.

**`loop_comment_index` scope (per-loop, not cross-loop):** Reset at the start of every AUDIT action, populated as finding comments are posted during AUDIT, consumed by the matching FIX action when it posts fix replies, and discarded after FIX completes. It does not persist across loops; each loop starts with an empty index and its own fresh set of comment URLs.

Shape: dict keyed by `finding_id`. Each value: `{finding_comment_id, finding_comment_url, thread_node_id, fix_status}` where `thread_node_id` is the PR review thread node id (`PRRT_kwDOxxx`) captured at audit time when calling `get_review_comments`, used by the FIX step's `resolve_thread` call. The loop number is implicit (the index resets at every AUDIT) so it does not repeat in each value. AUDIT populates `finding_comment_id`, `finding_comment_url`, and `thread_node_id` when it posts the per-loop review; FIX sets `fix_status` when its commit lands.

#### Multi-PR sub-team tracking

When `/bugteam` runs against multiple PRs across repos, each PR operates as a
logical sub-team within the master `bugteam` team. The PR identity token is
`{owner}/{repo}#{N}` (e.g. `jl-cmd/claude-code-config#422`). The slugified form
comes from `slugify_pr_identity(owner, repo, pr_number)` in
[`_path_resolver.py`](../../_shared/pr-loop/scripts/_path_resolver.py).

- **Teammate name:** `bugfind-{owner}-{repo}-pr{N}-loop{L}-{letter}`
- **Task subject:** `{owner}/{repo}#{N} audit {letter}`
- **Outcome XML:** `diff_patch_path(run_temp_dir, owner, repo, pr_number, loop_number)` from `_path_resolver.py`

The lead filters by the slugified prefix to group tasks and teammates by PR.
Self-claiming by task subject prefix keeps each teammate on its assigned PR.

### --bugbot-retrigger flag

**`--bugbot-retrigger` flag:** when present, the FIX subagent posts a `bugbot
run` issue comment via the Step 2.5 issue-comments fallback endpoint after
every successful FIX push, to re-trigger Cursor's bugbot on the new commit.

**Opt-out gate.** When `CLAUDE_REVIEWS_DISABLED` (comma-separated,
case-insensitive, whitespace-tolerant) contains the token `bugbot`, the FIX
subagent skips the re-trigger post even when the flag is present. The rest of
the bugteam audit/fix cycle continues unchanged.
