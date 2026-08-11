# Plain Language

All prose a person reads (chat, `AskUserQuestion`, docs, PR/issue bodies, commits): everyday words, short active sentences, lead with the answer, define jargon on first use, and give only the detail the reader needs to act (progressive disclosure). Aim for first-pass readability by a non-specialist. Exact identifiers, file paths, and API names stay exact; code is out of scope.

The `plain_language_blocker` PreToolUse hook (AskUserQuestion + `.md` Write/Edit/MultiEdit) names an everyday swap for a heavy word when `CLAUDE_PROSE_STYLE_ENFORCEMENT` is on (default off). That path is **allow with a systemMessage advisory** — it does not deny the write. AskUserQuestion lean-block structure stays always on and still denies chat detail. When the flag is off, heavy-word hits only emit privacy-safe advisory candidates (see [`docs/references/prose-style-enforcement.md`](../docs/references/prose-style-enforcement.md)). Code fences, inline code, blockquotes, URLs, and file paths are skipped.

[`eli11-replies`](eli11-replies.md) governs reply length and shape; [`opus5-communication-contract`](opus5-communication-contract.md) governs progress and finals; this rule governs word choice.

A project can keep its own domain words out of the check with a `.claude/plain-language-allow.json` file: a JSON array of terms. An exact, case-insensitive, whole-word match on any term passes. The hook reads this file only from inside the project tree, up to the repository root, so each project's allowlist stays with its own code.
