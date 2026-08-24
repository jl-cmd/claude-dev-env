# Task seeds

Register each item with `update_plan` at audit start. Complete with evidence.

1. Load the rule: `docs/agents/name-by-capability.md` when present, else `reference/rule-checklist.md` (always keep the skill checklist as fallback).
2. Fetch PR title, body, and changed/renamed paths via `reference/fetch-commands.md`.
3. Classify each naming signal as violation, OK driver, or skip (`reference/offense-examples.md` classifier first).
4. Emit report from `reference/report-template.md`.
5. Apply the requested or suggested rename direction by default; an explicit audit-only request is report-only and ends after the report.
6. When the mode is `preflight-proposal`, verify the resolved PR number and immutable base and head SHAs, create the proposal evidence from `reference/preflight-proposal.md`, record its immutable proposal ID, changed paths, exact tests and outcomes, and add the ID to the downstream owner's selected or dispositioned proposal collection.
