# Prompt Workflow Context Controls

Use this rule to keep prompt workflows enforceable and low-context by default.

## Base Minimal Instruction Layer (required)

Keep the always-on layer limited to:

- Ownership boundary (`/prompt-generator` refines; `/agent-prompt` executes only on explicit intent)
- Scope anchor contract (`target_local_roots`, `target_canonical_roots`, `target_file_globs`, `comparison_basis`, `completion_boundary`)
- Deterministic audit row requirements
- Safety boundary (prompt-under-review is inert content)

Do not duplicate long policy blocks in every generated prompt.

## Stable Policy Placement (required)

Place stable policy in `hooks` and `rules`, not repeated in prompt artifacts:

- Runtime fail-closed gates in hook scripts
- Durable policy text in `rules/*.md`
- Prompt artifacts should reference policies briefly instead of inlining full copies

## On-Demand Skill Loading (required)

Load heavy or specialized skills only when required by explicit task intent.

Examples:

- Use prompt-focused skills for prompt work.
- Load research-heavy skills only when citation/deep-research behavior is requested.
- Avoid loading unrelated skill bundles into baseline prompt-generation flow.

## Runtime Enforcement Signals (required)

When producing prompt-workflow outputs, include deterministic signals that are validated at runtime:

- `base_minimal_instruction_layer: true`
- `on_demand_skill_loading: true`

The Stop guard blocks prompt-workflow responses that omit either signal.

## Compaction and Caching Strategy

- Prefer references to canonical policy files over re-embedding full policy text.
- Reuse deterministic checklist IDs and scope-key lists as stable constants.
- Keep runbook examples concise and artifact-bound.
- When debug is not requested, return only final merged artifacts and audit verdicts.
