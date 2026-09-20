# Flag Non-Breaking Findings

**When this applies:** Writing or changing a local gate — a git hook, a
pre-commit entry, a Claude tool-use hook — and deciding what one of its checks
does when it finds something.

## Rule

A gate blocks on a breaking finding and records a non-breaking one.

A **breaking** finding means the change is wrong: a bug, a secret in the
tree, a broken test, a syntax error, an instruction file that no longer
loads. The gate fails and the work stops there.

A **smell** finding means the change reads poorly: a length limit, a naming
convention, a prose term, a comment rule, a structural preference. The gate
records it and lets the commit, the push, or the tool call proceed. A later
pull request carries the fix.

Every check a gate runs declares which of the two it is. A check that cannot
say which one it raises is a breaking check until someone decides otherwise.

## Why

A smell that blocks a commit stops delivery for something the reader would
have fixed in the next pass anyway. The writer then reaches for the bypass
flag, and the bypass turns off the breaking checks beside it. The gate that
blocks on everything ends up enforcing nothing.

Recording the smell keeps both halves working. The breaking checks stay
sharp because nobody routes around them, and the smells still get fixed
because the ledger holds them until a pull request does.

## The ledger

A recorded finding lands in `.claude/followups/smells.jsonl` at the
repository root, one JSON object per line carrying the rule identifier, the
repository-relative path, and the message. `hooks/followup_ledger.py` writes
and reads it. Every write there is fail-safe, so a ledger failure leaves the
gate's decision unchanged.

The ledger is per-checkout state and stays out of the repository.

## Reading and clearing it

| Command | What it does |
|---|---|
| `cde followup list` | Names every recorded follow-up |
| `cde followup ingest REPORT` | Records the diagnostics a policy-lint JSON report carries |
| `cde followup brief` | Writes the task an agent fixes them from |
| `cde followup clear` | Empties the ledger |

The `/fix-followups` command drives the whole pass: it reads the brief, fixes
each rule group, opens a draft pull request, and clears the ledger.

## Worked example

`scripts/validate_instruction_pairs.py` raises five findings and splits them
on this line. A missing governing `AGENTS.md`, an import text that differs,
and an instruction path that is not a regular file each stop the instructions
loading, so the gate fails. A non-canonical filename and a Git mode other than
100644 leave the instructions loading, so the gate records them and passes.

`SEVERITY_BY_RULE_ID` in that module is the whole declaration. Add a check,
add its row.

## Sibling rules

| Rule | Role |
|---|---|
| [`ci-owns-the-gate.md`](ci-owns-the-gate.md) | The full check suite runs once, on CI |
| [`git-workflow.md`](git-workflow.md) | A red required check blocks the branch |
