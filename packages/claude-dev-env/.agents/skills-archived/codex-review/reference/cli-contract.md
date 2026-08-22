# CLI contract

Observed shape of the Codex CLI review surface the skill classifies from. Fixture capture baseline: `codex` 0.144.3. Scripts under `../scripts/` implement this contract.

## Wrapper entrypoint

```text
run_codex_review(
    repository_directory=<repo root Path>,
    run_state_directory=<run-state Path>,
    base_branch=<branch> | is_uncommitted=True | commit_sha=<sha> | is_prompt_target=True,
)
```

Exactly one target among `base_branch`, `is_uncommitted`, `commit_sha`, and `is_prompt_target`. Zero or more than one raises `ValueError`.

### Return shape (`CodexReviewOutcome`)

Capture only — skill-level classes `down` / `clean` / `findings` are **not** produced here.

| Field | Meaning |
|---|---|
| `outcome_class` | `completed` or `codex_down` |
| `exit_code` | Last process exit code, or a sentinel when none ran (`127` missing binary, `124` timeout, `70` decode error) |
| `binary_version` | Parsed `codex --version` string, or empty |
| `jsonl_path` | Path to captured JSONL (`codex-review.jsonl` under the run-state directory), or `None` when review did not run |
| `agent_message` | Last `agent_message` text from the JSONL stream (stderr text when the run fails with empty agent text) |

Detail classes from `classify_codex_run` are a separate step (see Failure classes). They are not fields on `CodexReviewOutcome`.

## Command shape

### Classifying path: `codex exec … review --json`

Skill classification (Step 4) reads only the JSONL stream from the classifying path. The wrapper builds:

```text
codex exec [exec-options] review --json <one-target>
```

| Target | Flag / payload |
|---|---|
| Uncommitted | `--uncommitted` |
| Base branch | `--base <BRANCH>` |
| Commit | `--commit <SHA>` |
| Custom instructions | positional PROMPT (`CUSTOM_INSTRUCTIONS_PROMPT`: freeform one-line summary, `Review comment:` heading, then `- [P#]` bullets — not fenced JSON) |

`CODEX_MODEL_PIN` is empty in the shipped constants, so `-m` is omitted unless a pin is set.

`--json` is required for a classifiable success stream. Without `--json`, stdout is not a Step 4 input.

### Ordering rule

`codex exec` options belong **before** the `review` subcommand. Review options such as `--json` and `--uncommitted` follow `review`.

- Parses: `codex exec review --json --uncommitted`
- Fails (exit 2, usage on stderr): trailing `-C <DIR>` after `review` (`unexpected argument '-C' found`)

Run from the target repo directory (the wrapper sets `cwd` to `repository_directory`), or place `-C <DIR>` before `review`.

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

Observed rejection when a flag target is combined with `[PROMPT]` (fixture capture: `codex` 0.144.3):

```text
error: the argument '--uncommitted' cannot be used with '[PROMPT]'
Usage: codex exec review --json --uncommitted [PROMPT]
```

Exit code 2.

### `codex exec` options (before `review`)

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

## Probe

The wrapper probes before every review. Any failure returns `outcome_class=codex_down` and does not run the review.

| Step | Command | Pass rule |
|---|---|---|
| Version | `codex --version` | Exit 0; version string parsed from stdout |
| Shape | `codex exec review --help` | Exit 0; help text contains each required flag as a **whole token** |

### Minimum shape signals

The `review` subcommand is proven by the probe itself: a CLI without it exits non-zero on `codex exec review --help`, which is already a `codex_down` signal.

Required whole-token flags:

| Signal | Role |
|---|---|
| `--uncommitted` | Staged + unstaged + untracked target |
| `--base` | Base-branch target |
| `--commit` | Commit-SHA target |
| `--json` | JSONL event stream on stdout |

Longer lookalikes (`--baseline`, `--uncommitted-only`, `--commit-message`) do not satisfy the required target flags.

### Fail-closed rule

Any missing signal, non-zero probe exit, missing binary, timeout, or decode failure is `codex_down` (skill class `down`). Do not continue to a review invoke when the probe fails.

## Success stream

With `--json`, a successful run writes JSONL on stdout and exits 0. The wrapper writes stdout to `run_state_directory/codex-review.jsonl`.

Fixture: `../scripts/fixtures/success_stream_v0.144.3.jsonl`.

Typical event order:

1. `thread.started` — includes `thread_id`
2. `turn.started`
3. `item.started` / `item.completed` pairs for `command_execution` items
4. `item.completed` with `"type":"agent_message"` — review text body
5. `turn.completed` — `usage` object (`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`)

The wrapper extracts the last `item.completed` / `agent_message` / `text` as `agent_message`.

### Finding text shapes

`parse_codex_findings` reads `agent_message` and never drops non-empty text.

| Priority | Shape | Fixture |
|---|---|---|
| 1 | Fenced JSON array of objects with keys `title`, `priority`, `file`, `line_range`, `body` | `../scripts/fixtures/structured_findings.txt` |
| 2 | Freeform bullets `- [P1] <title> — <path>:<start>-<end>` plus body paragraphs | `../scripts/fixtures/freeform_findings_v0.144.3.txt` |
| 3 | Floor: one unstructured finding whose `body` is the raw text | any non-empty unmatched text |

Empty agent text or a structured empty array (`[]`) yields zero findings (`clean` for gate callers).

## Failure classes

All observed CLI failures map to wrapper `outcome_class=codex_down`. Every nonzero review exit maps to `codex_down`. Wrapper `outcome_class` is the capture success signal: a shape-probe miss can still return `codex_down` when the help process exits 0 but required flags are missing. Callers that need a detail class run `classify_codex_run(exit_code=..., stream_text=...)` separately — that helper treats exit 0 as `completed` and every nonzero exit as `codex_down` plus a detail class. Fixtures under `../scripts/fixtures/` are the source of truth for observed shapes.

| Detail class | Outcome | Fixture | Observed shape |
|---|---|---|---|
| `completed` | `completed` | `success_stream_v0.144.3.jsonl` | Exit 0; JSONL success stream |
| `config_error` | `codex_down` | `config_load_failure_v0.125.0.txt` | Exit 1; plain stderr, e.g. `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in 'service_tier'` |
| `model_error` | `codex_down` | `model_rejection_v0.125.0.jsonl` | Exit 1; JSONL `error` with embedded 400 `invalid_request_error` (`model is not supported` / `requires a newer version of Codex`), then interrupted agent message, then `turn.failed` |
| `usage_limit` | `codex_down` | `usage_limit_synthetic.txt` | Exit 1; phrase markers such as rate limit, too many requests, `http 429`, ` (429)`, credits exhausted, out of credits, api quota, usage quota (bare status numbers alone are not markers) |
| `auth_failure` | `codex_down` | `auth_failure_synthetic.txt` | Exit 1; phrase markers such as unauthorized, authentication failed, login required, not authenticated (bare status numbers alone are not markers) |
| `unknown` | `codex_down` | `unknown_failure_synthetic.txt` | Exit nonzero with no known marker (also empty stream on nonzero exit) |

Probe and process failures (missing binary exit `127`, timeout exit `124`, decode error exit `70`, shape probe miss) also return `outcome_class=codex_down` from the wrapper. Skill step 4 maps these to skill class `down`. Detail classification is optional for those paths.

CLI parse errors (exit 2, usage on stderr, no JSONL) are `codex_down` with detail `unknown` unless a marker matches.

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
| `clean` | Wrapper `completed` and `parse_codex_findings(agent_message)` empty (blank text or structured `[]`) | Usable review, zero addressable findings |
| `findings` | Wrapper `completed` and `parse_codex_findings(agent_message)` non-empty (fenced JSON objects, freeform `- [P#]` bullets, or floor text) | Usable review with addressable findings |

## Auth surface

Placeholders only — never commit real tokens, hosts, or account ids.

| Mode | How |
|---|---|
| ChatGPT / file store | Credentials under the Codex home directory as `auth.json`. `CODEX_HOME` relocates that directory. `cli_auth_credentials_store = "file"` in `config.toml` pins the file store. |
| API key (exec only) | `CODEX_API_KEY=<YOUR_API_KEY>` authenticates a single `codex exec` invocation. |
| Access-token login | Pipe an enterprise access token into `codex login --with-access-token` (token from a secret store; never inline). |

The same `config.toml` serves the desktop app and the CLI. A value one accepts can fail the other's parser; that path surfaces as the `config_error` row above.

The wrapper inherits the process environment, so `CODEX_HOME` and `CODEX_API_KEY` pass through when set.

## Cloud runbook

End-to-end path for a headless host (CI runner, remote agent, or cloud VM). Every account-specific value is a placeholder.

1. **Install the CLI.** `npm install -g @openai/codex` (or pin a version that still exposes `codex exec review --json` with `--base` / `--uncommitted` / `--commit`).
2. **Supply one auth mode from a secret store.**
   - File store: write `auth.json` under `CODEX_HOME=<CODEX_HOME_DIR>` with credentials from the secret store, and set `cli_auth_credentials_store = "file"`.
   - API key: export `CODEX_API_KEY` from the secret store for the process that runs the wrapper.
   - Access token: `printf '%s' "$CODEX_ACCESS_TOKEN" | codex login --with-access-token`.
3. **Fetch a resolvable base ref** when the target is a PR base branch. A bare `git fetch origin <BASE_BRANCH>` only updates `FETCH_HEAD` on a shallow or unconfigured remote and does **not** create `refs/heads/<BASE_BRANCH>`. Create or update a named ref the wrapper can pass to `--base`:

   ```text
   git fetch origin <BASE_BRANCH>:refs/remotes/origin/<BASE_BRANCH>
   ```

   Then pass that remote-tracking name as `base_branch` (for example `origin/<BASE_BRANCH>`), or create a local branch that points at the same commit (`git branch -f <BASE_BRANCH> origin/<BASE_BRANCH>`) and pass the local name.
4. **Run the wrapper** from the repo root with a writable run-state directory:

   ```text
   run_codex_review(
       repository_directory=<REPO_ROOT>,
       run_state_directory=<RUN_STATE_DIR>,
       base_branch=origin/<BASE_BRANCH>,   # PR loops — same ref the fetch step created
       # or is_uncommitted=True            # standalone
   )
   ```

5. **Parse JSONL / agent text.** On `outcome_class=completed`, call `parse_codex_findings(agent_message)`.
6. **Classify failures.** On nonzero exit or `outcome_class=codex_down`, call `classify_codex_run(exit_code=..., stream_text=<stdout+stderr>)` when a detail class is needed. Every non-completed detail class is gate-level `codex_down` (fail closed; orchestrators bypass the clean-SHA requirement rather than block forever — see [loop-integration.md](loop-integration.md)).
