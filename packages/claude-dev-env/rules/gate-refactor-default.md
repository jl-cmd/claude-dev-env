# Gate Refactor-to-Pass Default

When a gate blocks an edit, the default is to refactor the code so it passes the gate.

The `gate_question_default_gate` hook (PreToolUse on AskUserQuestion) backs this: on a question about a gate-blocked edit, it wants the "Refactor to pass the gate" choice listed first and marked recommended, and it denies a gate question that buries or drops that choice.

The skip flag is a last resort. An agent may write a gate-skip token (the `hooks/blocking/gate_skip_token` store) only on user approval and only in a true deadlock. The token escalates the block to a permission prompt, where a human click grants it — the token never allows an edit on its own, and never carries a new finding past. It is wired into both gate surfaces, `code_rules_enforcer` and `run_all_validators`.
