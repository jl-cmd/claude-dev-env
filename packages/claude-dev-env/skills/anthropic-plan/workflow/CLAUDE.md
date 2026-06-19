# workflow

Workflow scripts for the `anthropic-plan` skill.

## Key files

| File | Role |
|---|---|
| `plan-packet.mjs` | Main workflow script. Resolves repo root, reads project context, builds the source inventory, writes the full packet under `docs/plans/<slug>/`, runs `validate_packet.py`, spawns `plan-packet-validator` in a fresh context, runs the reuse audit, builds the visual HTML from `templates/visual-plan.template.html`, and returns the packet path and validation state. |
| `plan-packet.contract.test.mjs` | Contract tests that verify the workflow script's interface and required steps without a live repo. |
| `debug-53b979.log` | Debug log artifact from a workflow run (not committed output; present in the working tree). |

## Running

The `plan-packet.mjs` script runs via the `Workflow` tool — do not invoke it directly with Node. The skill's `SKILL.md` specifies the exact call signature and required `args`.
