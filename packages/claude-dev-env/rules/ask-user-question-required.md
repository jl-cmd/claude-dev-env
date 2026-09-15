# AskUserQuestion Required

Route every user-directed question through the `AskUserQuestion` tool — never a plain-text question in a response's final paragraph. Structure: concise `question`, `header` of 12 chars or fewer, 2-4 options (the UI adds the "Other" fallback), `multiSelect` only when choices genuinely combine.

No hook checks this. Read your own final paragraph before you send it. A paragraph that ends in a question mark, or that carries an ask-phrase such as "would you like", "should I", or "let me know if", belongs in an `AskUserQuestion` call instead. A rhetorical question answered in the same paragraph is fine, and so is a question inside code or a blockquote. `verify-before-asking` settles whether the question belongs to the user at all.

## The question block stays lean

`AskUserQuestion` renders as one plain unformatted text block. Detail — plans, counts, tradeoffs, background — goes in chat text before the call. The block itself carries a lean question and short choices. When a choice needs formatting, an inline visualizer tool carries it.

No hook denies an over-full block, so keep an `AskUserQuestion` call inside these caps yourself. They apply to the `question` text and to the `description` under any of the `options`:

| What the block carries | Cap |
|---|---|
| Fenced code block | none |
| Heading | none |
| Table row | none |
| Bullet or numbered list marker | none |
| Paragraphs | 1 — a blank line splits the block in two |
| `question` sentences | 2 |
| `question` words | 40 |
| `description` sentences | 1 |
| `description` words | 15 |

Two fields are counted, and each one gets the same treatment: the `question` text, and the `description` under every entry of `options`. The four structure markers apply to both. The paragraph cap applies to both. The sentence and word caps differ by field, as the table shows.

Structure is read at block level on the raw text: a marker counts when it opens a line, so a fence written on a single line still reads as a fence. Line endings fold to one spelling first, so a blank line counts whichever way it is written.

An inline code span — a path, a flag, a command the reader needs verbatim — weighs one word against either word cap on both fields, so a question naming `--dry-run` and a choice naming `C:\dev\gate.py` both pass. A span sits inside a line, so it never opens one with a marker.

A sentence closes on `.`, `!`, or `?` followed by a capitalized word or by the end of the text. A word is any whitespace-separated token carrying a letter or a digit. When a block breaks a cap, move that detail back into chat text before the call.
