# Block classification

Every input prompt decomposes into six block types. Tag each region of the input as exactly one type before applying any spoke rules.

## Block types

**Mission block.** One sentence stating what the agent does. The opening directive of the prompt.

**Metadata block.** Identifiers, SHAs, PR numbers, target paths, ID prefixes, scope flags, mode toggles. Short atomic facts the agent uses as parameters.

**Framework block.** The checklist, sub-bucket list, surface list, category list, or step list the agent processes. Multi-item structures with named entries.

**Questions block.** Cross-cutting questions, synthesis questions, or open questions the agent answers after completing the framework.

**Output spec block.** The format the agent's output takes — totals header, per-item shape, ordering, severity tags, locator format, length cap, lead phrase, closing phrase.

**Data body block.** Any of:
- Fenced code block (triple backtick) that sits INSIDE the prompt content — not the outer paste-mode fence that wraps the entire prompt artifact
- Diff, file dump, transcript, log, table, or document inlined as content
- Any single content region of 500 characters or more that the agent inspects rather than acts on

## Tagging procedure

1. Read the input prompt top to bottom.
2. Annotate each region with exactly one tag.
3. Confirm every content region is either tagged with one of the six block types or part of a gap-report block. Gap-note lines (`> Gap:`) and `<!-- gap-report:` comment blocks from a prior invocation form a passthrough region — preserved in place during classification and reordering, not re-tagged. During emission, the gap-report region is deterministically replaced by the current run's gap notes per [`output-contract.md`](output-contract.md). The gap-report region sits at the end of the prompt and carries no classification tag.
4. Proceed to the matching spoke.
