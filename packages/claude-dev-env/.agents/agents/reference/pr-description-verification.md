# Human-checkable PR verification

Use this only when the PR writer needs a concrete verification sample.

Verification should lead with something a reviewer can open, see, click, compare, or try.

Good:

Open the generated PR description. The first paragraph should tell the story in plain words before it names any code detail. If the change has a visible result, point to the exact file, screen, output, or behavior the reviewer can inspect.

Tests: focused checks pass.

Weak:

- Contract test passed.
- Static analysis passed.
- Internal schema assertion passed.

Machine checks can support the claim. They should not be the whole proof when a person can inspect the result directly.
