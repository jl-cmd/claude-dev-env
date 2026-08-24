# Task seeds

Register each item with `update_plan` at audit start. Complete with evidence.

1. Load the rule: `docs/agents/name-by-capability.md` when present, else `reference/rule-checklist.md` (always keep the skill checklist as fallback).
2. Fetch PR title, body, and changed/renamed paths via `reference/fetch-commands.md`.
3. Classify each naming signal as violation, OK driver, or skip (`reference/offense-examples.md` classifier first).
4. Emit report from `reference/report-template.md`.
5. After the report, continue with `SKILL.md` **Mode routing**.
6. For `preflight-proposal`, complete the shared contract referenced by `SKILL.md` **Mode routing**.
