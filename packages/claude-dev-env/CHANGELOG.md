# Changelog

## Unreleased

## [1.17.4](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.3...claude-dev-env-v1.17.4) (2026-04-12)


### Refactoring

* **zoekt-hook:** phase 2 guidance API on main ([#86](https://github.com/jl-cmd/claude-code-config/issues/86)) ([#90](https://github.com/jl-cmd/claude-code-config/issues/90)) ([e069818](https://github.com/jl-cmd/claude-code-config/commit/e0698188d4646e0069c5900a4bd0e669f5a79d68))

## [1.17.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.2...claude-dev-env-v1.17.3) (2026-04-11)


### Bug Fixes

* **hooks:** prevent duplicate write-visible gh calls under bypassPermissions mode ([#85](https://github.com/jl-cmd/claude-code-config/issues/85)) ([5522ea5](https://github.com/jl-cmd/claude-code-config/commit/5522ea555f6ce5ba7e6e7a1d1f6d8692602012a7))

## [1.17.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.1...claude-dev-env-v1.17.2) (2026-04-10)


### Refactoring

* **prompt-workflow:** replace Stop hook with file-based validation loop ([#75](https://github.com/jl-cmd/claude-code-config/issues/75)) ([43758b1](https://github.com/jl-cmd/claude-code-config/commit/43758b16d4bd46df3e368c76be119f3ba2201458))

## [1.17.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.0...claude-dev-env-v1.17.1) (2026-04-10)


### Documentation

* **prompt-generator:** replace jargon with plain language ([#73](https://github.com/jl-cmd/claude-code-config/issues/73)) ([0c66d92](https://github.com/jl-cmd/claude-code-config/commit/0c66d926f09f2db779a64784efa5a38797b264c2))

## [1.17.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.16.1...claude-dev-env-v1.17.0) (2026-04-10)


### Features

* **claude-dev-env:** add skill package prompt templates and workflow wiring ([#66](https://github.com/jl-cmd/claude-code-config/issues/66)) ([387e418](https://github.com/jl-cmd/claude-code-config/commit/387e418dce69a337ef288171ba4f120818dc527a))

## [1.16.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.16.0...claude-dev-env-v1.16.1) (2026-04-10)


### Bug Fixes

* **ci:** sync claude-dev-env version with manifest and pin release PR title ([69f978e](https://github.com/jl-cmd/claude-code-config/commit/69f978e2bb99324e0ba0123993124ef950bd328b))
* **ci:** unblock release-please for claude-dev-env npm publish ([4253536](https://github.com/jl-cmd/claude-code-config/commit/4253536074c01d09e53092d2d22d106d3cafe491))

## [1.16.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.15.1...claude-dev-env-v1.16.0) (2026-04-09)


### Features

* **claude-dev-env:** add --only flag for selective group installs ([#29](https://github.com/jl-cmd/claude-code-config/issues/29)) ([7c9ea43](https://github.com/jl-cmd/claude-code-config/commit/7c9ea43f4a7032d57750a0f441ffc6984438a3f9))
* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([d25a598](https://github.com/jl-cmd/claude-code-config/commit/d25a5989331115a75a11fd10fb54d7ff7fc59f59))
* **claude-dev-env:** prompt-workflow Stop gate for required XML sections (v1.13.1) ([#54](https://github.com/jl-cmd/claude-code-config/issues/54)) ([d0960d2](https://github.com/jl-cmd/claude-code-config/commit/d0960d21b0f8f8e8601ee80c26de424a52eeeb2d))
* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([083ab3c](https://github.com/jl-cmd/claude-code-config/commit/083ab3c28ed29fd659067d34baa0bf31941a526f))
* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([276de6e](https://github.com/jl-cmd/claude-code-config/commit/276de6e58c5ea4e3d2216784cfc7e61fd245ea06))
* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([f28b114](https://github.com/jl-cmd/claude-code-config/commit/f28b11432a1904820287536fd9571517134afabb))
* **hooks:** clipboard on prompt-workflow delivery; background section + nested fences ([#56](https://github.com/jl-cmd/claude-code-config/issues/56)) ([558512e](https://github.com/jl-cmd/claude-code-config/commit/558512e444d93af8202b0299bd5e9c27587fcd85))
* **prompt-generator:** deterministic enforcement for evals 8 and 9 ([#47](https://github.com/jl-cmd/claude-code-config/issues/47)) ([7078813](https://github.com/jl-cmd/claude-code-config/commit/7078813e49b2243608766417900f959bd13276cf))
* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([1e072c5](https://github.com/jl-cmd/claude-code-config/commit/1e072c5543c3d2f8e22e3732e98cba62176ad587))
* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([7f3137f](https://github.com/jl-cmd/claude-code-config/commit/7f3137fa0818aaa175fbfb49096b00082944e7ed))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([f4f2ede](https://github.com/jl-cmd/claude-code-config/commit/f4f2ede2a288e7745d6a05189bfb28d893e565a3))


### Bug Fixes

* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([0d704b6](https://github.com/jl-cmd/claude-code-config/commit/0d704b6e1678cfc831022ff64c8ab800143dc718))
* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([318e94a](https://github.com/jl-cmd/claude-code-config/commit/318e94a8eef158a563324212c134dd9ec41db69e))
* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([6563449](https://github.com/jl-cmd/claude-code-config/commit/65634497661e85f048423049e0e8d4aebde1a85b))
* **hooks:** remove PreToolUse agent-execution-intent-gate ([#51](https://github.com/jl-cmd/claude-code-config/issues/51)) ([a0d15cd](https://github.com/jl-cmd/claude-code-config/commit/a0d15cd79152983e4bde40010804a9974ad4b750))
* **prompt-generator:** close eval compliance gaps in SKILL.md ([f2a4af4](https://github.com/jl-cmd/claude-code-config/commit/f2a4af4f45404b99164dd341c91be8946cd44cac))
* **prompt-generator:** stop requiring checklist table in user-facing output ([#49](https://github.com/jl-cmd/claude-code-config/issues/49)) ([4c236c7](https://github.com/jl-cmd/claude-code-config/commit/4c236c74828d1d88714e3bdb0b1c46c12368542e))

## [1.15.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.15.0...claude-dev-env-v1.15.1) (2026-04-09)

### Documentation

* **prompt-generator:** align `SKILL.md` (including §7 ordered steps for code inside `<illustrations>`), `TARGET_OUTPUT.md`, eval spec (eval 13), runbook, `REFERENCE.md`, and `skill-writer-agent` samples with required `<background>` and optional `<illustrations>` naming and nested-fence notes ([#58](https://github.com/jl-cmd/claude-code-config/pull/58))

## [1.15.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.14.1...claude-dev-env-v1.15.0) (2026-04-09)

### Features

* **claude-dev-env:** add --only flag for selective group installs ([#29](https://github.com/jl-cmd/claude-code-config/issues/29)) ([7c9ea43](https://github.com/jl-cmd/claude-code-config/commit/7c9ea43f4a7032d57750a0f441ffc6984438a3f9))
* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([d25a598](https://github.com/jl-cmd/claude-code-config/commit/d25a5989331115a75a11fd10fb54d7ff7fc59f59))
* **claude-dev-env:** prompt-workflow Stop gate for required XML sections (v1.13.1) ([#54](https://github.com/jl-cmd/claude-code-config/issues/54)) ([d0960d2](https://github.com/jl-cmd/claude-code-config/commit/d0960d21b0f8f8e8601ee80c26de424a52eeeb2d))
* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([083ab3c](https://github.com/jl-cmd/claude-code-config/commit/083ab3c28ed29fd659067d34baa0bf31941a526f))
* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([276de6e](https://github.com/jl-cmd/claude-code-config/commit/276de6e58c5ea4e3d2216784cfc7e61fd245ea06))
* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([f28b114](https://github.com/jl-cmd/claude-code-config/commit/f28b11432a1904820287536fd9571517134afabb))
* **hooks:** clipboard on prompt-workflow delivery; background section + nested fences ([#56](https://github.com/jl-cmd/claude-code-config/issues/56)) ([558512e](https://github.com/jl-cmd/claude-code-config/commit/558512e444d93af8202b0299bd5e9c27587fcd85))
* **prompt-generator:** deterministic enforcement for evals 8 and 9 ([#47](https://github.com/jl-cmd/claude-code-config/issues/47)) ([7078813](https://github.com/jl-cmd/claude-code-config/commit/7078813e49b2243608766417900f959bd13276cf))
* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([1e072c5](https://github.com/jl-cmd/claude-code-config/commit/1e072c5543c3d2f8e22e3732e98cba62176ad587))
* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([7f3137f](https://github.com/jl-cmd/claude-code-config/commit/7f3137fa0818aaa175fbfb49096b00082944e7ed))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([f4f2ede](https://github.com/jl-cmd/claude-code-config/commit/f4f2ede2a288e7745d6a05189bfb28d893e565a3))


### Bug Fixes

* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([0d704b6](https://github.com/jl-cmd/claude-code-config/commit/0d704b6e1678cfc831022ff64c8ab800143dc718))
* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([318e94a](https://github.com/jl-cmd/claude-code-config/commit/318e94a8eef158a563324212c134dd9ec41db69e))
* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([6563449](https://github.com/jl-cmd/claude-code-config/commit/65634497661e85f048423049e0e8d4aebde1a85b))
* **hooks:** remove PreToolUse agent-execution-intent-gate ([#51](https://github.com/jl-cmd/claude-code-config/issues/51)) ([a0d15cd](https://github.com/jl-cmd/claude-code-config/commit/a0d15cd79152983e4bde40010804a9974ad4b750))
* **prompt-generator:** close eval compliance gaps in SKILL.md ([f2a4af4](https://github.com/jl-cmd/claude-code-config/commit/f2a4af4f45404b99164dd341c91be8946cd44cac))
* **prompt-generator:** stop requiring checklist table in user-facing output ([#49](https://github.com/jl-cmd/claude-code-config/issues/49)) ([4c236c7](https://github.com/jl-cmd/claude-code-config/commit/4c236c74828d1d88714e3bdb0b1c46c12368542e))

## [1.14.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.14.0...claude-dev-env-v1.14.1) (2026-04-09)

### Features

* **prompt-workflow:** copy fenced `xml` artifact to the system clipboard when Stop hook gates pass ([#56](https://github.com/jl-cmd/claude-code-config/pull/56))

### Bug Fixes

* **prompt-workflow:** require `<background>` instead of `<context>` in fenced XML; parse nested Markdown code fences inside `xml` blocks so extraction and clipboard copy stay complete ([#56](https://github.com/jl-cmd/claude-code-config/pull/56))

## [1.14.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.13.0...claude-dev-env-v1.14.0) (2026-04-09)


### Features

* **claude-dev-env:** prompt-workflow Stop gate for required XML sections (v1.13.1) ([#54](https://github.com/jl-cmd/claude-code-config/issues/54)) ([d0960d2](https://github.com/jl-cmd/claude-code-config/commit/d0960d21b0f8f8e8601ee80c26de424a52eeeb2d))

## [1.13.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.12.2...claude-dev-env-v1.13.0) (2026-04-09)


### Features

* **claude-dev-env:** add --only flag for selective group installs ([#29](https://github.com/jl-cmd/claude-code-config/issues/29)) ([7c9ea43](https://github.com/jl-cmd/claude-code-config/commit/7c9ea43f4a7032d57750a0f441ffc6984438a3f9))
* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([d25a598](https://github.com/jl-cmd/claude-code-config/commit/d25a5989331115a75a11fd10fb54d7ff7fc59f59))
* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([083ab3c](https://github.com/jl-cmd/claude-code-config/commit/083ab3c28ed29fd659067d34baa0bf31941a526f))
* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([276de6e](https://github.com/jl-cmd/claude-code-config/commit/276de6e58c5ea4e3d2216784cfc7e61fd245ea06))
* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([f28b114](https://github.com/jl-cmd/claude-code-config/commit/f28b11432a1904820287536fd9571517134afabb))
* **prompt-generator:** deterministic enforcement for evals 8 and 9 ([#47](https://github.com/jl-cmd/claude-code-config/issues/47)) ([7078813](https://github.com/jl-cmd/claude-code-config/commit/7078813e49b2243608766417900f959bd13276cf))
* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([1e072c5](https://github.com/jl-cmd/claude-code-config/commit/1e072c5543c3d2f8e22e3732e98cba62176ad587))
* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([7f3137f](https://github.com/jl-cmd/claude-code-config/commit/7f3137fa0818aaa175fbfb49096b00082944e7ed))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([f4f2ede](https://github.com/jl-cmd/claude-code-config/commit/f4f2ede2a288e7745d6a05189bfb28d893e565a3))


### Bug Fixes

* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([0d704b6](https://github.com/jl-cmd/claude-code-config/commit/0d704b6e1678cfc831022ff64c8ab800143dc718))
* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([318e94a](https://github.com/jl-cmd/claude-code-config/commit/318e94a8eef158a563324212c134dd9ec41db69e))
* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([6563449](https://github.com/jl-cmd/claude-code-config/commit/65634497661e85f048423049e0e8d4aebde1a85b))
* **hooks:** remove PreToolUse agent-execution-intent-gate ([#51](https://github.com/jl-cmd/claude-code-config/issues/51)) ([a0d15cd](https://github.com/jl-cmd/claude-code-config/commit/a0d15cd79152983e4bde40010804a9974ad4b750))
* **prompt-generator:** close eval compliance gaps in SKILL.md ([f2a4af4](https://github.com/jl-cmd/claude-code-config/commit/f2a4af4f45404b99164dd341c91be8946cd44cac))
* **prompt-generator:** stop requiring checklist table in user-facing output ([#49](https://github.com/jl-cmd/claude-code-config/issues/49)) ([4c236c7](https://github.com/jl-cmd/claude-code-config/commit/4c236c74828d1d88714e3bdb0b1c46c12368542e))

## [1.12.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.12.1...claude-dev-env-v1.12.2) (2026-04-09)


### Bug Fixes

* **hooks:** remove PreToolUse agent-execution-intent-gate ([#51](https://github.com/jl-cmd/claude-code-config/pull/51)) ([a0d15cd](https://github.com/jl-cmd/claude-code-config/commit/a0d15cd79152983e4bde40010804a9974ad4b750))


## [1.12.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.12.0...claude-dev-env-v1.12.1) (2026-04-09)


### Bug Fixes

* **prompt-generator:** stop requiring checklist table in user-facing output ([#49](https://github.com/jl-cmd/claude-code-config/issues/49)) ([4c236c7](https://github.com/jl-cmd/claude-code-config/commit/4c236c74828d1d88714e3bdb0b1c46c12368542e))

## [1.12.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.11.0...claude-dev-env-v1.12.0) (2026-04-09)


### Features

* **prompt-generator:** deterministic enforcement for evals 8 and 9 ([#47](https://github.com/jl-cmd/claude-code-config/issues/47)) ([7078813](https://github.com/jl-cmd/claude-code-config/commit/7078813e49b2243608766417900f959bd13276cf))

## [1.11.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.10.1...claude-dev-env-v1.11.0) (2026-04-09)


### Features

* **claude-dev-env:** add --only flag for selective group installs ([#29](https://github.com/jl-cmd/claude-code-config/issues/29)) ([7c9ea43](https://github.com/jl-cmd/claude-code-config/commit/7c9ea43f4a7032d57750a0f441ffc6984438a3f9))
* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([d25a598](https://github.com/jl-cmd/claude-code-config/commit/d25a5989331115a75a11fd10fb54d7ff7fc59f59))
* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([083ab3c](https://github.com/jl-cmd/claude-code-config/commit/083ab3c28ed29fd659067d34baa0bf31941a526f))
* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([276de6e](https://github.com/jl-cmd/claude-code-config/commit/276de6e58c5ea4e3d2216784cfc7e61fd245ea06))
* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([f28b114](https://github.com/jl-cmd/claude-code-config/commit/f28b11432a1904820287536fd9571517134afabb))
* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([1e072c5](https://github.com/jl-cmd/claude-code-config/commit/1e072c5543c3d2f8e22e3732e98cba62176ad587))
* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([7f3137f](https://github.com/jl-cmd/claude-code-config/commit/7f3137fa0818aaa175fbfb49096b00082944e7ed))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([f4f2ede](https://github.com/jl-cmd/claude-code-config/commit/f4f2ede2a288e7745d6a05189bfb28d893e565a3))


### Bug Fixes

* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([0d704b6](https://github.com/jl-cmd/claude-code-config/commit/0d704b6e1678cfc831022ff64c8ab800143dc718))
* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([318e94a](https://github.com/jl-cmd/claude-code-config/commit/318e94a8eef158a563324212c134dd9ec41db69e))
* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([6563449](https://github.com/jl-cmd/claude-code-config/commit/65634497661e85f048423049e0e8d4aebde1a85b))
* **prompt-generator:** close eval compliance gaps in SKILL.md ([f2a4af4](https://github.com/jl-cmd/claude-code-config/commit/f2a4af4f45404b99164dd341c91be8946cd44cac))

## [1.10.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.9.0...claude-dev-env-v1.10.0) (2026-04-09)


### Features

* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([1e072c5](https://github.com/jl-cmd/claude-code-config/commit/1e072c5543c3d2f8e22e3732e98cba62176ad587))

## [1.9.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.8.2...claude-dev-env-v1.9.0) (2026-04-07)


### Features

* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([083ab3c](https://github.com/jl-cmd/claude-code-config/commit/083ab3c28ed29fd659067d34baa0bf31941a526f))

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
