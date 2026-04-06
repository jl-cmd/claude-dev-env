# Changelog

## Unreleased

### Documentation

* migrate `prompt-generator` and `agent-prompt` pipeline refinements from local `~/.claude/skills` into `packages/claude-dev-env/skills` so changes remain durable and release-managed in the canonical repository

## [1.7.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.6.0...claude-dev-env-v1.7.0) (2026-04-06)


### Features

* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([7f3137f](https://github.com/jl-cmd/claude-code-config/commit/7f3137fa0818aaa175fbfb49096b00082944e7ed))

## [1.6.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.5.0...claude-dev-env-v1.6.0) (2026-04-06)


### Features

* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([f28b114](https://github.com/jl-cmd/claude-code-config/commit/f28b11432a1904820287536fd9571517134afabb))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([f4f2ede](https://github.com/jl-cmd/claude-code-config/commit/f4f2ede2a288e7745d6a05189bfb28d893e565a3))


### Bug Fixes

* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([6563449](https://github.com/jl-cmd/claude-code-config/commit/65634497661e85f048423049e0e8d4aebde1a85b))

## [1.5.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.4.1...claude-dev-env-v1.5.0) (2026-04-05)


### Features

* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([276de6e](https://github.com/jl-cmd/claude-code-config/commit/276de6e58c5ea4e3d2216784cfc7e61fd245ea06))
