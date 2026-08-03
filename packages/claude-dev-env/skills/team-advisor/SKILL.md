---
name: team-advisor
description: >-
  Spawn one warm session-advisor at the strongest reachable tier and consult
  it before substantive work, completion, commits, or when stuck. Triggers:
  'team-advisor', 'team advisor', 'second opinion', 'advisor', 'consult',
  'verify', 'validate', 'commit', 'push'.
---

# Team Advisor

One warm advisor at the strongest tier this session can reach. This session is the sole consumer.

## Refs

| Doc | Holds |
|---|---|
| [`docs/references/advisor-tool.md`](../../docs/references/advisor-tool.md) | **Consult cadence and weight** — when to call, hard rule before first write, how to treat advice. Read this for every consult. |
| [`~/.claude/_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md) | **Bind and lifecycle** — host detect, model floor, warm-up, CLI fallback; its read map routes each moment to a `reference/` detail file. |
| [`agents/session-advisor.md`](../../agents/session-advisor.md) | **Reply contract** — ENDORSE / CORRECTION / PLAN / STOP; SendMessage only. |
| [`reference/advisor-docs-review.md`](reference/advisor-docs-review.md) | Anthropic advisor-tool doc facts: consult timing, Sonnet steering, cost levers, failure modes. |

## Bind

1. Detect the host profile first (protocol **Host profiles**), then walk the model floor.
2. Floor: the stronger of Opus and this session's own tier on Claude; Opus floor with Fable first on a third-party host.
3. Name: `team-advisor-agent` on Claude (Agent spawn of `session-advisor`); one CLI `session_id` on a third-party host via the protocol Claude-chain.
4. A Fable-tier spawn or re-spawn carries the exact token `FABLE-SPAWN-AUTHORIZED` in its prompt (protocol warm-up; `fable_spawn_gate` requires it).
5. Skip the multi-consumer "who you are" opener — sole consumer.
6. When the bind or reply path fails, fail closed and report to the user. On a third-party host, only the bound Claude advisor issues ENDORSE / CORRECTION / PLAN / STOP.

Full walk, charter, consult packet, Sol routing, and drift re-bind live in the protocol read map and its authoritative `reference/` leaves.

## Consult

Follow **When to call**, **Hard rule**, and **How to treat advice** in `advisor-tool.md`.

Build every first brief with [`_shared/advisor/reference/consult-format.md`](../../_shared/advisor/reference/consult-format.md). Later briefs carry only the delta and changed evidence.

Aim for two consults on a normal task: one after orientation and one after writes and validation. Reserve a third for advisory recovery or reconciliation guidance, and add a consult when a material fork produces new evidence. This is an advisory target owned by the task, not a cap or gate.

## Constraints

- One bind per session; this session owns spawn or CLI bind, drift re-bind, and shutdown.
- Bind at or above the protocol floor for this host.
- The advisor only answers (messaging); the session runs tools and posts.
