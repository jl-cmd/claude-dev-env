# Right-Sized Engineering

**Build it right, but build it simple.** Good engineering principles at the appropriate scale.

## Always Do
- Extract constants and configuration (no hardcoding)
- Create reusable functions (no copy-paste)
- Use proper error handling
- Follow DRY from the start
- Single responsibility per function

## Never Do (Solo Scale)
- Abstract base classes for single implementations
- Dependency injection frameworks
- Complex patterns (CQRS, microservices)
- Multiple inheritance hierarchies
- Over-abstracted interfaces

## Complexity Budget

**State BEFORE implementation:** Files (target 1-2, max 3), Lines (~50-300), Checkpoints ("Is this MINIMUM?", "Fewer files?", "Functions vs classes?")

## YAGNI for API Surface

**Don't expose optional parameters until they're actually used.**

If a value will always be a constant for now, use the constant internally.
Only add the parameter when callers actually need to vary it.
