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
   - XML scaffold includes all sections — verified by the Stop hook at runtime; each required section tag must have both an opening and a closing tag:
     - `<role>`
     - `<background>`
     - `<instructions>`
     - `<constraints>`
     - `<output_format>`
     - `<illustrations>`
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
   - Default output must not leak the raw internal refinement object fields.

## Deterministic Checklist Coverage

Audit report must include all check IDs:

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
- `artifact_language_confidence`

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
- Execution handoffs that go through `/agent-prompt` carry scope-block context in the execution prompt as needed.
- Final refined prompt content is treated as artifact text during refinement and audit.
- Execution steps (when requested) are bound to scope block artifacts.

## Scope-Phrasing Validation

- Reject ambiguous scope wording such as "this session", "current files", "here", "above", or "as needed" when used as scope boundaries.
- Require artifact-bound replacements using explicit roots, globs, comparison basis, and measurable completion boundary.

## Runtime Hook Gate Validation

Validate fail-closed runtime gates:

1. **Stop leakage/scope/checklist gate**
   - **Section-presence gate (Stop)** — Block responses where the fenced XML artifact is missing any of the five required section tag pairs: `role`, `background`, `instructions`, `constraints`, `output_format`.
   - Block responses that leak raw internal refinement object fields unless debug intent is explicit.
   - Block responses missing deterministic checklist rows when audit output is present.
   - Block responses using ambiguous scope phrasing in scope-bound sections.
   - Block responses containing negative keywords (no, not, don't, never, avoid, etc.) inside fenced XML artifacts.
   - Block responses containing hedging language (might be, possibly, I think, etc.) inside fenced XML artifacts.

## Context-Footprint Controls

- Keep baseline prompt-workflow policy minimal by default.
- Store stable enforcement text in hooks/rules; avoid repeating full policy blocks in prompt artifacts.
- Load heavy skills on demand based on explicit task intent.
- Prefer canonical references and compact outputs over repeated long policy text.

## Deterministic vs Semantic Boundary

- **Deterministic (fail-closed):**
  - Missing required scope anchors (when Stop guard applies)
  - Raw internal object leakage without debug intent
  - Missing required checklist rows in audit output
  - Missing required XML sections (`role`, `background`, `instructions`, `constraints`, `output_format`) in the fenced artifact (opening and closing tags)
  - Ambiguous scope terms in scope-bound text
  - Negative keywords inside fenced XML artifacts
  - Hedging language inside fenced XML artifacts
- **Semantic-only (auditor layer):**
  - Overall quality/readability of scope wording beyond banned-term checks
  - Whether instruction binding quality is "good enough" beyond explicit anchor presence
  - Whether context compaction is optimal for a specific task

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
