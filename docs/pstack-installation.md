# Install pstack across hosts

A full `claude-dev-env` install also installs [pstack](https://github.com/michael-denyer/pstack-claude) as a plugin from its own marketplace, so `npx -y claude-dev-env@latest` needs no second command. The plugin ships its own skills, agents, model defaults, and SessionStart hook. Upstream owns every one of those, so this repository holds no pstack tree, no pinned commit, and no adapter files.

## What the install step runs

For Claude Code, with `CLAUDE_CONFIG_DIR` set to the managed root this run writes to:

```bash
claude plugin marketplace add michael-denyer/pstack-claude
claude plugin install pstack@pstack-claude
```

For Codex, with `CODEX_HOME` set to the resolved Codex home:

```bash
codex plugin marketplace add michael-denyer/pstack-claude
codex plugin add pstack@pstack-claude
```

Both commands run without a prompt and report their outcome on stdout. Claude Code records the marketplace under `extraKnownMarketplaces` and the plugin under `enabledPlugins` in that root's `settings.json`, then unpacks the plugin under `plugins/cache/pstack-claude/pstack/<version>`.

## When a host is absent

Each host is one member of the batch. A host whose command-line tool is not on `PATH` is skipped, and a host whose command fails is reported. Either outcome leaves the other host installed and never stops the rules, hooks, and skills this run already wrote.

Set `CDE_CLAUDE_EXECUTABLE` or `CDE_CODEX_EXECUTABLE` to name an interpreter outside `PATH`.

## Turning the step off

The step runs on a full install only. A `--only <group>` run installs the named groups and skips it. Two controls turn it off:

- `npx -y claude-dev-env@latest --no-pstack`
- `CDE_INSTALL_PSTACK=0` in the environment

The plugin keeps its own state under each host's plugin store. The install manifest does not record those paths, so the stale-file prune and `--uninstall` leave the plugin in place. Remove it with `claude plugin uninstall pstack@pstack-claude` or `codex plugin remove pstack@pstack-claude`.

## Updating and configuring

`claude plugin marketplace update pstack-claude` refreshes the catalog and `claude plugin install pstack@pstack-claude` adopts the new version. A later `claude-dev-env` install runs the same two commands, so an install adopts whatever the marketplace publishes.

Run `/pstack:setup-pstack` in Claude Code, or `setup-pstack` in Codex, to change the plugin's model defaults or turn its automatic routing off. This repository's own `subagent-model-policy.json` and its `subagent_model_routing` hook stay in place and are unrelated to the plugin's routing.

## Retired integration points

An earlier `claude-dev-env` installed pstack itself: a pinned upstream commit, a release store under the managed root, generated host adapters, a `cde-pstack` command, a copied model selector, seeded model preference files, and a `session-continuity` companion registered as a hook in Claude, Codex, and Cursor. The plugin covers each of those, including the SessionStart context the companion supplied.

Every full install now clears the companion's hook registrations from all three host configuration files, because a registration left behind points every session at a deleted script.

## Cloud setup

For Claude cloud, `npx -y claude-dev-env@latest` in the environment setup script installs the plugin with everything else. For Codex cloud, put the two `codex plugin` commands above in the environment setup script.

Git and Node 22 or later are installer prerequisites. The plugin's own workflows still need the CLIs, browser access, credentials, and permissions their steps use.

## Sources

[Claude Code plugins](https://code.claude.com/docs/en/plugins), [Claude Code plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), and the [pstack-claude README](https://github.com/michael-denyer/pstack-claude#install) define the marketplace and plugin commands each host accepts.
