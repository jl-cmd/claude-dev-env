# Code Standards

> **MANDATORY REFERENCE:** CODE_RULES.md - Load for ALL code generation.
> This is the single source of truth for code standards. Non-negotiable.

`CODE_RULES.md` (`~/.claude/docs/CODE_RULES.md`) is the compact reference for every standard: self-documenting names, centralized configuration, constant reuse, no magic literals, full words, complete type hints, required-vs-optional parameters, construction logic in the model, temporary-code `TODO:` markers, behavior-first component names, and TDD.

Two standards live there in full and nowhere else:

- **TDD** — CODE_RULES §8 is canonical: red, green, refactor, with no production code before a failing test.
- **Right-sized engineering** — CODE_RULES §7 is canonical: functions over classes, concrete over abstract, an abstraction added at the commit that introduces its second concrete implementation.

BDD is the outer process and TDD is the inner loop: [`bdd.md`](bdd.md) discovers and formulates the behavior a feature needs, then each formulated behavior is built through the CODE_RULES §8 red-green-refactor cycle.
