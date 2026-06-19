# bdd-protocol

**Trigger:** `/bdd-protocol`, "Example Mapping", "BDD anti-patterns", "§7.6", writing executable specifications, BDD scenario quality, "the one where" discovery examples.

On-demand BDD depth layered on top of the always-on `<behavior_protocol>` in the system prompt. The skill adds the Example Mapping algorithm (Smart & Molak §6.4), the scenario quality catalog (§7.6), outside-in test layout, and solo BDD patterns.

## Subdirectories

| Directory | Role |
|---|---|
| `references/` | Loaded reference docs: Example Mapping algorithm and the anti-patterns catalog. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Entry point. `@`-imports both reference files so they load with the skill. Lists authorities and scope boundaries. |
| `references/example-mapping.md` | Example Mapping algorithm: core moves ("The one where …"), the chat algorithm for solo use, time-boxing guidance. Source: Smart & Molak §6.4. |
| `references/anti-patterns.md` | §7.6 scenario quality catalog: anti-patterns to avoid and the criteria for a good scenario. |

## What the skill adds

The base `<behavior_protocol>` (Deliberate Discovery → Illustrate → Formulate → Automate) is always active. This skill adds depth only when:
- The task needs Example Mapping steps or parking-lot question management.
- Scenarios need the §7.6 quality bar applied.
- Tests need outside-in layout using describe / when / should.
