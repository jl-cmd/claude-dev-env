# Surface cleanup

The optimized prompt has consistent surface formatting.

## Pass list

| Surface | State after cleanup |
|---|---|
| Typos in mission, metadata, framework, output spec, or questions | Spelled correctly |
| Bullet style within a single section | Single style throughout (`-`) |
| Code block language tags | Every fenced block inside the prompt artifact carries a language tag |
| Trailing whitespace on lines | Removed |
| Runs of 3+ blank lines | Collapsed to one blank line |
| Heading levels | Sequential within each block (no jumps from `#` to `###`) |

## Scope

This pass changes surface formatting only. Identifiers, content, and ordering pass through unchanged.

## Typo-correction carve-out

Typo fixes apply only to plain-language prose — narrative sentences, mission statements, instructions to the agent, and similar running text. The pass leaves these surfaces untouched even when they look like typos:

- Text inside backtick code spans (e.g., `` `mispelled_var` `` stays as-is)
- Text inside fenced code blocks (any language, any content)
- Identifiers, file paths, URLs, IDs, SHAs, ID prefixes, proper names
- Any quoted substring the user could be referencing literally (e.g., `"recieve"` in quotes stays as-is)

These surfaces are subject to the byte-for-byte preservation invariant in [`output-contract.md`](output-contract.md). When in doubt about whether a token is prose or a literal reference, leave it unchanged.

## Disposition reporting

Every surface-formatting change emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines (e.g., `> Gap: Typo corrected in mission line — "recieve" → "receive".`, `> Gap: Code block language tag added — python.`). When the surface pass makes zero changes, emit a single note: `> Gap: Surface cleanup verified — no formatting issues found.` Silent pass is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
