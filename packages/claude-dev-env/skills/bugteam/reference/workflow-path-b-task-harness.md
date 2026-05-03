# Bugteam — Path B workflow (Task harness)

Load when bugteam `SKILL.md` **Path routing** selects **Path B** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is not exactly **`1`** after trim — typical Cursor IDE). Execute **after** shared `SKILL.md` steps through **Step 2 loop state**. **Do not** run `TeamCreate` or `TeamDelete`. Harness substitutions vs Path A:

| Path A | Path B |
| --- | --- |
| `TeamCreate(...)` | **Omit.** |
| `Agent(..., team_name=..., ...)` | **`Task`** (or host-equivalent) with the same `model` and prompt contracts as Path A — **omit** `team_name`. `subagent_type` follows this file's **AUDIT** / **FIX spawn** sections (Claude Code: `code-quality-agent` / `clean-coder`; Cursor: `code-quality-agent` / `generalPurpose` + mandatory `clean-coder.md` **Read** on FIX when the enum rejects `clean-coder`). |
| `SendMessage` shutdown | **Omit.** Await Task completion. |
| `TeamDelete()` | **Omit.** |
| Three parallel `Agent` (`loop_count >= 4`) | Three parallel **`Task`** with `subagent_type="code-quality-agent"`; merge outcomes in the lead like Path A `-a`/`-b`/`-c`. |

## Step 2 harness — Path B

No `TeamCreate`. After shared `SKILL.md` **Step 1** completes (PR scope **and** `<team_temp_dir>/pr-<N>/` per Step 1 items 1–3 there), use the same `team_name` string only as a **logical label** for paths under that `<team_temp_dir>`; do not pass `team_name` into spawns.

**`--bugbot-retrigger` flag:** same as Path A [`workflow-path-a-orchestrated-teams.md`](workflow-path-a-orchestrated-teams.md) § Step 2 harness — the **lead** posts the issue comment after each successful FIX push when the flag is present.

## Step 2.5 — who posts (Path B)

The **lead** runs the **same** `gh api` / `jq` sequences as `SKILL.md` **Step 2.5** after reading each **`Task`** handoff / outcome XML — same JSON shapes and anchor rules; only **who executes the shell** changes.

## AUDIT spawn (Path B)

After shared setup in `SKILL.md` (`mkdir`, `gh pr diff`):

`Task` with `subagent_type="code-quality-agent"`, **omit** `team_name`, same `model`, `description`, and `prompt="<audit XML; see PROMPTS.md>"` as Path A [`workflow-path-a-orchestrated-teams.md`](workflow-path-a-orchestrated-teams.md) § AUDIT spawn.

Fresh **Task** each loop (clean-room intent: do not reuse prior Task transcript as audit input). Lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml`, fills `loop_comment_index` per `SKILL.md`.

**Parallel auditors (`loop_count >= 4`):** three **`Task`** calls with `subagent_type="code-quality-agent"` in one assistant message; merge outcomes in the lead exactly as Path A documents for variants `-a`/`-b`/`-c`. Await all three Tasks — no `SendMessage`.

## FIX spawn (Path B)

**Hosts that accept `clean-coder` as a `Task` subtype (typical Claude Code):** `Task` with `subagent_type="clean-coder"` (or `subagent_type="groq-coder"` when `BUGTEAM_FIX_IMPLEMENTER=groq-coder` per Path A optional Groq rules), **omit** `team_name`, same fields otherwise as Path A [`workflow-path-a-orchestrated-teams.md`](workflow-path-a-orchestrated-teams.md) § FIX spawn. Await Task completion — no `SendMessage`.

**Cursor and other hosts with a fixed `Task` enum (no `clean-coder` value):** use `Task` with `subagent_type: "generalPurpose"` and put the **same** FIX obligations from Path A into the **`prompt`**, after a mandatory first step to **Read** the clean-coder agent markdown: macOS/Linux `$HOME/.claude/agents/clean-coder.md`, Windows `%USERPROFILE%\.claude\agents\clean-coder.md`. State that file is binding for naming, TDD when behavior changes, hooks, one commit, and scope. Do **not** use a bare `generalPurpose` prompt without that Read. Same bundle as [`../../pr-converge/SKILL.md`](../../pr-converge/SKILL.md) Fix protocol **Implement**. If `Task` cannot run, stop and notify the user.

Verify and outcome handling: unchanged from `SKILL.md` § FIX action.
## Step 4 harness — after worktree remove, before shared `rmtree`

Run **after** `SKILL.md` § Step 4 step 1 (`git worktree remove` for each PR).

**Omit** teammate `SendMessage` rounds and **`TeamDelete()`**. Then continue with `SKILL.md` § Step 4 step 3 (shared `rmtree` on `<team_temp_dir>`).

## Clean-room note

Path B approximates Path A isolation by spawning a **new** Task per AUDIT (and per FIX) with the same prompt contract as Path A, without reusing prior Task context as audit input.
