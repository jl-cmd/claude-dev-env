# Team-Advisor Skill Invocation

`/team-advisor` spawns a standing review agent for the session at the strongest reachable model tier, run at the highest reasoning effort. Use it to get a second opinion from a distinct model line than the one driving the session — for example, when the main session runs on Opus, invoke `/team-advisor` to get a Fable-backed advisor.

## When to use it

Consult the spawned advisor before big decisions, before declaring work complete, before any commit, when a failure repeats, or when reconsidering a chosen approach.

## Relationship to the advisor tool

`/team-advisor` and the `advisor()` tool (see `advisor-tool.md` in this directory) serve different moments in a session, and both get used as the moment calls for it: `advisor()` for a fast, history-forwarding check before substantive work; `/team-advisor` for a standing reviewer consulted at decision points.
