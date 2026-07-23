# Advisor Tool

`advisor()` is a review tool backed by a stronger reviewer model. It takes no parameters — calling it forwards the entire conversation history automatically, so the reviewer sees the task, every tool call made, and every result seen so far.

## When to call it

Call `advisor()` before substantive work: before writing, before committing to an interpretation, before building on an assumption. Orientation work — finding files, fetching a source, seeing what exists — comes first; call `advisor()` once that orientation is done and before the substantive step begins.

Treat the advisor as more experienced than the calling agent. Consult it whenever a path forward is uncertain.

## Availability

`advisor()` is present only in environments where it has been configured as a tool. Check the available tools before relying on it; when it is absent, fall back to `/team-advisor` (see `team-advisor-skill.md` in this directory).
