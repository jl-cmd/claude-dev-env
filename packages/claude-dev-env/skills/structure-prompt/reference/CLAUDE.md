# structure-prompt/reference

One reference file per optimization spoke, loaded on demand by the routing table in `SKILL.md`.

## Key files

| File | Purpose |
|---|---|
| `block-classification.md` | How to classify each block in the input prompt (mission, metadata, framework, questions, output spec, data body). Read on every invocation. |
| `research.md` | Steps to take when a spoke needs information not in the input. Read on every invocation. |
| `output-contract.md` | How to emit the rewritten prompt (fenced paste mode or in-place file rewrite). Read on every invocation. |
| `structure.md` | Re-ordering blocks and handling large content regions (≥500 chars, fenced code, diffs, transcripts). |
| `persona.md` | Converting role assignments ("You are…", "Act as…") to task constraints. |
| `per-category.md` | Enforcing per-category dispositions when the prompt names 2+ categories or criteria. |
| `directives.md` | Rewriting performance directives ("be thorough", "think step by step"). |
| `constraints.md` | Rewriting narrative directives ("try to", "make sure", "consider"). |
| `instantiation.md` | Expanding placeholder tokens (`[REPO/ARTIFACT]`, `[N]`, etc.). |
| `citation-depth.md` | Adding `file:line` citations to sub-bucket bullets that reference identifiers. |
| `canonical-case.md` | Marking the ⭐ canonical sub-bucket when a framework has 5+ sub-buckets and none is marked. |
| `adversarial-tuning.md` | Sharpening generic adversarial-pass phrasing. |
| `cleanup.md` | Fixing typos, mixed bullet styles, untagged code blocks, trailing whitespace. |
| `examples.md` | Spoke-matched examples for situations not covered by the named spokes above. |

## Conventions

- Read `block-classification.md`, `research.md`, and `output-contract.md` on every first invocation of a session.
- For all other files: load only the one(s) that match the input situation — the `SKILL.md` routing table maps each situation to its spoke file.
- Never load the full set; spoke files are designed for on-demand use to keep context lean.
