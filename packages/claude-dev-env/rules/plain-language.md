# Plain Language

All prose a person reads (chat, `AskUserQuestion`, docs, PR/issue bodies, commits): everyday words, short active sentences, lead with the answer, define jargon on first use, and give only the detail the reader needs to act (progressive disclosure). Aim for first-pass readability by a non-specialist. Exact identifiers, file paths, and API names stay exact; code is out of scope.

The `plain_language_blocker` PreToolUse hook (AskUserQuestion + `.md` Write/Edit/MultiEdit) blocks a heavy word and names the everyday swap; code fences, inline code, blockquotes, URLs, and file paths are skipped.
