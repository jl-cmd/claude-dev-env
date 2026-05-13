# Detection Rules

All 10 rules. Run every rule against every file. Do not skip. Do not combine. Rules are independent — a file can trigger multiple rules.

## Rule 1: Canonical-source cross-reference

For every canonical source, scan every other file for usages of the concepts it defines. The canonical source is the ground truth. Flag every mismatch.

How: Take the canonical MCP payload doc. Extract every tool name and its parameter names. Scan every markdown file for calls to those tools. Compare each call's parameter names against the canonical form.

How: Take the canonical config file. Extract every constant name and value. Scan every other file. Flag any file that hardcodes the value. Flag any file that uses a different value for the same concept.

This rule caught 20 of Copilot's 43 findings. It is the highest-signal rule. Run it first.

## Rule 2: Parameter naming convention

Group all MCP tool calls by tool name. Check whether all call sites use the same parameter naming convention.

How: Extract every parameter name from every tool call. Group by tool. If `add_issue_comment` appears in 10 files and 8 use `issueNumber` while 2 use `issue_number`, flag the 2.

Conventions are per-tool. `issue_read` uses `issue_number` (snake_case). `add_issue_comment` uses `issueNumber` (camelCase). Snake_case for `add_issue_comment` is wrong.

Also: check for two different parameter names that mean the same thing. `--number` vs `--pr-number` for a script that expects `--pr-number`.

## Rule 3: Code vs docstring behavior

For every function whose docstring makes a claim about return values or error handling, read the implementation.

How: Find docstrings that say "returns X when Y" or "raises Z on error." Trace the code path. If the docstring says returns 0 when path missing but the code catches OSError and returns failure, flag it.

How: Find docstrings that claim a side effect. Check whether the code does it unconditionally. Flag missing precondition checks.

How: Find error handling claims like "tolerates already-removed worktrees." Read the except blocks. Read the conditionals. Verify every claim.

## Rule 4: Nonexistent reference

Every file path, script name, function name, tool name, or import referenced in a doc must resolve to something real.

How: Extract every backtick-quoted identifier. Try to resolve it against the diff and the repo. Flag anything that cannot be found. A reference to `fetch_copilot_inline_comments.py` when no such file exists is P0. A reference to `EnterWorktree(path=...)` when no MCP tool by that name exists is P0.

## Rule 5: Placeholder detection

Scan for text that looks like a template never filled in. This is text that cannot be executed as written.

Patterns to search for:
- Double spaces where a value should be: "Spawn  — brief it: check  for"
- Angle-bracket placeholders outside the standard `<O>` `<R>` `<N>` `<SHA>` set
- Ellipsis as placeholder: "...", "…"
- "TODO", "FIXME", "HACK", "XXX" in production documentation
- "TKTK", "TK", "placeholder"
- Missing arguments after a flag: `--flag` with no value following
- Sentences that trail off: text ending in ", or", "like", "such as" without completing

Severity: unexecutable placeholder is P0. Incomplete but still directionally useful is P1.

## Rule 6: Cross-file contradiction

When two files describe the same operation, they must agree.

How: Group descriptions by topic — "how to post a review," "how to trigger bugbot," "who owns PR posting." For each topic, extract the description from every file. Compare who performs the action, what API is used, what parameters are passed, what the workflow order is. Flag any contradiction.

Flag both files. Do not assume which is correct unless a canonical source resolves it.

## Rule 7: Stale reference

When a doc describes a feature, branch, phase, or pattern by name, verify the implementation still contains it.

How: Extract named concepts from decision branches and gotcha sections. Search implementation files for each concept. If a doc describes an "inline_lag" branch but no implementation file contains "inline_lag" or "inline_lag_streak," the doc references a removed feature.

P1: doc mentions something absent from implementation. P0: doc decision tree includes a branch whose predicate can never be reached because the implementation was removed.

## Rule 8: Cross-platform assumption

Code that handles platform-specific behavior must not break on other platforms.

When you see Windows-specific patterns (`os.chmod` with `stat.S_IWRITE`, backslash paths, ReadOnly attribute handling), check: Does it run on Linux without crashing? Does `os.chmod(path, stat.S_IWRITE)` produce the right permissions on POSIX? It sets write-only, stripping read and execute from directories.

Flag anything that would fail on a non-Windows system. Flag the reverse: POSIX-only code that would fail on Windows.

## Rule 9: Script invocation correctness

Every `python scripts/foo.py --*` in docs must match the script's actual argparse interface.

From your manifest, compare each documented invocation against the script's `add_argument` definitions. Check every flag name matches exactly. Check every `required=True` argument is present. Check no argument appears that the script does not accept.

Missing required args = P0. Wrong flag names = P0. Missing optional args = P2.

argparse converts `--pr-number` to `pr_number`. The invocation flag is `--pr-number`, not `--pr_number` or `--number`.

## Rule 10: Value consistency

When the same named concept has a numeric value in multiple files, all files must agree.

How: Group constants, thresholds, and timeouts by semantic concept. "Bugbot post-trigger wakeup" vs "inline-lag retry delay" are different concepts. Values that represent the same thing must match. Flag any file whose value differs from the majority or from the canonical config.

Values that legitimately differ by context are not conflicts. Group by full semantic meaning before comparing.
