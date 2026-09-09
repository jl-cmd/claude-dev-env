# Install pstack across hosts

The full claude-dev-env package command also runs the shared pstack installer. It fetches the pinned cursor/plugins commit and keeps complete pstack and cursor-team-kit trees, including scripts, playbooks, references, agents, licenses, and images. Generated entry points load the compatibility instructions before the upstream workflow. The original upstream files remain under upstream/ in each release.

## Commands

From this repository checkout:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --refresh --strict
node packages/claude-dev-env/bin/pstack.mjs verify --project "$PWD"
```

After a package containing this change is published, the installed commands are:

```bash
claude-dev-env
cde-pstack launch --host claude --
cde-pstack launch --host codex --
cde-pstack launch --host cursor -- --wait .
```

Use these launch commands on local machines and on servers where you launch the CLI yourself. They check the verified channel at a one-hour interval before starting the host. Use --interval-ms to change the interval, --force to refresh immediately, and --offline to use an existing installation. Keep Cursor's --wait flag so the launcher remains alive with the editor task.

A launcher records its process as an active session. Other launcher sessions reuse that release until the active processes end. Each generated skill also records immutable absolute paths to its own supporting files. Direct launches outside this wrapper do not register a session lease. Restart those sessions before adopting a new pin.

Use --root to select a Claude config root or --project to install into a repository. The full package wrapper respects the existing target and profile selection. Commands that select a partial CDE install or perform management actions leave pstack alone. Run cde-pstack explicitly for those installations.

## Discovery and names

Project entries live in .claude/skills with matching .agents/skills links. User entries live in the selected Claude config root and its existing sibling agents home. Existing shared directory pointers stay intact. The installer creates no .cursor/skills directory.

The generated names are pstack-poteto-mode, pstack-how, and other pstack-prefixed names. Dependency names include cursor-team-kit-deslop, cursor-team-kit-control-cli, and cursor-team-kit-control-ui. Invoke /pstack-poteto-mode in Claude or Cursor, or $pstack-poteto-mode in Codex. These are direct skills. Cursor plugin registration metadata remains in the untouched upstream copy, so native loaders keep the component-prefixed names. The mapping resolves upstream short names through release.json.

Each skill entry loads the common mapping and one of host-claude.md, host-codex.md, or host-cursor.md. Delegation prompts carry those paths and the upstream agent definition to the child. Required independent or cross-model work reports a missing host capability rather than substituting a weaker review. The copied model selector receives an explicit preferencesDirectory outside the release, preserving host settings through updates. cde-create-skill provides the portable authoring workflow when the native creator is absent.

The separate session-continuity companion recognizes the generated pstack-poteto-mode name and resolves its immutable release path. Reinvocation, compaction, and resume keep the recorded release. A new session adopts the newly installed revision. Legacy invocations and explicit source overrides remain supported.

## Cloud setup and maintenance

For Codex cloud using this repository, put this command in the environment setup script:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --refresh --strict
```

Put this command in its maintenance script:

```bash
node packages/claude-dev-env/bin/pstack.mjs install --project "$PWD" --refresh
```

For Claude cloud, run the setup command in its environment setup script. The repository's .claude/settings.json also invokes the pstack SessionStart hook. Each startup checks the verified channel at the configured interval. A fresh installation uses the bundled pin with a warning when the channel is unavailable. Resume, clear, and compaction events verify and retain the installed release. The companion restores the immutable skill source recorded for that session. The hook emits native SessionStart JSON with the installed revision and compatibility paths.

For other repositories, install the published package's cde-pstack command in the environment and use cde-pstack install --project "$PWD" --refresh in setup and maintenance. Add the same repository SessionStart registration for Claude, pointing at the installed command with hook. A setup script in this repository does not change settings in an existing remote environment. Configure each environment's script fields separately.

Git and Node 22 or later are installer prerequisites. Runtime workflows still need the CLIs, browser access, credentials, and permissions their steps use. The adapters require checking those capabilities before work. No installer can supply an absent native subagent or browser tool by copying files.

## Shared pin and rollback

The shared record is pstack.lock.json on the pstack-verified branch. It names one upstream commit and the exact adapter digest used for its checks. The bundled scripts/pstack.lock.json supplies the initial revision when the channel is unavailable.

The nightly Pstack installation workflow selects upstream HEAD once. Linux and Windows test the same candidate, install the bundled pin, update to the candidate, verify integrity, and reuse the installation offline. Linux also checks every installed skill through the native Codex loader. Both jobs must pass before publication.

After live-cloud acceptance, set the repository variable PSTACK_ENABLE_PROMOTION=true. Successful scheduled or manual runs on main then advance the channel with a fast-forward push. An unchanged record leaves the branch unchanged. Pull request runs exercise the checks with read-only repository access. The publication job alone receives contents write access.

Local launches and full package installs check the channel, as do cloud setup, maintenance, and new Claude sessions. Each environment adopts a matching record at its next eligible check. The installer rejects missing verification metadata and mismatched adapter digests. Existing installations retain their checked release and report the failure. Fresh installs use the bundled pin with a warning. Active launcher leases and the existing continuity record preserve running sessions.

The published verification level is install-contract. It records installation checks, while authenticated Claude/Codex cloud tasks and actual local host behavior require the acceptance below. Promotion remains gated until those checks pass.

The adapter digest covers the installer code and compatibility files with consistent line endings on Linux and Windows. A release records its upstream commit, adapter digest and version, installed skills and agents, and file hashes. Installation stages a release before publishing pointers, checks unmanaged path collisions, and restores prior pointers if publication fails. Old releases remain on disk. An update error reports the retained revision; a first-install failure returns a failure status. verify checks installed files and pointers and labels the result filesystem-only.

## Acceptance before enabling the default

Run a fresh Claude cloud session and a fresh Codex cloud session against this branch. In each, invoke pstack-poteto-mode, load its Feature playbook, dispatch one supported native subagent with the adapter and upstream agent-definition paths, and complete a small repository task. Save the host version, selected models, exact skill and playbook paths, child final response, changed artifact, and observed verification result.

Repeat on the actual local Claude, Codex, and Cursor profiles. Confirm the separate session-continuity companion loads the generated entry and restores the same immutable release after compaction. Test a real changed, added, and removed upstream skill across the environments, then an unreachable upstream and an incompatible dependency.

The automated tests cover filesystem discovery locations, metadata, resources, dependencies, update reconciliation, collision handling, rollback, offline reuse, launch leases, and hook JSON. The real-upstream CI job checks both the bundled pin and the channel candidate on Linux and Windows. Publisher tests create and fast-forward a local Git channel and read it through the installer. The Linux job also asks Codex 0.153.4 to list the installed skills through its native app server and checks each name and entry path. This read-only discovery test sends no agent task. Cloud task execution, delegation, Claude and Cursor menus, and actual profile launch integration remain separate acceptance evidence.

## Sources

[Claude skills](https://code.claude.com/docs/en/skills), [Claude cloud environments](https://code.claude.com/docs/en/cloud-environments), [Codex skills](https://developers.openai.com/codex/skills/), [Codex cloud environments](https://developers.openai.com/codex/cloud/environments/), and [Cursor skills](https://cursor.com/docs/skills) define host discovery and startup behavior. The [pstack-claude port](https://github.com/michael-denyer/pstack-claude) informed the entry-point mapping approach. This implementation fetches cursor/plugins directly and imports no code from that port.
