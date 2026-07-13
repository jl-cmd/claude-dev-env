---
name: team-advisor
description: >-
  Spawn one warm session-advisor at the strongest reachable tier and consult
  it before big decisions, completion, commits, or when stuck. Triggers:
  'team-advisor', 'team advisor', 'second opinion', 'advisor', 'consult',
  'verify', 'validate', 'commit', 'push'.
---

# Team Advisor

## Principle

One warm, addressable advisor available at the strongest model tier the session can reach. The session sends concise briefs when a decision benefits from a second opinion: before acting on a plan, at completion, before commits, when stuck, when reconsidering the approach, or when an agent deems it necessary and beneficial to the user's goals.

## Follow the shared protocol

**Detect the host profile first** (Host profiles in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
— e.g. `ADVISOR_HOST_PROFILE` or `GROK_BUILD`). Do not start a model-floor
walk until the host is known.

This session is the shared advisor's sole consumer, so its model floor is
simply this session's own tier — no routing table to take a max against.

**Claude host:** follow the shared protocol for the model-floor walk, the
warm-up spawn and charter, the consult format and cadence, drift-respawn, and
the CLI fallback — using `team-advisor-agent` as the name and this session as
the only consumer (skip the "who you are and your assignment" opener in each
consult; a single-consumer session doesn't need it).

**Grok host:** bind a max-tier Claude advisor through the shared CLI Claude-chain
in the protocol (Fable high, then Opus max; `claude_chain_runner.py` walks
`~/.claude/claude-chain.json` for account usage failover). Consult via
`--resume <session_id>` on that bind. This session is the sole consumer of that
CLI advisor; skip the multi-consumer opener. When the chain cannot bind or
reply, fail closed and report to the user — do **not** answer ENDORSE /
CORRECTION / PLAN / STOP as this Grok session.

## Constraints

- One advisor bind per session (`team-advisor-agent` on Claude; one CLI
  `session_id` on Grok), owned by this session for its whole lifecycle
  (spawn or CLI bind, drift re-bind, shutdown) — see
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
- Never bind the advisor, or its CLI path, at a tier below the protocol floor
  for this host (Claude: this session's own tier; Grok: Opus floor with Fable
  first).
- The advisor only answers. It never edits a file, never runs a build or
  test, and never posts anything on the session's behalf.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Pointer to the shared advisor protocol; this session's consumer-specific wiring and constraints. |

## Folder Map

- `SKILL.md` — complete team-advisor workflow instructions.
