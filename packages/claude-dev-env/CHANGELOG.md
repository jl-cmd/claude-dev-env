# Changelog

## [1.31.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.31.0...claude-dev-env-v1.31.1) (2026-04-27)


### Bug Fixes

* **hooks:** address Copilot review findings on Stop-wrapper debounce ([#268](https://github.com/jl-cmd/claude-code-config/issues/268)) ([f5e6fdd](https://github.com/jl-cmd/claude-code-config/commit/f5e6fdd3ea6bcede17da9531dfa3740e59325e72))
* **logifix:** always run full LCore relaunch count ([#264](https://github.com/jl-cmd/claude-code-config/issues/264)) ([42c1e0d](https://github.com/jl-cmd/claude-code-config/commit/42c1e0d590f429a5888197e1a70ab27eed001e4c))


### Performance

* **hooks:** debounce Stop-hook extractor to eliminate per-turn latency ([#267](https://github.com/jl-cmd/claude-code-config/issues/267)) ([b390af4](https://github.com/jl-cmd/claude-code-config/commit/b390af46a78ad51991847303cb66577194a82465))


### Tests

* **hooks:** rename misnamed Stop-wrapper timestamp test ([#269](https://github.com/jl-cmd/claude-code-config/issues/269)) ([21dac4b](https://github.com/jl-cmd/claude-code-config/commit/21dac4b9bd5b560be15c4091032cba1254cad118))

## [1.31.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.30.1...claude-dev-env-v1.31.0) (2026-04-25)


### Features

* **agents:** positive framing + rules-aware bug finder ([#263](https://github.com/jl-cmd/claude-code-config/issues/263)) ([d8a85be](https://github.com/jl-cmd/claude-code-config/commit/d8a85bea3de34a3ddc30910cda785224e0228f48))
* **hooks:** auto-allow cwd-scoped destructive commands in ephemeral worktrees ([#256](https://github.com/jl-cmd/claude-code-config/issues/256)) ([2000728](https://github.com/jl-cmd/claude-code-config/commit/2000728afdfc8425a9062be63c14e9549e2db121))
* **hooks:** enforce structured user questions via AskUserQuestion ([#260](https://github.com/jl-cmd/claude-code-config/issues/260)) ([0f65c5d](https://github.com/jl-cmd/claude-code-config/commit/0f65c5d5c502f14084abec8a245a1d84f4844020))
* **hooks:** hook-log extractor to Neon (phases 1-5) ([#257](https://github.com/jl-cmd/claude-code-config/issues/257)) ([ce4bc51](https://github.com/jl-cmd/claude-code-config/commit/ce4bc51c073efa16b693d4277ccaac11e1590a15))
* **installer:** abort install when package source has unmerged git conflicts ([#262](https://github.com/jl-cmd/claude-code-config/issues/262)) ([cc36a42](https://github.com/jl-cmd/claude-code-config/commit/cc36a4261a5eebc708f1707c6661612a313f4fd4))


### Bug Fixes

* **hooks:** exempt config/ from file-global-constants use-count rule ([#259](https://github.com/jl-cmd/claude-code-config/issues/259)) ([c0e345e](https://github.com/jl-cmd/claude-code-config/commit/c0e345ef9aae02aaa71dd0d8a8c9caae4fe12bb1))


### Maintenance

* **hooks:** record Themes hook-log isolation migration ([#261](https://github.com/jl-cmd/claude-code-config/issues/261)) ([d92b260](https://github.com/jl-cmd/claude-code-config/commit/d92b2606ee5017222da05da5f95946acb25003aa))

## [1.30.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.30.0...claude-dev-env-v1.30.1) (2026-04-24)


### Documentation

* add SOLID principles guidance with right-sized engineering reconciliation ([#254](https://github.com/jl-cmd/claude-code-config/issues/254)) ([c13a05b](https://github.com/jl-cmd/claude-code-config/commit/c13a05bbd1694459b25b1938156556f3456e3bc9))

## [1.30.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.29.3...claude-dev-env-v1.30.0) (2026-04-24)


### Features

* **agents:** expand code-quality-agent zero-defect generation guide ([#251](https://github.com/jl-cmd/claude-code-config/issues/251)) ([5da7abf](https://github.com/jl-cmd/claude-code-config/commit/5da7abf435f363404d76d10ec296cf42bd8818c7))
* **enforcer:** expand gate with 6 new checks, retire pre-push-review skill ([#232](https://github.com/jl-cmd/claude-code-config/issues/232)) ([5c81b39](https://github.com/jl-cmd/claude-code-config/commit/5c81b3982bc7c6a9df3c0083d6e4044d08ff3905))
* **hooks:** auto-allow rm -rf in ephemeral target paths ([#235](https://github.com/jl-cmd/claude-code-config/issues/235)) ([cc8d263](https://github.com/jl-cmd/claude-code-config/commit/cc8d263af6bc403e4915b6f65173750ed28901c0))
* **skills:** add monitor-open-prs and groq-backed FIX pipeline ([#241](https://github.com/jl-cmd/claude-code-config/issues/241)) ([e2f1182](https://github.com/jl-cmd/claude-code-config/commit/e2f118220ce860f40437ed023f183668acfdcd7a))


### Bug Fixes

* **groq-bugteam:** address Cursor Bugbot PR [#237](https://github.com/jl-cmd/claude-code-config/issues/237) review ([#242](https://github.com/jl-cmd/claude-code-config/issues/242)) ([e21c2f3](https://github.com/jl-cmd/claude-code-config/commit/e21c2f3edfd0fe5b1676c50c7a9a2523c352f5ad))
* **tests:** resolve full-suite config namespace collision ([#253](https://github.com/jl-cmd/claude-code-config/issues/253)) ([798bd18](https://github.com/jl-cmd/claude-code-config/commit/798bd183823bb44f1797548ece410c827c54fbcc))

## [1.29.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.29.2...claude-dev-env-v1.29.3) (2026-04-22)


### Bug Fixes

* **tests:** eliminate remaining preflight skips and subprocess flakiness ([#250](https://github.com/jl-cmd/claude-code-config/issues/250)) ([f787b81](https://github.com/jl-cmd/claude-code-config/commit/f787b819249d547fa0cb778b39ba29f351c7bcfd))
* **tests:** use tmp_path as subprocess cwd to stabilize on UNC worktrees ([#248](https://github.com/jl-cmd/claude-code-config/issues/248)) ([492e567](https://github.com/jl-cmd/claude-code-config/commit/492e567764df2f813262bc637cb93834057e00ee))

## [1.29.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.29.1...claude-dev-env-v1.29.2) (2026-04-22)


### Bug Fixes

* stabilize 4 baseline test failures on main ([#246](https://github.com/jl-cmd/claude-code-config/issues/246)) ([ffc7879](https://github.com/jl-cmd/claude-code-config/commit/ffc7879bc52cb43af4f970610e387a972b8bdf37))

## [1.29.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.29.0...claude-dev-env-v1.29.1) (2026-04-22)


### Bug Fixes

* **setup_project_paths:** evict stale config bindings before import ([#244](https://github.com/jl-cmd/claude-code-config/issues/244)) ([905b271](https://github.com/jl-cmd/claude-code-config/commit/905b271104d382ed770ce244fb237d473d30df9e))

## [1.29.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.28.1...claude-dev-env-v1.29.0) (2026-04-22)


### Features

* **agents:** add caveman agent and output style ([#238](https://github.com/jl-cmd/claude-code-config/issues/238)) ([5c874b5](https://github.com/jl-cmd/claude-code-config/commit/5c874b5344754478b542d5b8e58922cc996bd526))
* **hooks:** es.exe path-rewriter + untracked-repo detector + setup script ([#230](https://github.com/jl-cmd/claude-code-config/issues/230)) ([528bb18](https://github.com/jl-cmd/claude-code-config/commit/528bb18b90484c4c2295a4d13772a045e515ac99))
* **scripts:** groq_bugteam.py — Groq-backed single-pass bugteam ([#237](https://github.com/jl-cmd/claude-code-config/issues/237)) ([fdaa52a](https://github.com/jl-cmd/claude-code-config/commit/fdaa52a85e4ddd4f974b74b05a88097e9ea426fa))
* **skills:** add copilot-review skill ([#228](https://github.com/jl-cmd/claude-code-config/issues/228)) ([e1e0742](https://github.com/jl-cmd/claude-code-config/commit/e1e0742a60135bdb68c257732a9052c2a6bbae4b))
* **skills:** bugteam/qbug spawn Opus 4.7 at xhigh effort ([#239](https://github.com/jl-cmd/claude-code-config/issues/239)) ([3523527](https://github.com/jl-cmd/claude-code-config/commit/3523527e57c911cdb931374113098b4776bdf660))


### Bug Fixes

* **qbug:** close audit-cycle leaks, enforce 1-loop convergence ([#231](https://github.com/jl-cmd/claude-code-config/issues/231)) ([39154b4](https://github.com/jl-cmd/claude-code-config/commit/39154b42c9338a44ac440ce5388506a3373f9fb3))


### Maintenance

* make AGENTS.md canonical for AI-rules sync ([#236](https://github.com/jl-cmd/claude-code-config/issues/236)) ([2c6d77d](https://github.com/jl-cmd/claude-code-config/commit/2c6d77d644b6c1491461312d0f14fa5e426d8fe8))

## [1.28.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.28.0...claude-dev-env-v1.28.1) (2026-04-21)


### Maintenance

* **qbug:** pin clean-coder subagent to sonnet via skill override ([#225](https://github.com/jl-cmd/claude-code-config/issues/225)) ([6dc93ee](https://github.com/jl-cmd/claude-code-config/commit/6dc93ee395556a000291f74470439f2248192c9e))

## [1.28.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.27.0...claude-dev-env-v1.28.0) (2026-04-20)


### Features

* **skills:** add /qbug — required-baseline single-subagent PR review ([#223](https://github.com/jl-cmd/claude-code-config/issues/223)) ([712876b](https://github.com/jl-cmd/claude-code-config/commit/712876b2f44fcc4ec1a56aa2a4f52063dbd7a4c2))

## [1.27.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.5...claude-dev-env-v1.27.0) (2026-04-20)


### Features

* **hooks:** externalize git reset --hard allow-list to settings.json ([#220](https://github.com/jl-cmd/claude-code-config/issues/220)) ([2c21fd9](https://github.com/jl-cmd/claude-code-config/commit/2c21fd97540022586e83239816dfbafd6dc76a88))
* **hooks:** ship native git pre-commit/pre-push hooks with CODE_RULES gate ([#213](https://github.com/jl-cmd/claude-code-config/issues/213)) ([efb7524](https://github.com/jl-cmd/claude-code-config/commit/efb7524c6d1083052961085132441b8817c3a14e))


### Bug Fixes

* **tdd-hook:** eliminate pragma bypass, add AST constants-only exemption, adopt split-channel output ([#221](https://github.com/jl-cmd/claude-code-config/issues/221)) ([034b314](https://github.com/jl-cmd/claude-code-config/commit/034b314ac1c62c64c1a6a80fd32fc8cf3c339406))


### Maintenance

* **hooks:** remove code_rules_enforcer.py from PreToolUse Write|Edit ([#214](https://github.com/jl-cmd/claude-code-config/issues/214)) ([cb65d82](https://github.com/jl-cmd/claude-code-config/commit/cb65d82c452880d085d9b9a2b7926c4b83679141))

## [1.26.5](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.4...claude-dev-env-v1.26.5) (2026-04-20)


### Bug Fixes

* **hedging-hook:** suppress skill dump from user chat output ([#215](https://github.com/jl-cmd/claude-code-config/issues/215)) ([cb31d66](https://github.com/jl-cmd/claude-code-config/commit/cb31d668495bb3cf9172886bd276b290e1ace9e9))

## [1.26.4](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.3...claude-dev-env-v1.26.4) (2026-04-20)


### Bug Fixes

* **bugteam:** orchestrator is lead; multi-PR supported via one team + per-PR worktrees ([#217](https://github.com/jl-cmd/claude-code-config/issues/217)) ([d1c9a03](https://github.com/jl-cmd/claude-code-config/commit/d1c9a03a18d1f1350c4497029e5e5d2b6fd96b8d))

## [1.26.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.2...claude-dev-env-v1.26.3) (2026-04-20)


### Bug Fixes

* **claude-dev-env:** record real package version in install manifest ([#210](https://github.com/jl-cmd/claude-code-config/issues/210)) ([3fb739c](https://github.com/jl-cmd/claude-code-config/commit/3fb739c8f0d32d493b8b9a69280f0843a43ab653))
* **hooks:** remove 6 hook entries referencing scripts that are not in the package ([#212](https://github.com/jl-cmd/claude-code-config/issues/212)) ([1a16d33](https://github.com/jl-cmd/claude-code-config/commit/1a16d33f4140f485ff8efff4aef7a06af48c9001))

## [1.26.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.1...claude-dev-env-v1.26.2) (2026-04-19)


### Bug Fixes

* **bugteam:** gate UTF-8 on Windows and optional --only-under scope ([#205](https://github.com/jl-cmd/claude-code-config/issues/205)) ([5ea5e50](https://github.com/jl-cmd/claude-code-config/commit/5ea5e501a536b2294536913302fe1a4fe5497bd8))


### Documentation

* **bugteam:** add sources.md; move Claude permission scripts under scripts/ ([#206](https://github.com/jl-cmd/claude-code-config/issues/206)) ([9b8d865](https://github.com/jl-cmd/claude-code-config/commit/9b8d865909bc6ba2a6d288082c517bda04dcd0f4))
* **bugteam:** concise SKILL, reference/, sources, eval citations ([#207](https://github.com/jl-cmd/claude-code-config/issues/207)) ([819dafa](https://github.com/jl-cmd/claude-code-config/commit/819dafa920a20b361f8e9125fbf2bcbf54aef490))

## [1.26.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.26.0...claude-dev-env-v1.26.1) (2026-04-19)


### Bug Fixes

* **reconcile:** /bugteam audit of range 7d37285..84a6c9d ([#203](https://github.com/jl-cmd/claude-code-config/issues/203)) ([dd2b9de](https://github.com/jl-cmd/claude-code-config/commit/dd2b9dea7bcef9f7fb22e2531c95a29cb6b966fd))

## [1.26.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.25.2...claude-dev-env-v1.26.0) (2026-04-18)


### Features

* **bugteam:** preflight, code-rules gate, and audit workflow ([#189](https://github.com/jl-cmd/claude-code-config/issues/189)) ([56bfe8a](https://github.com/jl-cmd/claude-code-config/commit/56bfe8a10a7e697a90bfd1461bd07e2c1f54c671))
* **code-rules-enforcer:** enforce file-global constants use count ([#180](https://github.com/jl-cmd/claude-code-config/issues/180)) ([#195](https://github.com/jl-cmd/claude-code-config/issues/195)) ([7caf07b](https://github.com/jl-cmd/claude-code-config/commit/7caf07b6f8579848f51e36ac942faba6a8027ead))
* **notifications:** add Discord push via Bitwarden Secrets Manager alongside ntfy ([#196](https://github.com/jl-cmd/claude-code-config/issues/196)) ([2ae4fdb](https://github.com/jl-cmd/claude-code-config/commit/2ae4fdb8ff11adeb654d93bfe04e0214ffb8fd3b))


### Bug Fixes

* **code-rules-enforcer:** mask string literals in magic-value scan ([#190](https://github.com/jl-cmd/claude-code-config/issues/190)) ([1d5bd3e](https://github.com/jl-cmd/claude-code-config/commit/1d5bd3e3b9e24c92c85da965fddd3d8143a3c140))
* **hooks:** repair six pre-existing test failures on main ([#186](https://github.com/jl-cmd/claude-code-config/issues/186)) ([826fcb2](https://github.com/jl-cmd/claude-code-config/commit/826fcb25b531bd8634c4f0085dafb29bc2cd7fef))
* **validators:** remove unused pytest import from integration test ([#198](https://github.com/jl-cmd/claude-code-config/issues/198)) ([c437237](https://github.com/jl-cmd/claude-code-config/commit/c43723784dd9261edd63fd9962856ae6b2f6e569))


### Documentation

* **bugteam:** literal tool calls + evals suite for deterministic traces ([#184](https://github.com/jl-cmd/claude-code-config/issues/184)) ([db62fbb](https://github.com/jl-cmd/claude-code-config/commit/db62fbbf5ebb9e555be3c9deadb73ff88b5fce58))
* **bugteam:** split SKILL.md into progressive-disclosure layout ([#143](https://github.com/jl-cmd/claude-code-config/issues/143)) ([#200](https://github.com/jl-cmd/claude-code-config/issues/200)) ([e61670e](https://github.com/jl-cmd/claude-code-config/commit/e61670e2ff4f1a7a6051ca3d1b77c3de1e887f8d))


### Maintenance

* **code-rules:** add file-global constants use-count rule ([#180](https://github.com/jl-cmd/claude-code-config/issues/180)) ([f966341](https://github.com/jl-cmd/claude-code-config/commit/f966341ab6e99a8c7fa885186138a9b5d346eb6b))


### Refactoring

* **code-rules-enforcer:** rename file to PEP 8 snake_case ([#191](https://github.com/jl-cmd/claude-code-config/issues/191)) ([02f730a](https://github.com/jl-cmd/claude-code-config/commit/02f730acdf26cf608fc5a4e5962e00dbdb69426b))
* **validators:** use package-qualified imports for validators/ ([#194](https://github.com/jl-cmd/claude-code-config/issues/194)) ([519e8b5](https://github.com/jl-cmd/claude-code-config/commit/519e8b51d0673cd7f781abafe10eab791656f25c))


### Reverts

* **tdd-enforcer:** drop hyphen-to-underscore stem fallback ([#197](https://github.com/jl-cmd/claude-code-config/issues/197)) ([3ffd257](https://github.com/jl-cmd/claude-code-config/commit/3ffd257606ca66f8df8b46f649d80dec16e5a3df))

## [1.25.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.25.1...claude-dev-env-v1.25.2) (2026-04-18)


### Bug Fixes

* **hooks:** make GH-REDIRECT duplicate guard opt-in via env var ([#187](https://github.com/jl-cmd/claude-code-config/issues/187)) ([3462eb2](https://github.com/jl-cmd/claude-code-config/commit/3462eb29c8b7002ffb71d0af194ccd4bcdaffcff))
* **hooks:** skip blocking TDD gate for .claude path segments ([#183](https://github.com/jl-cmd/claude-code-config/issues/183)) ([7d37285](https://github.com/jl-cmd/claude-code-config/commit/7d37285605cc42b24ca2999884cff206e0c6c315))
* **ntfy:** remove public fallback topic ([#188](https://github.com/jl-cmd/claude-code-config/issues/188)) ([40eeb59](https://github.com/jl-cmd/claude-code-config/commit/40eeb59e84e71e1fdd258a442df5b9a08ca0fcf2))

## [1.25.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.25.0...claude-dev-env-v1.25.1) (2026-04-18)


### Maintenance

* task_scope directive + root doc cleanup ([#181](https://github.com/jl-cmd/claude-code-config/issues/181)) ([13e929c](https://github.com/jl-cmd/claude-code-config/commit/13e929c2af14346995995c068c0bd69bc2ef1d1f))

## [1.25.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.24.0...claude-dev-env-v1.25.0) (2026-04-18)


### Features

* **code-rules-enforcer:** block Any annotations and unjustified # type: ignore ([#177](https://github.com/jl-cmd/claude-code-config/issues/177)) ([1fbdef5](https://github.com/jl-cmd/claude-code-config/commit/1fbdef56788e7e067e21fd8f3f96d99cca113188))
* **code-rules-enforcer:** enforce banned identifiers (result, data, etc.) ([#176](https://github.com/jl-cmd/claude-code-config/issues/176)) ([60e450a](https://github.com/jl-cmd/claude-code-config/commit/60e450a2511e922e30aae889618835ef6fa763ed))
* **code-rules-enforcer:** flag structural literals inside f-strings ([#174](https://github.com/jl-cmd/claude-code-config/issues/174)) ([f370bed](https://github.com/jl-cmd/claude-code-config/commit/f370bed70296bb42a9d5c80dc832cefde481f2ef))
* **code-rules-enforcer:** require is_/has_/should_/can_ prefixes on booleans ([#173](https://github.com/jl-cmd/claude-code-config/issues/173)) ([821a141](https://github.com/jl-cmd/claude-code-config/commit/821a1419da3e29340a31074122694a9e6b079151))
* **hooks:** add gh-body-file blocker to prevent backtick corruption on GitHub ([#123](https://github.com/jl-cmd/claude-code-config/issues/123)) ([9a668b6](https://github.com/jl-cmd/claude-code-config/commit/9a668b6973545c3d8e2b58f31c0320592c91756b))
* **skill:** add obsidian-vault on-demand skill ([#110](https://github.com/jl-cmd/claude-code-config/issues/110)) ([#159](https://github.com/jl-cmd/claude-code-config/issues/159)) ([c26e577](https://github.com/jl-cmd/claude-code-config/commit/c26e57772aedc391c99c549fb15f73989d3c4739))
* **tdd-enforcer:** block production writes without a fresh matching test ([#178](https://github.com/jl-cmd/claude-code-config/issues/178)) ([dea30d6](https://github.com/jl-cmd/claude-code-config/commit/dea30d61c1e1846853f676362044907927e2d349))


### Bug Fixes

* **code-rules-enforcer:** align magic-value allowlist with CODE_RULES (drop 2, 100) ([#162](https://github.com/jl-cmd/claude-code-config/issues/162)) ([8193f91](https://github.com/jl-cmd/claude-code-config/commit/8193f91feabf4448af82f7ee1fe139e848455ad0))
* **code-rules-enforcer:** anchor conftest pattern to .py filename ([#172](https://github.com/jl-cmd/claude-code-config/issues/172)) ([5aaf055](https://github.com/jl-cmd/claude-code-config/commit/5aaf0557a6ec31a1bc66d40d1a19a3efad91c7d9))
* **code-rules-enforcer:** flag f-strings in logger.*/logging.*/log.* calls ([#170](https://github.com/jl-cmd/claude-code-config/issues/170)) ([934e80c](https://github.com/jl-cmd/claude-code-config/commit/934e80c845ae186e83bbc1ba8bb1ada9a27cb41e))
* **code-rules-enforcer:** recognize .test.{ts,tsx,js} files as tests ([#163](https://github.com/jl-cmd/claude-code-config/issues/163)) ([72566c1](https://github.com/jl-cmd/claude-code-config/commit/72566c1713fa986f697fe0dbf9f8d4009680232e))
* **code-rules-enforcer:** scope TYPE_CHECKING import bypass to its block only ([#171](https://github.com/jl-cmd/claude-code-config/issues/171)) ([88feb8f](https://github.com/jl-cmd/claude-code-config/commit/88feb8f58c2cc2fd339ba79f534b150712e72590))
* **magic-value-checks:** align validator allowlist with CODE_RULES (drop 2, 100) ([#164](https://github.com/jl-cmd/claude-code-config/issues/164)) ([4dbbdc0](https://github.com/jl-cmd/claude-code-config/commit/4dbbdc0ea65a38cb52e17978828eaae6dd91bf68))
* **magic-value-checks:** exempt numbers nested inside dict/tuple/list-valued constants ([#166](https://github.com/jl-cmd/claude-code-config/issues/166)) ([330c32b](https://github.com/jl-cmd/claude-code-config/commit/330c32bae5eca554ee8fb123bafb86f1990af1da))
* **magic-value-checks:** skip test and config files to match Pre-Write hook ([#175](https://github.com/jl-cmd/claude-code-config/issues/175)) ([9305efb](https://github.com/jl-cmd/claude-code-config/commit/9305efbbe5614e3e9ef2ca144291b3d79fd079f1))


### Documentation

* **code-rules:** document full tool-marker comment-exemption list ([#167](https://github.com/jl-cmd/claude-code-config/issues/167)) ([401360c](https://github.com/jl-cmd/claude-code-config/commit/401360c81ca089ecc3c5df82d0fd8a4c37dcbbb8))
* **code-rules:** document migration and workflow-registry UPPER_SNAKE exemptions ([#165](https://github.com/jl-cmd/claude-code-config/issues/165)) ([ab2c4d5](https://github.com/jl-cmd/claude-code-config/commit/ab2c4d5d46f4f4fe60d573998eab93da1e365b9a))

## [1.24.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.23.1...claude-dev-env-v1.24.0) (2026-04-17)


### Features

* **bugteam:** batch findings into one PR review per loop for tree-shaped comments ([#158](https://github.com/jl-cmd/claude-code-config/issues/158)) ([db503ae](https://github.com/jl-cmd/claude-code-config/commit/db503aecc21810a7c47a673afe9ecd7f32419965))

## [1.23.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.23.0...claude-dev-env-v1.23.1) (2026-04-17)


### Bug Fixes

* **bugteam:** allow project paths containing spaces ([#155](https://github.com/jl-cmd/claude-code-config/issues/155)) ([6d23d54](https://github.com/jl-cmd/claude-code-config/commit/6d23d541292e853bd9c1329307ea20169f803dce))

## [1.23.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.22.1...claude-dev-env-v1.23.0) (2026-04-17)


### Features

* **claude.md:** add task_scope directive — scope-match + ambiguity gate ([#154](https://github.com/jl-cmd/claude-code-config/issues/154)) ([4ac22c9](https://github.com/jl-cmd/claude-code-config/commit/4ac22c9037dd167cc4de734bd9242437907dced2)), closes [#111](https://github.com/jl-cmd/claude-code-config/issues/111)

## [1.22.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.22.0...claude-dev-env-v1.22.1) (2026-04-17)


### Bug Fixes

* centralize /bugteam permission scripts and harden portability ([#138](https://github.com/jl-cmd/claude-code-config/issues/138)) ([815428b](https://github.com/jl-cmd/claude-code-config/commit/815428b84d1787b6713a91a6daee07bfcf3e90b7))

## [1.22.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.21.2...claude-dev-env-v1.22.0) (2026-04-17)


### Features

* add /findbugs, /fixbugs, /bugteam skills for autonomous code-quality audit-and-fix cycles ([#135](https://github.com/jl-cmd/claude-code-config/issues/135)) ([ef2a89b](https://github.com/jl-cmd/claude-code-config/commit/ef2a89b458f9fa9bacb1b4e0532c9c2c883f945e))

## [1.21.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.21.1...claude-dev-env-v1.21.2) (2026-04-17)


### Bug Fixes

* **sync:** force-add listener destinations past gitignore wildcards ([#130](https://github.com/jl-cmd/claude-code-config/issues/130)) ([7dbb1af](https://github.com/jl-cmd/claude-code-config/commit/7dbb1af2cb8a39f2e3a77431d8f97cd6ebcdfa3a))

## [1.21.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.21.0...claude-dev-env-v1.21.1) (2026-04-17)


### Maintenance

* **rules:** add test-file exemptions to CODE_RULES and copilot-instructions ([0a87255](https://github.com/jl-cmd/claude-code-config/commit/0a87255943145fa79b6ec9b42f7e98d02389146c))
* **rules:** add test-file exemptions to CODE_RULES and copilot-instructions ([70f5e0f](https://github.com/jl-cmd/claude-code-config/commit/70f5e0f58f9789dd9eda413bdf864de0e12510ba))

## [1.21.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.20.1...claude-dev-env-v1.21.0) (2026-04-17)


### Features

* **rules:** restore full rule content gutted in llm-settings PR[#17](https://github.com/jl-cmd/claude-code-config/issues/17) ([83fafd7](https://github.com/jl-cmd/claude-code-config/commit/83fafd710518b6a7dd805274c882fede2bf8877d))
* **rules:** restore full rule content gutted in llm-settings PR[#17](https://github.com/jl-cmd/claude-code-config/issues/17) ([c6281a2](https://github.com/jl-cmd/claude-code-config/commit/c6281a27793a9f57aec0cfdda3a6cad27992d10c))


### Bug Fixes

* **rules:** remove hardcoded personal vault path from distributable rule ([7f90f29](https://github.com/jl-cmd/claude-code-config/commit/7f90f29ceb7d3a564832daf4d2a170d298e1d2a1))

## [1.20.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.20.0...claude-dev-env-v1.20.1) (2026-04-16)


### Documentation

* **system-prompt:** add CI-scoped incremental-commit clause to git_workflow ([9c1114e](https://github.com/jl-cmd/claude-code-config/commit/9c1114e197f8e5f8973ae03553785c771d9662fe))

## [1.20.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.19.3...claude-dev-env-v1.20.0) (2026-04-15)


### Features

* **claude-dev-env:** add BDD rule and retire TDD rule file ([e2ea92b](https://github.com/jl-cmd/claude-code-config/commit/e2ea92beae759971f3ce9353f3708b156726b129))
* **claude-dev-env:** add canonical system prompt and pointer rules ([1264e4e](https://github.com/jl-cmd/claude-code-config/commit/1264e4ef81209489f3154e7effb8a73ae731bdba))
* **claude-dev-env:** BDD rule, canonical system prompt, and pointer rules ([323df7e](https://github.com/jl-cmd/claude-code-config/commit/323df7eddec5d476b7f9ca6e3c808a1f46dc292d))


### Bug Fixes

* address Copilot PR review (sync script, XML, bdd-protocol) ([f18f860](https://github.com/jl-cmd/claude-code-config/commit/f18f86079f754ee0282d4d88097a80bf2a4e37a3))
* address review feedback from pullrequestreview-4115370513 ([266b5c6](https://github.com/jl-cmd/claude-code-config/commit/266b5c6a33481fa80bec4056ecf395efed959f0a))
* **install:** backup existing CLAUDE.md hub before overwrite ([6cbab98](https://github.com/jl-cmd/claude-code-config/commit/6cbab98fae9741576fee1a7caed797c5efd278d1))
* **scripts:** address Copilot review on sync_to_cursor package ([1c087db](https://github.com/jl-cmd/claude-code-config/commit/1c087dbcd2f5a8d0345109c03198de8292f48943))
* **scripts:** fix banned param name, invalid YAML globs, and stale footer reference ([1d5bf55](https://github.com/jl-cmd/claude-code-config/commit/1d5bf55a7c18e776401040c5b650c18f1c3e7edb))
* **scripts:** fix dry-run mkdir, optional-check, and hardcoded tasklings glob ([99e1450](https://github.com/jl-cmd/claude-code-config/commit/99e1450e07279a5acf679fe1fab8294e962e1882))


### Refactoring

* **scripts:** move constants to config.py or inline per function scope ([b798375](https://github.com/jl-cmd/claude-code-config/commit/b7983753a69f3fc41b81417a12e45650bac0103d))
* **scripts:** split sync-to-cursor into sync_to_cursor package ([fce13fc](https://github.com/jl-cmd/claude-code-config/commit/fce13fcc0370313523215b23b4c2109279045c8e))

## [1.19.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.19.2...claude-dev-env-v1.19.3) (2026-04-15)


### Bug Fixes

* address code review feedback on PR [#100](https://github.com/jl-cmd/claude-code-config/issues/100) ([33d336f](https://github.com/jl-cmd/claude-code-config/commit/33d336fa54814f0a5f0465fc64a6b0aae219288f))


### Documentation

* align with prompt-generator extraction and add issue redirect ([4d0a5ba](https://github.com/jl-cmd/claude-code-config/commit/4d0a5ba78cb504feafebc1e33267abbad4181cbc))

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

### Documentation

* Documentation aligned with extraction: top-level CLAUDE.md, top-level README.md, and the GitHub issue-redirect template now describe @jl-cmd/prompt-generator as the source of the prompt-generator surface.

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
