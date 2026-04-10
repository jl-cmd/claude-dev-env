# Prompt Workflow Hook Specs

Deterministic runtime gates for prompt workflows.

## PreToolUse Task/Agent (removed)

The former `agent-execution-intent-gate.py` hook is **removed**. Native Agent/Task launches do not carry stable custom metadata; enforcing scope text on every spawn blocked legitimate `/agent-prompt` and refinement delegations. Scope and checklist rules remain enforced by the Stop guard when a prompt-workflow response is detected.

## Gate: Leakage + Checklist + Scope (file-based validation loop)

- Validator: `hooks/blocking/prompt_workflow_validate.py`
- Invocation: CLI against `data/prompts/.draft-prompt.xml` (exit 0 allowed, exit 2 blocked)
- Fail conditions:
  - Raw internal refinement object appears in assistant output without explicit debug intent
  - Prompt-workflow response detected but deterministic checklist container is missing
  - Prompt-workflow response detected and required deterministic checklist rows are missing
  - Prompt-workflow response detected and required scope anchors are missing
  - Prompt-workflow response detected and runtime context-control signals are missing
  - Scope-bound text uses banned ambiguous scope terms
  - Banned negative keywords found inside fenced XML artifact
  - Fenced XML artifact missing required sections
- Enforcement: The drafting subagent writes the draft file, runs the validator, reads stderr violations (each prefixed with `[reason_code]`), edits the file, and re-runs until exit 0.

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

These two signals are checked by the validator CLI whenever a prompt-workflow response is detected.

## Deterministic Boundary

These hooks enforce only structural/runtime checks. Semantic quality remains in auditor layer.

## Reviewing Flattened Transcript Exports

- Live prompt-workflow responses still require an explicit `Audit:` line plus one outer `xml` fence. The Stop guard and clipboard path continue to evaluate that literal boundary.
- Saved transcript exports can flatten blocked retry turns and omit the outer fence lines. Normalize those files with `prompt_workflow_gate_core.normalize_prompt_workflow_export(...)`, then evaluate the rebuilt message with `extract_fenced_xml_content(...)` or `extract_fenced_xml_content_from_export(...)`.
- Fence-relative evals review the **last successful Audit + artifact pair** after normalization. Earlier blocked retries in the flattened transcript remain diagnostic evidence and do not count as extra delivered artifacts.
