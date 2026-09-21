# Flag Non-Breaking Findings

**When this applies:** Writing or changing a local gate — a git hook, a
pre-commit entry, a Claude tool-use hook — and deciding what one of its checks
does when it finds something.

## Rule

A gate blocks on a breaking finding and records a non-breaking one.

A **breaking** finding means the change is wrong: a bug, a secret in the
tree, a broken test, a syntax error, an instruction file that fails to
load. The gate fails and the work stops there.

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
repository root, one JSON object per line. `hooks/followup_ledger.py` writes
and reads it. Every write there is fail-safe, so a ledger failure leaves the
gate's decision unchanged.

| Field | What it carries |
|---|---|
| `rule_id` | The rule that raised the finding |
| `check_id` | The single check behind it, which a severity table keys on |
| `file_path` | The repository-relative path the finding names |
| `message` | The text a reader acts on |
| `severity` | The class the gate put it in |
| `origin_commit` | The revision checked out when it was recorded |

The origin commit groups a follow-up pull request by the change that raised
the findings. A smell seen again under a later revision keeps the revision
that first raised it, so one smell stays one record.

The ledger is per-checkout state and stays out of the repository.

## The check identifier

Most lint rules run one check, so their rule identifier already names it. The
`code-rules` and `validators` rules bundle many checks behind one identifier.
`scripts/policy_lint/check_catalog.py` resolves those to a `<rule>/<check>`
identifier, which `cde lint --format json` emits as `check_id` on every
diagnostic. A consumer partitions findings by that identifier rather than by
message text.

A message no catalog entry names resolves to `<rule>/unclassified`, which a
partition treats as blocking. A check whose wording moves reports louder
rather than going quiet, and the catalog's synchronization tests fail on the
same change.

## Reading and clearing it

| Command | What it does |
|---|---|
| `cde followup list` | Names every recorded follow-up |
| `cde followup ingest REPORT` | Records the diagnostics a policy-lint JSON report carries |
| `cde followup brief` | Writes the task an agent fixes them from |
| `cde followup clear` | Empties the ledger |
| `cde followup count` | Reports the backlog against the threshold |

`count` exits non-zero once the backlog passes
`FOLLOWUP_BACKLOG_THRESHOLD` in
`scripts/dev_env_scripts_constants/followup_constants.py`, so a scheduled job
escalates rather than opening one more quiet pull request. The number is the
repository's setting, and raising or lowering it is one edit there.

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

`scripts/repository_policy.py` splits the committed-tree checks the same way.
`SEVERITY_BY_CHECK_ID` in `repository_checks/config/constants.py` carries one
row per check id, and a check id with no row reads as breaking. The
`package-inventory` check is the one smell there. A production file whose
package inventory omits its row still imports and still runs, so the check
prints its finding with an `advisory:` prefix, records it in the ledger, and
leaves the tree passing. Every other committed-tree check blocks: a `CLAUDE.md`
naming a file that does not exist, an env-var row naming a file that never
reads the variable, a test outside the testpaths allowlist, and a tracked
secret.

## Sibling rules

| Rule | Role |
|---|---|
| [`ci-owns-the-gate.md`](ci-owns-the-gate.md) | The full check suite runs once, on CI |
| [`git-workflow.md`](git-workflow.md) | A red required check blocks the branch |
