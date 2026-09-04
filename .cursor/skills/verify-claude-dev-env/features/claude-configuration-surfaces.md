# Claude configuration surfaces

The installer installs rules, skills, agents, commands, and the `CLAUDE.md` hub.

## Sub-features

- Global and path-scoped rules.
- Skill and agent discovery.
- The `CLAUDE.md` instruction hub.

## How to get to it (user POV)

Start a fresh Claude session after installation. The session loads the installed configuration for the current path.

## Driving it with Node.js

Run `npm test` from `packages/claude-dev-env`. Use the tests under `tests/fresh-session/` for the changed configuration.

## Gotchas

Fresh-session tests use disposable profiles. The command-line interface path is opt-in and needs explicit binary mappings.
