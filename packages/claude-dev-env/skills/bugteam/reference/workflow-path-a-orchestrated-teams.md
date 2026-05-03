# Bugteam — Path A workflow (orchestrated teams)

Load when bugteam `SKILL.md` **Path routing** selects **Path A** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` equals **`1`** after trim). Execute **after** shared `SKILL.md` steps through **Step 2 loop state**; then use this file for **harness-only** steps. Shared gate scripts, Step 3 cycle numbering, Step 2.5 `jq`/`gh` payload shapes, `PROMPTS.md`, and outcome XML rules remain in **`SKILL.md`**.

## Step 2 harness — lifecycle, `TeamCreate`, and team metadata

**This session is the lead.** Step 2 first resolves the team lifecycle from the [Team lifecycle](../SKILL.md#team-lifecycle-path-a-only) table in `SKILL.md`, then either creates or attaches to a team.

**Lifecycle resolution (read once, then apply):**

```python
import os
import re

mode = os.environ.get("BUGTEAM_TEAM_LIFECYCLE", "auto").strip().lower() or "auto"
attached_team_name = os.environ.get("BUGTEAM_TEAM_NAME", "").strip()

if mode == "attach" and not attached_team_name:
    raise RuntimeError(
        "BUGTEAM_TEAM_LIFECYCLE=attach requires BUGTEAM_TEAM_NAME to name an existing team."
    )
```

The mode then drives Step 2's `TeamCreate` decision:

- **`mode == "attach"`** — skip `TeamCreate` entirely. Set `team_name = attached_team_name`, `team_owned = false`. Continue to teammate spawns using that `team_name`.

- **`mode == "owned"`** — call `TeamCreate(team_name=<computed_team_name>, ...)` (form below). On the runtime error matching `Already leading team "(.+)"\.` → **fail** with `Already leading team <existing>; rerun with BUGTEAM_TEAM_LIFECYCLE=attach BUGTEAM_TEAM_NAME=<existing>`. On success, set `team_owned = true`.

- **`mode == "auto"`** (default) — call `TeamCreate(team_name=<computed_team_name>, ...)`. On the same runtime error, parse the existing team name with the regex `r'Already leading team "([^"]+)"'`, set `team_name = <existing>`, `team_owned = false`, and continue without retrying `TeamCreate`. On success, set `team_owned = true`. Both branches honor §Team name below.

**`TeamCreate` call shape (only when `mode != "attach"` and the auto branch did not already attach):**

```
TeamCreate(
  team_name="<computed_team_name>",
  description="Bugteam audit/fix loop for PR <number> (<owner>/<repo>)",
  agent_type="team-lead"
)
```

**Team name:** For a single-PR invocation use `bugteam-pr-<number>-<YYYYMMDDHHMMSS>`. For a multi-PR invocation use `bugteam-<YYYYMMDDHHMMSS>`. The timestamp is captured once at team-creation time. Apply the no-PR fallback (`bugteam-<sanitized-head>-<YYYYMMDDHHMMSS>`) only when no PR resolves at all. `TeamCreate` implements natural-language team creation ([`sources.md`](../sources.md) § Team creation in natural language).

**Sanitize head branch (no-PR only):** replace characters outside `[A-Za-z0-9._-]` with `-` (e.g. `feat/foo*bar` → `feat-foo-bar`). Apply once; reuse everywhere below.

**`<team_temp_dir>`:** `Path(tempfile.gettempdir()) / team_name` (lead resolves once to an absolute path; every shell gets that literal string).

**Roles (spawned per loop, not here):** bugfind → `code-quality-agent` opus (4.7) at xhigh effort; bugfix → `clean-coder` opus (4.7) at xhigh effort. `model="opus"` resolves to Opus 4.7 on the Anthropic API and runs at the model's default `xhigh` effort level — see [`CONSTRAINTS.md`](../CONSTRAINTS.md) § **Opus 4.7 at xhigh effort for both teammates** for rationale. **Display:** inherit `teammateMode` from `~/.claude.json`. Reference subagent types by name when spawning teammates ([`sources.md`](../sources.md) § Referencing subagent types when spawning teammates).

**Optional Groq-backed FIX path (explicit opt-in only):** when the user explicitly sets `BUGTEAM_FIX_IMPLEMENTER=groq-coder` before invocation, spawn the FIX teammate with `subagent_type="groq-coder"`. Before Step 3, `groq_bugteam.py` loads `packages/claude-dev-env/.env` when that file exists (gitignored; start from `packages/claude-dev-env/.env.example`). If `GROQ_API_KEY` is still unset after that load, stop and prompt the user to create `packages/claude-dev-env/.env` from the example path above—do not continue the Groq path without a key. Any other `BUGTEAM_FIX_IMPLEMENTER` value (or unset) keeps `clean-coder` on Opus. The FIX spawn XML in [`PROMPTS.md`](../PROMPTS.md) is identical for both implementers.

**`--bugbot-retrigger` flag:** when present on the `/bugteam` invocation, after every successful FIX push in Step 3, post an additional `bugbot run` issue comment via the Step 2.5 issue-comments fallback endpoint (`POST .../issues/{issue}/comments`) to re-trigger Cursor's bugbot on the new commit. Omit when the flag is absent.

## Step 2.5 — who posts (Path A)

**Bugfind** posts one `POST .../pulls/<n>/reviews` per loop after audit. **Bugfix** posts `.../comments/<id>/replies` after push. The **lead’s** only PR write before Step 4.5 is unchanged from `SKILL.md` (Step 4.5 body edit).

## AUDIT spawn (Path A)

After shared setup in `SKILL.md` (`mkdir`, `gh pr diff`):

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind-pr<N>-loop<L>",
  team_name="<team_name>",
  model="opus",
  description="Bugfind audit PR <N> loop <L>",
  prompt="<audit XML; see PROMPTS.md>"
)
```

Fresh `Agent` each loop; teammate context excludes lead history ([`sources.md`](../sources.md) § Teammate context isolation). [`PROMPTS.md`](../PROMPTS.md): XML + outcome schema. Lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml`, fills `loop_comment_index` per `SKILL.md`.

**Shutdown:** If `Agent` returned and the teammate already ended, skip. Otherwise:

```
SendMessage(
  to="bugfind-pr<N>-loop<L>",
  message={"type": "shutdown_request", "reason": "audit PR <N> loop <L> complete; outcome XML captured"}
)
```

`approve: false` → `error: bugfind teammate refused shutdown` → Step 4 then 5 per `SKILL.md`.

**Parallel auditors (`loop_count >= 4`):** after three full audit/fix rounds without convergence, issue three `Agent` calls in one assistant message with `team_name="<team_name>"` per `SKILL.md` § parallel variant naming (`-a` / `-b` / `-c`). Shutdown: parallel `SendMessage` to `b` and `c`, then `a`.

## FIX spawn (Path A)

```
Agent(
  subagent_type="clean-coder",
  name="bugfix-pr<N>-loop<L>",
  team_name="<team_name>",
  model="opus",
  description="Bugfix PR <N> loop <L>",
  prompt="<fix XML; see PROMPTS.md>"
)
```

**Shutdown:** same pattern as AUDIT; `SendMessage(to="bugfix-pr<N>-loop<L>", message={"type": "shutdown_request", "reason": "fix PR <N> loop <L> complete; commit <sha7> pushed"})`. `approve: false` → `error: bugfix teammate refused shutdown` → Step 4 then 5.

Verify and outcome handling: unchanged from `SKILL.md` § FIX action (**Verify**, stuck message, [`PROMPTS.md`](../PROMPTS.md)).

## Step 4 harness — after worktree remove, before shared `rmtree`

Run **after** `SKILL.md` § Step 4 step 1 (`git worktree remove` for each PR).

1. For each live teammate **spawned by this invocation**: `SendMessage(to="<name>", message={"type": "shutdown_request", "reason": "bugteam cycle ending"})`. `approve: false` on cleanup → log and continue. Teammates that pre-existed an attached team (mode `attach` or `auto` after the attach branch) are owned by the orchestrator, not this invocation — leave them alone.

2. `TeamDelete()` — **only when `team_owned=true`** (set in Step 2 lifecycle resolution). When `team_owned=false`, **skip `TeamDelete`** and log `cleanup: skipped TeamDelete (team not owned by this invocation; lifecycle=<mode>)`. The orchestrator that originally created the team owns teardown — see [Team lifecycle](../SKILL.md#team-lifecycle-path-a-only).

Then continue with `SKILL.md` § Step 4 step 3 (`<team_temp_dir>` cleanup, also gated on `team_owned`).
