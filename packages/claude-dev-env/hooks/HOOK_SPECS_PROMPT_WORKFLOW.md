# Prompt Workflow Hook Specs

Deterministic runtime gates for prompt workflows.

## Gate: Execution Intent (PreToolUse Task/Agent)

- Hook: `hooks/blocking/agent-execution-intent-gate.py`
- Event: `PreToolUse`
- Matcher: `Task|Agent`
- Fail condition:
  - Missing explicit execution marker (`execution_intent: explicit` or equivalent explicit-intent markers)
  - Missing required scope anchors in launch payload
- Action: `deny` with concrete missing requirement list.

## Gate: Leakage + Checklist + Scope (Stop)

- Hook: `hooks/blocking/prompt-workflow-stop-guard.py`
- Event: `Stop`
- Fail condition:
  - Raw internal refinement object appears in assistant output without explicit debug intent
  - Audit output present but required deterministic checklist rows missing
  - Scope-bound text uses banned ambiguous scope terms
  - Scope block implied but required anchors are missing
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
- `no_destructive_shortcuts_guidance`
- `concrete_output_contract`
- `scope_boundary_present`
- `explicit_scope_anchors_present`
- `all_instructions_artifact_bound`
- `no_ambiguous_scope_terms`
- `completion_boundary_measurable`
- `citation_grounding_policy_present`
- `source_priority_rules_present`

## Deterministic Boundary

These hooks enforce only structural/runtime checks. Semantic quality remains in auditor layer.
