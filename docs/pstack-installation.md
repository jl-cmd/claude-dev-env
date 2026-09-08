# Install pstack for Claude Code, Codex and Cursor

`cde-pstack` installs a pinned pstack revision and its cursor-team-kit dependencies
into a workspace. One installation serves all three hosts. Upstream files remain
complete and unchanged. Generated skill entry points load the compatibility rules
before reading an immutable upstream workflow.

The package adds a separate executable. The existing `claude-dev-env` command keeps
its current installation and uninstall behavior. Run the pstack command from the
launch process or cloud scripts described below.

## Local launch

From this repository checkout, run one of these commands. Set `--root` to the
workspace where the agent will work. These commands also work on remote CLI servers.

```sh
node packages/claude-dev-env/bin/pstack.mjs launch --host claude --root /path/to/project -- claude
node packages/claude-dev-env/bin/pstack.mjs launch --host codex --root /path/to/project -- codex
node packages/claude-dev-env/bin/pstack.mjs launch --host cursor --root /path/to/project -- cursor --wait .
```

After the package containing this change is published, `cde-pstack` is available
alongside `claude-dev-env`. Existing external launchers need to call it. This change
leaves launchers owned by other repositories in place.

The launcher passes arguments without a shell, forwards signals and returns the
agent's exit code. On Windows, use the agent's executable. For a shell-only `.cmd`
launcher, explicitly launch `cmd.exe` or PowerShell with that command. Cursor's
`--wait` keeps the launcher alive while the window is in use. Closing the wrapper
while its agent continues removes its protection against concurrent updates.

For installation without launching an agent:

```sh
node packages/claude-dev-env/bin/pstack.mjs install --host codex --root /path/to/project
node packages/claude-dev-env/bin/pstack.mjs verify --root /path/to/project
```

Node 22 and Git are required for installation. Workflows may need additional runtime
tools such as Bun, a PTY, a browser, GitHub authentication or an application under
test. The compatibility rules require the agent to check these before the relevant
step and report a missing capability. Installing a skill does not create these tools.

## Cloud setup and maintenance

For a cloud environment working on this repository, set the setup field to:

```sh
bash scripts/pstack-cloud-setup.sh codex
```

Set the Codex maintenance field to:

```sh
bash scripts/pstack-cloud-maintenance.sh codex
```

Use `claude` instead of `codex` for the Claude environment setup field. The committed
`.claude/settings.json` SessionStart hook refreshes pstack for a new session and
returns the release path as agent context. A resumed or compacted session keeps its
recorded release. Its next new session checks for an update.

For a different repository, install the package in the environment setup step and
call the same executable with that repository as `--root`. Commit a corresponding
Claude SessionStart hook in that repository. Repository-local hooks are the reliable
cloud entry point; a hook in a local user's home directory does not transfer to cloud.

Committing these scripts does not change hosted environment settings. Select them
in each environment before relying on automatic setup or maintenance. Setup needs
network access to GitHub. Cached installations can be checked with `--offline`.

## Installation layout and compatibility

`.claude/pstack/releases/<commit>-<adapter-digest>` holds each complete upstream
checkout, the generated wrappers, the existing host and model policies, the model
selector and a hash inventory. `.claude/pstack/current` selects the installed release.
The installer retains previous releases for sessions and recovery.

`.claude/skills/pstack` and `.claude/skills/cursor-team-kit` are the canonical skill
entry points. `.agents/skills/<skill>` links expose them to Codex. Cursor reads the
Claude-compatible directories. The installer writes no `.cursor/skills` directory.
Native poteto-agent and comment-sicko definitions are installed for each host.
Every child receives the release path and reads the same compatibility policy.

The adapter maps Cursor's Task, question, terminal and browser requests through the
active host's tool definitions. It uses the existing model selector rather than
hardcoded Cursor model IDs. A required independent or distinct-model review remains
a requirement. Missing capabilities are reported rather than silently simulated.

The complete cursor-team-kit is installed, including deslop, control-cli and
control-ui. The generated create-skill workflow provides the missing builtin's
portable authoring steps. Model setup writes only
`.claude/pstack/preferences/pstack-model-preferences.<host>.json`. Updates preserve
these files. The installer refuses to overwrite existing user-owned discovery paths
or agent registrations.

Add generated installation paths to the target repository's local Git excludes.
This repository ignores generated pstack state, discovery links
and native agent files. Source code, adapters and the bundled pin remain tracked.

## Shared update channel

The bundled pin bootstraps a fresh environment. Subsequent checks read
`pstack.lock.json` from this repository's `pstack-verified` branch. The record names
one upstream commit, an adapter version and the digest of the adapter that passed.
An environment with a different adapter keeps its working release and asks for a
package update. Local launches check at most once every
six hours; `--force-check` checks now. A new Claude cloud session checks immediately.
Every environment converges on the same approved commit at its next check.

The Pstack installation workflow tests behavior on Linux and Windows, then installs
the current upstream candidate into three clean directories and checks its files,
required dependencies and host registrations. It retains evidence as a workflow
artifact. On scheduled or manual runs, promotion publishes only the checked lock
record to the channel branch with a normal fast-forward push.

Promotion is gated by the repository variable `PSTACK_ENABLE_PROMOTION=true`. Enable
it after the live-host acceptance below has passed. Until then, installations use
the bundled pin or the last published channel record. The channel describes
`install-contract` verification, not a claim that all workflows ran in cloud.

Updates are prepared and checked before publication. A fetch, dependency or adapter
failure keeps the checked previous installation and emits a warning. A corrupt
installed release fails verification instead of being described as working. Active
launcher processes defer publication. Agent instructions use immutable release paths.

## Verification and acceptance

Run the behavioral suite:

```sh
node --test packages/claude-dev-env/bin/pstack.test.mjs packages/claude-dev-env/bin/pstack-pin.test.mjs
```

The suite uses explicitly synthetic Git fixtures. It checks clean installation for
each host, full file retention, child bindings, changed/added/removed skills,
idempotency, preference preservation, network failure, missing dependencies,
user-file collisions, dirty source rejection, integrity failures, active-session
protection, resumed-session pinning and CLI arguments and exit codes.

Live acceptance remains a separate check. In a clean Claude cloud environment and
a clean Codex cloud environment, run their setup scripts. Start the host and invoke
Poteto Mode by its discovered name. Ask it to read the Feature playbook, dispatch a
supported native subagent to make a small fixture change, and run the fixture's test.
Record the installed commit, host version, loaded skill path, child tool call,
model-selection result, test output and final child report. Repeat after a cached
environment resumes. Inspect the host's actual skill menu and tools, not just files.

Then check a changed, added and removed skill through the host after an update.
Keep actual runtime failures distinct from installation failures. Enable channel
promotion only after this acceptance passes and the evidence has been reviewed.

## Sources and prior art

The adapter builds on this repository's pstack-host-mapping.md, pstack-models.md and
select_pstack_models.mjs. The michael-denyer/pstack-claude port informed the choice to
provide a mapping at every skill entry point and propagate agent instructions. Its
edited workflow bodies are not used as the update source.

- Claude skills: https://code.claude.com/docs/en/skills
- Claude subagents: https://code.claude.com/docs/en/sub-agents
- Claude cloud setup and hooks: https://code.claude.com/docs/en/cloud-environments
- Codex skills: https://developers.openai.com/codex/skills/
- Codex subagents: https://developers.openai.com/codex/subagents/
- Codex setup and maintenance: https://developers.openai.com/codex/cloud/environments/
- Cursor skills: https://cursor.com/docs/skills
- Port reviewed: https://github.com/michael-denyer/pstack-claude
