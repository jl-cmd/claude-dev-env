# File-based PR splitting principles

Load when heuristics need a re-rank or the user challenges slice order.

## Goal

Each PR tells **one story** a human can review without holding the whole feature in working memory. Slices form a **dependency chain**: later PRs base on earlier ones.

## Default chain

1. **Database** — schema, migrations  
2. **Contracts** — shared types, protos  
3. **Backend** — API, services, middleware  
4. **Frontend** — UI, hooks, pages  
5. **Tests** — unit/integration coverage  
6. **Config** — packaging, CI, lockfiles  
7. **Docs** — markdown / docs tree  

Skip empty layers. Keep tests with their layer only when the user wants vertical slices; default is a dedicated tests slice so production code reviews stay focused.

## Independence rules

- Slice N must build on merge of 1…N−1 (stacked bases).
- Prefer each slice green on its own after prior merges (project-specific validate is judgment; this skill does not invent `npm test` for every repo).
- Never leave a source path unassigned.

## What this skill does not do

- Line-level hunk splitting (`git add -p`)  
- Interactive “write me a bash script” tutoring  
- Review or converge of the resulting PRs (hand off to `/pr-converge`)
