# Proposal format (decision brief + AskUserQuestion)

Present **one** coherent plan. Do not drip slices across turns.

## Decision brief (chat, before AskUserQuestion)

**Required.** Print this brief in the agent chat response **before** any `AskUserQuestion` call. The approval control is not the first place the plan appears.

Cover, in order:

1. **Source** — PR `#N`, title, file count  
2. **Decisions** — what path-layer heuristics got wrong (if anything) and every re-bucket you made (path or layer moves, empty `other`, order changes)  
3. **Slice table** — index, story, file count, branch, base  
4. **Merge order** — `1 → 2 → …`  
5. **Execute mode after approve** — draft stacked PRs (default) or local branches only  
6. **Source branch** — stays intact (no rewrite, no force-push)

Keep it scannable: short paragraphs, one table, no open-ended “how should we split?” prose.

## AskUserQuestion options

After the brief is visible, call `AskUserQuestion` with a short confirm question and these options:

1. **Approve recommended split** (Recommended) — run execute with `--push --create-prs`  
2. **Approve local branches only** — execute without push/PRs  
3. **Abort** — no git mutations  

The question text may restate the slice count and merge order in one line. Full tables and decision rationale live in the chat brief above the tool call.

Use **Other** for adjust instructions (move path X to slice Y, rename, drop a layer merge). After adjust: edit plan → verify → new decision brief → new `AskUserQuestion`.

## Do not

- Call `AskUserQuestion` before the decision brief is in chat  
- Ask open-ended “how would you like to split this?” without a concrete plan  
- Offer more than one full alternative matrix unless the user rejected the first plan  
