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

This session is the shared advisor's sole consumer, so its model floor is
simply this session's own tier — no routing table to take a max against.
Follow [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
for the model-floor walk, the warm-up spawn and charter, the consult format
and cadence, drift-respawn, and the CLI fallback — using
`team-advisor-agent` as the name and this session as the only consumer (skip
the "who you are and your assignment" opener in each consult; a
single-consumer session doesn't need it).

**Grok host:** when the host profile is Grok (see Host profiles in the
shared protocol — e.g. `GROK_BUILD=1` or `ADVISOR_HOST_PROFILE=Grok`), use
the self-as-advisor path: this session answers ENDORSE / CORRECTION / PLAN /
STOP itself. Do not spawn a Claude `session-advisor` subagent and do not walk
the Claude multi-tier ladder.

## Constraints

- One `team-advisor-agent` per session, owned by this session for its whole
  lifecycle (spawn, drift-respawn, shutdown) — see
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
- Never spawn the warm agent, or its CLI fallback, at a tier below this
  session's own tier.
- The warm agent (or its CLI equivalent) only answers. It never edits a
  file, never runs a build or test, and never posts anything on the
  session's behalf.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Pointer to the shared advisor protocol; this session's consumer-specific wiring and constraints. |

## Folder Map

- `SKILL.md` — complete team-advisor workflow instructions.
