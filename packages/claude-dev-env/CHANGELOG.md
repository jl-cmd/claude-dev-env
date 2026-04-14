# Changelog

## [1.19.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.19.1...claude-dev-env-v1.19.2) (2026-04-14)


### Bug Fixes

* **claude-dev-env:** convert 400-line file cap from blocking to advisory ([#101](https://github.com/jl-cmd/claude-code-config/issues/101)) ([8b2dddc](https://github.com/jl-cmd/claude-code-config/commit/8b2dddc11273c145732b4f00ccf7e4649f9c007c))

## [1.19.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.19.0...claude-dev-env-v1.19.1) (2026-04-12)


### Bug Fixes

* **hooks:** wire Zoekt redirector into PreToolUse ([#96](https://github.com/jl-cmd/claude-code-config/issues/96)) ([897c941](https://github.com/jl-cmd/claude-code-config/commit/897c94192d21a55de747c0b4325385d572bff9f0))

## [1.19.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.18.0...claude-dev-env-v1.19.0) (2026-04-12)


### Features

* **claude-dev-env:** add --only flag for selective group installs ([#29](https://github.com/jl-cmd/claude-code-config/issues/29)) ([968b651](https://github.com/jl-cmd/claude-code-config/commit/968b651ed3e3b74250f3259dc4013fe689ff8178))
* **claude-dev-env:** add skill package prompt templates and workflow wiring ([#66](https://github.com/jl-cmd/claude-code-config/issues/66)) ([9f60c55](https://github.com/jl-cmd/claude-code-config/commit/9f60c558d822eb9865d23d31e48a105ce7961d07))
* **claude-dev-env:** consolidate sibling packages into single npm package ([#27](https://github.com/jl-cmd/claude-code-config/issues/27)) ([6d1a87b](https://github.com/jl-cmd/claude-code-config/commit/6d1a87bee55b084a74421a9c8d7102fa57d2658c))
* **claude-dev-env:** prompt-workflow Stop gate for required XML sections (v1.13.1) ([#54](https://github.com/jl-cmd/claude-code-config/issues/54)) ([0c033b6](https://github.com/jl-cmd/claude-code-config/commit/0c033b6b12d563c88ea1a05851b46088014b782d))
* **claude-dev-env:** split Stop-hook gates into diagnostic and user channels ([#39](https://github.com/jl-cmd/claude-code-config/issues/39)) ([98e1d48](https://github.com/jl-cmd/claude-code-config/commit/98e1d4849ad1ca25dc41da03cfe4747020f7045a))
* convert to npm workspaces monorepo with claude-journal and claude-deep-research ([#13](https://github.com/jl-cmd/claude-code-config/issues/13)) ([7db06fc](https://github.com/jl-cmd/claude-code-config/commit/7db06fc96a35adf2d30360b6695c3e07a042c73b))
* extract prompt-workflow tooling into standalone claude-prompt-tools package ([#19](https://github.com/jl-cmd/claude-code-config/issues/19)) ([19df4a7](https://github.com/jl-cmd/claude-code-config/commit/19df4a76b93932cb69209d9d5f292f3aeb52d61c))
* **hooks:** clipboard on prompt-workflow delivery; background section + nested fences ([#56](https://github.com/jl-cmd/claude-code-config/issues/56)) ([37feb29](https://github.com/jl-cmd/claude-code-config/commit/37feb29c49a88a5ba45bb4c713414770e41e5a90))
* **prompt-generator:** deterministic enforcement for evals 8 and 9 ([#47](https://github.com/jl-cmd/claude-code-config/issues/47)) ([d3bf1e8](https://github.com/jl-cmd/claude-code-config/commit/d3bf1e845b0fd8e23551c855df3a7b0d8e267752))
* **prompt-generator:** eval contract and SKILL output rules ([#42](https://github.com/jl-cmd/claude-code-config/issues/42)) ([8309c91](https://github.com/jl-cmd/claude-code-config/commit/8309c910d96df2735931934008f5a1ed895dbec8))
* **skill-writer:** rewrite to mirror prompt-generator structure ([#25](https://github.com/jl-cmd/claude-code-config/issues/25)) ([3939d6b](https://github.com/jl-cmd/claude-code-config/commit/3939d6b9d44e81787d1fabdada78e89eed5370f1))
* sync hook and prompt pipeline artifacts into claude-dev-env ([#16](https://github.com/jl-cmd/claude-code-config/issues/16)) ([548929c](https://github.com/jl-cmd/claude-code-config/commit/548929ce20c8d5348d1804ea8cf970b39d1c60b6))


### Bug Fixes

* **ci:** sync claude-dev-env version with manifest and pin release PR title ([fedf8ce](https://github.com/jl-cmd/claude-code-config/commit/fedf8cecb4743a56f851c4ee654f354a147b044b))
* **ci:** unblock release-please for claude-dev-env npm publish ([cf77bc2](https://github.com/jl-cmd/claude-code-config/commit/cf77bc29d33983276f37ac8ad0e2fbbd9d37009a))
* **claude-dev-env:** include prompt-workflow hooks and rules in prompts group ([#30](https://github.com/jl-cmd/claude-code-config/issues/30)) ([9da5242](https://github.com/jl-cmd/claude-code-config/commit/9da5242cd23a130dd2ccae73ae48abc39616c490))
* **hooks:** accept text-based execution intent without env var gate ([#36](https://github.com/jl-cmd/claude-code-config/issues/36)) ([1151945](https://github.com/jl-cmd/claude-code-config/commit/1151945bb51dd505ecb0e49ee6410d3042541022))
* **hooks:** enforce prompt workflow execution intent contract ([#18](https://github.com/jl-cmd/claude-code-config/issues/18)) ([206354e](https://github.com/jl-cmd/claude-code-config/commit/206354e6f75b96b7ebc340c5bfe8b4f848612a05))
* **hooks:** prevent duplicate write-visible gh calls under bypassPermissions mode ([#85](https://github.com/jl-cmd/claude-code-config/issues/85)) ([84b583c](https://github.com/jl-cmd/claude-code-config/commit/84b583c4f6313b8f689c22617c824ee68bb87e29))
* **hooks:** remove PreToolUse agent-execution-intent-gate ([#51](https://github.com/jl-cmd/claude-code-config/issues/51)) ([299caa7](https://github.com/jl-cmd/claude-code-config/commit/299caa737c6c61140aad84531316ec3ff911626a))
* **prompt-generator:** close eval compliance gaps in SKILL.md ([c59994c](https://github.com/jl-cmd/claude-code-config/commit/c59994cd8ba4e7b400bc8b6ec790782bba134cc4))
* **prompt-generator:** stop requiring checklist table in user-facing output ([#49](https://github.com/jl-cmd/claude-code-config/issues/49)) ([0f44196](https://github.com/jl-cmd/claude-code-config/commit/0f441962ae4f03ab965e31e44459fc32f777fb8a))


### Documentation

* **prompt-generator:** align contract with background, illustrations, and §7 sample rules ([#58](https://github.com/jl-cmd/claude-code-config/issues/58)) ([6f64ab0](https://github.com/jl-cmd/claude-code-config/commit/6f64ab02210fc4738366ac1e5bdb3c39e8d8202a))
* **prompt-generator:** integrate Harnessing Claude hooks 1-12 ([093980c](https://github.com/jl-cmd/claude-code-config/commit/093980c7c133868c0791cd7d45d73ad7bab3f4c1))
* **prompt-generator:** replace jargon with plain language ([#73](https://github.com/jl-cmd/claude-code-config/issues/73)) ([1d3b7c6](https://github.com/jl-cmd/claude-code-config/commit/1d3b7c676593336d7364cca02b6f0c85dfab509e))
* **prompt-generator:** tighten artifact quality and eval-aligned framing ([e4ca5b9](https://github.com/jl-cmd/claude-code-config/commit/e4ca5b9dc0647b3f65b060fcfadf86740d47474f))


### Maintenance

* bump claude-dev-env to 1.10.1 ([6c6d246](https://github.com/jl-cmd/claude-code-config/commit/6c6d246f8cc6e5bb22646cf07dcaf1f40d56df68))
* **claude-dev-env:** bump version to 1.16.2 ([e36c851](https://github.com/jl-cmd/claude-code-config/commit/e36c851b4e009039ccb2fe0411f45941e41ca61d))
* **claude-dev-env:** release v1.14.1 ([2afded1](https://github.com/jl-cmd/claude-code-config/commit/2afded1d1420c1aa7f1b07e752f71674f991c572))
* **main:** release claude-dev-env 1.11.0 ([467b4bc](https://github.com/jl-cmd/claude-code-config/commit/467b4bca144f1321d9f8edc217dcc545f6da4b73))
* **main:** release claude-dev-env 1.11.0 ([f6638f0](https://github.com/jl-cmd/claude-code-config/commit/f6638f0b35cd09182eb660e90b1b24953c7eda6e))
* **main:** release claude-dev-env 1.12.0 ([#48](https://github.com/jl-cmd/claude-code-config/issues/48)) ([3dfe9d5](https://github.com/jl-cmd/claude-code-config/commit/3dfe9d53c02287e732654d4c0bf10295e5df5324))
* **main:** release claude-dev-env 1.12.1 ([#50](https://github.com/jl-cmd/claude-code-config/issues/50)) ([73568df](https://github.com/jl-cmd/claude-code-config/commit/73568df35520c070f49481fd1b729c2673644917))
* **main:** release claude-dev-env 1.12.2 ([#52](https://github.com/jl-cmd/claude-code-config/issues/52)) ([8795b44](https://github.com/jl-cmd/claude-code-config/commit/8795b44fe40cab740469c27d7ccd3095a76470bf))
* **main:** release claude-dev-env 1.13.0 ([#53](https://github.com/jl-cmd/claude-code-config/issues/53)) ([b7b9a27](https://github.com/jl-cmd/claude-code-config/commit/b7b9a2702e9b5954c3565d045f866f14bc725206))
* **main:** release claude-dev-env 1.14.0 ([#55](https://github.com/jl-cmd/claude-code-config/issues/55)) ([73d2645](https://github.com/jl-cmd/claude-code-config/commit/73d26459f2abbf6f57066261064ba15fb3d0b261))
* **main:** release claude-dev-env 1.15.0 ([#57](https://github.com/jl-cmd/claude-code-config/issues/57)) ([60e49bf](https://github.com/jl-cmd/claude-code-config/commit/60e49bfa99b4bcac239ef43289d8ae24f2d68302))
* **main:** release claude-dev-env 1.16.0 ([#59](https://github.com/jl-cmd/claude-code-config/issues/59)) ([8d40b8e](https://github.com/jl-cmd/claude-code-config/commit/8d40b8e3f13d1ce00d87ee0acf144b050524fb0c))
* **main:** release claude-dev-env 1.16.1 ([32f2e1b](https://github.com/jl-cmd/claude-code-config/commit/32f2e1bdecc3bf9802f4fddbefb4d3ac9d97f5b7))
* **main:** release claude-dev-env 1.16.1 ([49de56d](https://github.com/jl-cmd/claude-code-config/commit/49de56df11ea1b67c87364d55859d9cdc284ad97))
* **main:** release claude-dev-env 1.17.0 ([#67](https://github.com/jl-cmd/claude-code-config/issues/67)) ([48d094f](https://github.com/jl-cmd/claude-code-config/commit/48d094fecd98d068f4ba39f723cad3e1e274c6e2))
* **main:** release claude-dev-env 1.17.1 ([#77](https://github.com/jl-cmd/claude-code-config/issues/77)) ([246aa4f](https://github.com/jl-cmd/claude-code-config/commit/246aa4f317cfab3d8ce8fc6d005e0e01465f8e4c))
* **main:** release claude-dev-env 1.17.2 ([#78](https://github.com/jl-cmd/claude-code-config/issues/78)) ([ba9d007](https://github.com/jl-cmd/claude-code-config/commit/ba9d0073287a750403d25966ecbd1cdfb0cbb6f4))
* **main:** release claude-dev-env 1.17.3 ([#87](https://github.com/jl-cmd/claude-code-config/issues/87)) ([06a87b5](https://github.com/jl-cmd/claude-code-config/commit/06a87b5e423b9c31c459041c6a1fe31856fc0518))
* **main:** release claude-dev-env 1.17.4 ([#91](https://github.com/jl-cmd/claude-code-config/issues/91)) ([04237e3](https://github.com/jl-cmd/claude-code-config/commit/04237e31fb7dda1c603ffe1a3cd9e43147cd8c88))
* **main:** release claude-dev-env 1.17.5 ([#95](https://github.com/jl-cmd/claude-code-config/issues/95)) ([a66f758](https://github.com/jl-cmd/claude-code-config/commit/a66f7580fde6f8e6f27262deafc54fde1ae895e3))
* **main:** release claude-dev-env 1.8.0 ([#28](https://github.com/jl-cmd/claude-code-config/issues/28)) ([5e27000](https://github.com/jl-cmd/claude-code-config/commit/5e27000f3cc39aa76d24184e3639103332e8b1de))
* **main:** release claude-dev-env 1.8.1 ([#31](https://github.com/jl-cmd/claude-code-config/issues/31)) ([9c0a79a](https://github.com/jl-cmd/claude-code-config/commit/9c0a79a86ab7eb51c02e160dca00e091781c7d14))
* release main ([c1f56da](https://github.com/jl-cmd/claude-code-config/commit/c1f56dad821c5c22d68f0c7a6c747408ad849e3c))
* release main ([16e5381](https://github.com/jl-cmd/claude-code-config/commit/16e5381705172e4672d7f3502243ec3baef1ce91))
* release main ([#14](https://github.com/jl-cmd/claude-code-config/issues/14)) ([d221975](https://github.com/jl-cmd/claude-code-config/commit/d221975db12fb420e0c7cbf1ef2578835c33be34))
* release main ([#20](https://github.com/jl-cmd/claude-code-config/issues/20)) ([b715494](https://github.com/jl-cmd/claude-code-config/commit/b71549424e7cd28603126b017e5026f8c1bd5da8))
* release main ([#26](https://github.com/jl-cmd/claude-code-config/issues/26)) ([35eb12d](https://github.com/jl-cmd/claude-code-config/commit/35eb12d763473845c894879034f203e16cba9b28))
* release main ([#40](https://github.com/jl-cmd/claude-code-config/issues/40)) ([ed5fe6a](https://github.com/jl-cmd/claude-code-config/commit/ed5fe6acafc7477791d5332058343a3aace5db6a))
* release main ([#43](https://github.com/jl-cmd/claude-code-config/issues/43)) ([e129b02](https://github.com/jl-cmd/claude-code-config/commit/e129b0295a62362d7e34db1f4491c659f298843e))


### Refactoring

* **prompt-tools:** compact table audit + remove context signals ([#33](https://github.com/jl-cmd/claude-code-config/issues/33)) ([17445c7](https://github.com/jl-cmd/claude-code-config/commit/17445c728a35e729a013ae6756b80df4171e88d9))
* **prompt-workflow:** replace Stop hook with file-based validation loop ([#75](https://github.com/jl-cmd/claude-code-config/issues/75)) ([8de312a](https://github.com/jl-cmd/claude-code-config/commit/8de312a4f50d7d862e684fa15853755243a69e03))
* source prompts install group from @jl-cmd/prompt-generator npm dependency ([#93](https://github.com/jl-cmd/claude-code-config/issues/93)) ([ca11cd3](https://github.com/jl-cmd/claude-code-config/commit/ca11cd34f6c8ab44277b305cab9755fe86fb184b))
* **zoekt-hook:** phase 2 guidance API on main ([#86](https://github.com/jl-cmd/claude-code-config/issues/86)) ([#90](https://github.com/jl-cmd/claude-code-config/issues/90)) ([e069818](https://github.com/jl-cmd/claude-code-config/commit/e0698188d4646e0069c5900a4bd0e669f5a79d68))

## [1.18.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.5...claude-dev-env-v1.18.0) (2026-04-12)


### Extraction Migration

* **prompt-generator:** delete in-tree copies now sourced from @jl-cmd/prompt-generator dependency

  Removed 11 in-tree artifacts (2 skill directories, 5 hook scripts, 3 test files,
  1 hook spec, 1 rule file) that are now installed from the @jl-cmd/prompt-generator
  npm package via install.mjs discoverDependencyGroups().

  Removed artifacts:
  - skills/prompt-generator/ (8 files)
  - skills/agent-prompt/ (1 file)
  - hooks/blocking/prompt_workflow_gate_config.py
  - hooks/blocking/prompt_workflow_gate_core.py
  - hooks/blocking/prompt_workflow_validate.py
  - hooks/blocking/prompt_workflow_clipboard.py
  - hooks/blocking/test_prompt_workflow_gate_core.py
  - hooks/blocking/test_prompt_workflow_clipboard.py
  - hooks/blocking/test_prompt_workflow_validate.py
  - hooks/HOOK_SPECS_PROMPT_WORKFLOW.md
  - rules/prompt-workflow-context-controls.md

  Rollback: revert this commit and pin @jl-cmd/prompt-generator below 1.0.0 in
  package.json to restore in-tree copies.

## [1.17.5](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.17.4...claude-dev-env-v1.17.5) (2026-04-12)


### Refactoring

* source prompts install group from @jl-cmd/prompt-generator npm dependency ([#93](https://github.com/jl-cmd/claude-code-config/issues/93)) ([ca11cd3](https://github.com/jl-cmd/claude-code-config/commit/ca11cd34f6c8ab44277b305cab9755fe86fb184b))

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
