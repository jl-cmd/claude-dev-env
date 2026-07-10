---
name: reviewer-gates
description: >-
  Runs the availability gates a PR-loop orchestrator checks before it starts an
  external reviewer: the CLAUDE_REVIEWS_DISABLED opt-out, the once-per-run
  Copilot quota pre-check, and the Cursor Bugbot trigger, acknowledge, and
  CI-detect flow. Decides whether a reviewer runs, never what it finds.
---

# Reviewer Gates

**Core principle:** one place decides whether an external reviewer is engaged. A caller never hand-parses `CLAUDE_REVIEWS_DISABLED`, never re-queries Copilot quota mid-run, and never invents a Bugbot trigger phrase.

## How callers invoke this

- **Skill-capable contexts** (a lead session with the `Skill` tool): `Skill({skill: "reviewer-gates", args: "--skill <caller> <gate> [gate parameters]"})`.
- **Fallback** (a subagent or teammate without the `Skill` tool): the caller's spawn prompt says "Read `~/.claude/skills/reviewer-gates/SKILL.md` and apply the `<gate>` section with the parameters below."

Every invocation carries the caller's identity (`--skill <caller>`, e.g. `pr-converge`, `qbug`). The refusal line in Gate 1 and every logged decision names the caller, so a multi-skill session's transcript shows which loop each gate served.

## Gate 1: Reviewer opt-out (`CLAUDE_REVIEWS_DISABLED`)

The `CLAUDE_REVIEWS_DISABLED` environment variable is a comma-separated token list (case-insensitive, whitespace-tolerant). Three tokens exist:

| Token | Disables |
|---|---|
| `bugteam` | The whole bug-audit family: `/bugteam`, `/qbug`, `/findbugs`, and audit dispatch in `/monitor-open-prs` |
| `bugbot` | Cursor Bugbot triggering and polling |
| `copilot` | GitHub Copilot review requests and polling |

Cursor Bugbot is off by default: it runs only when `CLAUDE_REVIEWS_ENABLED` lists `bugbot`, and a `bugbot` token in `CLAUDE_REVIEWS_DISABLED` keeps it off even when the opt-in lists it.

Run the shared parser — never an inline shell parse:

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer <bugbot|bugteam|copilot>
```

- **Exit 0** — the named reviewer is disabled for this run (opted out, or, for Bugbot, off by default without the `CLAUDE_REVIEWS_ENABLED` opt-in). A skill whose whole run depends on that reviewer responds with its refusal line and stops. A copilot- or bugteam-dependent caller names the opt-out: `/<caller> is disabled via CLAUDE_REVIEWS_DISABLED.` A Bugbot-dependent caller off by default names the opt-in the run needs: `/<caller> is disabled: Cursor Bugbot needs a `bugbot` token in CLAUDE_REVIEWS_ENABLED.` A loop that merely includes the reviewer as one gate marks the reviewer down (`bugbot_down = true`, `copilot_down = true`) and continues on its remaining signals.
- **Exit 1** — the reviewer is available; continue.

## Gate 2: Copilot quota pre-check (once per run)

At run start — before any Copilot request, poll, or agent spawn — run:

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/copilot_quota.py"
```

It resolves the configured GitHub account, reads the remaining Copilot premium-request quota via `gh api copilot_internal/user`, and prints one line. Log that line.

- **Exit 0** — Copilot has quota. Leave `copilot_down` false (or pass `copilotDisabled: false` to a workflow).
- **Any non-zero exit** — skip Copilot for the whole run: the account is out of quota, the quota API or account access is down, or no account is set. Set `copilot_down = true` (or `copilotDisabled: true`). The no-account line names the exact `.env` path and key to set; the account comes from the `COPILOT_QUOTA_ACCOUNT` environment variable or a git-ignored `.env` file.

Run the pre-check once per run, not per tick or per round. Every later tick reads the stored flag. While `copilot_down` is true:

- Skip every Copilot fetch, request, poll, and agent spawn outright.
- Export `CLAUDE_REVIEWS_DISABLED="copilot"` in the shell of any convergence check (`check_convergence.py`), so the check bypasses its Copilot review gate and pending-requested-reviews gate and the run still marks ready on the remaining signals.

`reviewer_availability.py` (same directory) is the single entry point when a caller wants one command answering "may reviewer X be engaged?" — it composes the opt-out parse and, for Copilot, the quota check: exit 0 to engage, non-zero to skip.

## Gate 3: Bugbot trigger, acknowledge, and CI-detect

Cursor Bugbot signals through CI check runs, not always through a posted review. The decision tree runs against `<current_head>` with `check_bugbot_ci.py` (installed at `$HOME/.claude/skills/pr-converge/scripts/check_bugbot_ci.py`; `--help` documents every mode):

1. **Silent-pass pre-check (always first).**
   `python "$HOME/.claude/skills/pr-converge/scripts/check_bugbot_ci.py" --check-clean --owner <O> --repo <R> --sha <current_head>`
   - Exit 0 — Bugbot CI completed with a `success`/`neutral` conclusion and posted no review: a silent pass. Record `bugbot_clean_at = <current_head>` and stop; do not trigger.
   - Exit 1 (not a silent pass) or exit 2 (gh CLI error, silent pass not confirmable) — continue.
2. **Already-queued check.**
   `... check_bugbot_ci.py --check-active --owner <O> --repo <R> --sha <current_head>`
   - Exit 0 — Bugbot is already queued on this commit. Skip posting; wait for completion (callers schedule their own wakeup).
   - Exit 1 — continue.
3. **Trigger.** Post exactly `bugbot run` as an issue comment (`add_issue_comment`) — no `@cursor[bot]` mention, no other text. `bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes; every other phrasing silently no-ops. Wait 8 seconds with an in-turn Monitor delay, never a foreground `sleep` (blocked in headless runs).
4. **Acknowledge check.**
   `... check_bugbot_ci.py --owner <O> --repo <R> --sha <current_head>`
   - Exit 0 — a check run is present: record `bugbot_acknowledged_at = <now, ISO 8601>`; the caller polls on its own cadence.
   - Exit non-zero — Bugbot is down: set `bugbot_down = true` and route past the Bugbot phase; the run continues on its remaining signals.

The silent-pass pre-check runs first so a bot that already finished cleanly is never re-prompted — Bugbot refuses to re-run on an evaluated commit, and without the pre-check the acknowledge step would falsely mark `bugbot_down = true`.

**Flag reset rule:** `bugbot_down` resets to false whenever `<current_head>` changes — a new HEAD invalidates the old down-detection. `copilot_down` never resets mid-run; it holds until the run ends.

## Gotchas

- **`bugbot run` is load-bearing text.** Alternative phrasings (`@cursor run`, `cursor review`, `bugbot please`) return no error and do nothing.
- **A skipped gate is a decision, not an omission.** When `copilot_down` or `bugbot_down` short-circuits a phase, record the flag and the exit line that set it — a convergence report that cannot show why a reviewer was skipped is incomplete.
- **The opt-out gate re-runs at every reviewer entry point;** the quota pre-check runs once per run. Confusing the two either re-spends quota-API calls per tick or misses a mid-run opt-out.

## Folder map

- `SKILL.md` — this file; the skill ships no scripts of its own. Gate scripts live in `_shared/pr-loop/scripts/` (`reviews_disabled.py`, `copilot_quota.py`, `reviewer_availability.py`) and `pr-converge/scripts/` (`check_bugbot_ci.py`).
