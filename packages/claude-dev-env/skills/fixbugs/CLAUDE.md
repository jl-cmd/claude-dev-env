# fixbugs

Bridges `/findbugs` audit results to `/agent-prompt` for automated fixing. Triggered by `/fixbugs`, `fix all the bugs`, `apply the audit fixes`, or `implement the findbugs results`.

## Purpose

A thin bridge: recover the prior `/findbugs` findings from the current conversation, apply an optional severity filter (`P0`, `P0+P1`, `P1`, or all), re-resolve PR scope, then hand the filtered finding list to `/agent-prompt` as a structured goal string. `/agent-prompt` authors the XML prompt, shows an Outcome preview, asks for confirmation, and spawns a background sonnet `clean-coder` agent to apply all fixes in one commit.

This skill never audits, never edits files, and never spawns agents directly. The `/agent-prompt` confirmation gate is always preserved.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Four-step process: recover findings, apply severity filter, re-resolve PR scope, hand off to `/agent-prompt` with a goal string in the exact expected shape. Includes refusal cases (no findings, zero bugs, empty filter, missing `agent-prompt` skill) and the implementer constraints (one commit, no `--force`, no rebase, explicit `git add` by path). |

## Invocation order

Run `/findbugs` first, then `/fixbugs`. Running `/fixbugs` with no prior `/findbugs` in the session returns `No findings in this session. Run /findbugs first.`
