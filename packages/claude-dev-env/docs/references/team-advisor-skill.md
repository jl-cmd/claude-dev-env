# Team-Advisor Skill Invocation

`/team-advisor` spawns a standing review agent for the session at the strongest reachable model tier, run at the highest reasoning effort. Use it to get a second opinion from a distinct model line than the one driving the session. For example:

- Claude session -> consult Fable xhigh
- Codex session -> consult Sol xhigh

## When to use it

Consult the spawned advisor before big decisions, before declaring work complete, before any commit, when a failure repeats, or when reconsidering a chosen approach.

## Relationship to the advisor tool

`/team-advisor` works standalone; it needs no `advisor()` tool present. When both are available (see `advisor-tool.md` in this directory), use `advisor()` for a fast, history-forwarding check before substantive work, and `/team-advisor` for a standing reviewer consulted at decision points.
