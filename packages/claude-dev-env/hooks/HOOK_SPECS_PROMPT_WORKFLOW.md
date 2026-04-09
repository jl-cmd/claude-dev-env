# Prompt Workflow Hook Specs

Deterministic runtime gates for prompt workflows.

## Gate: Execution Intent (PreToolUse Task/Agent)

- Hook: `hooks/blocking/agent-execution-intent-gate.py`
- Event: `PreToolUse`
- Matcher: `Task|Agent`
- Fail condition:
  - Missing structured execution intent contract field:
    - `tool_input.execution_intent: explicit|execute|delegate`, or
    - `tool_input.execution_intent_explicit: true`, or
    - `tool_input.metadata.execution_intent: explicit|execute|delegate`
  - Missing required scope anchors in launch payload (always enforced when execution launch is evaluated)
- Compatibility fallback:
  - Text markers are only accepted when `PROMPT_WORKFLOW_ALLOW_TEXT_INTENT_FALLBACK=1` is set.
  - Fallback usage is logged to stderr.
- Action: `deny` with concrete missing requirement list.

## Gate: Leakage + Checklist + Scope (Stop)

- Hook: `hooks/blocking/prompt-workflow-stop-guard.py`
- Event: `Stop`
- Fail condition:
  - Raw internal refinement object appears in assistant output without explicit debug intent
  - Prompt-workflow response detected but deterministic checklist container is missing
  - Prompt-workflow response detected and required deterministic checklist rows are missing
  - Prompt-workflow response detected and required scope anchors are missing
  - Prompt-workflow response detected and runtime context-control signals are missing
  - Scope-bound text uses banned ambiguous scope terms
- Action: `block` with correction reason.

## Required Scope Anchors

- `target_local_roots`
- `target_canonical_roots`
- `target_file_globs`
- `comparison_basis`
- `completion_boundary`

## Required Deterministic Checklist Rows

- `structured_scoped_instructions`
- `sequential_steps_present`
- `positive_framing`
- `acceptance_criteria_defined`
- `safety_reversibility_language`
- `reversible_action_and_safety_check_guidance`
- `concrete_output_contract`
- `scope_boundary_present`
- `explicit_scope_anchors_present`
- `all_instructions_artifact_bound`
- `scope_terms_explicit_and_anchored`
- `completion_boundary_measurable`
- `citation_grounding_policy_present`
- `source_priority_rules_present`

## Runtime Context-Control Signals

- `base_minimal_instruction_layer: true`
- `on_demand_skill_loading: true`

These two signals are runtime-checked by the Stop guard whenever a prompt-workflow response is detected.

## Deterministic Boundary

These hooks enforce only structural/runtime checks. Semantic quality remains in auditor layer.
