# templates

Template files the `plan-packet.mjs` workflow renders when building a plan packet.

## Key files

| File | Role |
|---|---|
| `README.md` | Markdown template for the packet's top-level `README.md`. Placeholder slots for plan title, goal, status, packet map, and build path. |
| `build-prompt.md` | Template for `handoff/build-prompt.md` — the standalone prompt the build agent reads to start coding without needing the rest of the packet. |
| `reuse-audit.md` | Template for `validation/reuse-audit.md` — the per-item verdict table the workflow fills in during the reuse audit step. |
| `source-map.md` | Template for `context/source-map.md` — the inventory of source files and facts the planner extracts. |
| `visual-plan.template.html` | Single-file offline HTML template. The workflow fills this with packet data after validation to produce `visual-plan.html` beside the packet. Inlines all CSS and JavaScript; references no external assets. |
