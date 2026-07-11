# docs

Reference documentation installed into `~/.claude/docs/` by `bin/install.mjs`. These files are loaded on demand by rules, skills, and agents — they are not always-on context.

## Files

| File | Purpose |
|---|---|
| `CODE_RULES.md` | Compact agent reference for all code rules; ⚡ marks hook-enforced rules; canonical source agents load before writing code |
| `TEST_QUALITY.md` | Test writing standards: what to test, what to remove, React testing patterns, anti-patterns |
| `BDD_DISCOVERY_PROTOCOL.md` | Example Mapping algorithm for discovery before implementation; based on Smart & Molak *BDD in Action* §6.4 |
| `BDD_SCENARIO_QUALITY.md` | Seven scenario quality patterns (§7.6-style catalog) |
| `BDD_TEST_LAYOUT.md` | `describe/when/should` test layout and soap-opera personas |
| `PR_DESCRIPTION_GUIDE.md` | Authoritative reference for the `pr-description-writer` agent; PR body shapes derived from a 120-PR Anthropic corpus |
| `DJANGO_PATTERNS.md` | Django-specific coding patterns |
| `REACT_PATTERNS.md` | React-specific coding patterns |
| `emotion-informed-prompt-design.md` | Guidance for emotionally-aware prompt authoring |
| `agents-md-alignment-plan.md` | Alignment between `AGENTS.md` review-tool rules and the local hook enforcement layer |

## Subdirectory

| Entry | Description |
|---|---|
| `references/` | Pointer documents to external sources and standard terminology; loaded on demand |

## Load pattern

Rules reference these docs with `@~/.claude/docs/<file>.md` to pull them into context only when needed, rather than loading every doc on every session start.
