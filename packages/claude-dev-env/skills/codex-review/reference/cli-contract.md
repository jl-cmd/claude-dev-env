# CLI contract

Observed shape of the Codex CLI review surface the wrapper invokes. Fixture capture: `codex` 0.144.3.

## Command shape

### `codex review`

Non-interactive code review.

| Form | Role |
|---|---|
| `[PROMPT]` | Optional custom review instructions; `-` reads stdin |
| `-c` / `--config key=value` | Dotted-path overrides, values parsed as TOML |
| `--uncommitted` | Staged + unstaged + untracked |
| `--base <BRANCH>` | Diff against a base branch |
| `--commit <SHA>` | Diff for a commit |
| `--title <TITLE>` | Review title |
| `--enable` / `--disable <FEATURE>` | Feature toggles |

Exactly one target among `PROMPT`, `--uncommitted`, `--base`, and `--commit`.

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
| `--json` | JSONL event stream on stdout |
| `-o` / `--output-last-message` | Write last message to a path |

### Ordering rule

`codex exec` options belong **before** the `review` subcommand.

- Parses: `codex exec review --json --uncommitted`
- Fails (exit 2, usage on stderr): trailing `-C <DIR>` after `review` (`unexpected argument '-C' found`)

Run from the target repo directory, or place `-C <DIR>` before `review`.

## Success stream

With `--json`, a successful run writes JSONL on stdout and exits 0.

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

All observed failures classify as `codex_down`.

| Class | Exit | Stream | Observed message shape |
|---|---|---|---|
| `codex_down` | 1 | Plain text on stderr; no JSONL | Config-load rejection, e.g. `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in 'service_tier'` |
| `codex_down` | 1 | JSONL on stdout | `error` event whose message embeds a 400 `invalid_request_error` JSON (`The '<model>' model is not supported when using Codex with a ChatGPT account.` / `The '<model>' model requires a newer version of Codex.`), then `item.completed` `agent_message` `Review was interrupted...`, then `turn.failed` repeating the embedded error |
| `codex_down` | 2 | Usage text on stderr; no JSONL | Argument / CLI parse error (e.g. unexpected option after `review`) |

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

The wrapper probes `codex exec review --help` and treats any unrecognized shape as `codex_down` (skill class `down`).
