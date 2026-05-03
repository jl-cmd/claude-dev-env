---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  second audit (**bugteam** always — `Skill({skill: "bugteam", ...})` when the host
  exposes `Skill`; bugteam `SKILL.md` **Path routing** picks Path A vs Path B from
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`; per-path harness in
  `bugteam/reference/workflow-path-a-orchestrated-teams.md` and
  `bugteam/reference/workflow-path-b-task-harness.md`). Each invocation runs one
  tick of work in the main session: fetches the latest reviewer state, applies
  TDD fixes for any findings, pushes one commit per tick, replies inline (or
  delegates fixes per §Multi-PR orchestration model), and re-triggers reviewers.
  Default behavior loops until back-to-back clean: pace the next tick with
  ScheduleWakeup when the harness exposes it, otherwise use the AHK
  auto-continue driver (see workflows/ahk-auto-continue-loop.md). Pacing details
  live in workflows next to SKILL.md — load exactly one per Step 4.
  Convergence requires a back-to-back clean cycle (bugbot CLEAN immediately
  followed by second-audit CLEAN with no intervening fixes), at which point the PR
  is flipped to ready for review and the loop terminates.
  Multi-PR runs persist traffic in `<TMPDIR>/pr-converge-<session_id>/state.json`
  per §Multi-PR orchestration model; single-PR-only runs may use the conversation
  state line instead. Triggers: '/pr-converge', 'drive PR to
  convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', 'converge this PR'.
---

# PR Converge

Each **invocation** runs **one tick** of the bugbot ↔ second-audit loop in the **parent session** (fetch state, address findings under the Fix
  protocol when needed, at most one fix commit per tick, inline replies or teammate handoffs, Bugbot re-trigger rules in Step 2 / Step 3).
  **By default** the skill **keeps going** until back-to-back clean on the same `HEAD`: after each tick, **Step 4** schedules the next tick with
  `ScheduleWakeup` when the tool exists, otherwise uses the **AHK auto-continue** driver. On convergence, mark the PR ready (`gh pr ready` or
  `mark_pr_ready.py` per §Step 2), then **stop all pacing** (omit further `ScheduleWakeup`; stop the AHK auto-typer when that fallback was in use).
  Default entry is **`/pr-converge`** (loops per Step 4). When the host exposes `ScheduleWakeup`, wakeups use `prompt: "/pr-converge"` unless the
  harness requires the `/loop` wrapper for wakeup execution (`workflows/schedule-wakeup-loop.md`).

## Table of contents

1. [Parent session](#parent-session)
2. [Pacing workflows (load exactly one)](#pacing-workflows-load-exactly-one)
3. [State across ticks](#state-across-ticks)
4. [Per-tick work](#per-tick-work)
   - [Step 1: Resolve current HEAD and PR context](#step-1-resolve-current-head-and-pr-context)
   - [Step 2: Branch on `phase`](#step-2-branch-on-phase)
   - [Step 3: Re-trigger bugbot](#step-3-re-trigger-bugbot)
   - [Step 4: Loop pacing](#step-4-loop-pacing)
5. [Fix protocol](#fix-protocol)
6. [Stop conditions](#stop-conditions)
7. [Ground rules](#ground-rules)
8. [Examples](#examples)

## Parent session

Use this skill on a **draft PR** where **Cursor Bugbot** and the **`/bugteam`** audit should **re-run after each push**, with
  **findings fixed between rounds**, until **back-to-back clean** on the same `HEAD`; then **mark the PR ready for review**.

Run **every converge tick** in the **parent harness session** (the conversation where the user invoked `/pr-converge`).
  **Loop pacing** (how the next tick is scheduled) is split into two workflow files — load **exactly one** per **Step 4**; see
  [Pacing workflows](#pacing-workflows-load-exactly-one).

This skill **complements** **bugteam** (same skill, **team** vs **background-agent** workflow per §Second-audit execution): it sequences Bugbot
  re-reviews, second-audit runs, the Fix protocol, and inline replies or teammate handoffs between pushes until back-to-back clean. On every
  BUGTEAM tick, run **bugteam** — never a hand-rolled substitute audit. **Fix protocol** production
  edits in the **main Cursor session** use **`Task`** with **`subagent_type: "generalPurpose"`** plus the clean-coder **Read** preamble in the **`prompt`**
  (see [Fix protocol](#fix-protocol)) - Cursor does not accept `subagent_type: "clean-coder"`. When **`state.json`** drives multi-PR orchestration,
  the **`clean-coder` teammate** path in that model is unchanged. **Loop pacing** stays
  in the **main** session when this host exposes `ScheduleWakeup`; otherwise use the AHK workflow file row below.

## Pacing workflows (load exactly one)

Before **Step 4** on each tick, **only the parent session** that is executing this skill's Step 4 (not a `Task` / `Explore` child) picks **one**
  workflow row using the steps below, then **Use the Read tool** on that row's file path next to this skill's `SKILL.md` (installed copies usually
  live under `$HOME/.claude/skills/pr-converge/`):

1. **Open the tool inventory for this turn** — every function or tool **name** the harness allows **this** assistant to invoke **in this message**
  (the same catalog that lists companions such as `Read`, `Task`, and your harness's shell or terminal tool). 
2. **`ScheduleWakeup` is invokable** if that catalog contains a **top-level** callable entry whose name is exactly **`ScheduleWakeup`**. If the
  catalog lists only indirect gateways (for example **`call_mcp_tool`** with server-qualified MCP tools inside descriptors), **`ScheduleWakeup` is
  not invokable** here unless **`ScheduleWakeup`** itself still appears as its own invocable name in that same catalog — when in doubt, **not**
  invokable.
3. **Pick the table row** — invokable → **`ScheduleWakeup` available**; otherwise → **`ScheduleWakeup` not available** (includes missing, empty, or
  unreadable catalogs: **fail closed** to the AHK workflow; do **not** attempt `ScheduleWakeup`).

| Route | Read this file |
| --- | --- |
| `ScheduleWakeup` available | `workflows/schedule-wakeup-loop.md` |
| `ScheduleWakeup` not available | `workflows/ahk-auto-continue-loop.md` |

All pacing-specific instructions for that route — delays, prompts, AHK setup, `continue` handling, convergence cleanup for the auto-typer,
  inline-lag pacing split, and route-only gotchas — live **only** in that workflow file. This `SKILL.md` keeps shared bugbot / second-audit / Fix
  protocol / stop rules.

- **`/pr-converge`** (default): loops until convergence. After each tick (unless converged or stopped), run **Step 4**, which starts by loading
  the correct workflow row from the table above.

## Progressive disclosure (skill folder)

This skill is a **folder** (`SKILL.md` plus `scripts/` plus `workflows/`): wrappers centralize gh pagination and body-file rules so the model composes orchestration instead of re-deriving CLI footguns. Read in this order ([Anthropic — internal patterns for Claude Code skills](https://x.com/trq212/status/2033949937936085378)):

1. This `SKILL.md` — phase graph, teammate contracts, stop conditions.
2. [`scripts/README.md`](scripts/README.md) — argv, stdout JSON shapes, pointers to `../../rules/gh-paginate.md` and `../../rules/gh-body-file.md`.
3. [`../bugteam/reference/workflow-path-b-task-harness.md`](../bugteam/reference/workflow-path-b-task-harness.md) **on demand** — bugteam **Path B** harness only (read after bugteam `SKILL.md` **Path routing** selects Path B). Path A harness: [`../bugteam/reference/workflow-path-a-orchestrated-teams.md`](../bugteam/reference/workflow-path-a-orchestrated-teams.md).
4. Individual script source or `--help` — only when a call fails or `${CLAUDE_SKILL_DIR}` resolves unexpectedly.

Taxonomy: **CI/CD & Deployment** in the [`babysit-pr` archetype](https://x.com/trq212/status/2033949937936085378) — monitors a PR, applies fixes between reviewer ticks, and flips it ready-for-review on convergence. If the doc feels broad, use **§Multi-PR orchestration model** as the workflow spine and **§Per-tick work** as the single-PR linearization.

## Gotchas

Non-default behaviors worth burning in; add a bullet here when a real run fails in a new way ([same source](https://x.com/trq212/status/2033949937936085378)):

- **`ScheduleWakeup` is not in subagent tool registries** — a background `general-purpose` tick cannot schedule the next re-entry; only the parent session where this skill runs with `ScheduleWakeup` in the tool registry can call it.
- **Bugbot only recognizes the literal re-trigger phrase `bugbot run`** — other comment text no-ops; prefer `trigger_bugbot.py` (temp body file) or
  the bundled `scripts/post-bugbot-run.ps1` so backticks in prose never corrupt the PR comment.
- **Review body and inline comments can desync for the same `commit_id`** — “dirty body, zero inline rows at `current_head`” is **`inline_lag`**, not **`dirty`**; bump `inline_lag_streak`, wait 60s, retry fetch (Step 2 BUGBOT fourth branch; §Fix result → general-purpose steps 4c–4e).
- **`state.json` without the §Concurrency lock loses merges** when several teammates finish in one wall-clock window.
- **`tick_count` must not double-increment** — conversation line (Step 1) only when **no** `state.json`; with `state.json`, only the orchestrator bump in §Orchestrator `state.json` writes increments `tick_count`.

## Second-audit execution (bugteam — Path A vs Path B)

The **second audit** (BUGTEAM phase) is **always** the **bugteam** skill: preflight, CODE_RULES gate, **`code-quality-agent`** / **`clean-coder`** loop,
  audit rubric, outcome shape, and Step 2 BUGTEAM §(b)–(d) contract all live in [`../bugteam/SKILL.md`](../bugteam/SKILL.md) plus `PROMPTS.md` /
  `EXAMPLES.md` / `CONSTRAINTS.md` — do not re-spec them here.

**Path routing is bugteam-internal:** [bugteam `SKILL.md` — Path routing](../bugteam/SKILL.md#path-routing-mandatory-first-branch) (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` equals **`1`** → Path A orchestrated teams; otherwise → Path B Task harness). **Harness-only** execution: Path A — [`../bugteam/reference/workflow-path-a-orchestrated-teams.md`](../bugteam/reference/workflow-path-a-orchestrated-teams.md); Path B — [`../bugteam/reference/workflow-path-b-task-harness.md`](../bugteam/reference/workflow-path-b-task-harness.md).

**pr-converge rule:** Prefer **`Skill({skill: "bugteam", args: "<PR URL or args>"})`** wherever the tool registry exposes `Skill` — bugteam executes the correct path. When **`Skill` is not invokable** (typical delegated teammate), that worker still runs **bugteam** by loading **`../bugteam/SKILL.md`** from the same checkout and following **Path routing** plus [`../bugteam/reference/workflow-path-b-task-harness.md`](../bugteam/reference/workflow-path-b-task-harness.md) when Path B applies; never replace bugteam with a hand-rolled audit.

### Team infrastructure detection (for pr-converge pacing and docs cross-links only)

This mirrors bugteam **Path routing** so pr-converge prose stays aligned with host capability checks elsewhere in this file:

- **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` == `1`** (trimmed) → bugteam **Path A** when `/bugteam` runs inside Claude Code with teams.
- **Otherwise** → bugteam **Path B** Task harness inside the same bugteam `SKILL.md` contract.

## Multi-PR orchestration model

### Core rule: orchestrator is a traffic controller only

The orchestrator (main session) **never** reads **repository source files**, writes code, audits findings, or does any per-PR **codebase** work inline. It **always** reads `state.json` for traffic state and may write only the narrow fields in §Orchestrator `state.json` writes; it receives teammate handoffs and spawns the next worker. Every unit of audit/fix work runs inside a dedicated teammate.

This is a [workflow-style skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#use-workflows-for-complex-tasks): the orchestrator decomposes the multi-PR problem into parallel per-PR subworkflows, each owned by a short-lived teammate. The orchestrator's only job is to keep the state file consistent and spawn the next agent in each chain.

### Per-PR state file

Create once at session start; each teammate writes its result back before going idle:

**Path:** `<TMPDIR>/pr-converge-<session_id>/state.json`

**Session ID:** `YYYYMMDDHHMMSS` captured once when the loop starts.

**Directory lifecycle:** Keep `<TMPDIR>/pr-converge-<session_id>/` for the **whole converge run** (every tick) until **each** `prs[...]` is
  **`converged`** or **`blocked`**, or the user stops. **Then** delete that folder if you want reclaim — **`mark_pr_ready.py` / `gh pr ready`** on
  GitHub is the canonical record of ready state. See [Memory](#memory) for the optional append-only log in the same directory.

**Barebones schema:**

```json
{
  "session_id": "20260502050000",
  "prs": {
    "289": {
      "owner": "jl-cmd",
      "repo": "claude-code-config",
      "branch": "feat/shared-pr-loop-extraction",
      "phase": "BUGBOT",
      "current_head": "f9a7d49e",
      "bugbot_clean_at": null,
      "inline_lag_streak": 0,
      "tick_count": 5,
      "last_action": "bugbot_triggered",
      "status": "in_progress",
      "last_updated": "2026-05-02T10:00:00Z"
    }
  }
}
```

**`status` values:** `fresh` | `in_progress` | `awaiting_bugbot` | `awaiting_bugteam` | `converged` | `blocked`

**Write rule:** Teammates write their result by reading the current file, merging **only** their PR's keyed entry under `prs`, and persisting the merged document back. Writes are keyed on `pr_number`; other PRs' entries are untouched in the merge logic — **but** see **Concurrency** below so parallel teammates never clobber each other.

**Concurrency (mandatory):** When multiple teammates can finish in the same wall-clock window (including the case where **10+** idle notifications arrive together), a naive read–modify–write on `state.json` **loses updates** (two writers read the same revision; the second `write` overwrites the first). Every `state.json` update from a teammate **must** use **serialized access** plus **atomic publish**:

1. **Acquire** an exclusive lock in the same directory as `state.json`, for example a sibling path `state.json.lock` created with an **atomic create-only** primitive (`mkdir` on Unix when the path does not exist; on Windows `New-Item` / `md` guarded so only one creator succeeds, or a host file lock API). If acquisition fails because the lock exists, sleep with jitter and **retry** until held (cap retries and escalate per **Stop conditions** if the lock never clears — indicates a stuck teammate).
2. **Read** `state.json`, merge this teammate's `prs[<pr_number>]` object only, then **write** the full merged JSON to `state.json.tmp` in that directory.
3. **Replace** `state.json` atomically from `state.json.tmp` (`os.replace` / same-volume rename semantics so readers never see a half-written file).
4. **Release** the lock (`rmdir` / `Remove-Item` on the lock path).

**Orchestrator `state.json` writes (traffic metadata only):** Teammates own audit/fix payloads. The orchestrator **must not** merge finding bodies, file contents, or teammate-owned fields other than the two narrow exceptions below. It **must** use the **same §Concurrency lock** for any orchestrator write.

1. **Per-tick `tick_count` bump (mandatory):** At the **start** of each orchestrator tick, before spawning teammates for that tick, perform one locked read–merge–atomic publish: for **every** `prs[<pr_number>]` whose `status` is **not** `converged` or `blocked`, increment `tick_count` by **1** (initialize to `0` if missing) and refresh `last_updated`. This is for human-readable progress only — there is **no** tick ceiling; the loop ends only on convergence or a **Stop conditions** branch.
2. **`phase` when only the orchestrator decides:** If the orchestrator applies a **Step 2 §Per-tick** phase transition (including **BUGTEAM §(d)** branches that set `phase = BUGBOT` without an immediate teammate `state.json` write) and no teammate merge occurs in the same tick for that PR, the orchestrator performs one locked merge that sets only `prs[<pr_number>].phase` (and `last_updated`) for the affected PR.

**Orchestrator reads this file at the start of every tick** instead of relying on conversation context for cross-PR state.

### Teammate spawning rules

When the orchestrator receives results from one or more PRs simultaneously (e.g. 10+ teammate idle notifications arrive together), it spawns one new agent **per PR** in a single parallel message — never processes any PR inline.

#### Audit result → fix worker per PR

When a bugfind teammate reports completion (findings or clean):

- Spawn **one fix worker per PR** with findings (Claude Code: `clean-coder` teammate / `Agent`; Cursor `Task`: `generalPurpose` + clean-coder **Read** preamble per [Fix protocol](#fix-protocol)). That worker:
  1. Reads the outcomes XML for the PR.
  2. Applies TDD fixes (test first, then production code).
  3. Commits and pushes one fix commit.
  4. Replies inline to each addressed finding comment via `reply_to_inline_comment.py`.
  5. **Writes its result to `state.json`** (per §Concurrency) (`last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"`, `status: "awaiting_bugbot"`, `last_updated` as an ISO-8601 UTC timestamp).
  6. Goes idle.

- For PRs with zero findings: spawn **one `general-purpose` agent** per PR. That agent:
  1. If `bugbot_clean_at == current_head` (back-to-back clean): run `mark_pr_ready.py`, append one convergence row to `<TMPDIR>/pr-converge-<session_id>/converged.log` per §Memory (same `session_id` as `state.json`), then **write `state.json`** (per §Concurrency) setting this PR's entry to at least `status: "converged"`, `last_action: "converged"` (or `marked_ready`), `phase: "BUGBOT"`, and `last_updated` to an ISO-8601 UTC timestamp — **before** going idle. Omitting this write leaves the orchestrator on later ticks with a stale `awaiting_bugteam` / `in_progress` row and risks duplicate work.
  2. Otherwise: update `state.json` (per §Concurrency) with `last_action: "audit_clean"`, `status: "awaiting_bugbot"`, `phase: "BUGBOT"`, then trigger bugbot via `trigger_bugbot.py`.
  3. Goes idle.

#### Fix result → general-purpose per PR

When a bugfix (clean-coder) teammate goes idle after pushing a fix:

- Spawn **one `general-purpose` agent** per PR. That agent:
  1. Reads `state.json` for its PR.
  2. Triggers bugbot via `trigger_bugbot.py`.
  3. Polls `fetch_bugbot_reviews.py` every 60s (up to 10 polls) until a review anchored to `current_head` appears.
  4. **Poll / classify loop** (repeat from **4a** whenever **4c** schedules a retry):
     - **4a.** Fetches inline comments via `fetch_bugbot_inline_comments.py`.
     - **4b.** Classify — same three outcomes as Step 2 BUGBOT once a review exists at `current_head`:
       - **`clean`:** Review body indicates clean against `current_head` and zero unaddressed inline findings.
       - **`dirty`:** At least one unaddressed inline finding for `current_head` (actionable for the Fix protocol / `clean-coder`).
       - **`inline_lag`:** Review body indicates findings against `current_head`, but the inline-comments API returns zero matching comments for `current_head` (transient desync between review body and inline API — Step 2 BUGBOT fourth bullet).
     - **4c.** **If `inline_lag`:** Locked merge to `state.json` (per §Concurrency): increment `inline_lag_streak` (treat missing as `0` before increment); set `last_action: "inline_lag_wait"`, `phase: "BUGBOT"`, `last_updated`, and keep `status` consistent with monitoring (for example `awaiting_bugbot`). If `inline_lag_streak >= 3`, **hard blocker** per §Stop conditions (structurally inconsistent review); report and go idle **without** classifying as `dirty`. Otherwise sleep **60 seconds** and repeat from **4a** (re-fetch inline only — do not re-run step 2 or step 3).
     - **4d.** **If `clean`:** Exit the loop. Locked merge: set `bugbot_clean_at` to `current_head`, reset `inline_lag_streak` to `0`, update `last_action`, `status`, and **`phase`: `BUGTEAM`** (next work is second audit).
     - **4e.** **If `dirty`:** Exit the loop. Locked merge: reset `inline_lag_streak` to `0`, record findings count, update `last_action`, `status`, and **`phase`: `BUGBOT`** (next work is another fix pass).
  5. Reports back to orchestrator: one-line summary of outcome.

- Orchestrator reads the updated `state.json` and spawns the appropriate next agent:
  - Result `clean` → spawn a `general-purpose` agent to run BUGTEAM phase (**bugteam** via `Skill` when available in that worker’s registry, else inline bugteam `SKILL.md` + Path B deltas per §Second-audit execution).
  - Monitor exited on **`dirty` (step 4e)** with actionable inline threads → spawn the same **fix worker** (same as "audit result with findings" above). Do **not** spawn `clean-coder` when the monitor only saw **`inline_lag`** (4c retries) without reaching **4e** — that path retries or escalates via the **`inline_lag_streak` ≥ 3** hard blocker in **Stop conditions** instead of a fix pass.

### What the orchestrator does per tick

1. Perform the **per-tick `tick_count` bump** in §Orchestrator `state.json` writes (traffic metadata only) for every non-terminal PR under `prs`.
2. Read `state.json`.
3. For each PR with new teammate results (idle notifications), spawn the next agent per the rules above — all in one parallel message.
4. Re-read `state.json` if needed for scheduling.
5. Call `ScheduleWakeup` with the appropriate delay.
6. Nothing else.

## Memory

**Run directory** `<TMPDIR>/pr-converge-<session_id>/` (same `session_id` as §Per-PR state file) holds **`state.json`** and optional **`converged.log`**.
  Treat both as **durable for this converge run**: keep them from first create through **every tick** until **each** PR under `prs` is **`converged`**
  or **`blocked`**, or a **Stop conditions** branch ends the loop. **After** that, deleting the whole directory is safe — **`mark_pr_ready.py` /
  `gh pr ready`** on GitHub is the canonical record of ready state. This skill is a **folder skill**, not a Cursor plugin package; do **not** rely on
  `${CLAUDE_PLUGIN_DATA}`. OS or disk cleanup of `<TMPDIR>` (reboot, policy) can still remove files mid-run; that is environmental risk, not intentional
  behavior of this spec.

**`converged.log` (multi-PR only — requires `state.json`):**

- **Path:** `<TMPDIR>/pr-converge-<session_id>/converged.log` (sibling of `state.json`).
- **Format:** one tab-separated row per converged PR — `<ISO8601_UTC>\t<owner>/<repo>#<number>\tbugbot=<SHA>\t<SECOND_AUDIT_LABEL>=<SHA>` where `<SECOND_AUDIT_LABEL>` is always `bugteam` (second audit is the bugteam skill) per §Second-audit execution.
- **Append site:** the agent that runs `mark_pr_ready.py` (see §Audit result → general-purpose convergence branch and Step 2 BUGTEAM second branch). Append **before** the locked `state.json` publish so the log row survives a failed or retried merge.
- **Never read inside the loop.** The orchestrator and teammates never gate behavior on this file; it is for the user and follow-up tooling only.

**Single-PR runs without `state.json`:** do **not** append `converged.log`; the in-conversation summary plus GitHub ready state are enough.

## Invocation modes

- **`/pr-converge`** (default): runs **one tick**, then **Step 4** per [Pacing workflows](#pacing-workflows-load-exactly-one) — same loop-until-convergence semantics whether the user typed it once, a `ScheduleWakeup` fires with `prompt: "/pr-converge"`, or AHK sends `continue` (`workflows/schedule-wakeup-loop.md`, `workflows/ahk-auto-continue-loop.md`). Omit the next wakeup only on convergence or another **Stop conditions** branch.
- **`/loop /pr-converge`**: optional **harness wrapper** when the parent only executes wakeup `prompt`s that are routed through the `/loop` skill; behavior is equivalent to default `/pr-converge` for per-tick work and Step 4. Use `prompt: "/loop /pr-converge"` in `ScheduleWakeup` only when that wrapper is required for the next firing to run.

## State across ticks

**Dual persistence:** When `<TMPDIR>/pr-converge-<session_id>/state.json` exists (multi-PR or file-backed session per §Multi-PR orchestration model),
  the orchestrator and teammates treat **that file** as the source of truth for `phase`, heads, counters, and status — not the conversation
  transcript. When **no** `state.json` is in use (typical single-PR `/pr-converge` in Cursor), track the following **in each assistant turn as plain
  text** so the **next tick that resumes in this transcript** can re-read them from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against
  `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick (observability only; no ceiling).

Each tick begins by reading the prior tick's state line from the most recent assistant message (when **no** `state.json`) and ends by emitting the
  updated state line; when `state.json` is in use, follow §What the orchestrator does per tick instead.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read the prior tick's state line from the most recent assistant message (or initialize all fields if none). **Increment `tick_count` by 1** in the **conversation state line** when **no** `state.json` is in use (single-PR-only invocation); when `state.json` exists, **do not** increment here — the orchestrator's per-tick bump in §Orchestrator `state.json` writes is the sole increment for that store.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/view_pr_context.py"
```

Output is a JSON object with `number`, `url`, `headRefOid`, `baseRefName`, `headRefName`, `isDraft`. Capture `number` (`<NUMBER>`), `headRefOid` (`current_head`), owner/repo (from `url`), branch name (`<BRANCH>`).

### Step 2: Branch on `phase`

#### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first and walk backwards until the first clean review. The script enforces the gh-paginate rule (uses `--paginate --slurp` plus Python JSON handling — see [`scripts/README.md`](scripts/README.md) and [`../../rules/gh-paginate.md`](../../rules/gh-paginate.md)) and classifies each review:

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER>
   ```

   Output is a JSON array of `{review_id, commit_id, submitted_at, body, classification}`, newest-first, with `classification` already set to `"dirty"` or `"clean"`. Track dirty entries in a temp file as you walk; the Fix protocol reads it back later in this tick:

   ```bash
   dirty_reviews_path=$(mktemp "${TMPDIR:-/tmp}/pr-converge-bugbot.XXXXXX")
   : > "$dirty_reviews_path"
   ```

   Iterate from index 0 (most recent) toward older entries:

   - For a dirty review, append one JSON line to `$dirty_reviews_path` with `{review_id, commit_id, submitted_at, body}`.
   - Stop at the first clean review. Older reviews are presumed addressed at that clean checkpoint and are not re-read.
   - When index 0 is itself clean, `$dirty_reviews_path` stays empty.

   Capture `commit_id`, `submitted_at`, body, and `classification` of the index-0 review for the decision branches below. When a branch routes to the **Fix protocol**, read every entry from `$dirty_reviews_path` and address all of them — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` for the **newest submitted Bugbot review** on `current_head`. The script enforces the same `--paginate --slurp` pattern as `fetch_bugbot_reviews.py`, resolves that review via the reviews list, then returns only inline rows whose `pull_request_review_id` matches that review (so stale threads from an older Bugbot review on the same SHA are excluded).

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_inline_comments.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER> --commit "$current_head"
   ```

   Output is a JSON array of `{comment_id, commit_id, path, line, body}` for those matching inline comments.

c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set
     `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at
     = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to BUGTEAM in this same tick — back-to-back
     convergence requires the second audit on the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix
     protocol** below. Reset `inline_lag_streak = 0`. When **`state.json`** is in use, the clean-coder teammate pushes, replies inline, writes
     `state.json`, then goes idle; **Step 3** (`trigger_bugbot.py` on the new HEAD) runs **after** via the orchestrator-spawned follow-up agent
     (§Fix result → general-purpose). When **no** `state.json` (typical single-PR Cursor tick), complete implement → push → inline replies → Step 3
     in the same tick per your loaded pacing workflow. Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments
     for `current_head`:** Treat as transient API propagation lag. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard
     blocker; report and terminate with no loop pacing; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` if that path was active.
     Otherwise complete **Step 4** using the **BUGBOT inline-lag** section of the pacing workflow you loaded ([Pacing workflows](#pacing-workflows-load-exactly-one)); if no workflow file applies, schedule the next wakeup at `delaySeconds: 60`.

**Gotcha (Bugbot already clean on `HEAD`, but another `bugbot run` fires):** When the latest Bugbot review on `current_head` already indicates
  **clean / no issues** (the branch that sets `bugbot_clean_at` and transitions to **`phase = BUGTEAM`**), the next action must be the **second
  audit in the same tick** per §Second-audit execution — never a redundant `bugbot run`. If merged findings require commits, continue with **Fix
  protocol** per [Fix protocol](#fix-protocol) (`Task` with `generalPurpose` and the clean-coder **Read** preamble). If **`Task`** cannot be invoked, STOP and notify the user.

#### `phase == BUGTEAM`

a. Run **bugteam** (second audit) on the current PR.

   - **When `Skill` is invokable** (see [Pacing workflows](#pacing-workflows-load-exactly-one) tool-inventory rules — same session): invoke **bugteam** with the `Skill` tool. Path A vs Path B is selected **inside** bugteam per [bugteam Path routing](../bugteam/SKILL.md#path-routing-mandatory-first-branch); pr-converge does not branch on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` here.

     ```
     Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

     Wait for completion; capture exit and final summary (convergence vs findings) for Step **(c)**.

   - **When `Skill` is not invokable** (typical `Task` teammate): that worker executes **bugteam** by reading [`../bugteam/SKILL.md`](../bugteam/SKILL.md) and, if Path B applies, [`../bugteam/reference/workflow-path-b-task-harness.md`](../bugteam/reference/workflow-path-b-task-harness.md) — same **`code-quality-agent`** / **`clean-coder`** loop and gates as Path A; only harness steps differ per that workflow file.

b. **Re-resolve current HEAD now** because the second audit may have pushed commits during its run. The `current_head` from Step 1 is potentially
  stale at this point:
   ```bash
   new_head=$(python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER>)
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits invalidate bugbot's prior clean.

c. Inspect the bugteam outcome. It reports either `convergence (zero findings)` or a list of unfixed findings with file:line (same semantics for both bugteam workflows).

d. Decide based on the (post-second-audit) state — order matters; check pushed-during-second-audit FIRST so a convergence report against a stale HEAD never falsely terminates:
   - **Second audit pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return.
   - **Second audit reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Prefer:
     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
       --owner <OWNER> --repo <REPO> --number <NUMBER>
     ```
     When scripts are unavailable, `gh pr ready <NUMBER> --repo <OWNER>/<REPO>` is an equivalent human-visible outcome. When `state.json` is in use, append the convergence row to `<TMPDIR>/pr-converge-<session_id>/converged.log` per §Memory; when not, skip file append. Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, <SECOND_AUDIT_LABEL> CLEAN at <SHA>; marked ready for review` where `<SECOND_AUDIT_LABEL>` is always **`bugteam`** (second audit is the bugteam skill on Path A and Path B; background `Task` workers still execute that skill per `workflow-path-b-task-harness.md` when Path B applies). **Omit loop pacing** per the **Convergence** section of whichever pacing workflow was active.
   - **Second audit reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Transition `phase = BUGBOT`, schedule next wakeup, return.
   - **Second audit reports findings without committing fixes:** apply the **Fix protocol** below; **Step 3** on the new HEAD runs after fix handoff per §Multi-PR or in-tick for single-PR. Transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. Prefer the portable script (temp body file, `gh pr comment --body-file`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

**Bundled PowerShell alternative** (same gh-body-file contract):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"
```

Shorthand `owner/repo#number`:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "<OWNER>/<REPO>#<NUMBER>"
```

Explicit repository and number:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" -Repository "<OWNER>/<REPO>" -Number <NUMBER>
```

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

If you cannot run the scripts above, use the Write tool to a temp file, then `gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path>` yourself.
  The body file must contain exactly the literal phrase `bugbot run` followed by a newline — empirically the only re-trigger Cursor Bugbot
  recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while a review is already queued):** Do not post another `bugbot run` when Bugbot has already picked up the latest trigger. On GitHub, the bugbot review signal is an **eyes** (`:eyes:`) reaction on the **most recent** `bugbot run` PR comment (Bugbot acknowledging the job). When that reaction is present, skip Step 3 for this wait cycle — a second comment spams the PR and can confuse tick logic; wait for the review to finish or for `HEAD` to change before re-triggering per Step 2.

**Default loop:** After each tick, run **Step 4** whenever pacing still applies — meaning convergence has not yet omitted pacing and no **Stop conditions** branch has omitted pacing for this tick. That rule covers the **first** user-typed **`/pr-converge`** the same as later wakeups or `continue` ticks: each invocation completes one tick, then **Step 4** loads the pacing workflow and schedules the next entry when the workflow says to. For **`ScheduleWakeup`**, set **`prompt: "/pr-converge"`** by default (`workflows/schedule-wakeup-loop.md`); set **`prompt: "/loop /pr-converge"`** when the harness requires the `/loop` wrapper for the next firing to execute.

When **`ScheduleWakeup` is unavailable**, run **Step 4** on the AHK workflow row; that path keeps **`/pr-converge`** on loop-until-done semantics per `workflows/ahk-auto-continue-loop.md`. When **no** pacing mechanism is active (no `ScheduleWakeup` tool and AHK not started per that file), end the tick with **return** only — there is nothing to schedule. Elsewhere, **schedule next wakeup, return** means run **Step 4** below; when Step 4 schedules nothing, treat that phrase as **return** only.

**Gotcha (Bugbot found errors, but a redundant `bugbot run` instead of a fix push):** When the latest Bugbot review on `current_head` still has
  **unaddressed findings** (inline threads and/or a non-clean review body), **do not** post another `bugbot run` on that same SHA as a
  substitute for fixing the code. A second trigger without a new commit cannot resolve the findings — it only duplicates noise and breaks tick
  expectations. Follow the **Fix protocol** end-to-end: spawn **`Task`** with **`subagent_type: "generalPurpose"`** and the clean-coder **Read** preamble from [Fix protocol](#fix-protocol) (never ad-hoc shell or a bare `generalPurpose` prompt for production edits), **commit and push** with mandatory pre-commit and pre-push hook validation (full stop and notify the user if hooks did not
  run or were bypassed), reply inline on each thread, **then** Step 3 `bugbot run` against the new SHA.

### Step 4: Loop pacing

**`ScheduleWakeup` field hints** (when not using the workflow files — not recommended; prefer [Pacing workflows](#pacing-workflows-load-exactly-one)):

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by **Step 3** after a fix via the follow-up agent chain, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/pr-converge"` — default; re-enters this skill on the next firing with default loop semantics. If the harness requires the `/loop` wrapper for wakeups, `prompt: "/loop /pr-converge"` is equivalent (`workflows/schedule-wakeup-loop.md`).

Throughout Step 2 and the Fix protocol, **schedule next wakeup, return** means: load the correct pacing workflow (see
  [Pacing workflows](#pacing-workflows-load-exactly-one)), then execute **Step 4** exactly as that file specifies (pace the next tick, then
  return).

**Entry paths** include `/pr-converge`, `/loop /pr-converge` when the harness uses that wrapper, an AHK `continue` tick, or a `ScheduleWakeup` whose `prompt` is `/pr-converge` or `/loop /pr-converge` per the schedule-wakeup workflow.

**On convergence:** apply the **Convergence** section of the **same** pacing workflow file you are using for this session (omit wakeups / stop
  AHK per that file).

## Fix protocol

### Cursor `Task` registry (single-PR / Cursor host)

Cursor's **`Task`** tool validates `subagent_type` against a **fixed enum**; **`"clean-coder"` is not a valid value**. When **no** `state.json` is in use
  (typical single-PR Cursor tick), **production edits** use **`Task`** with **`subagent_type: "generalPurpose"`** and the clean-coder contract in the **`prompt`**
  per the **Implement** bullet below - not a separate `clean-coder` spawn.

The fix protocol is executed by a **`clean-coder` teammate** when **`state.json`** drives the session (§Multi-PR orchestration model), or by the **`Task` + `generalPurpose`** path in the **main session** when **no** `state.json` is in use (typical single-PR Cursor). The orchestrator **never** performs production edits inline in multi-PR mode. Pre-commit and pre-push hook handling is governed by §Ground rules and the gates below.

**Multi-PR (`state.json`) teammate obligations** (in addition to TDD, commit, push):

- Replies inline on each addressed finding thread via `reply_to_inline_comment.py` (what changed and the commit identifier), matching §Audit result → fix worker step 4 — **before** writing `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"`, `status: "awaiting_bugbot"`, and `last_updated` (ISO-8601 UTC) to `state.json` (per §Concurrency).
- Goes idle. The orchestrator spawns the follow-up `general-purpose` agent for bugbot trigger and monitoring.

**The orchestrator does not reply to inline comments, does not trigger bugbot, and does not read repository source files during the fix phase** when the multi-PR model is active.

**Single-PR (no `state.json`) — same gates, main session executor:**

- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the fix.
- **Implement** by invoking **`Task`** with **`subagent_type: "generalPurpose"`**. The **`prompt`** MUST begin by requiring the subagent to **Read** the clean-coder agent markdown **before** editing production files: on macOS/Linux `$HOME/.claude/agents/clean-coder.md`, on Windows `%USERPROFILE%\.claude\agents\clean-coder.md`. The prompt MUST state that file is binding for code generation (naming, TDD when behavior changes, hook-safe single commit, scope limited to the listed findings). Do **not** use ad-hoc shell edits for production code on this path. Do **not** emit a bare `generalPurpose` prompt that omits the clean-coder file step. If **`Task`** cannot be invoked, **full stop** and tell the user – do not substitute another subagent type for production edits.
- Stage the affected files and create one new commit on the existing branch:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  **Pre-commit gate:** Never pass `--no-verify`, `--no-gpg-sign` (unless the user has explicitly required otherwise), or any flag that skips hooks. After `git commit`, confirm from the **same terminal transcript** that the **pre-commit** hook ran (visible hook output or your configured hook runner's success banner) and exited **0**. If the transcript shows hooks were **skipped**, **bypassed**, or **did not run** when your repo expects them, **full stop** — do not push, do not reply inline, do not trigger Bugbot — and notify the user with what you observed. When a hook **rejects** (non-zero exit), read the message, fix the cause, retry commit until hooks pass.
- Push the new commit:
  ```bash
  git push origin <BRANCH>
  ```
  **Pre-push gate:** Never pass `--no-verify` or equivalent. After `git push`, confirm from the **same terminal transcript** that **pre-push** ran (when your repo defines a pre-push hook) and exited **0**. If push output shows pre-push was **skipped**, **bypassed**, or **absent** when it should have run, **full stop** — do not update `current_head`, do not reply inline, do not trigger Bugbot — and notify the user. Capture the new HEAD SHA only after both gates pass. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per gh-body-file rule):
  ```bash
  gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments/<comment_id>/replies \
    --field body=@<path/to/reply.md>
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same tick** when you would otherwise wait for Bugbot — regardless of which phase originated the findings. Step 3 is the **mechanism** that restarts Bugbot on the new `HEAD`, but the **meaning** is broader: a new commit **resets the full convergence cycle**. Prior bugbot clean and prior second-audit clean on an older SHA **do not** count toward convergence on the new `HEAD`. You must **again** obtain **bugbot CLEAN** on `current_head`, then **second-audit CLEAN** on that same `HEAD` with **no intervening push** (the same back-to-back rule as Step 2). Re-triggering Bugbot in the same tick after the push saves a full wakeup cycle compared to deferring Step 3 to the next tick.

## Stop conditions

- **Convergence** (back-to-back clean — second audit reports convergence AND `bugbot_clean_at == current_head` with no push during this tick): prefer `mark_pr_ready.py`; when unavailable use `gh pr ready`. When `state.json` is in use, append the convergence row to `<TMPDIR>/pr-converge-<session_id>/converged.log` per §Memory; otherwise skip file append. Report one-sentence summary, then **omit loop pacing** per **Convergence** in the pacing workflow from the Step 4 table (or omit `ScheduleWakeup` when no workflow file applies). End any ongoing loops once all PRs are converged.
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or **bugteam** (either workflow) reports a stuck state. Report the specific blocker and the diagnosis, then **omit loop pacing** per the active workflow; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.
- **User stops the loop:** user says "stop the converge loop" → **omit loop pacing** per the active workflow; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.

## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **Bugbot findings on the current SHA mean fix-then-push-then-`bugbot run`, not another naked `bugbot run`.** Unaddressed Bugbot errors require the Fix protocol before Step 3; posting `bugbot run` again without a new commit does not clear the review state.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires Bugbot clean and **bugteam** clean (team or background-agent workflow) against the same HEAD with no intervening fixes; either side clean alone counts as in-progress.
- **Clean Bugbot on `HEAD` means advance to second audit, not another `bugbot run`.** After Bugbot reports clean on the current SHA, set `bugbot_clean_at` and run the BUGTEAM phase per Step 2 — never post `bugbot run` as a substitute.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings silently no-op.
- **`gh pr ready` / `mark_pr_ready.py` is the convergence action.** Mark the PR ready for review and stop there. Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.
- **Adapt when reality contradicts on-disk state.** This skill is a state machine, but the spec assumes `state.json` (when used) and `git`/`gh` agree with the live PR. When they diverge — the user pushed manually between ticks, the branch was force-reset, the worktree moved, the PR was closed/merged externally, or `gh` auth dropped mid-tick — **do not execute the spec literally against stale state**. Report the specific drift and escalate as a hard blocker per §Stop conditions; let the user decide whether to reset the loop, refresh credentials, or stop.

## Examples

<example>
User: `/pr-converge`
Claude: [PR context + one tick of bugbot/bugteam work; then Step 4 per loaded pacing workflow — default loop until convergence or stop]
</example>

<example>
User: `/loop /pr-converge`
Claude: [same per-tick work and Step 4 as bare `/pr-converge` — harness wrapper only when the host routes wakeups through `/loop`]
</example>

<example>
Tick fires in BUGBOT phase, latest bugbot review is against an older commit.
Claude: [posts `bugbot run` comment, sets `bugbot_clean_at = null`, completes Step 4 per `workflows/schedule-wakeup-loop.md` when on that path
  (e.g. 270s wakeup), returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot has 2 unaddressed findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads, posts `bugbot run`, Step 4 per schedule-wakeup workflow at 270s
  when on that path, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot is clean against HEAD.
Claude: [sets `bugbot_clean_at = HEAD`, transitions `phase = BUGTEAM`, runs `Skill({skill: "bugteam", ...})` in the same tick — bugteam Path routing picks Path A vs Path B internally]
</example>

<example>
In BUGTEAM phase, bugteam (team workflow) reports convergence and `bugbot_clean_at == current_head`.
Claude: [runs `gh pr ready <NUMBER>`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", applies
  **Convergence** from the active pacing workflow]
</example>

<example>
In BUGTEAM phase, bugteam pushed a fix commit during its run.
Claude: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, Step 4 per
  schedule-wakeup workflow at 270s when on that path]
</example>

<example>
Tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching
  comments for `current_head`.
Claude: [increments `inline_lag_streak` to 1, Step 4 inline-lag rules from the active pacing workflow (60s `ScheduleWakeup` vs AHK cadence),
  returns; expects inline comments on the next tick]
</example>

<example>
BUGTEAM tick with no agent teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is unset; bugteam Path B applies inside `Skill({skill: "bugteam", ...})`.
Claude: [invokes bugteam; bugteam runs Path B per `bugteam/SKILL.md` + `bugteam/reference/workflow-path-b-task-harness.md`; applies Step 2 §(b)–(d) unchanged against the skill outcome]
</example>
