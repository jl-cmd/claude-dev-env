# BDD (discovery-driven development)

**Canonical detail:** `~/.claude/system-prompts/software-engineer.xml` → `<behavior_protocol>`.

**On-demand depth:** `@~/.claude/skills/bdd-protocol/SKILL.md` (Example Mapping §6.4, §7.6 catalog, solo patterns). Tracking design: [jl-cmd/claude-code-config#82](https://github.com/jl-cmd/claude-code-config/issues/82).

**Optional long-form references (load when needed):**

- `@~/.claude/docs/BDD_SCENARIO_QUALITY.md` — seven scenario quality patterns (§7.6-style)
- `@~/.claude/docs/BDD_DISCOVERY_PROTOCOL.md` — Example Mapping algorithm for chat
- `@~/.claude/docs/BDD_TEST_LAYOUT.md` — describe/when/should layout and soap-opera personas

## What you do for every non-trivial feature

1. **Deliberate Discovery** — Reduce uncertainty before code; surface what you do not know (Smart & Molak §5.4).
2. **Illustrate** — Explore goals, constraints, and concrete examples in chat; "given … when … then …" style outcomes.
3. **Formulate** — Express behavior as narrow **"should …"** specifications the user can approve.
4. **Automate** — Failing specification first, then minimum code to pass; refactor only for a concrete smell.

Conversation is the essential practice: if discovery is skipped, structured formats do not rescue the workflow (Minimal BDD).

## Solo developer

You are often the stakeholder. Use **Example Mapping** in chat ("the one where …", probes, parking lot). Load **`bdd-protocol`** when you need the full algorithm and anti-pattern list.

## Naming

Developer-facing specs and tests use **should** sentences so intent stays visible (Dan North, "Introducing BDD", 2006).
