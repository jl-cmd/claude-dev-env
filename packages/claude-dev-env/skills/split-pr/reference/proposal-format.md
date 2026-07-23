# Proposal format (AskUserQuestion)

Present **one** coherent plan. Do not drip slices across turns.

## User-visible summary (in the question text)

- Source PR `#N` — title — file count  
- Slice table: index, story, file count, branch, base  
- Warnings from analyze (`other` layer, below threshold, single layer)  
- Merge order: `1 → 2 → …`  
- Execute mode after approve: draft stacked PRs (default)

## Options

1. **Approve recommended split** (Recommended) — run execute with `--push --create-prs`  
2. **Approve local branches only** — execute without push/PRs  
3. **Abort** — no git mutations  

Use **Other** for adjust instructions (move path X to slice Y, rename, drop a layer merge). After adjust: edit plan → verify → new AskUserQuestion.

## Do not

- Ask open-ended “how would you like to split this?” without a concrete plan  
- Offer more than one full alternative matrix unless the user rejected the first plan  
