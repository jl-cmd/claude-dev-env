# AskUserQuestion Required

Route every user-directed question through the `AskUserQuestion` tool — never a plain-text question in a response's final paragraph. Structure: concise `question`, `header` of 12 chars or fewer, 2-4 options (the UI adds the "Other" fallback), `multiSelect` only when choices genuinely combine.

The `question_to_user_enforcer` Stop hook blocks a response whose final paragraph (after stripping code fences, inline code, and blockquotes) ends in a question mark or contains ask-phrases ("would you like", "should I", "let me know if", ...). Rhetorical questions answered in the same paragraph, and questions inside code or blockquotes, pass. `verify-before-asking` gates whether the question belongs to the user at all.
