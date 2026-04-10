# prompt-generator — file map

Baseline inventory of files in the prompt-generator skill package.

## Baseline inventory

| Path | Role |
| --- | --- |
| `SKILL.md` | Orchestrator rules, subagent contract, compliance audit |
| `TARGET_OUTPUT.md` | User-visible output contract for evals and hooks |
| `REFERENCE.md` | Tiered sources, harness patterns, debug schema |
| `REFINEMENT_PIPELINE_RUNBOOK.md` | Evidence-grounding runbook |
| `evals/prompt-generator.json` | Scenario eval rows |
| `templates/skill-from-ground-up.md` | Net-new skill checkpoint template |
| `templates/skill-refinement-package.md` | Existing-skill refinement template |
| `hooks/blocking/prompt_workflow_validate.py` | Validator CLI (file-based loop) |
| `hooks/blocking/prompt_workflow_gate_core.py` | Fence extraction, markers |
| `hooks/blocking/prompt_workflow_clipboard.py` | Clipboard copy for artifacts |
