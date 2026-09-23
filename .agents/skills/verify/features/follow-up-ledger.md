# Follow-up ledger

A local gate that finds a non-breaking smell records it in a per-checkout ledger and lets the work proceed. `cde followup` reads the ledger back, briefs the agent that fixes it, and empties it.

## Sub-features

- The ledger file `.claude/followups/smells.jsonl`, one JSON record per line with `rule_id`, `check_id`, `file_path`, `message`, `severity`, and `origin_commit`. `hooks/followup_ledger.py` writes and reads it.
- The gates that write to it. `scripts/validate_instruction_pairs.py` records `instruction-filename` and `instruction-git-mode` and exits 0. `scripts/repository_policy.py` records its `package-inventory` finding through `scripts/repository_checks/followups.py`.
- `cde followup list`, `ingest REPORT`, `brief`, `count`, and `clear`, run by `scripts/followup_cli.py`. Each takes `--repository-root PATH`.
- The `check_id` field of `cde lint --format json`, which `ingest` copies into each record.
- The `/fix-followups` command in `commands/fix-followups.md`, which reads `brief`, fixes each check group, opens a draft pull request, and runs `clear`.

## How to get to it (user POV)

Make a scratch Git repository with one commit. Record a smell through a gate, or pipe a lint report into `ingest`. Then read it back with `list`, `brief`, and `count`, and empty it with `clear`.

## Driving it with the package

Run these from the scratch repository root. `$cde` is the absolute path of `packages/claude-dev-env/bin/cde.mjs` in this checkout.

```powershell
node $cde followup list
node $cde followup count
node $cde lint --files src\app.py --format json > lint.json
node $cde followup ingest lint.json
node $cde followup list
node $cde followup brief
node $cde followup clear
python <checkout>\packages\claude-dev-env\scripts\validate_instruction_pairs.py --repository-root .
```

Expected results:

| Command | Output | Exit |
|---|---|---|
| `list` or `brief` on an empty ledger | `no follow-ups recorded` | 0 |
| `count` at or under 20 records | `<n> follow-ups recorded, threshold 20` | 0 |
| `count` over 20 records | `... over the threshold of 20. Work the backlog down ...` | 1 |
| `ingest` of a readable report | Nothing, and one ledger line per new finding | 0 |
| `ingest` of a missing or non-JSON file | `cannot read the lint report: <path>` | 2 |
| `ingest` with no path, or an unknown subcommand | The usage text | 2 |
| `list` | One line per record: check id, path, origin commit, message, tab-separated | 0 |
| `brief` | A header, one `- [<check id>] <path>: <message> (recorded at <commit>)` line per record, and a footer naming `clear` | 0 |
| `clear` | Nothing, and `smells.jsonl` is gone | 0 |
| The instruction-pair gate on a `CLAUDE.md` with Git mode 100755 | `recorded for follow-up: Commit the instruction file with Git mode 100644: CLAUDE.md` | 0 |

Run the paired tests:

```powershell
python -m pytest packages/claude-dev-env/hooks/test_followup_ledger.py packages/claude-dev-env/scripts/test_followup_cli.py packages/claude-dev-env/scripts/test_validate_instruction_pairs.py -q
node --test packages/claude-dev-env/bin/cde.test.mjs
```

## Gotchas

- `--repository-root` defaults to the working directory. A command run from a subdirectory reads and writes a separate ledger under that subdirectory.
- `ingest` records every diagnostic as a `smell`, including the ones `cde lint` marks `error`. Settle the blocking findings before you ingest a report.
- `cde lint` exits 1 when it writes any diagnostic. Read the report file, and ignore that exit code before `ingest`.
- Write the lint report from `pwsh` 7, whose `>` writes UTF-8 with no byte-order mark. `ingest` reads UTF-8 only, so a UTF-16 file from the Windows PowerShell 5.1 `>` or a UTF-8 file with a byte-order mark stops with `cannot read the lint report` and exit 2.
- A diagnostic with no `check_id` records its `rule_id` in that field. A diagnostic with no `rule_id` or no `message` is skipped.
- A record is written once per `check_id`, path, and message. A second `ingest` of the same report adds no line.
- `origin_commit` comes from the `.git/HEAD` file and the loose ref it names. It is empty in a linked worktree, where `.git` is a file, and after `git pack-refs` moves the branch ref into `packed-refs`.
- The `brief` footer names `python <absolute path>/followup_cli.py clear`, the script inside the package that ran it.
- The first record writes `.claude/followups/.gitignore` holding `*`, so `git status` lists nothing from the ledger directory. `clear` removes only `smells.jsonl`.
