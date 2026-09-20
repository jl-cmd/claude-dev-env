---
name: team-advisor
description: >-
  Bind one advisor, the built-in advisor tool or a warm session-advisor, and
  consult it before substantive work, completion, commits, or when stuck.
  Triggers:
  'team-advisor', 'team advisor', 'second opinion', 'consult the advisor',
  'get an advisor', 'check my approach with an advisor'.
---

# Team Advisor

One warm advisor at the strongest tier this session can reach. This session is the sole consumer.

## Refs

| Doc | Holds |
|---|---|
| [`docs/references/advisor-tool.md`](../../../docs/references/advisor-tool.md) | **Consult cadence and weight.** When to call, the hard rule before first write, and how to treat advice. Read this for every consult. |
| [`~/.claude/_shared/advisor/advisor-protocol.md`](../../../_shared/advisor/advisor-protocol.md) | **Bind and lifecycle.** Session identity, host detect, model floor, warm-up, CLI fallback. Its read map routes each moment to a `reference/` detail file. |
| [`agents/session-advisor.md`](../../agents/session-advisor.md) | **Reply contract.** ENDORSE / CORRECTION / PLAN / STOP. SendMessage only. |
| [`reference/advisor-docs-review.md`](reference/advisor-docs-review.md) | Anthropic advisor-tool source facts: measured effects, Sonnet steering, cost levers, failure modes. Background. Read it when tuning the bind, not on every consult. |

## Bind

1. Name the session identity first (protocol **Host profiles**), then walk the model floor.
2. Claude: when `advisor` is in this session's tool list, the built-in advisor tool is the advisor. Spawn nothing and call `advisor()` at each consult point. Otherwise spawn Fable in-session at `ADVISOR_EFFORT` (default low). When Fable is out of usage, bind Astra at the same effort. Codex: Astra in-session. Third-party: headless Fable then Astra. When the host's walk fails, fail closed.
3. Name: `team-advisor-agent` on Claude (Agent spawn of `session-advisor`); a native Astra subagent on Codex with `flags: ["--advisor"]`; one CLI `session_id` on a third-party host via the protocol Claude-chain or Astra helper.
4. Skip the multi-consumer "who you are" opener. This session is the sole consumer.
5. When the bind or reply path fails, fail closed and report to the user. On a third-party host, only the bound advisor issues ENDORSE / CORRECTION / PLAN / STOP.

**GOTCHA (Cursor / ThirdParty + Astra):** when the walk reaches Astra or the user asks for Astra, first tool call is `python ~/.claude/_shared/advisor/scripts/codex_astra_advisor.py --bind --enable-astra --cwd <repo-root>` with the charter on stdin. Do not use Agent or Task. Do not search for a probe path. Details: [`third-party-bind.md`](../../../_shared/advisor/reference/third-party-bind.md) GOTCHA and [`astra-rung.md`](../../../_shared/advisor/reference/astra-rung.md).

Full walk, charter, consult packet, Astra routing, and drift re-bind live in the protocol read map and its `reference/` files.

## Consult

Follow **When to call**, **Hard rule**, and **How to treat advice** in `advisor-tool.md`.

Build every first brief with [`_shared/advisor/reference/consult-format.md`](../../../_shared/advisor/reference/consult-format.md). Later briefs carry only the delta and changed evidence.

With the built-in advisor tool, call `advisor()` with no brief. The tool forwards the whole transcript. Its reply is free text, not one of the four signal words, so weigh it per **How to treat advice** in `advisor-tool.md`.

Aim for two consults on a normal task: one after orientation and one after writes and validation. Reserve a third for advisory recovery or reconciliation guidance, and add a consult when a material fork produces new evidence. This is an advisory target owned by the task, not a cap or gate.

## Constraints

- One bind per session; this session owns the built-in tool choice, spawn, in-session Astra spawn, or CLI bind, drift re-bind, and shutdown.
- Bind at or above the protocol floor for this host.
- The advisor only answers (messaging); the session runs tools and posts.
- Keep an optional reference gap in the reference record: path, status, repair action, and repair result. A reference gap leaves bind status separate.
- On Codex, select native Astra when its bind and reply validation pass. Record `selected_tier: Astra` and `reply_path: native`.
- Mark `fallback_kind: broken` only when the selected bind or reply path fails. Record the selected tier, fallback reason, and reply path in the same evidence object.
- Record first, recovery, and completion consults with changed evidence, validation, unresolved risks, and report-back status.
- Write the evidence object to the session-controlled `model-tier-run.json` record described in `advisor-tool.md`.
