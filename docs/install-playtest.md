# Install playtest

A check suite grades the source tree. This gate grades the shipped product: it
installs the package into a scratch home the way a person installs it, then
starts hooks out of that installed tree and reads the envelope each one returns.

## What the gate runs

`packages/claude-dev-env/scripts/ci/install-playtest.mjs` drives three stages,
in order.

| Stage | What runs | What it reads back |
|---|---|---|
| `install` | `bin/install.mjs` against a scratch `HOME` | `~/.claude/settings.json` exists and carries a hook roster |
| `session_start_hook` | the `SessionStart` hook the installed roster names for `working_style_prompt.py` | a `SessionStart` envelope carrying a non-empty `additionalContext` |
| `blocking_hook` | the `PreToolUse` hook the installed roster names for `bash_pre_tool_use_dispatcher.py`, against a `git show <rev>:<path>` payload | a `PreToolUse` envelope deciding `allow` with the argument-conversion rewrite in `updatedInput.command` |

Each stage writes the envelope it read to the evidence directory and prints one
line naming the stage, the artifact path and the artifact's SHA-256 digest. The
CI job uploads the evidence directory, so a failed run carries the envelope that
failed it.

The hook commands come from the installed `settings.json`, so a hook the
installer leaves out of the roster fails the stage that names it.

## Exit codes

```
every stage read the envelope it expected -> exit 0
one stage read something else             -> exit 1
```

## Running it

```
cd packages/claude-dev-env
node scripts/ci/install-playtest.mjs
```

The run installs into a fresh scratch home and removes it at the end. Two flags
change that:

- `--home <dir>` installs into a named directory and keeps it after the run.
- `--skip-install` grades the tree already in that directory, which is how a
  broken install is read back.
- `--evidence <dir>` names where the envelopes are written.

## Proving it goes red

`scripts/ci/install-playtest.test.mjs` runs the driver green against a fresh
install. It then writes a script that prints an empty line over the installed
`working_style_prompt.py`, runs the driver again with `--skip-install`, and
asserts exit code 1 and the line

```
[FAIL] playtest session_start_hook The hook wrote no SessionStart envelope
```

The break lands on the installed artifact. The driver carries no switch that
forces a stage to fail.

## Where it runs in CI

The `install-playtest` job in `.github/workflows/ci-tests.yml` runs the driver on
Ubuntu and uploads the evidence. The `javascript` job runs the paired test
through `npm test`, which covers the red direction.
