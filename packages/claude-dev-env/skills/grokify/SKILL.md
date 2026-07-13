---
name: grokify
description: >-
  Grok Build execution handoff prompt, embed Claude advisor.
---

# Grokify

## Principle

One paste-ready handoff turns this session's work into a plan a Grok Build session can execute alone. Grok gets no access to this conversation, so the handoff carries everything: repos, findings, constraints, the phased plan, and a Claude advisor Grok reaches through the `claude` CLI.

## Gotchas

- Grok Build can use `spawn_subagent`, `--agent` / agent definitions, and can read skills under the user's Claude config paths. Skill evals measure these when `GROK_CAPABILITY_EVALS=1` (see `evals/README.md`).
- The **grokify handoff's Claude-tier advisor** is an out-of-process `claude -p` bind/resume. Never write Claude Agent-tool, `session-advisor`, or SendMessage protocol into the handoff for that advisor path — product design for a Claude-model advisor, not a claim that Grok lacks agents.
- Grok does not expose a Claude/GSD Workflow tool. When that tool is required, workflow orchestration stays with Claude.
- A `--resume` after a usage-limit failover to another binary fails, because a session store belongs to the binary that minted it. The handoff must tell Grok to treat that failure as starting over: re-send the charter plus a compact recap, capture the new `session_id`.
- Conversation-relative phrases ("as discussed", "the plan above", "the earlier choice") are dead text to Grok — every statement stands on its own.
- Copy findings' measured numbers and `file:line` citations into the handoff exactly, and label each figure measured, bounded, or unverified.
- The advisor session starts empty. The bind step must pipe the findings, constraints, and plan into the charter, or every later consult is answered from nothing.
- `claude` sessions are project-scoped by working directory. The handoff must tell Grok to run every bind and every `--resume` with the cwd set to the repo root it names — a bind launched from the Grok sandbox cwd files the session under that other project, and a later resume from the real worktree reports `No conversation found with session ID`. Treat a session-not-found error as a wrong-cwd or expired-session signal, not a model failure.
- `--output-format json` returns a JSON array of events, not one object. `session_id` comes from any event; the reply text is the `type == "result"` event's `.result` field. A parser expecting one top-level object reports a missing session id on a working bind.
- The charter travels as a file piped to stdin, or as one clean argv string. Half-escaped multiline shell expansion mangles the prompt in transit and the advisor sees a fragment.

## When this applies

The user types `/grokify`, alone or with guidance.

- Bare `/grokify`: build the handoff from the current session's context — the task in flight, its findings, plan, and constraints.
- `/grokify <guidance>`: the guidance names or scopes the task — a plan written earlier in the session, a file to read, or a fresh instruction. Build the handoff for that.

**Refusal:** no session context and no guidance — reply `What should Grok execute? One sentence.` and stop.

## Process

1. Collect the substance: repos and branch, established findings with `file:line` and measured numbers, hard constraints, and the phased plan with acceptance criteria. Pull from session context first, then from the guidance; read any files the guidance names.
2. Fill `templates/handoff-template.md`. Adapt every bracketed section to the task; keep the advisor CLI commands, signal rules, and consult cadence exactly as the template writes them.
3. Mark any decision that belongs to the user as an explicit ask-the-user fork inside the plan. The handoff never lets Grok pick silently.
4. Deliver one fenced markdown block (four-backtick fence, so inner fences survive), then one or two sentences naming the choices you baked in.

## Fixed advisor structure (never vary these parts)

- **Bind once, first:** charter + findings + constraints + plan piped from a temp file into `claude -p --model fable --effort high --output-format json`; parse and save `session_id` from the JSON reply.
- **Consult:** brief piped into `claude -p --resume <session_id> --model fable --effort high --output-format json`.
- **ConsultB** If fable is unavailable, use opus with max effort: `claude -p --resume <session_id> --model opus --effort max --output-format json`.
- **Signals:** every advisor reply opens with exactly one of ENDORSE, CORRECTION, PLAN, or STOP. CORRECTION and PLAN are actions to take, with a report-back in the next consult on that topic. STOP halts that line of work and surfaces it to the user. When the CLI is unreachable, Grok stops and says so — it never self-endorses in the advisor's place.
- **Cadence, mandatory:** after planning and before any edit; per phase before implementation (TDD red + approach) and after (diff, tests, acceptance evidence); before every `git commit` and `git push`; on every user-facing fork before asking; on any twice-repeated failure or stall.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Trigger, process, fixed advisor structure. |
| `templates/handoff-template.md` | Section-by-section skeleton of the handoff prompt. |
| `capability-claims.test.mjs` | Offline static guards on capability wording. |
| `evals/README.md` | How to run opt-in live capability evals. |
| `evals/run-capability-evals.mjs` | Live E1–E5 runner (manual / opt-in only). |

## Folder map

- `SKILL.md` — the whole workflow.
- `templates/` — the handoff skeleton.
- `evals/` — opt-in live Grok capability measurements.
- `capability-claims.test.mjs` — offline claim guards for `npm test`.
