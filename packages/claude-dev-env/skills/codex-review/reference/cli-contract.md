# CLI contract

Observed shape of the Codex CLI review surface the skill classifies from. Fixture capture: `codex` 0.144.3.

## Command shape

### Classifying path: `codex exec … review --json`

Skill classification (Step 4) reads only the JSONL stream from:

```text
codex exec [exec-options] review --json [review-options] [PROMPT]
```

`--json` is required for a classifiable success stream. Without `--json`, stdout is not a Step 4 input.

### `codex review` (non-classifying)

Plain `codex review` is a non-interactive review form. It is **not** the skill classifying path: bare `codex review --json` is not a supported classifiable form on the observed CLI (0.144.3). Do not feed plain `codex review` stdout into skill classification.

| Form | Role |
|---|---|
| `[PROMPT]` | Optional custom review instructions; `-` reads stdin |
| `-c` / `--config key=value` | Dotted-path overrides, values parsed as TOML |
| `--uncommitted` | Staged + unstaged + untracked |
| `--base <BRANCH>` | Diff against a base branch |
| `--commit <SHA>` | Diff for a commit |
| `--title <TITLE>` | Review title |
| `--enable` / `--disable <FEATURE>` | Feature toggles |

Exactly one target among `PROMPT`, `--uncommitted`, `--base`, and `--commit`. The four targets are mutually exclusive: a flag target never carries a positional `[PROMPT]`, and the custom-instructions text is itself the fourth target (PROMPT mode only). The same target flags apply under `codex exec … review`.

Observed rejection when a flag target is combined with `[PROMPT]` (fixture: `codex` 0.144.3):

```text
error: the argument '--uncommitted' cannot be used with '[PROMPT]'
Usage: codex exec review --json --uncommitted [PROMPT]
```

Exit code 2.

### `codex exec`

Subcommands: `resume`, `review`, `help`.

| Option | Role |
|---|---|
| `-c` / `--config` | Config override |
| `-i` / `--image` | Image input |
| `-m` / `--model` | Model id |
| `--oss` | OSS path |
| `-p` / `--profile` | Profile |
| `-s` / `--sandbox <read-only\|workspace-write\|danger-full-access>` | Sandbox mode |
| `--full-auto` | Full auto |
| `--dangerously-bypass-approvals-and-sandbox` | Bypass approvals and sandbox |
| `-C` / `--cd <DIR>` | Working directory |
| `--json` | JSONL event stream on stdout (required for classification) |
| `-o` / `--output-last-message` | Write last message to a path |

### Ordering rule

`codex exec` options belong **before** the `review` subcommand. Review options such as `--json` and `--uncommitted` follow `review`.

- Parses: `codex exec review --json --uncommitted`
- Fails (exit 2, usage on stderr): trailing `-C <DIR>` after `review` (`unexpected argument '-C' found`)

Run from the target repo directory, or place `-C <DIR>` before `review`.

## Success stream

`codex exec … review --json` writes JSONL on stdout and exits 0 on success.

1. `thread.started` — includes `thread_id`
2. `turn.started`
3. `item.started` / `item.completed` pairs for `command_execution` items (read-only git commands via the shell)
4. `item.updated` for a `todo_list` item
5. `item.completed` with `"type":"agent_message"` — review text body
6. `turn.completed` — `usage` object: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`

### Finding-bullet format

The `agent_message` text is a one-line summary, then `Review comment:`, then finding bullets:

```text
- [P1] <title> — <path>:<start>-<end>
```

Each bullet is followed by an explanation paragraph. Priority tags use the `[P1]` form (and sibling priority numbers).

## Failure classes

All observed CLI failures map to wrapper `outcome_class=codex_down`.

| Class | Exit | Stream | Observed message shape |
|---|---|---|---|
| `codex_down` | 1 | Plain text on stderr; no JSONL | Config-load rejection, e.g. `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in 'service_tier'` |
| `codex_down` | 1 | JSONL on stdout | `error` event whose message embeds a 400 `invalid_request_error` JSON (`The '<model>' model is not supported when using Codex with a ChatGPT account.` / `The '<model>' model requires a newer version of Codex.`), then `item.completed` `agent_message` `Review was interrupted...`, then `turn.failed` repeating the embedded error |
| `codex_down` | 2 | Usage text on stderr; no JSONL | Argument / CLI parse error (e.g. unexpected option after `review`) |

## Wrapper capture boundary

Entrypoint: `scripts/run_codex_review.py` → `run_codex_review(...)`.

The wrapper is **capture only**. It returns one of two classes:

| Wrapper class | Meaning |
|---|---|
| `completed` | Review process exited 0; JSONL stream written under `run_state_directory` |
| `codex_down` | Binary missing, timeout, decode failure, shape miss, or non-zero review exit |

Skill-level classes `down` / `clean` / `findings` are **not** produced here. The skill (Step 4) maps:

| Skill class | Source |
|---|---|
| `down` | Wrapper `codex_down` |
| `clean` | Wrapper `completed` and findings parse empty |
| `findings` | Wrapper `completed` and findings parse non-empty |

### Capture fields

| Field | Role |
|---|---|
| `outcome_class` | Success signal for the capture boundary (`completed` / `codex_down`) |
| `exit_code` | Process status only (or a sentinel). May be `0` while `outcome_class` is `codex_down` (shape probe exits 0 but required flags are missing) |
| `binary_version` | Parsed `codex --version` string, or empty |
| `jsonl_path` | Path to captured stdout JSONL, or `None` when review did not run |
| `agent_message` | Last JSONL `agent_message` text when present; on non-zero review exit, falls back to stderr when JSONL has no agent message |

### Caller contracts

- Create `run_state_directory` before calling the wrapper; the wrapper writes `codex-review.jsonl` into that directory and does not create parents.
- A missing `repository_directory` or `run_state_directory` raises `ValueError`. Both are checked before any Codex process starts, so a bad path costs no review run.
- Treat `outcome_class` as the capture success signal; do not treat `exit_code == 0` alone as success.
- `codex-review.jsonl` holds the stream's own line endings, so the captured file matches the bytes Codex wrote to stdout.

## Skill classification map

Skill steps and loop re-entry use three skill-level classes. This page's raw CLI failure name is `codex_down` only.

| Skill class (`SKILL.md` Step 4) | Maps from this page | Signal |
|---|---|---|
| `down` | Any `codex_down` row; unrecognized probe shape | Non-usable review |
| `clean` | Success stream (exit 0 JSONL) with no finding bullets in the `agent_message` body | Usable review, zero addressable findings |
| `findings` | Success stream (exit 0 JSONL) with one or more `- [P#] …` bullets in the `agent_message` body | Usable review with addressable findings |

## Auth surface

- Credentials live under the Codex home directory as `auth.json`. `CODEX_HOME` relocates that directory. `cli_auth_credentials_store = "file"` pins the file store.
- `CODEX_API_KEY` authenticates a single `codex exec` invocation.
- The same `config.toml` serves the desktop app and the CLI. A value one accepts can fail the other's parser; that path surfaces as the config-load `codex_down` row above.

## Probe

Probe command: `codex exec review --help`. The wrapper probes this help surface and treats any unrecognized shape as `codex_down`.

### Minimum shape signals

The `review` subcommand is proven by the probe itself: a CLI without it exits non-zero on `codex exec review --help`, which is already a `codex_down` signal.

The help text must then include each of these four flags as a **whole token** (not a mere substring of a longer flag name):

| Signal | Role |
|---|---|
| `--uncommitted` | Staged + unstaged + untracked target |
| `--base` | Base-branch target |
| `--commit` | Commit-SHA target |
| `--json` | JSONL event stream on stdout |

Longer lookalikes (`--baseline`, `--uncommitted-only`, `--commit-message`) do not satisfy the required target flags.

### Fail-closed rule

Any missing signal, non-zero probe exit, or missing binary is `codex_down` (skill class `down`). Do not continue to a review invoke when the probe fails.
