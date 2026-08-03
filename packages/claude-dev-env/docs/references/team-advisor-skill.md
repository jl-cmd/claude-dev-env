# Team-Advisor Skill

`/team-advisor` binds one standing warm advisor for this session at the strongest reachable tier. This skill is the selected custom reproduction path for advisor behavior: it forwards explicit packets to a warm Agent/SendMessage advisor or the read-only `codex_sol_advisor.py` path across many decision points.

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

`/team-advisor` is the deliberately selected path for this repository. It reproduces the advisor contract with explicit first-consult packets, delta consults, a standing warm reviewer, and a read-only Sol CLI option; native `advisor()` mechanics remain source context and are not invoked by this skill.
