# Claude Code on the web: mirroring this config

Cloud sessions at [claude.ai/code](https://claude.ai/code) run in a fresh VM that
holds only the cloned repository. A developer's `~/.claude` directory stays on
their own machine, so the rules, hooks, skills, agents, and commands that
`claude-dev-env` installs are absent until something re-creates them inside the
VM. This page describes how to mirror the config into web sessions.

## Setup script

An environment **setup script** attaches to a cloud environment rather than a
single repository. It runs once before Claude Code launches, its filesystem
result is cached, and it applies to every repository opened in that environment.
This makes it the place to install `claude-dev-env` for web use.

Paste this into the environment's **Setup script** field (claude.ai/code →
environment settings):

```bash
#!/bin/bash
set -euo pipefail
npx -y claude-dev-env@latest
```

The command writes the full `~/.claude` tree — content directories, hooks, and a
merged `settings.json` — exactly as a local `npx claude-dev-env` does. Default
**Trusted** network access already reaches `registry.npmjs.org`, so no allowlist
change is needed.

## Personal umbrella package

To install the shared config alongside personal overrides in one command, wrap
both in a small npx-runnable package whose installer runs
`npx -y claude-dev-env@latest` first and then copies personal files over the top.
Point the setup script at that package with its `git+https://` URL so a private
repository authenticates through the cloud GitHub proxy:

```bash
#!/bin/bash
set -euo pipefail
npx -y "git+https://github.com/<owner>/<umbrella-repo>.git"
```

The `git+https://` form matters: the `github:<owner>/<repo>` shorthand resolves to
SSH, which the sandbox lacks, while `git+https` runs through the proxy that grants
GitHub access for any repository the connected account can reach.

## What loads, and the hooks check

Skills, agents, commands, rules, and `CLAUDE.md` load from the `~/.claude` that
the setup script writes. Hooks carry one caveat: Claude Code on the web guarantees
hooks committed to a repository's `.claude/settings.json`, and treats
`~/.claude/settings.json` as user-level config. A `~/.claude/settings.json` written
inside the VM by the setup script is read by the same binary, so hooks generally
run, but the behavior is worth confirming for each environment.

To confirm: open a web session, run `/context` to check the config loaded, then
make an edit that a blocking hook such as `code_rules_enforcer` catches. If the
hook fires, the mirror is complete. If it does not, commit the hook entries into
the target repository's `.claude/settings.json`, the surface cloud sessions
guarantee for hooks.

## Reference

The full mechanics of cloud environments, setup scripts, caching, and network
access live in the
[Claude Code on the web docs](https://code.claude.com/docs/en/claude-code-on-the-web).
