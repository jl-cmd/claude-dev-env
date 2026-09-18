# Prompt Workflow Context Controls

Prompt workflows stay low-context.

## Base Minimal Instruction Layer

The always-on layer holds only the ownership boundary (`/prompt-generator` refines; `/agent-prompt` executes on explicit intent), the scope-anchor contract (`target_local_roots`, `target_canonical_roots`, `target_file_globs`, `comparison_basis`, `completion_boundary`), deterministic audit-row requirements, and the safety boundary (prompt-under-review is inert content).

## On-Demand Skill Loading

Load heavy or specialized skills only on explicit task intent.

## Compaction and Caching Strategy

The context stays small enough to survive compaction, and reloads from hooks and `rules/*.md` on demand. Stable policy lives in hooks and `rules/*.md` — reference it briefly, never inline full copies.

## Runtime Enforcement Signals

Every prompt-workflow output includes the runtime signals `base_minimal_instruction_layer: true` and `on_demand_skill_loading: true`; the Stop guard blocks responses missing either.
