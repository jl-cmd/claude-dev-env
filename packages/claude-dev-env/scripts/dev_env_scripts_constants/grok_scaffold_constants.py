"""Named constants for the grok batch scaffold generator.

::

    grok_batch_scaffold.py reads these to emit, under the run dir:
        report-contract.md   <- REPORT_CONTRACT_TEMPLATE
        <role>.brief.md      <- READONLY_BRIEF_TEMPLATE or BUILD_BRIEF_TEMPLATE
        <role>.task.md       <- TASK_BODY_TEMPLATE
        batch-spec.json      <- the wired skeleton

Batch-spec field keys and worker defaults are reused from
``grok_worker_constants`` so a scaffolded spec loads through the launcher's own
reader.
"""

from __future__ import annotations

REPORT_CONTRACT_TEMPLATE: str = """# Report contract

End your turn with exactly these sections, in this order. Use plain markdown.
Make the report your last action.

## Changed files

- List every path you wrote or edited, one per line.
- Write `none` for a read-only role or an unchanged tree.

## Red-green evidence

- For each test you added or changed: the failing command/output before the
  fix (red), then the passing command/output after (green).
- Write `n/a - investigation only` for read-only workers.

## Acceptance mapping

For each acceptance line from the brief:

- **Acceptance:** [quote the line]
- **Status:** met | not met | blocked
- **Evidence:** [command output summary or `file:line` proof]

## Test results

- Commands run (full command lines)
- Exit codes
- Short pass/fail summary (paste the key lines and keep logs short)

## Open questions

- Questions for the lead session or advisor (empty list if none)
- Unverified claims that need a second look
- Scope gaps that blocked a full answer
"""
"""Fixed report contract appended as the last prompt part for every worker."""

READONLY_BRIEF_TEMPLATE: str = """# Role: read-only investigation

You investigate only. You read the code and report what you find.

## Scope

- Working directory: [absolute path]
- Paths or symbols in scope: [list]
- Question to answer: [one clear question]
- Boundary paths (report facts here as open questions): [list]

## Method

1. Read the named paths and their direct callers or callees as needed.
2. Cite every claim with `file:line`.
3. Prefer measured facts (names, signatures, call sites) over guesses.
4. When a fact is unproven, label it `unverified`.

## Boundaries

- Work with read-only tools: read files and report.
- Leave every git and GitHub step to the lead session.
- Stay within the listed paths; record any fact you need outside them as an
  open question.

## Done when

You can answer the question with file:line evidence, or you can name the exact
gap that blocks an answer.
"""
"""Brief scaffolded for a ``readonly`` worker; the caller fills the brackets."""

BUILD_BRIEF_TEMPLATE: str = """# Role: build worker

You edit code and run tests for one closed task. Hand every result back to the
lead session, which stages, verifies, commits, pushes, and posts.

## Scope

- Working directory: [absolute path]
- Task: [one sentence]
- Files you may touch: [list]
- Files to leave as-is: [list]
- Acceptance lines (each must map to evidence in the report):
  1. [line]
  2. [line]

## Method

1. Read the in-scope files before editing.
2. Write or update tests that pin the acceptance lines (red first when you add
   behavior).
3. Make the smallest edit that satisfies the acceptance lines.
4. Run the named test commands and capture pass/fail output.
5. Stop with a stage-ready tree and a full report; the lead session commits.

## Boundaries

- Leave every git and `gh` step to the lead session.
- Keep git history and config as you found them.
- Stay within the allow-listed files; record any file you need outside the list
  as an open question.
- Back every acceptance mark with command output or a `file:line` proof.

## Done when

Every acceptance line has evidence, tests you own are green (or failures are
listed with command output), and the report lists every changed file.
"""
"""Brief scaffolded for a ``build`` worker; the caller fills the brackets."""

TASK_BODY_TEMPLATE: str = """# Task

Replace this file with the task-specific scope for this worker: the closed
scope, the exact absolute paths, and the acceptance lines. Keep it
self-contained. A headless worker reads the prompt parts it is given, so write
every part to stand on its own.
"""
"""Placeholder task body the caller overwrites with per-worker scope."""

REPORT_CONTRACT_FILENAME: str = "report-contract.md"
"""Filename of the one shared report-contract part written under the run dir."""

BRIEF_FILENAME_SUFFIX: str = ".brief.md"
"""Suffix for each worker's brief part file, prefixed by the worker role name."""

TASK_BODY_FILENAME_SUFFIX: str = ".task.md"
"""Suffix for each worker's task-body part file, prefixed by the role name."""

BATCH_SPEC_FILENAME: str = "batch-spec.json"
"""Filename of the batch-spec skeleton written under the run dir."""

WORKER_TOKEN_SEPARATOR: str = ":"
"""Separator between role name and tool profile in a ``--worker`` token."""

ROLE_NAME_PATTERN: str = "^[a-z0-9][a-z0-9-]*$"
"""Accepted role-name shape: a lowercase slug safe as a filename prefix."""

CWD_PLACEHOLDER: str = "FILL_ME__absolute_worker_cwd"
"""Working-directory value the caller replaces before launching the batch."""

DEFAULT_SHOULD_PING: bool = False
"""``should_ping`` value seeded into a scaffolded batch spec."""

DEFAULT_IS_REPO_ONLY: bool = False
"""``is_repo_only`` value seeded into each scaffolded worker entry."""

JSON_INDENT: int = 2
"""Indent used when writing the batch-spec skeleton for readable hand-editing."""

CLI_WORKER_FLAG: str = "--worker"
"""CLI flag naming one ``role_name:profile`` worker; repeatable."""

SCAFFOLD_ERROR_STDERR_PREFIX: str = "batch scaffold failed: "
"""Prefix on the stderr diagnostic the CLI prints for a bad argument."""

SCAFFOLD_RESULT_SPEC_FILE_KEY: str = "spec_file"
"""Result JSON key for the batch-spec skeleton path."""

SCAFFOLD_RESULT_REPORT_CONTRACT_FILE_KEY: str = "report_contract_file"
"""Result JSON key for the shared report-contract path."""

SCAFFOLD_RESULT_WORKERS_KEY: str = "workers"
"""Result JSON key for the list of per-worker scaffolded paths."""

SCAFFOLD_WORKER_ROLE_NAME_KEY: str = "role_name"
"""Per-worker result key for the worker role name."""

SCAFFOLD_WORKER_BRIEF_FILE_KEY: str = "brief_file"
"""Per-worker result key for the scaffolded brief part path."""

SCAFFOLD_WORKER_TASK_BODY_FILE_KEY: str = "task_body_file"
"""Per-worker result key for the scaffolded task-body part path."""
