# Headless-safety preamble

Every agent prompt the workflow authors carries a headless-safety preamble: the
run is unattended, so agents never inline a destructive-command literal
(`rm -rf`, `git reset --hard`, `dd`) into a Bash command — the
`destructive_command_blocker` hook matches those patterns as raw text, and a
confirmation prompt no human can answer would stall the run.

## Two forms

The preamble has two forms. Read-only agents — the review, verify, and utility
spawns that edit nothing — receive a trimmed form that drops the rm-shape rules,
since a read-only agent never runs `rm`. Edit agents — the fix and commit spawns
— receive the full form that carries the rm-shape rules below.

Agents verify destructive-blocker behavior through the committed test suite
(`python -m pytest`) and keep scratch work in the OS temp dir.

## The rm auto-allow paths (full form)

The full preamble describes three auto-allow paths:

1. **Standalone path** — a standalone Bash call whose target resolves inside the
   ephemeral namespace (`/tmp`, `/temp`, the OS temp root, or the run worktree).
   It fails closed on `$(...)` substitution and backtick subshells. It declines a
   `$`-bearing target only when the literal path is not already under an
   ephemeral root, so it does not by itself stop a `$VAR` that expands inside an
   ephemeral root.
2. **Compound path** — accepts an rm joined with benign reporting segments when
   every rm target is an absolute ephemeral path. It fails closed on `$(...)`
   substitution, backtick subshells, and any `$` in the target — including
   `$CLAUDE_JOB_DIR`.
3. **Cwd-scoped path** — matches only when the command itself declares an
   ephemeral working directory (it `cd`s into one, or runs under one). It
   resolves the target against the declared cwd, fails closed on `$(...)`,
   backticks, and unknown variables, and resolves the known temporary variables
   `TEMP`, `TMP`, `TMPDIR`, and `CLAUDE_JOB_DIR` to the OS temp root. Under a
   declared ephemeral cwd, a bare `$CLAUDE_JOB_DIR/tmp/<name>` target and a
   relative target after a `cd` are auto-allowed.

Even so, for any cleanup whose path is variable-built or whose teardown spans
multiple steps, agents author a Python helper file and run it as
`python <file>.py` — keeping every destructive literal out of a Bash command
string entirely and independent of which auto-allow path matches.
