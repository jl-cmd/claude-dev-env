# Changelog

## Unreleased

### Documentation

* migrate `prompt-generator` and `agent-prompt` pipeline refinements from local `~/.claude/skills` into `packages/claude-dev-env/skills` so changes remain durable and release-managed in the canonical repository

## [1.8.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.8.1...claude-dev-env-v1.8.2) (2026-04-07)


### Bug Fixes

* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([318e94a](https://github.com/jl-cmd/claude-code-config/commit/318e94a8eef158a563324212c134dd9ec41db69e))

## [1.8.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.8.0...claude-dev-env-v1.8.1) (2026-04-06)


### Bug Fixes

* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([0d704b6](https://github.com/jl-cmd/claude-code-config/commit/0d704b6e1678cfc831022ff64c8ab800143dc718))

## [1.8.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.7.0...claude-dev-env-v1.8.0) (2026-04-06)


### Features

* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([d25a598](https://github.com/jl-cmd/claude-code-config/commit/d25a5989331115a75a11fd10fb54d7ff7fc59f59))

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
