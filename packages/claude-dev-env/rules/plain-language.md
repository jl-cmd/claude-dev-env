# Plain Language

All prose a person reads (chat, `AskUserQuestion`, docs, PR/issue bodies, commits): everyday words, short active sentences, lead with the answer, define jargon on first use, and give only the detail the reader needs to act (progressive disclosure). Aim for first-pass readability by a non-specialist. Exact identifiers, file paths, and API names stay exact; code is out of scope.

The `plain_language_blocker` PreToolUse hook (AskUserQuestion + `.md` Write/Edit/MultiEdit) blocks a heavy word and names the everyday swap; code fences, inline code, blockquotes, URLs, and file paths are skipped. AskUserQuestion calls also face `ask_user_question_style_blocker` for context-before-question and plain-brief length/structure checks (see `ask-user-question-required.md` and `output-styles/plain-brief.md`).

A project can keep its own domain words out of the check with a `.claude/plain-language-allow.json` file: a JSON array of terms. An exact, case-insensitive, whole-word match on any term passes. The hook reads this file only from inside the project tree, up to the repository root, so each project's allowlist stays with its own code.
