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
| [`~/.claude/_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md) | **Bind and lifecycle** — host detect, model floor, warm-up or CLI bind, charter, drift re-bind, CLI fallback, executor paste blocks. Package-root `_shared/` (installs to `~/.claude/_shared/`); **not** `skills/_shared/`. |
| [`agents/session-advisor.md`](../../agents/session-advisor.md) | **Reply contract** — ENDORSE / CORRECTION / PLAN / STOP; SendMessage only. |

## Bind

1. Detect the host profile first (protocol **Host profiles**). Do not walk the model floor until the host is known.
2. Floor: this session's own tier on Claude; Opus floor with Fable first on a third-party host.
3. Name: `team-advisor-agent` on Claude (Agent spawn of `session-advisor`); one CLI `session_id` on a third-party host via the protocol Claude-chain.
4. Skip the multi-consumer "who you are" opener — sole consumer.
5. When the bind or reply path fails, fail closed and report to the user. On a third-party host, do **not** answer ENDORSE / CORRECTION / PLAN / STOP as this session.

Full walk, charter, consult message shape, and drift re-bind live in the protocol.

## Consult

Follow **When to call**, **Hard rule**, and **How to treat advice** in `advisor-tool.md`.

Each brief: delta since last consult, live decision or blocker, paths or excerpts needed. Protocol owns the full consult format.

## Constraints

- One bind per session; this session owns spawn or CLI bind, drift re-bind, and shutdown.
- Never bind below the protocol floor for this host.
- The advisor only answers. It never edits, builds, tests, or posts on the session's behalf.
