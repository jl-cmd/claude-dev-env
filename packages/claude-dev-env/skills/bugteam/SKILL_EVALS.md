# Bugteam — Evaluation Suite

Evaluation-driven iteration set for the `bugteam` skill, following [Anthropic — Agent Skills best practices: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration).

## Methodology

Evals are split into two layers. Both layers run against the same trace but carry different failure semantics.

**Layer A — Ironclad invariants.** Order-and-presence rules that MUST hold on every run regardless of fixture, regardless of model choice, regardless of the exact number of loops taken. Citations use **section headings and companion files** (`SKILL.md`, `CONSTRAINTS.md`, `reference/*.md`) — not fragile line numbers — so layout edits to `SKILL.md` do not invalidate the contract. If an assertion fails, either the run diverged from the skill or the cited text is ambiguous and needs patching.

**Layer B — Fixture-dependent expectations.** The concrete tool trace predicted for a specific fixture (fixed PR state, canned audit XML, canned fix XML). Layer B is prediction — reality may diverge in small ways (extra `Bash("git rev-parse HEAD")` checkpoints the lead inserts for sanity; retry loops on transient failures; consolidated cleanup calls) without indicating a skill defect. Layer B failures trigger reconciliation, not auto-failure.

**Process note.** This document was drafted before running a real trace. Layer B predictions are labeled *predicted*, not *observed*. On the first real run, every Layer B prediction is reconciled against the observed trace and the diffs written back here — that reconciliation is Cycle 0 of the iteration protocol below.

## Ironclad invariants (Layer A, apply to every eval)

Each invariant cites the normative section or companion file it derives from.

| # | Invariant | Citation |
|---|---|---|
| I-1 | `Bash` invoking `scripts/grant_project_claude_permissions.py` precedes every `TeamCreate`. | `SKILL.md` § Step 0 |
| I-2 | `Bash` invoking `scripts/revoke_project_claude_permissions.py` runs exactly once per invocation, after the last `TeamDelete`, on every exit path (converged, stuck, cap reached, error). | `SKILL.md` § Step 5 |
| I-3 | Exactly one `TeamCreate` and exactly one `TeamDelete` per invocation. | `SKILL.md` § Step 2; § Step 4 |
| I-4 | Before `TeamDelete`, no teammate remains active without cleanup: either the teammate self-terminated after `Agent` returned, or the lead sent a matching `SendMessage(..., shutdown_request)` (including parallel-auditor shutdowns). No orphaned teammates when `TeamDelete` runs. | `SKILL.md` § AUDIT action (**Shutdown**); § FIX action (**Shutdown**); § Step 4 |
| I-5 | `Agent` calls are fresh per loop — the same `name` is never reused across loops without an intervening shutdown. | `CONSTRAINTS.md` — **Fresh teammate per loop** |
| I-6 | Both audit and fix `Agent` calls pass `model="opus"` (resolves to Opus 4.7 via the Anthropic API alias; effort remains the Claude Code/model-config default `xhigh`). | `SKILL.md` § Step 2 (**Roles**); `CONSTRAINTS.md` — **Opus 4.7 at xhigh effort for both teammates** |
| I-7 | `TeamDelete()` is called with no arguments. | TeamDelete schema: no required params, no properties |
| I-8 | Loop count ≤ 10 audits. 11th audit never fires. | `SKILL.md` YAML `description` (10-loop cap); § Step 3 (**Pre-audit** / **FIX** increment rules) |
| I-9 | From loop 4 onward without convergence, the audit phase emits three parallel `Agent` calls in a single assistant message with names `bugfind-loop-<N>-a/b/c`. | `SKILL.md` § AUDIT action (**Parallel auditors**); `reference/audit-and-teammates.md` § **Parallel auditors** |
| I-10 | Lead reads `.bugteam-loop-<N>.outcomes.xml` with the `Read` tool after each audit, before the next action. | `SKILL.md` § AUDIT action |
| I-11 | On exit of any kind, ordering is: teammate shutdowns → `TeamDelete` → temp-dir cleanup → Step 4.5 PR rewrite → revoke. | `SKILL.md` § Step 4; § Step 4.5; § Step 5; `reference/teardown-publish-permissions.md` § **Step 4** / **Step 4.5** / **Step 5** |
| I-12 | Lead never posts PR review comments, finding comments, or fix replies. The only lead-side PR mutation is the final `gh pr edit --body-file` in Step 4.5. | `CONSTRAINTS.md` — **Teammates own audit/fix comment posting**; **Lead owns the final PR description rewrite only** |
| I-13 | Only the orchestrator (lead session) invokes `TeamCreate`. Every teammate `Agent(...)` call passes `team_name=<lead_team_name>`. No teammate ever calls `TeamCreate`. When supplementary work arises mid-cycle (parallel auditors, adjacent-file audits, infrastructure fixes), the lead spawns additional teammates into the existing team rather than creating a second team. | `CONSTRAINTS.md` — **Orchestrator-only `TeamCreate`** (runtime error quoted there) |

Any eval failing one or more Layer A invariants fails the run.

## Observation strategy

Evals run in a harness that intercepts the tool layer:

- A **mock tool layer** records each tool call with its arguments and returns synthetic responses matching the real tool's response shape. Nothing hits GitHub; no real teammates spawn.
- A **fixture repo** supplies deterministic git state and a mocked `gh` CLI that returns canned JSON for `pr view`, `pr diff`, and `api` calls.
- **Assertions** run against the recorded call list, not against real PR state.

The harness does not yet exist; this document defines its contract.

---

## Eval 1 — Refusal: agent teams not enabled

**Scenario.** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is unset in both `claude config` and `~/.claude/settings.json`.

**Trigger.** `/bugteam`

**Layer A invariants.** None fire downstream — this is a pre-cycle refusal.

**Layer B predicted trace.**
1. `Bash("claude config get env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")` → empty.
2. `Read("~/.claude/settings.json")` → settings without the env var.
3. No grant script, no `TeamCreate`, no `Agent`.

**Pass criteria.**
- Final assistant message contains the exact string `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 not set. /bugteam requires the agent teams feature.`.
- Zero `TeamCreate`, `Agent`, `SendMessage`, `TeamDelete` calls.
- Zero invocations of the grant or revoke scripts.

---

## Eval 2 — Refusal: missing PR, no upstream diff

**Scenario.** Current branch is `main` with no PR and no upstream difference.

**Layer B predicted trace.**
1. `Bash("gh pr view --json ...")` → non-zero exit.
2. `Bash("git merge-base HEAD origin/main")` → empty.
3. No grant script, no `TeamCreate`.

**Pass criteria.** Assistant message matches `No PR or upstream diff. /bugteam needs a target.`. Zero downstream tool calls.

---

## Eval 3 — Refusal: uncommitted changes in working tree

**Scenario.** Clean PR exists but `git status --porcelain` shows unstaged changes.

**Pass criteria.** Assistant message matches `Uncommitted changes detected. Stash, commit, or revert before /bugteam.`. Zero downstream tool calls.

---

## Eval 4 — Refusal: required subagent missing

**Scenario.** `code-quality-agent` is present in the available-agents list; `clean-coder` is not.

**Pass criteria.** Assistant message contains `Required subagent type clean-coder not installed.`. Zero grant script call, zero `TeamCreate`.

---

## Eval 5 — Happy path: converges in 2 loops

**Scenario.** PR #42 contains three P1 bugs all addressable by the mock fix teammate. Loop 1 audit returns 3 findings; loop 1 fix commits cleanly; loop 2 audit returns zero findings.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-7, I-10, I-11, I-12.

**Layer B predicted trace.**

| # | Tool call | Source |
|---|---|---|
| 1 | `Bash("python .../scripts/grant_project_claude_permissions.py")` | `SKILL.md` § Step 0 |
| 2 | `Bash("gh pr view --json number,baseRefName,headRefName,url")` | `SKILL.md` § Step 1 |
| 3 | `Bash("git rev-parse HEAD")` → captures `starting_sha` | `SKILL.md` § Step 2 — **Loop state** block |
| 4 | `TeamCreate(team_name="bugteam-pr-42-<ts>", description=..., agent_type="team-lead")` | `SKILL.md` § Step 2 |
| 5 | `Bash("mkdir -p <team_temp_dir>")` | `SKILL.md` § AUDIT action |
| 6 | `Bash("gh pr diff 42 -R ... > <team_temp_dir>/loop-1.patch")` | `SKILL.md` § AUDIT action |
| 7 | `Agent(subagent_type="code-quality-agent", name="bugfind", team_name=..., model="opus", description=..., prompt=<audit XML loop 1>)` | `SKILL.md` § AUDIT action |
| 8 | `Read(".bugteam-loop-1.outcomes.xml")` | `SKILL.md` § AUDIT action |
| 9 | `SendMessage(to="bugfind", message={type: "shutdown_request", reason: "audit loop 1 complete; outcome XML captured"})` | `SKILL.md` § AUDIT action (**Shutdown** fallback) |
| 10 | `Agent(subagent_type="clean-coder", name="bugfix", team_name=..., model="opus", description=..., prompt=<fix XML loop 1>)` | `SKILL.md` § FIX action |
| 11 | `Read(".bugteam-loop-1.outcomes.xml")` — bugfix outcome XML overwrites same filename | `SKILL.md` § FIX action |
| 12 | `Bash("git rev-parse HEAD")` → verify HEAD advanced | `SKILL.md` § FIX action (**Verify**) |
| 13 | `Bash("git fetch origin <branch> && git rev-parse origin/<branch>")` → verify push landed | `SKILL.md` § FIX action (**Verify**) |
| 14 | `SendMessage(to="bugfix", message={type: "shutdown_request", reason: "fix loop 1 complete; commit <sha7> pushed"})` | `SKILL.md` § FIX action (**Shutdown** fallback) |
| 15 | `Bash("gh pr diff 42 -R ... > <team_temp_dir>/loop-2.patch")` | `SKILL.md` § AUDIT action |
| 16 | `Agent(subagent_type="code-quality-agent", name="bugfind", ...)` (loop 2) | `SKILL.md` § AUDIT action |
| 17 | `Read(".bugteam-loop-2.outcomes.xml")` — zero findings | `SKILL.md` § AUDIT action |
| 18 | `SendMessage(to="bugfind", message={type: "shutdown_request", reason: "audit loop 2 complete; zero findings"})` | `SKILL.md` § AUDIT action (**Shutdown** fallback) |
| 19 | `TeamDelete()` | `SKILL.md` § Step 4 |
| 20 | `Bash("python -c \"import os, shutil, stat, sys; h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); shutil.rmtree(r'<team_temp_dir>', **({'onexc': h} if sys.version_info >= (3, 12) else {'onerror': h}))\"")` | `SKILL.md` § Step 4 (Windows-safe teardown) |
| 21 | `Bash("gh pr diff 42 -R ... > .bugteam-final.diff")` | `SKILL.md` § Step 4.5 step 1 |
| 22 | `Bash("gh pr view 42 -R ... --json body --jq .body > .bugteam-original-body.md")` | `SKILL.md` § Step 4.5 step 2 |
| 23 | `Agent(subagent_type="pr-description-writer", description=..., prompt=<brief>)` | `SKILL.md` § Step 4.5 |
| 24 | `Write(".bugteam-final-body.md", <returned body>)` | `SKILL.md` § Step 4.5 step 4 |
| 25 | `Bash("gh pr edit 42 -R ... --body-file .bugteam-final-body.md")` | `SKILL.md` § Step 4.5 step 4 |
| 26 | `Bash("rm .bugteam-final.diff .bugteam-original-body.md .bugteam-final-body.md")` | `SKILL.md` § Step 4.5 step 5 (lead may add `.bugteam-loop-*.outcomes.xml` in the same or a separate `rm` — reconcile on first real run) |
| 27 | `Bash("python .../scripts/revoke_project_claude_permissions.py")` | `SKILL.md` § Step 5 |

**Pass criteria.**
- All Layer A invariants hold.
- Exactly 2 `Agent(name="bugfind"...)` calls, exactly 1 `Agent(name="bugfix"...)` call.
- Exactly 2 bugfind shutdown messages + 1 bugfix shutdown message.
- Final report contains `/bugteam exit: converged` and `Loops: 2`.

**Process check after first real run.** Compare the observed trace against steps 1–27. Common expected divergences that should not fail the eval:
- Extra `Bash("git rev-parse HEAD")` calls the lead inserts for bookkeeping.
- Consolidated `Bash` calls (step 26 may split into two or three calls).
- Extra `Read` calls when the lead re-reads an outcome XML to quote specific findings.
- Reordered but still-Layer-A-compliant cleanup sequencing.

Patch this table to match observation and annotate each correction.

---

## Eval 6 — Stuck path: fix teammate produces no commit

**Scenario.** Loop 1 audit finds 2 P1 bugs; the mock fix teammate reports both as `could_not_address` (no commit created).

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-7, I-10, I-11, I-12. I-8 trivially holds.

**Layer B predicted trace.** Identical to Eval 5 steps 1–14 with this divergence:
- Step 11 bugfix outcome XML marks every finding `status="could_not_address"`.
- Step 12 `Bash("git rev-parse HEAD")` returns the pre-fix SHA unchanged.
- Skill sets exit reason = `stuck`, skips loop 2, and falls through to `TeamDelete()`.

**Pass criteria.**
- Loop count stops at 1.
- Final report contains `/bugteam exit: stuck` and names the two unresolved findings.
- Steps 19–27 fire despite the stuck exit — I-2 and I-11 enforce this.

---

## Eval 7 — Cap reached: 10 loops, no convergence

**Scenario.** Mock audit returns one P2 finding every loop. Mock fix teammate always commits but never clears the finding.

**Layer A invariants.** All of I-1 through I-12.

**Layer B predicted behavior.**
- Loops 1–3: single `Agent(name="bugfind")` per loop.
- Loops 4–10: three parallel `Agent(name="bugfind-loop-<N>-a/b/c")` in a single assistant message per loop, followed by two parallel `-b`/`-c` shutdowns and one `-a` shutdown.
- Each loop produces one `Agent(name="bugfix")` and its matching shutdown.
- Exactly 10 audit phases, exactly 10 fix phases.
- Steps 19–27 from Eval 5 fire at teardown.

**Pass criteria.**
- I-8 holds: exactly 10 audit phases.
- I-9 holds: loops 4–10 each emit three audit `Agent` calls in a single assistant message.
- Final report contains `/bugteam exit: cap reached` and the remaining bug count.

**Process check.** The distinct `Agent(name=...)` audit-call count is a prediction. On the first real run, record the exact count and rewrite the formula here.

---

## Eval 8 — Clean on first audit

**Scenario.** Loop 1 audit returns zero findings.

**Layer A invariants.** I-1 through I-7, I-10, I-11, I-12.

**Layer B predicted trace.** Eval 5 steps 1–9 and 19–27 only — no FIX phase because zero findings means the skill exits the loop at `last_action == "audited"` and `last_findings.total == 0`.

**Pass criteria.**
- Exactly 1 `Agent(name="bugfind"...)` call, 0 `Agent(name="bugfix"...)` calls, 1 bugfind shutdown.
- Bugfind's outcome XML records zero findings; the per-loop review POST carries body `## /bugteam loop 1 audit: 0P0 / 0P1 / 0P2 → clean`.
- Step 4.5 and Step 5 still fire.

---

## Eval 9 — Anchor fallback: finding outside diff

**Scenario.** Loop 1 audit returns 3 findings; 1 anchors to a line outside the captured diff.

**Layer A invariants.** Same as Eval 5.

**Layer B predicted teammate-side behavior** (observed via the recorded `gh api ... /reviews` POST payload in the bugfind teammate fixture).
- `comments[]` length in the POST body = 2 (anchored findings only).
- Review body contains a `### Findings without a diff anchor` section listing the third finding.
- Bugfix outcome XML marks all 3 findings with a `reply_comment_url`; the unanchored finding's `used_fallback="true"` and `finding_comment_url` equals the parent review URL.

**Pass criteria.** Confirmed in the fixture's canned teammate outcome XML; Layer A invariants hold on the lead side.

---

## Eval 10 — Review POST failure fallback

**Scenario.** The first `POST /pulls/42/reviews` call from the bugfind teammate returns HTTP 422.

**Layer B predicted teammate-side behavior.**
- Bugfind teammate retries via the issue-comments endpoint `POST /repos/.../issues/42/comments` with a single body carrying the review header and every finding inline.
- Every finding's outcome XML carries `used_fallback="true"` and the issue-comment URL as `finding_comment_url`.
- Cycle continues to the FIX action without aborting.

**Open item for the real run.** The issue-comments fallback shape is `jq -Rs | gh api .../issues/<number>/comments --input -` (`SKILL.md` § Step 2.5 **Review POST fails**; full narrative in `reference/github-pr-reviews.md` § **Review POST failure fallback**). Before running Eval 10 for real, confirm the teammate obeys this shape — the fixture must assert the endpoint path and the `--input -` pattern.

---

## Eval 11 — Hook-blocked fix commit

**Scenario.** Bugfix stages edits but `git commit` fails because a `pre-commit` hook returns non-zero.

**Layer B predicted behavior.**
- Bugfix teammate outcome XML marks every finding `status="hook_blocked"` with populated `<hook_output>`.
- Bugfix teammate posts `Hook blocked the fix commit: <one-line summary>` to each finding comment.
- Lead's `Bash("git rev-parse HEAD")` after fix detects no SHA change → exit reason `stuck`.
- Steps 19–27 from Eval 5 fire at teardown.

**Pass criteria.** Layer A I-2 and I-11 hold. Final report contains `/bugteam exit: stuck` and surfaces the hook_output summary.

---

## Eval 12 — `pr-description-writer` unavailable, `general-purpose` available

**Scenario.** The available-agents list does not include `pr-description-writer` but does include `general-purpose`.

**Layer B predicted trace.** Eval 5 steps 1–22 identical; step 23 becomes:

```
Agent(subagent_type="general-purpose", description="Rewrite PR 42 body from cumulative diff", prompt=<same brief>)
```

Steps 24–27 follow normally.

**Pass criteria.** Exactly 1 `Agent(subagent_type="general-purpose", ...)` call for the description rewrite. `gh pr edit` fires. Final report carries no Step 4.5 skip warning.

---

## Eval 13 — Neither PR-description agent available

**Scenario.** Neither `pr-description-writer` nor `general-purpose` appear in the available-agents list.

**Layer B predicted trace.** Eval 5 steps 1–22, then skip steps 23–25. Steps 26–27 still fire.

**Pass criteria.**
- Zero `Agent` calls for PR description rewriting.
- Zero `gh pr edit` calls.
- Final report carries the Step 4.5 skip warning.
- Layer A I-2 holds: revoke still fires.

---

## Eval 14 — Permissions revoke on error path

**Scenario.** Bugfind teammate refuses `shutdown_request` during loop 1, returning `{type: "shutdown_response", approve: false}`.

**Layer B predicted trace.** Eval 5 steps 1–8, then:
- Step 9 `SendMessage(to="bugfind", ...)` receives `approve: false`.
- Skill sets exit reason = `error: bugfind teammate refused shutdown`.
- Steps 19–27 all fire (Layer A I-2 and I-11 mandate this).

**Pass criteria.** Final report surfaces the error and the loop number. Revoke fires despite the error.

---

## Eval 15 — Orchestrator-only `TeamCreate` (supplementary work path)

**Scenario.** A loop 1 audit surfaces a P0/P1 finding whose root cause sits in adjacent infrastructure the lead needs to fix before the cycle can converge (e.g., a broken CI hook, a misbehaving lint config, a wrong GitHub API shape in a teammate's own dependency). The lead recognizes supplementary work is needed and decides to spawn additional teammates to handle it.

**Layer A invariants.** I-1, I-3, I-4, I-5, I-6, I-7, I-11, I-12, **I-13 (primary focus)**.

**Layer B predicted trace.** Eval 5 steps 1–9 identical. At step 10 (where a standard cycle spawns `bugfix`), the lead decides the finding requires adjacent infrastructure work first. Rather than call `TeamCreate` for a new team, the lead spawns a supplementary teammate into the existing team:

```
Agent(
  subagent_type="code-quality-agent",
  name="bugfind-adjacent",
  team_name="<lead_team_name>",          // same team as bugfind/bugfix
  model="opus",
  description="Supplementary audit of adjacent infrastructure",
  prompt=<brief naming the specific adjacent files + observed symptom>
)
```

The adjacent-audit teammate writes its own outcome XML, self-terminates. Lead reads the XML, decides fix strategy, spawns an adjacent-fix teammate into the same team. Cycle eventually returns to the standard `bugfix` spawn for the original finding(s). All spawns pass the same `team_name`.

**Pass criteria.**
- Layer A I-13 holds: zero `TeamCreate` calls beyond the single one at skill Step 2.
- Every `Agent(...)` call in the session carries `team_name="<lead_team_name>"`. No teammate spawn omits `team_name`.
- If the lead attempts a second `TeamCreate` call, the runtime returns the exact error quoted in I-13's citation; the lead treats this as a signal to spawn a teammate into the existing team instead.
- Working behavior is unchanged from a single-set cycle: grant → TeamCreate (once) → Agent spawns (many, all same team_name) → SendMessage shutdowns as needed → TeamDelete (once) → temp cleanup → Step 4.5 → revoke.

**Failure mode.** A second `TeamCreate` call in the session, or any `Agent(...)` call without `team_name` once the team exists. Either signals the orchestrator-only invariant has been violated and the clean-room/team semantics are broken.

**Observation source for this eval.** This eval was added after a real /bugteam run on PR #184 where the lead discovered a broken hook mid-cycle and initially spawned a standalone subagent (no `team_name`) for the adjacent audit — a direct violation. The runtime had already prevented a second `TeamCreate` with the error quoted in I-13. The eval codifies the correct path (spawn as teammate into existing team) so future runs do not repeat the violation.

---

## Iteration protocol

1. **Cycle 0 — Reconcile predictions with reality.** On the first real run, diff every Layer B predicted trace against the observed trace. Patch this file to match reality and annotate each correction with a reason.
2. **Baseline.** Run every eval with the skill unloaded. Record which cases the base model handles from memory versus which it gets wrong.
3. **Treatment.** Run every eval with the skill loaded. Layer A invariants must pass on every case. Layer B mismatches trigger Cycle 0 reconciliation.
4. **Regress on change.** Every edit to normative text in `SKILL.md`, `CONSTRAINTS.md`, `PROMPTS.md`, or `reference/*.md` sections that Layer A cites re-runs the full suite. A passing→failing transition on any Layer A invariant blocks the change. A Layer B mismatch after such an edit triggers a patch to the affected eval trace in the same commit.
5. **Extend on gotcha.** When the skill misfires in real use, add a new eval that reproduces the miss before patching the orchestration or companion files.

## Harness sketch (future work)

A minimal Python harness under `packages/claude-dev-env/skills/bugteam/evals/`:

- `harness.py` — loads a fixture, injects a mock tool layer that records calls and returns canned responses, invokes the lead with the trigger, collects the recorded trace, evaluates pass criteria.
- `fixtures/` — one subdirectory per eval with canned `gh` responses, canned audit XML, canned fix XML, and the expected trace JSON.
- `run_evals.py` — discovery + pass/fail reporting, exits non-zero on any failure for CI.
- `invariants.py` — the Layer A assertion bank, imported by every fixture.

## Open research items flagged during this pass

1. **GitHub REST review-POST payload shape.** Eval 9 and Eval 10 depend on the exact body shape of `POST /pulls/<number>/reviews`. The `jq -n --rawfile ... --argjson ... | gh api ... --input -` fence lives in `SKILL.md` § Step 2.5 (**Review POST**); expanded copy in `reference/github-pr-reviews.md` § **Per-loop review**. Before running Eval 9/10 for real, fetch the current GitHub REST reference to confirm the request schema (fields `commit_id`, `event`, `body`, `comments[]`) and the multi-line anchor `{path, start_line, start_side, line, side, body}` shape still apply. Record the confirmed version and URL here.
2. **`SendMessage` shutdown origination — RESOLVED.** `SendMessage` tool docs include the line "Don't originate `shutdown_request` unless asked." `TeamCreate` tool docs explicitly direct the lead to originate `{type: "shutdown_request"}` for teammate cleanup. Real-run observation (loop 1 of eval run 2026-04-18) resolved the contradiction: teammates self-terminate when their task is complete — the `Agent` call returns and the teammate's session ends without any `SendMessage`. The cycle proceeded correctly without the lead ever needing to originate a `shutdown_request`. `SKILL.md` § AUDIT / FIX actions document self-termination as the expected path and lead-originated `SendMessage(shutdown_request)` as a fallback; `reference/audit-and-teammates.md` carries the longer shutdown narrative. Layer A **I-4** encodes “no orphaned teammates,” not “always send SendMessage.”
3. **Model override redundancy.** `clean-coder` pins `model: opus` in its agent definition, while `code-quality-agent` currently uses `model: inherit`. The explicit `model="opus"` in every spawn is insurance against frontmatter drift; on the first real run, confirm the resolved model is `claude-opus-4-7` and that effort defaults to `xhigh` (Claude Code shows the active effort next to the spinner per the model-config docs). If a teammate's frontmatter ever pins a non-default `effort:` value, that frontmatter overrides the model default for that subagent (https://code.claude.com/docs/en/model-config — *"Frontmatter effort applies when that skill or subagent is active, overriding the session level but not the environment variable."*).
