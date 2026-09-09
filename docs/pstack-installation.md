# Install pstack across hosts

A full `claude-dev-env` install also installs the pinned pstack release, so `npx -y claude-dev-env@latest` needs no second command. Run `cde-pstack` to manage that release on its own: verify it, refresh its pin, or launch a host with it. The pstack installer keeps complete pstack and cursor-team-kit trees, including scripts, playbooks, references, agents, licenses, and images. Generated entry points load the compatibility instructions before the upstream workflow. The original upstream files remain under `upstream/` in each release.

## Commands

From this repository checkout:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --strict
node packages/claude-dev-env/bin/pstack.mjs verify --project "$PWD"
```

After a package containing this change is published, the installed commands are:

```bash
cde-pstack launch --host claude --
cde-pstack launch --host codex --
cde-pstack launch --host cursor -- --wait .
```

Use `cde-pstack install` before these launch commands. The launcher checks the shared pin at a one-hour interval before starting the host. Use `--interval-ms` to change the interval, `--force` to refresh immediately, and `--offline` to use an existing installation. Keep Cursor's `--wait` flag so the launcher remains alive with the editor task.

A launcher records its process as an active session. Other launcher sessions reuse that release until the active processes end. Each generated skill also records immutable absolute paths to its own supporting files. Direct launches outside this wrapper do not register a session lease. Restart those sessions before adopting a new pin.

Use `--root` to select a Claude config root or `--project` to install into a repository.

## The pstack step inside a full install

A full install installs the pstack release into the managed Claude root it already writes to. The step reaches the network for the pinned upstream commit. A failure prints a warning and the install continues, so a network problem never stops the rules, hooks, and skills.

The step runs on a full install only. A `--only <group>` run installs the named groups and skips pstack.

Two controls turn the step off:

- `npx -y claude-dev-env@latest --no-pstack`
- `CDE_INSTALL_PSTACK=0` in the environment

The pstack store keeps its own state and its own entry pointers. The install manifest does not record them, so the stale-file prune and `--uninstall` leave the pstack store in place. Remove it with the store directory under the managed root.

## Discovery and names

Project pstack entries live under `.claude/skills/pstack/<subskill>` with matching `.agents/skills/pstack/<subskill>` paths. User entries use the selected Claude config root and its existing sibling agents home. The installer publishes one managed `pstack` pointer per distinct skills home. The pointed-to tree carries `.claude-plugin/plugin.json` with every pstack subskill path, so the release is self-contained. Existing shared skills-directory pointers stay intact. The installer creates no `.cursor/skills` directory.

The generated pstack skill names remain `pstack-poteto-mode`, `pstack-how`, and other pstack-prefixed names. Dependency names such as `cursor-team-kit-deslop`, `cursor-team-kit-control-cli`, and `cursor-team-kit-control-ui` remain flat entries beside the `pstack` folder. The mapping resolves upstream component and short names through `release.json`.

If an unmanaged `pstack` path already exists in a skills home, the installer leaves it in place and reports the collision instead of replacing it. A managed update swaps the one pstack pointer to the new immutable release, so added and removed subskills converge with the release tree.

Each skill entry loads the common mapping and one of host-claude.md, host-codex.md, or host-cursor.md. Delegation prompts carry those paths and the upstream agent definition to the child. Required independent or cross-model work reports a missing host capability rather than substituting a weaker review. The copied model selector receives an explicit preferencesDirectory outside the release, preserving host settings through updates. cde-create-skill provides the portable authoring workflow when the native creator is absent.

## Cloud setup and maintenance

For Codex cloud using this repository, put this command in the environment setup script:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --strict
```

Put this command in its maintenance script:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --refresh
```

For Claude cloud, `npx -y claude-dev-env@latest` in the environment setup script installs pstack with everything else. Run the command above instead when the environment needs a project-scoped install. This installer does not change the repository's Claude hooks. Install the existing session-continuity companion separately if the environment uses it.

For other repositories, install the published package's cde-pstack command in the environment and use cde-pstack install --project "$PWD" in setup, adding --refresh in maintenance. Add the same repository SessionStart registration for Claude, pointing at the installed command with hook. A setup script in this repository does not change settings in an existing remote environment. Configure each environment's script fields separately.

Git and Node 22 or later are installer prerequisites. Runtime workflows still need the CLIs, browser access, credentials, and permissions their steps use. The adapters require checking those capabilities before work. No installer can supply an absent native subagent or browser tool by copying files.

## Shared pin and rollback

`packages/claude-dev-env/scripts/pstack.lock.json` is the shared record on `main`. Update the commit through a reviewed pull request. Environments adopt the merged record on their next install or refresh.

The adapter digest covers the installer code and compatibility files with consistent line endings on Linux and Windows. A release records its upstream commit, adapter digest and version, installed skills and agents, and file hashes. Installation stages a release before publishing pointers, checks unmanaged path collisions, and restores prior pointers if publication fails. Old releases remain on disk. An update error reports the retained revision; a first-install failure returns a failure status. verify checks installed files and pointers and labels the result filesystem-only.

## Acceptance before enabling the default

Run a fresh Claude cloud session and a fresh Codex cloud session against this branch. In each, invoke pstack-poteto-mode, load its Feature playbook, dispatch one supported native subagent with the adapter and upstream agent-definition paths, and complete a small repository task. Save the host version, selected models, exact skill and playbook paths, child final response, changed artifact, and observed verification result.

Repeat on the actual local Claude, Codex, and Cursor profiles. Confirm the separate session-continuity companion loads the generated entry and restores the same immutable release after compaction. Test a real changed, added, and removed upstream skill across the environments, then an unreachable upstream and an incompatible dependency.

The automated tests cover filesystem discovery locations, metadata, resources, dependencies, update reconciliation, collision handling, rollback, offline reuse, launch leases, and hook JSON. The real-upstream CI job runs on Linux and Windows. The Linux job also asks Codex 0.153.4 to list the installed skills through its native app server and checks each name and entry path. This read-only discovery test sends no agent task. Cloud task execution, delegation, Claude and Cursor menus, and actual profile launch integration remain separate acceptance evidence.

## Sources

[Claude skills](https://code.claude.com/docs/en/skills), [Claude cloud environments](https://code.claude.com/docs/en/cloud-environments), [Codex skills](https://developers.openai.com/codex/skills/), [Codex cloud environments](https://developers.openai.com/codex/cloud/environments/), and [Cursor skills](https://cursor.com/docs/skills) define host discovery and startup behavior. The [pstack-claude port](https://github.com/michael-denyer/pstack-claude) informed the entry-point mapping approach. This implementation fetches cursor/plugins directly and imports no code from that port.
