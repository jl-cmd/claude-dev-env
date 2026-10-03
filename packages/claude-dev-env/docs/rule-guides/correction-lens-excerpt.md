# Correction lens excerpt

This file carries the Codex copy of [`rules/correction-lens.md`](../../rules/correction-lens.md). The Codex compatibility materializer projects the fenced block below into a managed `AGENTS.md`.

## Excerpt for repository-instruction sessions

Codex reads its repository `AGENTS.md`; this excerpt supplies the standalone
contract.

```
Correction handling for this run, from rules/correction-lens.md.

Every correction the user gives becomes a control. Run it through five layers
and land it at the highest one that can hold it:

1. Codebase. The mistake is impossible by how the code is written: a type, a
   signature, a data structure, an API shape.
2. Static analysis. A program reads the tree and decides: a lint rule, an
   enforcer check, a paired test, a CI gate.
3. Review tooling. A reviewer or a review bot reads the criterion: a code-rules
   row, a BUGBOT pointer, a Graphite rule.
4. Skill. An agent follows a procedure.
5. Style guide. Word choice and prose shape.

Close the correction with three sentences: the layer chosen, why each higher
layer cannot hold the lesson, and the change opened at that layer in this run.
Effort rules out no layer; a missing capability does, and you name which one.

The same correction arriving twice means the layer was too low. Move it up one
layer and say so.

Land the control in the repository whose code, CI, or pipeline it guards. The
shared environment package takes only repo-agnostic controls that any
repository could use. A memory file records the decision and encodes nothing.
```
