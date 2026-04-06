# Prompt Refinement Pipeline Runbook

## Purpose

Validate deterministic behavior for:

1. Base prompt generation (`/prompt-generator`)
2. Six section refiners (owned by `/prompt-generator`)
3. Merge + final audit with citation-grounded checks
4. Targeted fix + capped re-audit loop

## Sample Input

Use this command:

```text
/prompt-generator Create a trusted final system prompt for a coding agent that edits files safely, follows user scope, and returns concise status updates.
```

## Expected Stage Artifacts

1. **Base stage**
   - Scope block is present and explicit:
     - `target_local_roots`
     - `target_canonical_roots` (if applicable)
     - `target_file_globs`
     - `comparison_basis`
     - `completion_boundary`
   - XML scaffold includes all sections:
     - `<role>`
     - `<context>`
     - `<instructions>`
     - `<constraints>`
     - `<output_format>`
     - `<examples>`
   - Includes internal refinement object with:
     - `pipeline_mode: internal_section_refinement_with_final_audit`
     - `required_sections` list with all six sections
     - section/merge/audit output contracts

2. **Section refinement stage**
   - Exactly 6 agent runs, one per section.
   - Each section output includes:
     - `improved_block`
     - `rationale`
     - `concise_diff`
   - No section agent edits another section.

3. **Merge stage**
   - One canonical merged prompt with all six sections.

4. **Audit stage**
   - Output includes:
     - `overall_status`
     - `checklist_results`
     - `corrective_edits`
     - `retry_count`
   - Every checklist item includes:
     - `status`
     - `evidence_quote` (direct quote)
     - `source_ref`
     - `fix_if_fail`

5. **Final output**
   - One complete prompt block that is copy-pasteable.
   - Internal refinement object is not shown unless debug output was requested.

## Deterministic Checklist Coverage

Audit report must include all check IDs:

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

## Citation and Grounding Validation

For each factual compliance claim in the audit:

- Include a source citation
- Include a word-for-word quote
- If unsupported, explicitly return "I don't know"

Source priority must be applied in this order:

1. Official vendor docs (external behavior)
2. Local project files (local behavior)
3. Academic / named experts
4. Reputable external URLs
5. Blog/community content

## Non-pass Loop Validation

If `overall_status` is `fail`:

1. Apply only targeted edits listed in `corrective_edits`
2. Re-run audit
3. Stop after retry cap (`max_retries: 2` unless explicitly overridden)
4. Return unresolved failures with evidence if still failing at cap

## Ownership and Execution-Intent Validation

- Prompt refinement remains inside `/prompt-generator`.
- `/agent-prompt` is used only after explicit execution/delegation intent.
- Final refined prompt content is treated as artifact text during refinement and audit.
- Execution steps (when requested) are bound to scope block artifacts.

## Doc Alignment Validation

Each major workflow requirement added in skills text must map to at least one principle:

- Structured/scoped instructions
- Clear sequential process
- Positive framing
- Explicit acceptance criteria
- Concrete output format contract
- Reversibility/safety constraints

## Traceability Validation

Each major requirement in skill text should point to:

- Anthropic best-practice URL, and/or
- Local source file path used as authority
