# Team-advisor skill

`/team-advisor` binds one advisor for this session. On a Claude host with the built-in `advisor` tool on, it calls `advisor()`. Otherwise it binds a standing warm advisor at the strongest reachable tier and sends explicit packets to a warm Agent/SendMessage advisor or the read-only `codex_astra_advisor.py` helper.

## Refs

| Doc | Holds |
|---|---|
| `.agents/skills/team-advisor/SKILL.md` | Sole-consumer bind wiring and constraints |
| `advisor-tool.md` | Consult timing, hard rule, how to treat advice |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Session identity, host bind, floor, lifecycle |

## When to use

Follow the call rules in `advisor-tool.md` (orientation first, then consult before substantive work; durable deliverable before the completion consult; stuck or reapproach; long tasks twice).

## Selected path

`/team-advisor` is the repository's advisor implementation. It uses the built-in advisor tool when the session has it. Without the tool, it provides explicit first-consult packets, delta consults, a standing warm reviewer, an in-session Astra spawn on Codex, and a read-only Astra CLI option.
