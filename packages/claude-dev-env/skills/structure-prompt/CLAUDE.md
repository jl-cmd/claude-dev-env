# structure-prompt

Restructures a prompt in one pass: orders blocks, converts persona framing to task constraints, enforces per-category dispositions, expands placeholder tokens, adds `file:line` citations, marks the canonical sub-bucket, and sharpens adversarial-pass phrasing.

**Trigger:** `/structure-prompt`, "optimize this prompt", "minimally invasive edit" to a prompt artifact, "tighten this prompt".

## Purpose

Applies a spoke-based ruleset to a prompt artifact. Each spoke targets a specific structural problem (persona framing, narrative directives, missing citations, etc.). One pass per invocation.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — pre-flight, first-invocation reads, spoke routing table |
| `reference/block-classification.md` | How to classify each block in the input prompt |
| `reference/research.md` | When a spoke needs information not in the input |
| `reference/output-contract.md` | How to emit the rewritten prompt |
| `reference/structure.md` | Re-ordering blocks and handling large content regions |
| `reference/persona.md` | Converting role assignments to task constraints |
| `reference/per-category.md` | Enforcing per-category dispositions |
| `reference/directives.md` | Rewriting performance directives |
| `reference/constraints.md` | Rewriting narrative directives |
| `reference/instantiation.md` | Expanding placeholder tokens |
| `reference/citation-depth.md` | Adding `file:line` citations |
| `reference/canonical-case.md` | Marking the canonical sub-bucket with ⭐ |
| `reference/adversarial-tuning.md` | Sharpening adversarial-pass phrasing |
| `reference/cleanup.md` | Fixing typos, mixed bullet styles, untagged code blocks |
| `reference/examples.md` | Spoke-matched examples for situations not covered above |

## Subdirectories

| Directory | Purpose |
|---|---|
| `reference/` | One file per spoke; loaded on demand based on the routing table in `SKILL.md` |

## Conventions

- On first invocation, read `block-classification.md`, `research.md`, and `output-contract.md` before anything else.
- The input arrives as the user's message body, a fenced block within it, or a file path argument.
- Emit the result as a single fenced block (paste mode) or rewrite the file in place (file-path mode).
- Load only the reference files the input situation matches — not all of them.
