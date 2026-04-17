# Code Standards

> **MANDATORY REFERENCE:** CODE_RULES.md - Load for ALL code generation.
> This is the single source of truth for code standards. Non-negotiable.

@~/.claude/docs/CODE_RULES.md

**Key principles (see CODE_RULES.md for complete reference):**
- Self-documenting code (no comments)
- Centralized configuration (one source of truth)
- Reuse constants (search before creating)
- No magic values (everything named)
- No abbreviations (full words)
- Complete type hints
- TDD (test first)

## Function Parameters - Required vs Optional

**Use required parameters when no valid use case exists for optional.**
**Remove unused parameters.**

## Encapsulation - Logic Belongs in Models

**NEVER scatter construction logic in calling code.**

Path/URL building, formatting, transformations -> Put in model methods.
If you find yourself building the same string pattern in multiple places, it belongs in the model.

## Document Temporary Code

**Scaffolding/placeholder code MUST have TODO comments.**

When code exists only to enable testing before full implementation:
- Add `// TODO: Replace with...` explaining what will replace it
- Explain WHY it's temporary, not just WHAT it does

## Naming Reflects Behavior

**Name components after what they ARE, not abstract concepts.**

If it overlays the viewport -> "Overlay" not "Screen"
If it validates input -> "Validator" not "Handler"
Names should describe observable behavior or visual appearance.
