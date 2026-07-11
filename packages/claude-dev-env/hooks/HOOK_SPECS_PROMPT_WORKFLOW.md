# Hook Specs: Prompt Workflow

Deterministic gate inventory for the prompt-workflow context-control policy.
Each row below names a gate, its trigger surface, and the enforcement outcome.
Runtime compliance is validated by these hooks and by the Stop guard.

## PreToolUse Task/Agent (removed)

The legacy PreToolUse Task/Agent gate was removed. Execution intent is now
routed through the dedicated intent gate below rather than the generic
Task/Agent PreToolUse hook.

## agent-execution-intent-gate.py

Status: pending implementation. The script `agent-execution-intent-gate.py`
is not yet present in the repository; this section specifies the intended
gate so the policy is captured ahead of the code. Until the script lands,
execution-intent enforcement is advisory only and no runtime hook blocks
ambiguous `/agent-prompt` invocations.

Intended behavior once implemented: fail-closed gate invoked before
`/agent-prompt` executes any spawned work. Confirms the user expressed
explicit execution intent. If the trigger is ambiguous (for example,
`/prompt-generator` output without a follow-up "go run it" signal), the
gate refuses to spawn.

## Leakage + Checklist + Scope (Stop)

Stop-hook guard that blocks prompt-workflow responses which leak prompt
scaffolding, omit required deterministic checklist rows, or violate the
scope anchor contract (`target_local_roots`, `target_canonical_roots`,
`target_file_globs`, `comparison_basis`, `completion_boundary`).

## Required Deterministic Checklist Rows

Every prompt-workflow audit artifact must include these checklist rows with
stable IDs so downstream validators can diff runs deterministically:

- `scope_anchor_present`
- `ownership_boundary_respected`
- `base_minimal_instruction_layer_declared`
- `on_demand_skill_loading_declared`
- `safety_boundary_preserved`

## Runtime Context-Control Signals

Generated prompt-workflow outputs must declare, in their audit frontmatter:

- `base_minimal_instruction_layer: true`
- `on_demand_skill_loading: true`

The Stop guard blocks responses that omit either signal. These signals are
the machine-checkable counterpart to the policy text in
`rules/prompt-workflow-context-controls.md`.
