# PR cleanup process inventory

| Step | Class | Home | Evidence | Paired test |
|---|---|---|---|---|
| Resolve PR and immutable parent SHA | deterministic | `task-seed:reference/task-seeds.md` | Target record and parent SHA | task-tool |
| Create isolated preflight worktrees | deterministic | `task-seed:reference/task-seeds.md` | Worktree paths and base SHA | task-tool |
| Run parallel preflight streams | borderline | `SKILL.md` and `task-seed:reference/task-seeds.md` | Stream reports and worker availability | task-tool |
| Apply or disposition findings | judgment | `SKILL.md` and `task-seed:reference/task-seeds.md` | Changed diff or exact disposition | task-tool |
| Validate parent head | deterministic | `task-seed:reference/task-seeds.md` | Scoped test and confirmation results | task-tool |
| Promote parent and record exact Ready SHA | deterministic | `task-seed:reference/task-seeds.md` | Remote parent Ready state and SHA | task-tool |
| Merge exact parent SHA into child | deterministic | `task-seed:reference/task-seeds.md` | Child merge commit and parent SHA | task-tool |
| Prove parent SHA ancestry | deterministic | `task-seed:reference/task-seeds.md` | `git merge-base --is-ancestor` exit code `0` | task-tool |
| Reapply relevant fixes to child | judgment | `SKILL.md` and `task-seed:reference/task-seeds.md` | Child diff and reapplication record | task-tool |
| Validate child and rerun confirmations | deterministic | `task-seed:reference/task-seeds.md` | New child-head tests, simplify, and review results | task-tool |
| Promote child and report | deterministic | `task-seed:reference/task-seeds.md` | Child Ready state and finish report | task-tool |
