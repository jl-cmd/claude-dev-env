---
description: Prevent over/under-engineering
allowed-tools: Task
---

Launch the clean-coder agent to review code for appropriate engineering practices.

The agent will evaluate whether abstractions, patterns, and practices match the actual needs of the project, ensuring code is neither over-engineered nor under-engineered for its current scale and purpose.

The review will identify:
- **Over-engineering**: Abstract classes with single implementations, unnecessary interfaces, complex patterns where simple functions would suffice
- **Under-engineering**: Hardcoded values, magic numbers/strings, copy-pasted code, missing error handling
- **Good examples**: Appropriate constant extraction, well-scoped functions, clear error handling, simple maintainable solutions

The goal is to build it right, but build it simple - applying good engineering principles at the appropriate scale for the project.