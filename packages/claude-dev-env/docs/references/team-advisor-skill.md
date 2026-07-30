# Team-Advisor Skill

`/team-advisor` binds one standing warm advisor for this session at the strongest reachable tier. Use it when `advisor()` is absent, or when you want a standing four-signal reviewer across many decision points.

## Refs

| Doc | Holds |
|---|---|
| `skills/team-advisor/SKILL.md` | Sole-consumer bind wiring and constraints |
| `advisor-tool.md` | Consult timing, hard rule, how to treat advice |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Host bind, floor, lifecycle |
| `agents/session-advisor.md` | ENDORSE / CORRECTION / PLAN / STOP |

## When to use

Follow the call rules in `advisor-tool.md` (orientation first, then consult before substantive work; durable deliverable before the completion consult; stuck or reapproach; long tasks twice).

## Relation to `advisor()`

`/team-advisor` works with no `advisor()` tool. When both exist: `advisor()` for a fast history-forwarded check; `/team-advisor` for a standing named reviewer consulted at the same cadence.
