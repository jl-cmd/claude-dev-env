# Changelog

## [1.82.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.81.0...claude-dev-env-v1.82.0) (2026-07-02)


### Features

* **autoconverge:** surface deferred hardening PRs for self-closing convergence ([6d6fa0d](https://github.com/jl-cmd/claude-code-config/commit/6d6fa0d2d916c8d3b56cc7a05a58b36df647847e))


### Bug Fixes

* **autoconverge:** clarify background-wait clause and full down-result schema ([940dd91](https://github.com/jl-cmd/claude-code-config/commit/940dd91535ba977793da5f0f5670656c809d42e6))
* **autoconverge:** describe the Monitor wait as a bounded until-loop ([66ea29f](https://github.com/jl-cmd/claude-code-config/commit/66ea29f94b3109daa5d8273ea085e9ca639d5ef9))
* **autoconverge:** route polling waits through Monitor tool for headless harness ([2c23f49](https://github.com/jl-cmd/claude-code-config/commit/2c23f497b06218f62ca786ce6bc869cd76c2bb12))
* **autoconverge:** size Monitor timeout_ms to the full poll wait span ([04fa92e](https://github.com/jl-cmd/claude-code-config/commit/04fa92e82d0025c2269bdd4b9cfd954ce283f1e2))

## [1.81.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.80.0...claude-dev-env-v1.81.0) (2026-07-02)


### Features

* **code-rules:** block docstring TYPE_CHECKING gate claim the module's code never runs ([63c0efe](https://github.com/jl-cmd/claude-code-config/commit/63c0efe690c8c7d661ac9ef57573d8acb52641fb))
* **converge:** close Copilot-only review gaps at write, commit, and audit layers ([fea4bb9](https://github.com/jl-cmd/claude-code-config/commit/fea4bb9de6b240e2155f1e7eecd707ee9efc6662))
* **converge:** close Copilot-only review gaps at write, commit, and audit layers ([56d3337](https://github.com/jl-cmd/claude-code-config/commit/56d333797b6950a12a8e56f8ec20e6e790eb389c))


### Bug Fixes

* **autoconverge:** don't reopen hardening PR when issue filing retries ([b646255](https://github.com/jl-cmd/claude-code-config/commit/b646255cc9960af25b049e177dfa74e889792bb7))
* **autoconverge:** make follow-up PR creation idempotent so the Copilot gate stops double-creating PRs ([c4d471d](https://github.com/jl-cmd/claude-code-config/commit/c4d471d5b56605a2866c41d6089a2007389ea82c))
* **autoconverge:** make follow-up PR creation idempotent so the Copilot gate stops double-creating PRs ([236ce2b](https://github.com/jl-cmd/claude-code-config/commit/236ce2bb7b4698728ef17c7a8e0d772ba67ab461))
* **autoconverge:** recognize a clean Copilot COMMENTED review so the gate stops false "down" bypasses ([5cb04ef](https://github.com/jl-cmd/claude-code-config/commit/5cb04ef96d72627e7eb504d65bf62a97a9311c25))
* **autoconverge:** recognize a clean Copilot COMMENTED review so the gate stops false down bypasses ([1f9afd5](https://github.com/jl-cmd/claude-code-config/commit/1f9afd500e17c8c313b11b6c07da7f76042ae238))
* **autoconverge:** resolve reuse-path standards threads against the filed issue ([7c7f332](https://github.com/jl-cmd/claude-code-config/commit/7c7f332c42187de1077bb07609c48d20f0d01c7d))
* **autoconverge:** retry standards follow-up filing after a transient failure ([438dfbf](https://github.com/jl-cmd/claude-code-config/commit/438dfbfcfbdb8cb15f828173619098386abbc196))


### Documentation

* **autoconverge:** restate Copilot poll count as the configured cap ([71c18e8](https://github.com/jl-cmd/claude-code-config/commit/71c18e89c5521f695047acd43a1fe6a52d12d05e))
* **autoconverge:** restate Copilot poll count as the configured cap ([9b6b268](https://github.com/jl-cmd/claude-code-config/commit/9b6b2681ef2da85a882f0bfda6094b2379899365))
* **autoconverge:** unify Copilot poll limit on "configured cap" ([72f5deb](https://github.com/jl-cmd/claude-code-config/commit/72f5deb87bbdfe415a08114498126b54af602f24))
* **autoconverge:** unify Copilot poll limit terminology on "configured cap" ([94a41b7](https://github.com/jl-cmd/claude-code-config/commit/94a41b783248712e7222fdb8c0663c2df60761ca))

## [1.80.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.79.0...claude-dev-env-v1.80.0) (2026-07-01)


### Features

* **code-rules:** block dead top-level runtime imports in TYPE_CHECKING-gated and workflow-registry files ([b1363cc](https://github.com/jl-cmd/claude-code-config/commit/b1363ccdb7fb97c18b23c3f6cf84b0cb97609cbc))
* **copilot-quota:** pre-check Copilot quota before the converge workflows ([91df044](https://github.com/jl-cmd/claude-code-config/commit/91df04408363d20a2815f57f43d220114576cf7d))
* **copilot-quota:** pre-check Copilot quota before the converge workflows ([d09d3a2](https://github.com/jl-cmd/claude-code-config/commit/d09d3a2bc78d43c652b10ea366939a68e8c97418))
* **hooks:** block JS [@returns](https://github.com/returns) object contradicted by a schema-less branch ([eea479c](https://github.com/jl-cmd/claude-code-config/commit/eea479c400650fe45792b9d284aebacb100578f7))
* **hooks:** block JS [@returns](https://github.com/returns) object contradicted by a schema-less branch ([28668e8](https://github.com/jl-cmd/claude-code-config/commit/28668e8edf2e406e791f5d5d4f50cdf11b0dee88))


### Bug Fixes

* **autoconverge:** remove inert workflow-resume machinery from converge.mjs ([c761409](https://github.com/jl-cmd/claude-code-config/commit/c76140911317212cb4d004aef4185896faac0f91))
* **autoconverge:** remove inert workflow-resume machinery from converge.mjs ([80e277a](https://github.com/jl-cmd/claude-code-config/commit/80e277abe1deff86fdcf6e9ae6fe7eee589a2a4d))
* forward copilotDisabled to converge child runs and align quota wording ([3cbc07f](https://github.com/jl-cmd/claude-code-config/commit/3cbc07f703aea683f98244139a712f18a5462152))
* **hooks:** align converge.mjs [@returns](https://github.com/returns) with schema-less resume branches ([80d0c71](https://github.com/jl-cmd/claude-code-config/commit/80d0c71ccbf8682f7d3b1dbb21d505139608f3a1))
* **hooks:** handle destructured params in JS returns-object schemaless check ([2863853](https://github.com/jl-cmd/claude-code-config/commit/28638535a11b197ae7ede7d5d97791593aaf738c))

## [1.79.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.78.0...claude-dev-env-v1.79.0) (2026-06-29)


### Features

* **hooks:** block boolean polarity name contradictions at Write/Edit time ([98385be](https://github.com/jl-cmd/claude-code-config/commit/98385bef49decf4805f36db2bd69e11036d4b799))
* **hooks:** block dataclass field run-mode vs per-record drift at Write/Edit time ([47a4d43](https://github.com/jl-cmd/claude-code-config/commit/47a4d43e2b066caff439dc55826fb9310e1593cd))
* **hooks:** block documented-but-unreferenced parameter at Write/Edit time ([50e2fa5](https://github.com/jl-cmd/claude-code-config/commit/50e2fa5a8620f4ccc8147884872f9b4dc6bb2ba7))
* **hooks:** block env-var table/code drift at Write/Edit time ([9a0aa5d](https://github.com/jl-cmd/claude-code-config/commit/9a0aa5d048eaeb046e58ad8b1b44abc2ad47687d))
* **hooks:** block module-docstring data-schema scope drift at Write/Edit time ([bd7a3f4](https://github.com/jl-cmd/claude-code-config/commit/bd7a3f4dce6799e5ab954fa08765f9303bd8ebc7))
* **hooks:** block vacuous cleanup-on-failure tests at Write/Edit time ([f6edba9](https://github.com/jl-cmd/claude-code-config/commit/f6edba94f2785f6dbaa2e458ed218bb05245d067))
* **hooks:** gate docstring length-constant superlative drift at Write/Edit time ([16efa97](https://github.com/jl-cmd/claude-code-config/commit/16efa97735c41d3abd3110e6a2db307a7d0f4a31))
* **hooks:** harden package-inventory stale-entry gate for SKILL.md inventories ([10bfe78](https://github.com/jl-cmd/claude-code-config/commit/10bfe78d9f47679aa842998aa9575f4e118cdd04))
* **hooks:** harden paired-test coverage gate for private-only suites ([f50911f](https://github.com/jl-cmd/claude-code-config/commit/f50911fe18f19f4e57be013a54a3c276a92f0d5e))
* **paired-test-coverage:** block dead public function on the test-file write order ([604d6a8](https://github.com/jl-cmd/claude-code-config/commit/604d6a8bbd88521781993ad23361f9a85c742eb4))


### Bug Fixes

* address converge-round findings for dead-public-function gate ([1856687](https://github.com/jl-cmd/claude-code-config/commit/1856687d45a593096f2f0b6bcbc6d9b3efeabe62))
* address converge-round findings for docstring length-constant superlative gate ([3755686](https://github.com/jl-cmd/claude-code-config/commit/375568631874b101ed4958f375c9b15ecc3686ef))
* **hooks:** block docstring no-network claim contradicted by path-metadata access ([d0606ae](https://github.com/jl-cmd/claude-code-config/commit/d0606ae81beaac84b1af4653e9fb2887611021c9))
* **hooks:** resolve reuse-pass findings in code_rules_naming_collection ([f3acc9f](https://github.com/jl-cmd/claude-code-config/commit/f3acc9f2251faeab789a7fd5adca2e908eaa30ec))
* **package-inventory:** address converge-round review findings ([cbf6e10](https://github.com/jl-cmd/claude-code-config/commit/cbf6e101c3776523a62d4554ae47708d2d18ac23))
* **paired-test-coverage:** apply converge-round review fixes ([f9d9417](https://github.com/jl-cmd/claude-code-config/commit/f9d94178208de675d98fc11ab90f617762589683))

## [1.78.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.77.0...claude-dev-env-v1.78.0) (2026-06-27)


### Features

* **code-rules:** block dead __all__-exported constants at write time ([8f4e969](https://github.com/jl-cmd/claude-code-config/commit/8f4e969e6760e3ebf989bca10cf06a186bc13d81))
* **code-rules:** block deferred code-standard classes at write time ([3f8532a](https://github.com/jl-cmd/claude-code-config/commit/3f8532a1d433a25f1e8ea195c0d9f98807c73c01))
* **code-rules:** block public functions missing a paired behavioral test ([a84bd70](https://github.com/jl-cmd/claude-code-config/commit/a84bd7051de98be40229c601c933209b0d2155dc))
* **code-rules:** block punctuation-mark glyph-enumeration docstring drift at write time ([fde3df4](https://github.com/jl-cmd/claude-code-config/commit/fde3df493b5285eff2f5c75e687ca3c2fd4c981a))
* **code-rules:** block unraisable LargeZipFile Raises clause at write time ([62dc36f](https://github.com/jl-cmd/claude-code-config/commit/62dc36f1cf1b80cba89e058e056f20ae91885db2))
* **code-rules:** widen dead-module-constant scan to resist same-name collisions ([15a81cb](https://github.com/jl-cmd/claude-code-config/commit/15a81cbfa77786ac8998e61c1ae6ff062cb6bf1d))


### Bug Fixes

* address converge-round findings on dead split branch hook ([e8e4dbb](https://github.com/jl-cmd/claude-code-config/commit/e8e4dbbf432c34f03184a05fd4e1939c0a85b48e))
* address converge-round review findings ([f33df66](https://github.com/jl-cmd/claude-code-config/commit/f33df668fffc1093aae5e93daaa83b47bbcba5f7))
* **hooks:** resolve convergence gate HEAD against the gh pr ready worktree ([6445a96](https://github.com/jl-cmd/claude-code-config/commit/6445a96e0cf54e8f4ff34fdad7eaf6189099fb60))
* **hooks:** resolve convergence gate HEAD against the gh pr ready worktree ([d30c0b1](https://github.com/jl-cmd/claude-code-config/commit/d30c0b1dd6b70eeb83d7996df8db654fe42bac6c))

## [1.77.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.76.0...claude-dev-env-v1.77.0) (2026-06-26)


### Features

* add cardinal-count docstring-drift gate to block it at write time ([15e9367](https://github.com/jl-cmd/claude-code-config/commit/15e9367eadd30d421ecee8917c37a3b25a872bd2))
* **code-rules:** flag run-on docstring sentences in narrative prose ([51a3eac](https://github.com/jl-cmd/claude-code-config/commit/51a3eacffd3ab56cfe01cf4a69476761519ed4b2))
* **code-rules:** flag run-on docstring sentences in narrative prose ([a0dee71](https://github.com/jl-cmd/claude-code-config/commit/a0dee71ff7e34e1957d7efd6a2addf91f8c387d4))
* **hooks:** block Args single-line scope drift over span-intersection body ([6997537](https://github.com/jl-cmd/claude-code-config/commit/69975372b8883017598ad2b98dcf4fdfb075c3c8))


### Bug Fixes

* **hooks:** scope docstring run-on joiner to spaced double-hyphen ([411e3dc](https://github.com/jl-cmd/claude-code-config/commit/411e3dc9156a1ddac52fdbf850c355555ede47b0))


### Documentation

* add plain-illustrative-docstrings rule and Category O9 audit sub-bucket ([e56c4a2](https://github.com/jl-cmd/claude-code-config/commit/e56c4a2b2ce97eb08ebde6d675f370bd05cfd2f5))
* add plain-illustrative-docstrings rule and Category O9 audit sub-bucket ([372902d](https://github.com/jl-cmd/claude-code-config/commit/372902d480d40a28af6faccb5556b1e6f4ce5834))


### Maintenance

* **hooks:** scope PR to the run-on docstring check ([90e8ba7](https://github.com/jl-cmd/claude-code-config/commit/90e8ba76a23eebef36d7e3824743c8a1004f56df))


### Style

* **hooks:** order hook_block_logger import alphabetically ([b2e8e1e](https://github.com/jl-cmd/claude-code-config/commit/b2e8e1e670923ee0582dbbf04b570570f80897d5))

## [1.76.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.75.0...claude-dev-env-v1.76.0) (2026-06-25)


### Features

* **anthropic-plan:** add plan-mode approval gate before packet workflow ([1beab23](https://github.com/jl-cmd/claude-code-config/commit/1beab23e5217e168e65e43a135d7448401378b2a))
* **anthropic-plan:** add plan-mode approval gate before packet workflow ([6f09fb1](https://github.com/jl-cmd/claude-code-config/commit/6f09fb1b1cba3efc363b72c252f75f840bdcc60e))
* flag printf tokens in str.format-logger (automation_logging) messages ([ea5f7b3](https://github.com/jl-cmd/claude-code-config/commit/ea5f7b3df4fee55adc0312950f380b1e98fdcc8f))
* **hooks:** block JS/.mjs spawn-JSDoc resume-task enumeration drift ([334fb4a](https://github.com/jl-cmd/claude-code-config/commit/334fb4a330066c25e2c53cc9dc4c69672308e462))
* **hooks:** block JS/.mjs spawn-JSDoc resume-task enumeration drift ([4e3dce3](https://github.com/jl-cmd/claude-code-config/commit/4e3dce39a42a93c02d5aab2609e33725a1a7a24b))
* **hooks:** block same-file inline duplicate function bodies at Write/Edit ([1068fd1](https://github.com/jl-cmd/claude-code-config/commit/1068fd1157be116343572e3ad109e0abaafddeae))
* **hooks:** block un-sorted import blocks at Write/Edit time (ruff I001) ([bf0fe36](https://github.com/jl-cmd/claude-code-config/commit/bf0fe361da8e692878c2149996d4af56966141b6))
* **hooks:** block un-sorted import blocks at Write/Edit time (ruff I001) ([6f5c193](https://github.com/jl-cmd/claude-code-config/commit/6f5c193f581e631f97b76bd7171f6e6e64a9bd61))
* **hooks:** extend CLAUDE.md orphan blocker to fenced run-command scripts ([44f73ed](https://github.com/jl-cmd/claude-code-config/commit/44f73ed2c2b45c2b657aeb53d2eb8df196818279))
* **hooks:** flag printf tokens in str.format-logger (automation_logging) calls ([17b2531](https://github.com/jl-cmd/claude-code-config/commit/17b25311faead731d9d918ccd552911c5f678158))


### Bug Fixes

* address converge-round findings on verdict recognition and orphan blocker ([e5496d2](https://github.com/jl-cmd/claude-code-config/commit/e5496d2ae99500077472240badd6fe22d1a8cb4c))
* address converge-round findings on verdict store and orphan blocker ([25dcc17](https://github.com/jl-cmd/claude-code-config/commit/25dcc17d1d4421a3a70103143fd8ac7711a48185))
* **autoconverge:** address converge-round findings on claude_md orphan blocker ([fa5d06c](https://github.com/jl-cmd/claude-code-config/commit/fa5d06cc7123c310d180cbfedcb60f2e3f0603b3))
* **autoconverge:** address converge-round findings on claude_md orphan blocker ([6b2dcc8](https://github.com/jl-cmd/claude-code-config/commit/6b2dcc8eae9bcc34ba46d59ae141a6d3a496a1ed))
* **autoconverge:** address review findings on JS resume task enumeration ([ee9f64b](https://github.com/jl-cmd/claude-code-config/commit/ee9f64baff760ba0abd06ee9c99837403198e375))
* **autoconverge:** address review findings on JS resume-task enumeration check ([dafb221](https://github.com/jl-cmd/claude-code-config/commit/dafb221a61d5221b710996ff995203bf3d3ab446))
* **autoconverge:** apply converge-round fixes for claude_md orphan blocker ([88cf807](https://github.com/jl-cmd/claude-code-config/commit/88cf807023ab47a0bf898e68a2651fdc20b7bdc2))
* **autoconverge:** apply converge-round fixes for import-sort hardening ([185c904](https://github.com/jl-cmd/claude-code-config/commit/185c9045279582b39dd3f0fb6708c95f77faf90b))
* **autoconverge:** enumerate fix-verify resume phase in verifier docstring ([67227fc](https://github.com/jl-cmd/claude-code-config/commit/67227fc9d661d891e4b47ffec3dd8997bfb0a1de))
* **autoconverge:** harden JS resume-task enumeration check against false negatives ([0122ac8](https://github.com/jl-cmd/claude-code-config/commit/0122ac835f9dd472ae75c9f2304f8b9695564f7b))
* **autoconverge:** isolate the converge fix path verifier from the editor ([b10beae](https://github.com/jl-cmd/claude-code-config/commit/b10beae84cb8b885c44a9b12b7be7ab61d581eb8))
* **claude-md-orphan:** handle trailing comments and avoid regex backtracking ([e022d77](https://github.com/jl-cmd/claude-code-config/commit/e022d775c7fd2645bb6f8c42cde03e8387b1a92f))
* **converge:** restore fresh-context isolation in fix-path verify, remove unused generalId parameter ([e63b354](https://github.com/jl-cmd/claude-code-config/commit/e63b3544c78d66435baaa77e631e6a3f5628992e))
* harden same-file inline duplicate body detection ([3680af7](https://github.com/jl-cmd/claude-code-config/commit/3680af78c717ea5226a3a1ee195c4b1d427c6cdb))
* harden same-file inline duplicate-body span detection ([f095bf2](https://github.com/jl-cmd/claude-code-config/commit/f095bf2a3c0dc33193f0583618653cacc60f6163))
* **hooks:** address converge-round findings on claude_md_orphan_file_blocker ([806b7ae](https://github.com/jl-cmd/claude-code-config/commit/806b7ae383872ce62a221e7345bb17c489e79fbe))
* **hooks:** address converge-round findings on JS resume task enumeration ([76d2de6](https://github.com/jl-cmd/claude-code-config/commit/76d2de6188f5dab2de991a7e14c6fc1a45c60715))
* **hooks:** address review findings in JS resume-task enumeration check ([1e048d4](https://github.com/jl-cmd/claude-code-config/commit/1e048d4f2b6e7e196c2099ee63082a4ae9376eee))
* **hooks:** address review findings on logging printf-token enforcer ([28ca5dc](https://github.com/jl-cmd/claude-code-config/commit/28ca5dca24723f8446832b322a15c1d5e6e12813))
* **hooks:** blank non-code regions before locating JS resume header ([4be7c19](https://github.com/jl-cmd/claude-code-config/commit/4be7c19d897ad9ac9af7509261206ad4c3340c96))
* **hooks:** correct run-command script-valued flag regex in claude_md orphan blocker ([22f0903](https://github.com/jl-cmd/claude-code-config/commit/22f0903d44ae3a119f78ed8e950ab06d4f3b039f))
* **hooks:** count nested statements in same-file duplicate-body guard ([007efa4](https://github.com/jl-cmd/claude-code-config/commit/007efa4f64d80f981c688f06b7721b5d9dd41449))
* **hooks:** harden JS region scanner for keyword-position regex and template-literal functions ([7545277](https://github.com/jl-cmd/claude-code-config/commit/75452771097e86ab863b5f42c754b6f420714954))
* **verdict:** recognize code-verifier from transcript when sidecar absent ([3d2ef56](https://github.com/jl-cmd/claude-code-config/commit/3d2ef564c16455adb63d1ee68301bbb28766cf25))
* **verdict:** recognize code-verifier from transcript when sidecar absent ([52659f2](https://github.com/jl-cmd/claude-code-config/commit/52659f2d7f8fda7d50f1d8e8a8a8521c84626d8c)), closes [#668](https://github.com/jl-cmd/claude-code-config/issues/668)


### Documentation

* **rules:** harden package-inventory scope-sentence drift at Write time ([78fdd21](https://github.com/jl-cmd/claude-code-config/commit/78fdd219f935ea71c03c547177ab05b3038c7567))


### Tests

* classify flag-gated advisory and allowlist illustrative docstring path ([59f9a0a](https://github.com/jl-cmd/claude-code-config/commit/59f9a0af95c988849d18c0d50d6137e0a002b205))

## [1.75.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.74.0...claude-dev-env-v1.75.0) (2026-06-24)


### Features

* **autoconverge:** consolidate non-clean-room agent spawns into 6 persistent groups ([899db40](https://github.com/jl-cmd/claude-code-config/commit/899db40606e0b9e81754092a3aa809419ea8fe3b))
* **autoconverge:** consolidate non-clean-room agent spawns into 6 persistent groups ([5e20638](https://github.com/jl-cmd/claude-code-config/commit/5e20638eabc1c976b8b03ceb92f6d05ee67c164b))
* **hooks:** block duplicate Windows rmtree helper trio at Write/Edit time ([26ca03c](https://github.com/jl-cmd/claude-code-config/commit/26ca03cc0c48fa74ea11e919edc38a5ed29b731c))


### Bug Fixes

* **autoconverge:** apply converge-round review fixes ([8048c76](https://github.com/jl-cmd/claude-code-config/commit/8048c7634321c19ae5e669ac0c823152c7ea7e7c))
* **autoconverge:** define label in resumeConvergenceCheckAgent ([d639d04](https://github.com/jl-cmd/claude-code-config/commit/d639d04cce77c87cf3069e90141e6ebeed7d7f9e))
* **rmtree-blocker:** mask triple-quoted strings and exempt by basename ([c6d60e7](https://github.com/jl-cmd/claude-code-config/commit/c6d60e7d31a9bf9d30ee43b0d215423480b74bd0))


### Refactoring

* **autoconverge:** close deferred code-standard items [#577](https://github.com/jl-cmd/claude-code-config/issues/577) [#610](https://github.com/jl-cmd/claude-code-config/issues/610) [#612](https://github.com/jl-cmd/claude-code-config/issues/612) [#615](https://github.com/jl-cmd/claude-code-config/issues/615) [#744](https://github.com/jl-cmd/claude-code-config/issues/744) ([317e671](https://github.com/jl-cmd/claude-code-config/commit/317e671ad564c76bfc04ee360c85a66d7d455904))
* **autoconverge:** close deferred code-standard items [#577](https://github.com/jl-cmd/claude-code-config/issues/577) [#610](https://github.com/jl-cmd/claude-code-config/issues/610) [#612](https://github.com/jl-cmd/claude-code-config/issues/612) [#615](https://github.com/jl-cmd/claude-code-config/issues/615) [#744](https://github.com/jl-cmd/claude-code-config/issues/744) ([8b5ca00](https://github.com/jl-cmd/claude-code-config/commit/8b5ca00a450f1412cb735a01bd476c41fc02787c))
* **hooks:** close deferred code-standard items [#579](https://github.com/jl-cmd/claude-code-config/issues/579) [#580](https://github.com/jl-cmd/claude-code-config/issues/580) [#623](https://github.com/jl-cmd/claude-code-config/issues/623) [#719](https://github.com/jl-cmd/claude-code-config/issues/719) [#725](https://github.com/jl-cmd/claude-code-config/issues/725) [#731](https://github.com/jl-cmd/claude-code-config/issues/731) [#742](https://github.com/jl-cmd/claude-code-config/issues/742) ([deeee6a](https://github.com/jl-cmd/claude-code-config/commit/deeee6ae128f672444f6cc6a7a2f50c31c4ec15b))
* **hooks:** close deferred code-standard items [#579](https://github.com/jl-cmd/claude-code-config/issues/579) [#580](https://github.com/jl-cmd/claude-code-config/issues/580) [#623](https://github.com/jl-cmd/claude-code-config/issues/623) [#719](https://github.com/jl-cmd/claude-code-config/issues/719) [#725](https://github.com/jl-cmd/claude-code-config/issues/725) [#731](https://github.com/jl-cmd/claude-code-config/issues/731) [#742](https://github.com/jl-cmd/claude-code-config/issues/742) ([41cd44e](https://github.com/jl-cmd/claude-code-config/commit/41cd44e6d19fc83b0c13a67d4c62b6f5e872b89a))

## [1.74.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.73.0...claude-dev-env-v1.74.0) (2026-06-22)


### Features

* gate docstring guard-drift violation classes at Write/Edit time ([dbd44b3](https://github.com/jl-cmd/claude-code-config/commit/dbd44b34ab1323e1c09e5bcb980589473cd7bd30))
* **hooks:** add hook-block logger and instrument all 37 blocking hooks ([21761bb](https://github.com/jl-cmd/claude-code-config/commit/21761bb43f806c55d250d04d0f3f9bbbe24ed8ab))
* **hooks:** block desk-side SendUserFile attaches, require local open ([4dd3aa6](https://github.com/jl-cmd/claude-code-config/commit/4dd3aa6006aff8b6d692123b69c5ac9d79fac8c4))
* **hooks:** block stale package-inventory CLAUDE.md entries at write time ([a7c12b0](https://github.com/jl-cmd/claude-code-config/commit/a7c12b0a48de2b8a5fe3ff27e87bfc78b074926b))
* **hooks:** gate O6 Returns-clause plural-cardinality docstring drift ([58215d9](https://github.com/jl-cmd/claude-code-config/commit/58215d9e32f9785f67ae20b4f80e406bfbdc22c5))
* **hooks:** gate stale gate-validator count in docstring-prose rule ([8c618aa](https://github.com/jl-cmd/claude-code-config/commit/8c618aac37fb76e7cc81bd1cea578d878fc3c74e))


### Bug Fixes

* address converge-round findings for package-inventory-stale blocker ([8ffef73](https://github.com/jl-cmd/claude-code-config/commit/8ffef736f37495930cc96f263d1057ef3c8ffe4d))
* address converge-round review findings on package inventory blocker ([4b07f5f](https://github.com/jl-cmd/claude-code-config/commit/4b07f5f6e131b4bb69757bbf4cb2cea6b6bef472))
* address reuse-pass review findings on package inventory blocker ([7c39661](https://github.com/jl-cmd/claude-code-config/commit/7c396614d139e99cfd042f95e2224009b3a81ee1))
* **docstring-gate:** guard gate-count drift on count-clause order ([bb881a3](https://github.com/jl-cmd/claude-code-config/commit/bb881a32ab84d80cefb59ccf844df8e4e4e4a0f8))
* **hooks:** address review findings in docstring guard-drift check ([dcd0315](https://github.com/jl-cmd/claude-code-config/commit/dcd03155a9639d0677b976e76fdaef3680be8ee7))
* **hooks:** clarify exempt-directory wording and ground inventory tests ([ccf2f38](https://github.com/jl-cmd/claude-code-config/commit/ccf2f3869b2d29462b1f70fb6f3738f69d47a716))
* **hooks:** drop inline-literal completeness claim from dispatcher constants docstrings ([dc17656](https://github.com/jl-cmd/claude-code-config/commit/dc176566d224d898749d3d8a3c037bdf56339a46))
* **hooks:** log block at payload-build site and guard home resolution ([3b7359c](https://github.com/jl-cmd/claude-code-config/commit/3b7359ca39afd8fed762dd02bc80f6dec38fb901))
* **hooks:** log correct hook event name on block ([9188c1c](https://github.com/jl-cmd/claude-code-config/commit/9188c1cb1f44a9ae3a680e41fb45414eea60a0e6))
* **hooks:** simplify production-file predicate and cover its true branch ([ad1b831](https://github.com/jl-cmd/claude-code-config/commit/ad1b8314818cbccf4b9ec8530159ea59fc22f4a6))
* **hooks:** stop config-shadowing and cross-mount mypy hook crashes ([18c1c71](https://github.com/jl-cmd/claude-code-config/commit/18c1c714e6688931567f0f20fb09626757543714))
* **hooks:** stop config-shadowing and cross-mount mypy hook crashes ([e56b631](https://github.com/jl-cmd/claude-code-config/commit/e56b631210bc4c5bd1b5dc8bacdaa00413d2a814))

## [1.73.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.72.0...claude-dev-env-v1.73.0) (2026-06-21)


### Features

* **autoconverge:** add a multi-PR sub-workflow that converges several PRs in parallel ([3c26687](https://github.com/jl-cmd/claude-code-config/commit/3c26687fe146d5c2139575da42e4f283c3a15ee7))
* **autoconverge:** add a multi-PR sub-workflow that converges several PRs in parallel ([bb5a964](https://github.com/jl-cmd/claude-code-config/commit/bb5a964f485f33f45712fa29447e1be7c65ce162))
* **claude-dev-env:** flag behavior-named tests that mock away their path ([471d537](https://github.com/jl-cmd/claude-code-config/commit/471d5379b74b5b86f327392b010b7128a8c0af0f))
* **hooks:** block deferred dead-config-field violation classes at write time ([a9315bc](https://github.com/jl-cmd/claude-code-config/commit/a9315bcc6d8613f1ff9f3700aa95e988f47c8dc7))
* **hooks:** block docstring claims that no literals appear inline ([433d663](https://github.com/jl-cmd/claude-code-config/commit/433d663de0e4bc90199ce11c896b4b33d2929446))
* **hooks:** block docstring claims that no literals appear inline ([d74de4b](https://github.com/jl-cmd/claude-code-config/commit/d74de4ba1ced6bc3fed7d3c3ca822ce026c6565d))
* **hooks:** block docstring step-enum prose drift at Write/Edit time ([524e1e0](https://github.com/jl-cmd/claude-code-config/commit/524e1e0e1b1619917af526074e1dda09a7cd1d9a))
* **hooks:** block docstring step-enum prose drift at Write/Edit time ([ed0fa83](https://github.com/jl-cmd/claude-code-config/commit/ed0fa83d3e1b31ba00fac48b585ba3f6d0b4fc43))
* **hooks:** block docstrings naming an undefined UPPER_SNAKE constant ([6aa91a1](https://github.com/jl-cmd/claude-code-config/commit/6aa91a178c70512b33f32607ebfa75ed20b92691))
* **hooks:** block docstrings naming an undefined UPPER_SNAKE constant ([9bbdc22](https://github.com/jl-cmd/claude-code-config/commit/9bbdc22e4c46ae800afeb7f1337d50a0d556bd40))
* **hooks:** block test files written outside pytest testpaths at Write/Edit ([280f498](https://github.com/jl-cmd/claude-code-config/commit/280f498c452addc546a37048e1fe3f3abd07cdda))
* **hooks:** gate code-verifier spawn with conflict + CODE_RULES pre-flight ([f16f4eb](https://github.com/jl-cmd/claude-code-config/commit/f16f4eb5413a839ad2f14e39f32be74fa966c5db))
* **hooks:** gate code-verifier spawn with conflict + CODE_RULES pre-flight ([cba8fba](https://github.com/jl-cmd/claude-code-config/commit/cba8fbaee29c782e94374ad3529834a8225bdf46))
* **hooks:** host Write/Edit hooks in Pre/PostToolUse dispatchers ([c47304f](https://github.com/jl-cmd/claude-code-config/commit/c47304f419e0f7bd29587648013f4d4fa355ccb3))
* **hooks:** host Write/Edit hooks in Pre/PostToolUse dispatchers ([a207481](https://github.com/jl-cmd/claude-code-config/commit/a207481bf6172b337201f5be7f1d5da29aed6796))


### Bug Fixes

* **hooks:** address converge-round findings for code-verifier spawn preflight gate ([fe8c941](https://github.com/jl-cmd/claude-code-config/commit/fe8c941dcd237f935a1ec41e073d2b73bc715ec6))
* **hooks:** address converge-round findings for docstring undefined-constant check ([536958a](https://github.com/jl-cmd/claude-code-config/commit/536958ae87a5709943341847c522aab0b9069f57))
* **hooks:** address converge-round findings for pytest testpaths orphan blocker ([cc7a57f](https://github.com/jl-cmd/claude-code-config/commit/cc7a57f5ba40a5733c7954c946e777b2e99358cd))
* **hooks:** address converge-round review findings on dispatcher hooks ([32ea81d](https://github.com/jl-cmd/claude-code-config/commit/32ea81d354035b42c9298af8adbe284c966ce6ed))
* **hooks:** address converge-round review findings on dispatcher hooks ([05fff85](https://github.com/jl-cmd/claude-code-config/commit/05fff85cb3a0c3bfb5207fd16c7e5c01f5755803))
* **hooks:** address converge-round review findings on dispatcher hooks ([3f748d9](https://github.com/jl-cmd/claude-code-config/commit/3f748d914c5f1ee4391c1520f964f1a4f8c89417))
* **hooks:** correct dead-config-field message label and align docstrings for selectors ([ce6605a](https://github.com/jl-cmd/claude-code-config/commit/ce6605a74c4b88f0c1dc689f0b81a8c71c02b68b))
* **hooks:** correct dead-config-field message label and align docstrings for selectors ([6b21d1e](https://github.com/jl-cmd/claude-code-config/commit/6b21d1e9a1a0400225ee8f309da8f22a2baeb4b6))


### Documentation

* **rules:** correct dispatch-coverage docstring exclusion + harden O6 lane ([21908ed](https://github.com/jl-cmd/claude-code-config/commit/21908ed98eb3459a523bfd4f5bcd656689b4c78e))
* **rules:** correct dispatch-coverage docstring exclusion + harden O6 lane ([ede86d1](https://github.com/jl-cmd/claude-code-config/commit/ede86d16e4ece42cd9eaea619f1218ccc0b4f23c))

## [1.72.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.71.0...claude-dev-env-v1.72.0) (2026-06-20)


### Features

* **autoconverge:** add reuse pass and pre-commit gate to fixers ([4f02aed](https://github.com/jl-cmd/claude-code-config/commit/4f02aed96823ba23d06a9f7e3590f8abc88ad400))
* **autoconverge:** add reuse pass and pre-commit gate to fixers ([28927b8](https://github.com/jl-cmd/claude-code-config/commit/28927b8fcb48eca6fa1fe8e7092ebfd2648e2ee2))
* **autoconverge:** rebase merge-conflicting PRs before bug checks ([4d04cfb](https://github.com/jl-cmd/claude-code-config/commit/4d04cfb8280ec94446a9765cbe919fde2722d252))
* **autoconverge:** rebase merge-conflicting PRs before bug checks ([c567050](https://github.com/jl-cmd/claude-code-config/commit/c5670502f7432c0fc031b16343060fdc2a103778))
* **claude-dev-env:** block stale test-name and no-consumer docstring at Write/Edit ([cf06267](https://github.com/jl-cmd/claude-code-config/commit/cf06267a7b43c4b764d83c37b4c5c3052ebc8f9f))
* **claude-dev-env:** size image windows to the asset on "show me" ([3045b2b](https://github.com/jl-cmd/claude-code-config/commit/3045b2b2f2c0c5f3ce21c3506d8a83cc67e32bab))
* **claude-dev-env:** size image windows to the asset on "show me" ([1a7c7b2](https://github.com/jl-cmd/claude-code-config/commit/1a7c7b2e9d970f97d52fe918c7ff7ff38a0b4fab))
* **type-escape:** block object-typed dereferenced parameters at Write/Edit ([ed93f10](https://github.com/jl-cmd/claude-code-config/commit/ed93f104800eec3506de987b56e3b9b336310d6d))


### Bug Fixes

* **code-rules-gate:** exempt test files from check_wrapper_plumb_through ([0c1cbda](https://github.com/jl-cmd/claude-code-config/commit/0c1cbda545ecf0b22b7db77ebaf5ce8df46c1bf7))
* **code-rules-gate:** exempt test files from check_wrapper_plumb_through false positive ([a369da7](https://github.com/jl-cmd/claude-code-config/commit/a369da76e7b31c6f08bca97871f8fdf689b89898))
* **hooks:** address converge-round findings on object-parameter type-escape check ([7bd5fdb](https://github.com/jl-cmd/claude-code-config/commit/7bd5fdbb2f1f8d76d259a4632a238a8485e0cd28))
* **hooks:** address converge-round review findings for object-parameter type-escape gate ([4c0ef02](https://github.com/jl-cmd/claude-code-config/commit/4c0ef02b9b0187954c3e2f3f608e1be3e649a365))
* **hooks:** address converge-round review findings for object-type escape gate ([641d77a](https://github.com/jl-cmd/claude-code-config/commit/641d77a9f3ddc45b536cecb349cf64091f48be09))
* **hooks:** apply converge-round review fixes for object type-escape gate ([282e9b2](https://github.com/jl-cmd/claude-code-config/commit/282e9b2475b6186c2ddaf519a87f33ef4196dda5))

## [1.71.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.70.0...claude-dev-env-v1.71.0) (2026-06-20)


### Features

* **pre-push:** block feature branches landing on protected remote branches ([b8dce67](https://github.com/jl-cmd/claude-code-config/commit/b8dce67bf417872db7f5e0029da28618fec50fe6))
* **pre-push:** block pushing a non-main local branch onto remote main ([b774a3a](https://github.com/jl-cmd/claude-code-config/commit/b774a3ace35d95f78d9fca1f9b9e90931028dda1))


### Documentation

* **audit:** align category-O prose-ordering claim across rubric and rule ([a2f785e](https://github.com/jl-cmd/claude-code-config/commit/a2f785e968d13b4a5f285623e1215aeefe4cfb67))
* **audit:** catch companion-doc ordering/content drift in prose rule ([1af8574](https://github.com/jl-cmd/claude-code-config/commit/1af85746ac971ff1ddd679042105976e641786b0))


### Performance

* **hooks:** skip orphan-file scan when no cells and prune noise dirs ([f50ecad](https://github.com/jl-cmd/claude-code-config/commit/f50ecad4d22e524854b6c3107cbce9dff90ea534))
* **hooks:** skip orphan-walk when no filenames referenced and prune noise directories ([3f031a0](https://github.com/jl-cmd/claude-code-config/commit/3f031a05adcf5c63c29388253fc5e954c15a37dc))

## [1.70.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.69.2...claude-dev-env-v1.70.0) (2026-06-19)


### Features

* **hooks:** block CLAUDE.md table cells naming nonexistent own-area files ([92010e1](https://github.com/jl-cmd/claude-code-config/commit/92010e18ecca8a4220d83e3981a31044f448ecda))


### Bug Fixes

* **autoconverge:** repair mobile report layout, add visual summary ([fbe27d9](https://github.com/jl-cmd/claude-code-config/commit/fbe27d96b4b9bf930b050977b316f58699e638d1))
* **autoconverge:** repair mobile report layout, add visual summary ([590b7d4](https://github.com/jl-cmd/claude-code-config/commit/590b7d497079abd52cb2d42b400ba7c104cf8cff))
* **claude-md-orphan:** edit-aware detection, fenced-row skip, robust scan ([42db2a4](https://github.com/jl-cmd/claude-code-config/commit/42db2a4ca436b6c14554eab231ac613ed2716e5b))
* **claude-md-orphan:** scope relative-path exemption to its own section ([90f8f11](https://github.com/jl-cmd/claude-code-config/commit/90f8f1111a557f26c7a618e4124efcd9d55adc62))

## [1.69.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.69.1...claude-dev-env-v1.69.2) (2026-06-19)


### Bug Fixes

* **hooks:** exempt ephemeral temp scripts from Write/Edit gates ([bbb4cf2](https://github.com/jl-cmd/claude-code-config/commit/bbb4cf249fc6e5959f21f8ab66ad8a3338fefcc7))

## [1.69.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.69.0...claude-dev-env-v1.69.1) (2026-06-19)


### Bug Fixes

* **code-rules:** address converge-round findings on dead-config-field check ([e5df152](https://github.com/jl-cmd/claude-code-config/commit/e5df15272665ed055736c592dd49d74d40f90587))
* **code-rules:** apply converge-round fixes to dead-config-field check ([b805a99](https://github.com/jl-cmd/claude-code-config/commit/b805a9966df3608011875be67cb15db06dfb205d))
* **dead-config:** treat *Config constructor keyword as a write, not a read ([1c5b4dd](https://github.com/jl-cmd/claude-code-config/commit/1c5b4dd9eb9ce38917fe68109dfb18fc65f9afb8))

## [1.69.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.68.0...claude-dev-env-v1.69.0) (2026-06-19)


### Features

* **claude-dev-env:** add run-claude-dev-env skill with sandboxed installer driver ([c5ac1d9](https://github.com/jl-cmd/claude-code-config/commit/c5ac1d9ffc0b4b44798514873b7851601420e6aa))
* **claude-dev-env:** add run-claude-dev-env skill with sandboxed installer driver ([b3e7be2](https://github.com/jl-cmd/claude-code-config/commit/b3e7be24669842317bafa8775ea2fb8fca65e1f9))
* **hooks:** block class-method docstring-prose drift at Write/Edit time ([aa39701](https://github.com/jl-cmd/claude-code-config/commit/aa3970178de60338b5126276608b300d27a766c4))
* **hooks:** block class-method docstring-prose drift at Write/Edit time ([efc88d9](https://github.com/jl-cmd/claude-code-config/commit/efc88d9b2cd4c245ecbdf5b7af58da8f8663f6ea))


### Bug Fixes

* **code-rules:** exempt workflow-registry files from file-global-constant check ([e5fbbd5](https://github.com/jl-cmd/claude-code-config/commit/e5fbbd57edb7a17b6dd550a926dda1ab87cb4bac))
* **code-rules:** exempt workflow-registry files from file-global-constant check ([b1bad63](https://github.com/jl-cmd/claude-code-config/commit/b1bad6318eeed6787dacf3e0e9d5561a618edb73))
* **converge:** address review findings for docstring-prose class-method drift ([5a40e06](https://github.com/jl-cmd/claude-code-config/commit/5a40e06e36e7c9e39c92146627d0e135c6663392))


### Documentation

* add per-directory CLAUDE.md orientation files ([c69fdf8](https://github.com/jl-cmd/claude-code-config/commit/c69fdf864aadc48ead4bb417db6f9a28f297acc1))
* **claude-dev-env:** add file index to run-claude-dev-env skill ([96f83c4](https://github.com/jl-cmd/claude-code-config/commit/96f83c4d6c2557e15d128aa2185998b61d84d6e4))
* **claude-md:** apply converge-round review fixes to per-directory CLAUDE.md files ([a553dfd](https://github.com/jl-cmd/claude-code-config/commit/a553dfd6b28c44f93780d9fbbfeb187695744061))
* **claude-md:** apply converge-round review fixes to per-directory CLAUDE.md files ([f76d78f](https://github.com/jl-cmd/claude-code-config/commit/f76d78f5964da5b8cba8cb856f62f68b4791261a))
* **claude-md:** correct command descriptions and drop phantom file rows ([6d69de5](https://github.com/jl-cmd/claude-code-config/commit/6d69de5f28b84340990b6a4a8d015b56d9f2c93c))
* **packages:** add per-directory CLAUDE.md across the claude-dev-env package ([d12f2f9](https://github.com/jl-cmd/claude-code-config/commit/d12f2f9838271494f1241745551fd83ddc026397))


### Tests

* **hooks:** guard the dead-module-constant gate on the edit-insert path ([0b5a1c4](https://github.com/jl-cmd/claude-code-config/commit/0b5a1c472b9b66aff714b1ea823688acfc73c893))

## [1.68.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.67.2...claude-dev-env-v1.68.0) (2026-06-18)


### Features

* **hooks:** block docstring-prose-vs-impl drift at Write/Edit time ([b892e6a](https://github.com/jl-cmd/claude-code-config/commit/b892e6a08770e11af062debc468b0c03530c0b24))


### Bug Fixes

* **autoconverge:** apply converge-round review fixes ([d355f06](https://github.com/jl-cmd/claude-code-config/commit/d355f0641902ed271a5c149d1424203ced5bbaa4))
* **autoconverge:** re-fix and re-verify when the verify step rejects a fix ([78a1f5f](https://github.com/jl-cmd/claude-code-config/commit/78a1f5fb65405d4f42ec9be5bf34c91aaaf46600))
* **autoconverge:** re-fix and re-verify when the verify step rejects a fix ([08d0879](https://github.com/jl-cmd/claude-code-config/commit/08d0879c75f7860372273b2031e73c5f6304f481))
* **hooks:** address review findings on O6 docstring fallback branch ([df70e79](https://github.com/jl-cmd/claude-code-config/commit/df70e7980e46ce20474508f2f17f4c398684e370))
* **hooks:** harden O6 docstring fallback branch in code_rules_docstrings ([86ac337](https://github.com/jl-cmd/claude-code-config/commit/86ac337a9779f0dcb26f9de2b4992bf7d5408576))

## [1.67.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.67.1...claude-dev-env-v1.67.2) (2026-06-18)


### Bug Fixes

* **anthropic-plan:** harden plan-packet writes against background isolation ([177197a](https://github.com/jl-cmd/claude-code-config/commit/177197a6e89cfeead0cbd58c7e54baee192243dc))
* **anthropic-plan:** harden plan-packet writes against background isolation ([2e2ddd2](https://github.com/jl-cmd/claude-code-config/commit/2e2ddd2d9c3367bcb30b55e147144178258e6800))

## [1.67.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.67.0...claude-dev-env-v1.67.1) (2026-06-18)


### Bug Fixes

* **anthropic-plan:** match whole reuse-audit verdict tokens ([f06f8d3](https://github.com/jl-cmd/claude-code-config/commit/f06f8d30f6ab902dc49e2985168de912b796755e))
* **anthropic-plan:** match whole reuse-audit verdict tokens ([341465f](https://github.com/jl-cmd/claude-code-config/commit/341465f386942650f6a09536829513dd796a2815)), closes [#676](https://github.com/jl-cmd/claude-code-config/issues/676)

## [1.67.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.66.2...claude-dev-env-v1.67.0) (2026-06-18)


### Features

* **plan:** add reuse-audit phase to the plan-packet workflow ([f508002](https://github.com/jl-cmd/claude-code-config/commit/f508002776ec58f894470db4a8fd09ac86de0623))
* **plan:** add reuse-audit phase to the plan-packet workflow ([1269f8e](https://github.com/jl-cmd/claude-code-config/commit/1269f8e4c328f144fff01f462eb3f8931bca3840))
* **plan:** add Visualize phase that builds an offline visual HTML ([0828a73](https://github.com/jl-cmd/claude-code-config/commit/0828a739b0cea9cc60ca3b81bc3ec7ee90ffb9b7))


### Refactoring

* **plan:** make the visual-plan view human-first with edit-recipe steps ([825393d](https://github.com/jl-cmd/claude-code-config/commit/825393d0ef69768dba7367a29fa3cadc3bd7f397))

## [1.66.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.66.1...claude-dev-env-v1.66.2) (2026-06-18)


### Bug Fixes

* **anthropic-plan:** fold repair-path recovery into top-level signal ([dc5c7f4](https://github.com/jl-cmd/claude-code-config/commit/dc5c7f42b14f9dc5ba74f85cf16ca0a65517a31a))
* **anthropic-plan:** pass launch payload as args and self-heal isolated writes ([6359f5f](https://github.com/jl-cmd/claude-code-config/commit/6359f5f9d4aa0c05708cf96ecc5420d54fae89a3))
* **anthropic-plan:** pass launch payload as args and self-heal isolated writes ([f0e74b7](https://github.com/jl-cmd/claude-code-config/commit/f0e74b73813c61a8f1c90452667b8650bfcd7f12))

## [1.66.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.66.0...claude-dev-env-v1.66.1) (2026-06-18)


### Bug Fixes

* **anthropic-plan:** align plan-packet workflow with runtime contract ([a5b9bd5](https://github.com/jl-cmd/claude-code-config/commit/a5b9bd5a8bdc844def23f2306c83938823b34637))
* **anthropic-plan:** align plan-packet workflow with runtime contract ([77bef2a](https://github.com/jl-cmd/claude-code-config/commit/77bef2a8d54692e67ef13bd591ba23e8d0f87015))

## [1.66.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.65.1...claude-dev-env-v1.66.0) (2026-06-18)


### Features

* **anthropic-plan:** workflow-backed plan packet system ([b0b252e](https://github.com/jl-cmd/claude-code-config/commit/b0b252ed31f3806c6978129a245089b3c20ea179))
* block flag-gated scenario test-naming violations at Write/Edit ([d58bf39](https://github.com/jl-cmd/claude-code-config/commit/d58bf39bfa722e1def5d2545d6f82c5f4d1a5448))


### Bug Fixes

* **anthropic-plan:** address converge-round review findings in validate_packet ([7d4891e](https://github.com/jl-cmd/claude-code-config/commit/7d4891e333fcfed62f598a22d37f67c86bc30cd8))
* **anthropic-plan:** address review findings in validate_packet ([e6c2a8f](https://github.com/jl-cmd/claude-code-config/commit/e6c2a8ffe6ac482e2cee97d24c9c2ae9a6883a54))
* **anthropic-plan:** harden packet path match and source-table detection ([71b39ea](https://github.com/jl-cmd/claude-code-config/commit/71b39eac2a0bddb23356817c185af44761d3eed2))
* **anthropic-plan:** tighten source-map file-token regex to real extensions ([5b20975](https://github.com/jl-cmd/claude-code-config/commit/5b20975128892b9048e6e866861f33474d333df1))
* **plan-packet:** broaden step detection and plan-path coverage ([31f47f2](https://github.com/jl-cmd/claude-code-config/commit/31f47f24118efaddc6a78359115c4946b8745175))

## [1.65.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.65.0...claude-dev-env-v1.65.1) (2026-06-18)


### Bug Fixes

* **autoconverge:** correct recovery cap to 2 and complete FIX_SCHEMA early returns ([dd67abf](https://github.com/jl-cmd/claude-code-config/commit/dd67abf3b99488364dcdfcac3675f2ee71e6b701))
* **autoconverge:** correct recovery cap to 2 and complete FIX_SCHEMA early returns ([7777e33](https://github.com/jl-cmd/claude-code-config/commit/7777e33a2aafea6a0fac2f9f9e3e1d7c43d6c4f5))
* **hooks:** count cross-tree consumers in dead-module-constant scan ([9a81a43](https://github.com/jl-cmd/claude-code-config/commit/9a81a437b870c842983db6d026971b44dea56839))
* **hooks:** count cross-tree consumers in dead-module-constant scan ([d2a8e15](https://github.com/jl-cmd/claude-code-config/commit/d2a8e15788c871682ca3f7c71254897bb916c8ed))
* **hooks:** restore scan cap and single-read widening in dead-module-constant scan ([fd0e059](https://github.com/jl-cmd/claude-code-config/commit/fd0e0590b5de828f24d4f4b2d4b25d9c5fe7ecbd))


### Tests

* **autoconverge:** harden fix-recovery assertions ([1231bca](https://github.com/jl-cmd/claude-code-config/commit/1231bcae6d993cd0ef29b6a222b4288d7836c6f9))

## [1.65.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.64.3...claude-dev-env-v1.65.0) (2026-06-17)


### Features

* **autoconverge:** recover from commit-time hook blocks instead of ending the run ([2af5f55](https://github.com/jl-cmd/claude-code-config/commit/2af5f55ff5ada64adef089c0414a07bbaf03d984))
* **autoconverge:** recover from commit-time hook blocks instead of ending the run ([5828ba9](https://github.com/jl-cmd/claude-code-config/commit/5828ba946a1c6c523e166c88b1839c72b2cf4f06))

## [1.64.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.64.2...claude-dev-env-v1.64.3) (2026-06-17)


### Documentation

* **CLAUDE.md:** drop Zoekt MCP from code-navigation and search guidance ([d3c7cc0](https://github.com/jl-cmd/claude-code-config/commit/d3c7cc0a733b6d23341dc3464bf32b2df16ca0d2))
* **CLAUDE.md:** drop Zoekt MCP from code-navigation and search guidance ([60c31b8](https://github.com/jl-cmd/claude-code-config/commit/60c31b8eb4194238a2c661333320a3863450e156))

## [1.64.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.64.1...claude-dev-env-v1.64.2) (2026-06-17)


### Documentation

* **CLAUDE.md:** add Everything Search MCP tool instructions ([3904dcb](https://github.com/jl-cmd/claude-code-config/commit/3904dcba2c94fb24edc0fb9338bc1232546fcd00))
* **CLAUDE.md:** add Serena code intelligence MCP instructions # verify-skip ([704806a](https://github.com/jl-cmd/claude-code-config/commit/704806a810cf630a3499bc407bd43c8cb4631da4))

## [1.64.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.64.0...claude-dev-env-v1.64.1) (2026-06-17)


### Bug Fixes

* **hooks:** skip dead-field check on module-level singleton dataclasses ([8a5e3b0](https://github.com/jl-cmd/claude-code-config/commit/8a5e3b02636d3f5c0a274284668c56bf19b284ea))
* **hooks:** skip dead-field check on module-level singleton dataclasses ([a047dee](https://github.com/jl-cmd/claude-code-config/commit/a047deec8a0c1f9e947dc57ed323d4df9f86fe00))

## [1.64.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.63.0...claude-dev-env-v1.64.0) (2026-06-17)


### Features

* **code-rules:** block dead argparse CLI arguments at Write/Edit time ([a6bcc1e](https://github.com/jl-cmd/claude-code-config/commit/a6bcc1e864ee650e37dfd8b59bddbdd7a5e350f9))


### Bug Fixes

* **code-rules:** generalize argparse namespace-escape suppression ([c5644e2](https://github.com/jl-cmd/claude-code-config/commit/c5644e290206579e5b808a3e8dd94e3f119725ba))
* **code-rules:** recognize tuple-unpacked and aliased argparse namespaces ([dce2428](https://github.com/jl-cmd/claude-code-config/commit/dce2428d0c3e4d9634dad8b53dca140e427dd6b7))
* **code-rules:** skip argparse argument with a non-literal dest ([e3fce1c](https://github.com/jl-cmd/claude-code-config/commit/e3fce1c2bed7cddc2fd5267cc85a5e22d4b06b15))
* **code-rules:** suppress dead-argparse check for an inline-consumed parse result ([a1f1945](https://github.com/jl-cmd/claude-code-config/commit/a1f1945dd27d7eaa7c8a2cc0afd8f43f62a66da9))
* **code-rules:** suppress dead-argparse false positives for untracked namespaces ([60a7314](https://github.com/jl-cmd/claude-code-config/commit/60a731427dd00f98efba581245df1a74b748d0f4))
* **code-rules:** track annotated argparse namespace bindings ([66ad9c8](https://github.com/jl-cmd/claude-code-config/commit/66ad9c80d0dd9cad8a05b2a8ef6583709906070a))

## [1.63.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.62.1...claude-dev-env-v1.63.0) (2026-06-16)


### Features

* **agents:** add code-advisor agent ([60bf451](https://github.com/jl-cmd/claude-code-config/commit/60bf451d1e04e79f9b96aa898b67b8e123cdf163))
* **agents:** add code-advisor agent to claude-dev-env ([429b954](https://github.com/jl-cmd/claude-code-config/commit/429b954b81e1a63b231c79ef5605006907bcb30d))


### Bug Fixes

* **verified-commit:** accept verdicts cross-worktree via surface hash ([c5464da](https://github.com/jl-cmd/claude-code-config/commit/c5464dadd1f9e69abadca1cec1274fd7a9dfb316))
* **verified-commit:** anchor verdict on surface hash; bring agent + skill into repo ([91bc704](https://github.com/jl-cmd/claude-code-config/commit/91bc7047511774180eeabaf375457eb2f2f65011))
* **verified-commit:** bind verification to the work tree under review ([411a85b](https://github.com/jl-cmd/claude-code-config/commit/411a85b0e25291c474ab92d60497ace53e01cbf0))
* **verified-commit:** bind verification to the work tree under review ([4724bea](https://github.com/jl-cmd/claude-code-config/commit/4724beaf46eb29bee605f47346249d9b664883fa))


### Documentation

* **autoconverge:** note grant-permissions classifier block and PR-branch positioning in pre-flight ([12d1394](https://github.com/jl-cmd/claude-code-config/commit/12d13943a9923379dca893722b12eda3224a620c))
* **autoconverge:** note grant-permissions classifier block and PR-branch positioning in pre-flight ([fea218f](https://github.com/jl-cmd/claude-code-config/commit/fea218f52fb0c3ecf67da165dd8b3cd95b1851fd))

## [1.62.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.62.0...claude-dev-env-v1.62.1) (2026-06-16)


### Documentation

* **pr-converge:** gotcha — named code-verifier never mints a verdict ([0612f8a](https://github.com/jl-cmd/claude-code-config/commit/0612f8a3be642f1d422f41f22b914ccff31f2ee8))
* **pr-converge:** gotcha — named code-verifier never mints a verdict ([9be4f34](https://github.com/jl-cmd/claude-code-config/commit/9be4f34877cad2680a6de9bc994cbd31df448ea0))

## [1.62.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.61.0...claude-dev-env-v1.62.0) (2026-06-16)


### Features

* **hooks:** add cross-module dead config-dataclass field check ([e351abd](https://github.com/jl-cmd/claude-code-config/commit/e351abd4a0f1778b781957c5314c5ebe6e783421))
* **hooks:** add cross-module dead config-dataclass field check ([7351707](https://github.com/jl-cmd/claude-code-config/commit/7351707efd8932e31284352fdf6c33e196a68e68))
* **hooks:** add on-the-fly verify-skip bypass marker to the commit gate ([cea7182](https://github.com/jl-cmd/claude-code-config/commit/cea71822e4f869aa8eae8a8144f633938cc3dc60))
* **hooks:** add on-the-fly verify-skip bypass marker to the commit gate ([4c8504e](https://github.com/jl-cmd/claude-code-config/commit/4c8504ef114cf34854c3621545dc3b7a4cd60f2d))
* **skills:** add /task-build skill with install wiring and task-tracking directive ([f0dfbf2](https://github.com/jl-cmd/claude-code-config/commit/f0dfbf2a9c40e4418308e0d6d7d06476e6554adb))
* **skills:** add /task-build skill with install wiring and task-tracking directive ([0bec32a](https://github.com/jl-cmd/claude-code-config/commit/0bec32a608747ac6bcf734865acc3294f69f3c77))


### Bug Fixes

* **autoconverge:** define the report appendix CSS selectors ([24e0dc4](https://github.com/jl-cmd/claude-code-config/commit/24e0dc4a235b4100d423e150c7398825f4dd0532))
* **autoconverge:** define the report appendix CSS selectors ([b2e0608](https://github.com/jl-cmd/claude-code-config/commit/b2e0608cb26c35b197416be6794b44d8c6c3974e))
* **hooks:** close dead-config-field false positives for augmented-assignment and dunder reads ([1c7b32c](https://github.com/jl-cmd/claude-code-config/commit/1c7b32c92cb7a3628e184f401ff0278cc5bade3c))
* **hooks:** keep cross-module dead-config check effective by narrowing whole-instance suppression ([c2fe6e7](https://github.com/jl-cmd/claude-code-config/commit/c2fe6e733db40289f6b228a709584ea7c101fc6a))
* **hooks:** stop dead-config-field check from flagging reflectively-consumed fields ([decfb0f](https://github.com/jl-cmd/claude-code-config/commit/decfb0f8d32c2fbfdda3835a978e03d75aca77a8))


### Documentation

* **autoconverge:** flag verified-commit gate stalls; require user sign-off before a verify-skip bypass ([50e7116](https://github.com/jl-cmd/claude-code-config/commit/50e7116c900c83e78a3c98fa1d49c7c133c74f20))
* **doc-gist:** add interactive decision sign-off example to the gallery ([94cff4d](https://github.com/jl-cmd/claude-code-config/commit/94cff4defc3134596e78c0afec24d3f98c0c22ec))
* **doc-gist:** add interactive decision sign-off example to the gallery ([b7709ab](https://github.com/jl-cmd/claude-code-config/commit/b7709abc1909ef6c6594c6f7750b2fef78d8851b))

## [1.61.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.60.0...claude-dev-env-v1.61.0) (2026-06-15)


### Features

* **autoconverge:** let the fix lens self-commit verified production fixes ([96af359](https://github.com/jl-cmd/claude-code-config/commit/96af35960ce495f17d37186cf0e0d6d8599f3192))
* **autoconverge:** let the fix lens self-commit verified production fixes ([0080d2e](https://github.com/jl-cmd/claude-code-config/commit/0080d2e085adf426ae72f81d118494719573d05c))
* **code-rules:** block orphan CSS classes at Write/Edit time ([fc0319b](https://github.com/jl-cmd/claude-code-config/commit/fc0319b781301868f7ed4d2dddb76583d518cb54))
* **code-rules:** block orphan CSS classes at Write/Edit time ([d5a1aa6](https://github.com/jl-cmd/claude-code-config/commit/d5a1aa6a830f0e969e27fb625dba77dfd904cbcd))
* **code-rules:** block unused known pytest fixture parameters at write time ([f2e762a](https://github.com/jl-cmd/claude-code-config/commit/f2e762abe60ead730939910ab412a64ea607ba50))
* **code-rules:** block unused known pytest fixture parameters at write time ([a1ceaf6](https://github.com/jl-cmd/claude-code-config/commit/a1ceaf69ba45661c6f654697170466a6b819f73e))


### Bug Fixes

* **audit-rubrics:** align Category E prompt skeleton with 9 rubric rows ([b2ff6c4](https://github.com/jl-cmd/claude-code-config/commit/b2ff6c4019b3ed827c6aea1861299180baa96c76))
* **audit-rubrics:** align Category E prompt skeleton with 9 rubric rows ([0564c59](https://github.com/jl-cmd/claude-code-config/commit/0564c59004e9dacbe990d8923ff876788096ad57))
* **autoconverge:** drop unused constant and cover render_report behavior ([ea2e467](https://github.com/jl-cmd/claude-code-config/commit/ea2e467e93bfafcd467cffe7fb0c2d49fcdad03e))
* **autoconverge:** make standards-deferral note conditional on hardening PR ([571470c](https://github.com/jl-cmd/claude-code-config/commit/571470c9b4fa3aedd4bf7c01726578d446146827))
* **autoconverge:** make standards-deferral note conditional on hardening PR ([8e1f65b](https://github.com/jl-cmd/claude-code-config/commit/8e1f65b49a3cdba799ff7bce0445bab11563cd60))
* **autoconverge:** route repair and standards-deferral through edit -&gt; verify -&gt; commit ([2f2e8d6](https://github.com/jl-cmd/claude-code-config/commit/2f2e8d649ab38f68f3d5659dad9ac1092e2c6340))
* **autoconverge:** route repair and standards-deferral through edit -&gt; verify -&gt; commit ([70eee29](https://github.com/jl-cmd/claude-code-config/commit/70eee298fe09ae7f2269860780ba30952a65090a))
* **code-rules:** eliminate false positives in unused-fixture check ([2641eac](https://github.com/jl-cmd/claude-code-config/commit/2641eac3542cb91d0e143d8e8c9b8ec5a5d699e9))
* **hooks:** close false-allow holes in the destructive ephemeral-cwd auto-allow gate ([755fb6d](https://github.com/jl-cmd/claude-code-config/commit/755fb6d2d883ab4ba55c1258757f14dbb8ade159))
* **hooks:** close find global-option, multi-exec, and parallel auto-allow escapes ([4d4bf22](https://github.com/jl-cmd/claude-code-config/commit/4d4bf22bd57905ad7deb6742412472b94aba8f00))
* **hooks:** collect the search root after a standalone find -O optimization flag ([c247074](https://github.com/jl-cmd/claude-code-config/commit/c2470749f1b678845578079142b6d6ae1ad9a7c4))
* **hooks:** decline ephemeral auto-allow for find -exec interpreter strings ([8a6962e](https://github.com/jl-cmd/claude-code-config/commit/8a6962e9ee0d54c8e25525ae68ec896859e8e940))
* **hooks:** harden destructive-blocker ephemeral-cwd auto-allow across command shapes ([8dfbac0](https://github.com/jl-cmd/claude-code-config/commit/8dfbac03509bd3fcc522083f4c5ac9113da45e26))
* **hooks:** scope destructive-blocker target check to the rm's own segment ([da83d1b](https://github.com/jl-cmd/claude-code-config/commit/da83d1bbee5a55cc8d05d04c56f41132d2b0b0b7))
* **hooks:** strip grouping chars at the compound-verdict rm-identification site ([4e00999](https://github.com/jl-cmd/claude-code-config/commit/4e00999ba1f755b71a6027195fb9326362ccdfd5))
* **mypy-validator:** honor project [tool.mypy] config when checking files ([1b6f81c](https://github.com/jl-cmd/claude-code-config/commit/1b6f81c8d084a4b1850c4c8398cb14bf7bb7d50d))
* **mypy-validator:** honor project [tool.mypy] config when checking files ([45e1314](https://github.com/jl-cmd/claude-code-config/commit/45e1314fc8c27fc9fa933a8859875f759b74320e))
* **verified-commit:** catch UnicodeDecodeError reading the agent-type sidecar ([d71f2e1](https://github.com/jl-cmd/claude-code-config/commit/d71f2e16a88427a0ca2f3abfff1ff627608a4290))
* **verified-commit:** resolve verifier agent type from its sidecar meta ([7411876](https://github.com/jl-cmd/claude-code-config/commit/7411876c7b494ca76d9e9a6815ff5c77a5b22a27))
* **verified-commit:** resolve verifier agent type from its sidecar meta ([2e95521](https://github.com/jl-cmd/claude-code-config/commit/2e95521a6e5ea66aba584ab83f3970a000f42881))


### Documentation

* **audit-rubrics:** add stale-payload-key probe to Category F sub-bucket F3 ([88ffb00](https://github.com/jl-cmd/claude-code-config/commit/88ffb001e2cea5d7c7f2677a6a22db76f629c009))
* **audit-rubrics:** harden Category F against stale-payload-key reads ([#629](https://github.com/jl-cmd/claude-code-config/issues/629)) ([409346a](https://github.com/jl-cmd/claude-code-config/commit/409346a8e78d6969245704378ce1797ff1c69ca2))
* **claude-md:** note destructive-command literals stall the Bash blocker ([7a38deb](https://github.com/jl-cmd/claude-code-config/commit/7a38deb8420b912347af599529c0c0f57db594e8))
* **claude-md:** note destructive-command literals stall the Bash blocker ([78c612b](https://github.com/jl-cmd/claude-code-config/commit/78c612bd4550a4d6c86a39da1ed588d01120bf18))
* **verified-commit:** enumerate every None path in minter sidecar docstrings ([d18a9cf](https://github.com/jl-cmd/claude-code-config/commit/d18a9cf306fa2e73f24b1ba7829629d3d646642e))


### Refactoring

* **code-rules:** unify fixture collectability and tidy the check ([dc8b3eb](https://github.com/jl-cmd/claude-code-config/commit/dc8b3eb6e5b21a6e655c91e2452dd48a0564d709))


### Tests

* **hooks:** guard code_rules check dispatch so deferred PR [#619](https://github.com/jl-cmd/claude-code-config/issues/619) classes stay blocked ([8efd45b](https://github.com/jl-cmd/claude-code-config/commit/8efd45b714ed5166ab08671513cadc8ff45cb911))
* **hooks:** guard that every code_rules check_* stays dispatched ([6e8d878](https://github.com/jl-cmd/claude-code-config/commit/6e8d878f6149fe96ae560aa1e7d0ec5d4177dc5b))
* **verified-commit:** cover non-object sidecar JSON and assert minted agent id ([a9d6801](https://github.com/jl-cmd/claude-code-config/commit/a9d68016c0fc2cae2e722483b9e1000dbf06199a))

## [1.60.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.59.0...claude-dev-env-v1.60.0) (2026-06-15)


### Features

* **autoconverge:** aggregate run journals and write the closing summary at teardown ([857d2e8](https://github.com/jl-cmd/claude-code-config/commit/857d2e8d826140473f57ece2d8bb7515071eb82e))
* **autoconverge:** LLM-written plain-language summary in the closing report ([1513941](https://github.com/jl-cmd/claude-code-config/commit/15139419394433edff383f3997ba87931f687f08))
* **autoconverge:** LLM-written plain-language summary in the closing report ([2ac6fc8](https://github.com/jl-cmd/claude-code-config/commit/2ac6fc875e5e39961c6d58ec6e1725091caf29d2))
* **code-rules:** block zero-payload function aliases at Write/Edit time ([9696b07](https://github.com/jl-cmd/claude-code-config/commit/9696b07e09082386d0005920e3aa1970f2c2e9ff))
* **code-rules:** surface cross-skill duplicate helpers at Write time ([1db2fe3](https://github.com/jl-cmd/claude-code-config/commit/1db2fe321c3498acf3020f78bedbf268df39cc9a))
* **code-rules:** surface cross-skill duplicate helpers at Write time ([655544f](https://github.com/jl-cmd/claude-code-config/commit/655544f0d1fde4ba1fb54b6ae1c851ae321e9d3e))
* **hooks:** block dead module-level constants in constants modules ([617ac8e](https://github.com/jl-cmd/claude-code-config/commit/617ac8efa45de8e8a595c947f34ffd80017ddc32))
* **hooks:** block dead module-level constants in constants modules at Write/Edit ([b8cde0e](https://github.com/jl-cmd/claude-code-config/commit/b8cde0e400857755401a196097c616d6a9795c9f))
* **hooks:** land verified-commit gate family with spawn-record minter ([acc7c61](https://github.com/jl-cmd/claude-code-config/commit/acc7c61988983f6dd7337794c3d527a6961a5f1c))
* **hooks:** land verified-commit gate family with spawn-record minter ([40db808](https://github.com/jl-cmd/claude-code-config/commit/40db80892406c004e1948de4acb3f45235d196d6))
* **hooks:** remove zoekt content-search redirector and references ([033da68](https://github.com/jl-cmd/claude-code-config/commit/033da687e5d7142c273ee22099b38317657fad9b))
* **hooks:** remove zoekt content-search redirector and references ([b1a1c7c](https://github.com/jl-cmd/claude-code-config/commit/b1a1c7c9825698bdf222be7fde3a8b7ab9bb4e30))
* **pr-loop:** add cwd/worktree preflight guard for convergence skills ([c025739](https://github.com/jl-cmd/claude-code-config/commit/c02573915d980b422ac7a70160d89babd572d037))


### Bug Fixes

* **autoconverge:** harden closing-report render against malformed LLM summaries ([91764ea](https://github.com/jl-cmd/claude-code-config/commit/91764ea40f8431a7569ed5083f02dc6be9d4d111))
* **autoconverge:** surface a blocker when the CLEAN-audit post is denied ([7bf854d](https://github.com/jl-cmd/claude-code-config/commit/7bf854d63ae7f55cd20a749b177020531de32dab))
* **autoconverge:** surface a blocker when the CLEAN-audit post is denied ([53a0669](https://github.com/jl-cmd/claude-code-config/commit/53a0669dead8cb62c36005da5558cd6c5fc9ff3d))
* **code-rules:** exclude decorated and default-adding forwarders from the zero-payload alias check ([b07edcf](https://github.com/jl-cmd/claude-code-config/commit/b07edcf9db70e7b126bdec6dea7a3dea48070db6))
* **code-rules:** exempt string-dispatched and target-incompatible zero-payload aliases, run the check at the hook Write/Edit boundary ([1f34253](https://github.com/jl-cmd/claude-code-config/commit/1f34253ec71430411cdc68f61dd60adaa5b6a580))


### Documentation

* **audit-rubrics:** catch dead constants-exports and Returns tool-claim drift ([#612](https://github.com/jl-cmd/claude-code-config/issues/612)) ([c53ebc8](https://github.com/jl-cmd/claude-code-config/commit/c53ebc82507bb40ffe6fd22f01567c7d6ae5467a))
* **audit-rubrics:** harden against deferred [#604](https://github.com/jl-cmd/claude-code-config/issues/604) code-standard classes ([fa857f9](https://github.com/jl-cmd/claude-code-config/commit/fa857f9dbe1b953891830354a82b1f50a236541f))
* **pr-converge:** qualify same_repo exit-code claim in per-tick ([405a760](https://github.com/jl-cmd/claude-code-config/commit/405a7601162e5a303eca97adad2640f64d345c91))

## [1.59.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.58.0...claude-dev-env-v1.59.0) (2026-06-14)


### Features

* **autoconverge:** handle Copilot out-of-usage quota exhaustion as a gate bypass ([#587](https://github.com/jl-cmd/claude-code-config/issues/587)) ([fd0fe0f](https://github.com/jl-cmd/claude-code-config/commit/fd0fe0f4d1a33582ef00b2c277a951fa3f71c3a2))
* **autoconverge:** proceed to ready when Copilot is down or out of quota ([#599](https://github.com/jl-cmd/claude-code-config/issues/599)) ([464954a](https://github.com/jl-cmd/claude-code-config/commit/464954ac327dce20774aaaa7648ec7ed02c151aa))
* **code-rules:** block cross-file duplicate function bodies at Write time ([#586](https://github.com/jl-cmd/claude-code-config/issues/586)) ([56b52cd](https://github.com/jl-cmd/claude-code-config/commit/56b52cd5064abe3892660725cc41e22163755674))
* **code-rules:** block unannotated pytest builtin fixtures in test files ([#588](https://github.com/jl-cmd/claude-code-config/issues/588)) ([dfda584](https://github.com/jl-cmd/claude-code-config/commit/dfda5849baa799c85c433f23c8784b9d579d1840))
* **destructive-blocker:** auto-allow ephemeral rm chains and quoted rm mentions ([#581](https://github.com/jl-cmd/claude-code-config/issues/581)) ([fbe883c](https://github.com/jl-cmd/claude-code-config/commit/fbe883ced6034dd4075798cbf4535427a78bf7fc))
* **hooks:** block bare per-iteration index tokens in .workflow.js templates ([#595](https://github.com/jl-cmd/claude-code-config/issues/595)) ([ca66231](https://github.com/jl-cmd/claude-code-config/commit/ca66231ed248912c8a0735672c6a8b9b05f7d6d3))
* **hooks:** block dead dataclass fields at Write/Edit time ([#578](https://github.com/jl-cmd/claude-code-config/issues/578)) ([e3b05f2](https://github.com/jl-cmd/claude-code-config/commit/e3b05f2d7eaa3eeb38ec0ffe66565bc16c11fcac))
* **hooks:** gate named subprocess-budget helpers that omit a reachable timeout ([#576](https://github.com/jl-cmd/claude-code-config/issues/576)) ([eb3ddf3](https://github.com/jl-cmd/claude-code-config/commit/eb3ddf342b011e1eef4d2994baf18fa211579b4b))
* keep destructive-command literals out of Bash commands in headless runs ([#603](https://github.com/jl-cmd/claude-code-config/issues/603)) ([500b66e](https://github.com/jl-cmd/claude-code-config/commit/500b66eda027524abea7cda2f3f0916841caccdc))
* **update:** offer a confirmed checkout switch so the fast-forward lands on disk ([#605](https://github.com/jl-cmd/claude-code-config/issues/605)) ([ad51725](https://github.com/jl-cmd/claude-code-config/commit/ad5172587746575c579673a1bc3d92383fe1d191))


### Bug Fixes

* **hooks:** block hook prose that overstates its path-shape detector ([#602](https://github.com/jl-cmd/claude-code-config/issues/602)) ([7df3c74](https://github.com/jl-cmd/claude-code-config/commit/7df3c74cd9d3e4cdc8f9266182db8d063e55d610))
* **hooks:** block magic-number slice bounds in code_rules_magic_values ([#584](https://github.com/jl-cmd/claude-code-config/issues/584)) ([e5533e9](https://github.com/jl-cmd/claude-code-config/commit/e5533e9f2414f14b1fd629d25fc1c5e408796ec0))
* **install:** bake resolved interpreter abspath on Windows ([#600](https://github.com/jl-cmd/claude-code-config/issues/600)) ([a505f54](https://github.com/jl-cmd/claude-code-config/commit/a505f543fca3f3ac40ffb40202a52f9098148502))


### Documentation

* **claude-dev-env:** rename verifier/advisor agents to code-verifier/code-advisor ([#592](https://github.com/jl-cmd/claude-code-config/issues/592)) ([5e7ad5a](https://github.com/jl-cmd/claude-code-config/commit/5e7ad5a05c3349716e88ca3a06d3a2bfeb041fd3))
* **claude-dev-env:** unpin coder model in two-phase workflow ([#596](https://github.com/jl-cmd/claude-code-config/issues/596)) ([7797b1d](https://github.com/jl-cmd/claude-code-config/commit/7797b1d3a2a5c803b273b6ad4e2b94e979ce2925))
* **rules:** harden docstring-prose-vs-implementation drift ([#594](https://github.com/jl-cmd/claude-code-config/issues/594)) ([6b97271](https://github.com/jl-cmd/claude-code-config/commit/6b97271dac48ec7f383e75fed2b073efd4f7e0ff))

## [1.58.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.57.2...claude-dev-env-v1.58.0) (2026-06-13)


### Features

* **auto-formatter:** ruff check --fix on new Python files; drop dead autoconverge HEAD reassignments ([#568](https://github.com/jl-cmd/claude-code-config/issues/568)) ([8192017](https://github.com/jl-cmd/claude-code-config/commit/8192017f48a9bc6cb4d9a57daf0a5acbe93f867a))
* **autoconverge:** add closing convergence-insights report to skill teardown ([#571](https://github.com/jl-cmd/claude-code-config/issues/571)) ([fb1a2d5](https://github.com/jl-cmd/claude-code-config/commit/fb1a2d53043f0aadfb93b286b74fb379d4a94b4c))
* **claude-dev-env:** long-horizon autonomy rule + two Stop hooks ([#567](https://github.com/jl-cmd/claude-code-config/issues/567)) ([37e1c74](https://github.com/jl-cmd/claude-code-config/commit/37e1c74c3d477136a514675ad8ee7e4e346ca7cf))

## [1.57.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.57.1...claude-dev-env-v1.57.2) (2026-06-13)


### Bug Fixes

* **autoconverge:** stop pinning workflow agents to a model ([#573](https://github.com/jl-cmd/claude-code-config/issues/573)) ([b81dd6b](https://github.com/jl-cmd/claude-code-config/commit/b81dd6b12c0a0f52f9ffb64cffc3858bf330a047))

## [1.57.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.57.0...claude-dev-env-v1.57.1) (2026-06-13)


### Documentation

* **claude-dev-env:** pipeline-systemic edit scope + term disambiguation ([#566](https://github.com/jl-cmd/claude-code-config/issues/566)) ([f2c2ebc](https://github.com/jl-cmd/claude-code-config/commit/f2c2ebc8f397d3f0818f788cf157721cb535f508))


### Maintenance

* **hooks:** disable the md-to-html experiment hooks ([#570](https://github.com/jl-cmd/claude-code-config/issues/570)) ([01040d9](https://github.com/jl-cmd/claude-code-config/commit/01040d933ffa76d99d0ec1473f7e9f99f0a4c378))

## [1.57.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.56.0...claude-dev-env-v1.57.0) (2026-06-13)


### Features

* **autoconverge:** pin workflow agents to Fable 5 and defer standards-only rounds ([#564](https://github.com/jl-cmd/claude-code-config/issues/564)) ([fd6df2f](https://github.com/jl-cmd/claude-code-config/commit/fd6df2f46a6ca24d8efc6515d2eb9778342fdeff))

## [1.56.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.55.2...claude-dev-env-v1.56.0) (2026-06-12)


### Features

* **hooks:** gate git commit on staged CODE_RULES violations via PreToolUse hook ([#560](https://github.com/jl-cmd/claude-code-config/issues/560)) ([1f53083](https://github.com/jl-cmd/claude-code-config/commit/1f530834c3b1bc112fedfee4fa21d45b19afcfda))


### Bug Fixes

* **pr-loop:** render agent-facing paths in POSIX form to stop Git Bash mangling ([#563](https://github.com/jl-cmd/claude-code-config/issues/563)) ([dc63327](https://github.com/jl-cmd/claude-code-config/commit/dc63327fa0e94372f24ddac8c96bb86086644383))


### Documentation

* **claude-dev-env:** codify converge-loop discipline, budget-aware pausing, and sub-agent output validation ([#558](https://github.com/jl-cmd/claude-code-config/issues/558)) ([e8abcd2](https://github.com/jl-cmd/claude-code-config/commit/e8abcd2358a08587596f2159f41af0ae78cce881))

## [1.55.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.55.1...claude-dev-env-v1.55.2) (2026-06-11)


### Bug Fixes

* **hooks:** exempt .claude-* profile directories from the md-to-html blocker ([#557](https://github.com/jl-cmd/claude-code-config/issues/557)) ([e765d3d](https://github.com/jl-cmd/claude-code-config/commit/e765d3dcfb2eb1b95730ea1c052c8443fe84505c))


### Documentation

* **claude-dev-env:** codify the coders + Fable-verifier workflow for code tasks ([#552](https://github.com/jl-cmd/claude-code-config/issues/552)) ([b075fb1](https://github.com/jl-cmd/claude-code-config/commit/b075fb1409e1c7fec9039f57c0ce601454c39303))

## [1.55.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.55.0...claude-dev-env-v1.55.1) (2026-06-10)


### Documentation

* **update-skill:** report checked-out branch and dirty tracked files after the ref move ([#554](https://github.com/jl-cmd/claude-code-config/issues/554)) ([87f5069](https://github.com/jl-cmd/claude-code-config/commit/87f5069da428c366875b2cfcd621b4a38e7f24e5))

## [1.55.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.54.0...claude-dev-env-v1.55.0) (2026-06-10)


### Features

* **clean-coder:** unpin model from agent and fix spawns ([#550](https://github.com/jl-cmd/claude-code-config/issues/550)) ([b6198d3](https://github.com/jl-cmd/claude-code-config/commit/b6198d3d53f28e76d7dc47ab8771eb2aa206df60))

## [1.54.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.53.0...claude-dev-env-v1.54.0) (2026-06-09)


### Features

* **clean-coder:** pin agent and fix spawns to fable model ([#548](https://github.com/jl-cmd/claude-code-config/issues/548)) ([8cd806c](https://github.com/jl-cmd/claude-code-config/commit/8cd806cfdcc855350eb544dc3bbaa1b04aea6386))

## [1.53.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.52.1...claude-dev-env-v1.53.0) (2026-06-09)


### Features

* **autoconverge:** single-pass PR convergence workflow ([#543](https://github.com/jl-cmd/claude-code-config/issues/543)) ([4afd80a](https://github.com/jl-cmd/claude-code-config/commit/4afd80aacc70b327c6103d446be91aef2a3a2a45))

## [1.52.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.52.0...claude-dev-env-v1.52.1) (2026-06-08)


### Bug Fixes

* **pr-converge:** auto-route cwd into the PR worktree for cross-repo PRs ([#541](https://github.com/jl-cmd/claude-code-config/issues/541)) ([15a5b20](https://github.com/jl-cmd/claude-code-config/commit/15a5b20fd98d624ca17a0ecc23664d67249fc226))

## [1.52.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.51.0...claude-dev-env-v1.52.0) (2026-06-08)


### Features

* **code-rules-enforcer:** add --check CLI pre-check mode and full-file forecast ([#536](https://github.com/jl-cmd/claude-code-config/issues/536)) ([150cfe6](https://github.com/jl-cmd/claude-code-config/commit/150cfe6b0ea0ff796853ef9663e952e062272e5b))
* **tdd-enforcer:** nested test-layout resolution and import-only edit exemption ([#537](https://github.com/jl-cmd/claude-code-config/issues/537)) ([4154b8f](https://github.com/jl-cmd/claude-code-config/commit/4154b8f70e029016d7f268a9d441cb40a17999ad))
* **update:** add /update skill to fast-forward a repo's main from a confirmed remote ([#539](https://github.com/jl-cmd/claude-code-config/issues/539)) ([f8bf49e](https://github.com/jl-cmd/claude-code-config/commit/f8bf49e47f494a5999ce777b5f7c1ed98ca54bfd))


### Bug Fixes

* **hooks:** disable zoekt content-search redirect ([#540](https://github.com/jl-cmd/claude-code-config/issues/540)) ([db2c0f2](https://github.com/jl-cmd/claude-code-config/commit/db2c0f2e2a792fe0898d6d7e396ce0c63944249f))

## [1.51.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.50.4...claude-dev-env-v1.51.0) (2026-06-07)


### Features

* **bugteam:** add audit categories O and P to close Copilot review gaps ([#533](https://github.com/jl-cmd/claude-code-config/issues/533)) ([2444ee1](https://github.com/jl-cmd/claude-code-config/commit/2444ee1530a0bdfa6ad567a66e32c93425dd6f32))


### Bug Fixes

* **bugteam:** self-heal stale local core.hooksPath in preflight ([#529](https://github.com/jl-cmd/claude-code-config/issues/529)) ([b570670](https://github.com/jl-cmd/claude-code-config/commit/b5706702201027c2161f53c8cd9ce2867b528502))


### Refactoring

* **context:** port startup-context instruction trims to canonical repo ([#535](https://github.com/jl-cmd/claude-code-config/issues/535)) ([6f00b67](https://github.com/jl-cmd/claude-code-config/commit/6f00b67edc12f8546eef05409d7aaa43cfe8126e))

## [1.50.4](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.50.3...claude-dev-env-v1.50.4) (2026-06-05)


### Documentation

* **pr-converge:** require full origin/main...HEAD diff for code-review and bugteam rounds ([#528](https://github.com/jl-cmd/claude-code-config/issues/528)) ([7737927](https://github.com/jl-cmd/claude-code-config/commit/77379279197f0edfed7d962f0a9bb6b388fea8ed))

## [1.50.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.50.2...claude-dev-env-v1.50.3) (2026-06-05)


### Bug Fixes

* **pr-loop:** restore A-N audit categories in build_audit_prompt and pin with test ([#526](https://github.com/jl-cmd/claude-code-config/issues/526)) ([2b3f86c](https://github.com/jl-cmd/claude-code-config/commit/2b3f86c84e93852fbf4b30e03aaee24c47df69e7))

## [1.50.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.50.1...claude-dev-env-v1.50.2) (2026-06-04)


### Refactoring

* **hooks:** split code_rules_enforcer into focused check modules ([#521](https://github.com/jl-cmd/claude-code-config/issues/521)) ([72798f5](https://github.com/jl-cmd/claude-code-config/commit/72798f5098633a9b0d77338f89e92df4b11053b2))

## [1.50.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.50.0...claude-dev-env-v1.50.1) (2026-06-04)


### Bug Fixes

* **hooks:** function-length gate measures executable lines, excluding docstrings ([#520](https://github.com/jl-cmd/claude-code-config/issues/520)) ([4c9a42e](https://github.com/jl-cmd/claude-code-config/commit/4c9a42e0bafd035425499ea8bc4babe447ad4e86))


### Refactoring

* **hooks:** split pr_description_enforcer into focused modules ([#522](https://github.com/jl-cmd/claude-code-config/issues/522)) ([65269c3](https://github.com/jl-cmd/claude-code-config/commit/65269c32f3631928a478ad7fe23226e8604334b9))
* **hooks:** split test_md_to_html_blocker into focused suites ([#523](https://github.com/jl-cmd/claude-code-config/issues/523)) ([70adb94](https://github.com/jl-cmd/claude-code-config/commit/70adb9452ed88462200674900e73e969fa3f2cf3))

## [1.50.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.49.1...claude-dev-env-v1.50.0) (2026-06-03)


### Features

* **code-rules:** enforce bool-param naming, must-check returns, and docstring Args drift at write time ([#517](https://github.com/jl-cmd/claude-code-config/issues/517)) ([93d5604](https://github.com/jl-cmd/claude-code-config/commit/93d5604115938626c64110015c9a5b309c1761ba))


### Bug Fixes

* **md-to-html-blocker:** exempt root CLAUDE.md and AGENTS.md ([#516](https://github.com/jl-cmd/claude-code-config/issues/516)) ([a410de6](https://github.com/jl-cmd/claude-code-config/commit/a410de6f744887075c008e2d354bcf7a2c192a4c))


### Documentation

* **audit-rubrics:** extend Category A to full-contract and doc-claim verification ([#519](https://github.com/jl-cmd/claude-code-config/issues/519)) ([ab132bf](https://github.com/jl-cmd/claude-code-config/commit/ab132bf4c72fa6124ed8cd4b88f252b621787b97))

## [1.49.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.49.0...claude-dev-env-v1.49.1) (2026-05-29)


### Bug Fixes

* **claude-dev-env:** bugteam teardown path + docs, and ship audit-rubrics in npm package ([#512](https://github.com/jl-cmd/claude-code-config/issues/512)) ([c256c04](https://github.com/jl-cmd/claude-code-config/commit/c256c048c37727d6c48d32f4fd31491ec91b7994))

## [1.49.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.48.0...claude-dev-env-v1.49.0) (2026-05-29)


### Features

* **hooks:** block complex words from the plainlanguage.gov list ([#508](https://github.com/jl-cmd/claude-code-config/issues/508)) ([b12f6a6](https://github.com/jl-cmd/claude-code-config/commit/b12f6a6085b2aaf0661980b1bb6cb53cce032ff5))


### Bug Fixes

* **hooks:** exempt code, quotes, and tables from the vague-language scan ([#509](https://github.com/jl-cmd/claude-code-config/issues/509)) ([6a609c0](https://github.com/jl-cmd/claude-code-config/commit/6a609c0a536133ed9f0991ed2b7f99e66a56820a))

## [1.48.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.47.0...claude-dev-env-v1.48.0) (2026-05-29)


### Features

* **pr-converge:** insert code-review layer between bugbot and bugteam ([#505](https://github.com/jl-cmd/claude-code-config/issues/505)) ([e06d2bf](https://github.com/jl-cmd/claude-code-config/commit/e06d2bfda8651744eb4d467000a58df5c35e476e))


### Bug Fixes

* **pr-converge:** code-review runs at session effort and applies fixes via --fix ([#507](https://github.com/jl-cmd/claude-code-config/issues/507)) ([e6ec504](https://github.com/jl-cmd/claude-code-config/commit/e6ec504c47e17705fa944598776c9aa18a752273))


### Documentation

* add CODE_RULES §9.8 — remove orphaned code in the same edit ([#498](https://github.com/jl-cmd/claude-code-config/issues/498)) ([c35d1c5](https://github.com/jl-cmd/claude-code-config/commit/c35d1c585db4901d01741110502214dd7185f877))
* **rules:** confirm implementation forks via AskUserQuestion ([#503](https://github.com/jl-cmd/claude-code-config/issues/503)) ([4aff1bf](https://github.com/jl-cmd/claude-code-config/commit/4aff1bf4088ab1bc2658fa71032666a332d8464b))
* **rules:** write all output in plain language ([#506](https://github.com/jl-cmd/claude-code-config/issues/506)) ([2948f7f](https://github.com/jl-cmd/claude-code-config/commit/2948f7f5446343e49146fc0a5befa20cb887d7c5))
* **session-log:** record authoring agent's session ID in report frontmatter ([#504](https://github.com/jl-cmd/claude-code-config/issues/504)) ([66c7528](https://github.com/jl-cmd/claude-code-config/commit/66c752860aa218cbd8822e5e7dea3f0e9f9383de))

## [1.47.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.46.0...claude-dev-env-v1.47.0) (2026-05-25)


### Features

* **zoekt-redirect:** document index-freshness escape hatch ([#495](https://github.com/jl-cmd/claude-code-config/issues/495)) ([fafdb1c](https://github.com/jl-cmd/claude-code-config/commit/fafdb1c1cd79f2efc14b18b4d0d966d8ab373025))


### Documentation

* **claude-md:** default to Edit over Write for existing files ([148a0f6](https://github.com/jl-cmd/claude-code-config/commit/148a0f6a0eca2f7f9cb19cf8666f53efde1735cb))
* **pre-compact:** confirm next-session intent, validate identifiers, resolve unknowns with the operator ([#500](https://github.com/jl-cmd/claude-code-config/issues/500)) ([ebfe6eb](https://github.com/jl-cmd/claude-code-config/commit/ebfe6eb4b3f3480395607fdd7bb47bd7c4d97a9d))
* **pre-compact:** scope the focus directive to next-step-relevant history ([#499](https://github.com/jl-cmd/claude-code-config/issues/499)) ([352cfcb](https://github.com/jl-cmd/claude-code-config/commit/352cfcb7cb8b268fa2c3a1b5b78365fc34f3a0f7))

## [1.46.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.45.0...claude-dev-env-v1.46.0) (2026-05-25)


### Features

* **zoekt-redirect:** default-exclude git worktrees from redirected searches ([#490](https://github.com/jl-cmd/claude-code-config/issues/490)) ([e8332e1](https://github.com/jl-cmd/claude-code-config/commit/e8332e13205be5ba62776d77592062e50f3b2901))


### Bug Fixes

* **pr-converge:** code-enforce CLAUDE_REVIEWS_DISABLED=bugbot opt-out ([#493](https://github.com/jl-cmd/claude-code-config/issues/493)) ([cf1d24e](https://github.com/jl-cmd/claude-code-config/commit/cf1d24e30d15fbb0cffe782f139a35457018ffb2))


### Tests

* **code-rules-gate:** isolate temp-repo hooks from global core.hooksPath ([#491](https://github.com/jl-cmd/claude-code-config/issues/491)) ([5c03078](https://github.com/jl-cmd/claude-code-config/commit/5c0307878de4acdbdc066b48514527f02876d1da))

## [1.45.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.44.0...claude-dev-env-v1.45.0) (2026-05-24)


### Features

* **hooks:** block plan writes with unresolved Open Questions ([#482](https://github.com/jl-cmd/claude-code-config/issues/482)) ([1457f06](https://github.com/jl-cmd/claude-code-config/commit/1457f06179c7335b236ee70177c40d6ac91e8470))
* **hooks:** close 4 process-leak gaps + extend audit rubric to A-N ([#484](https://github.com/jl-cmd/claude-code-config/issues/484)) ([b9614b5](https://github.com/jl-cmd/claude-code-config/commit/b9614b53fcfda6786f800ef25544134a96591207))

## [1.44.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.43.0...claude-dev-env-v1.44.0) (2026-05-22)


### Features

* **skills:** pre-compact - focus directive for /compact, clipboard hand-off ([#480](https://github.com/jl-cmd/claude-code-config/issues/480)) ([99f3267](https://github.com/jl-cmd/claude-code-config/commit/99f326765b5698c931ecbe9bb17edb36a17489a2))

## [1.43.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.42.0...claude-dev-env-v1.43.0) (2026-05-21)


### Features

* prevent pr-description-writer regressions ([#472](https://github.com/jl-cmd/claude-code-config/issues/472)) ([b72b536](https://github.com/jl-cmd/claude-code-config/commit/b72b536b340a5680f8dea4cc37722ff9f0e890f7))


### Bug Fixes

* centralize .md blocker exemptions and fix validator repo-root hang ([#476](https://github.com/jl-cmd/claude-code-config/issues/476)) ([b7b2f3b](https://github.com/jl-cmd/claude-code-config/commit/b7b2f3bdd93cb556210ff0ef4edcf84fce89ed0a))
* **code-rules:** route python comment detection through tokenize ([#479](https://github.com/jl-cmd/claude-code-config/issues/479)) ([2c9d308](https://github.com/jl-cmd/claude-code-config/commit/2c9d3088e47bb7850b9f4b157f2b1f4a386cc858))
* **code-rules:** skip docstring lines in check_imports_at_top ([#478](https://github.com/jl-cmd/claude-code-config/issues/478)) ([030ac9b](https://github.com/jl-cmd/claude-code-config/commit/030ac9bcdf067cad1de98d9851a92bb21ed1f68a))
* **pr-converge:** snapshot+restore sys.path in test conftest, document check_all Raises ([#473](https://github.com/jl-cmd/claude-code-config/issues/473)) ([2017e5c](https://github.com/jl-cmd/claude-code-config/commit/2017e5c1937a74bcc9a38de6578eb19ff27eded7))
* **rename:** unique per-tree constants packages eliminate bare `config` collision ([#475](https://github.com/jl-cmd/claude-code-config/issues/475)) ([3294c00](https://github.com/jl-cmd/claude-code-config/commit/3294c00893a20400ba9e2a4ed1e2af30c30b1c71))


### Refactoring

* **session-log:** delegate HTML design to doc-gist ([#477](https://github.com/jl-cmd/claude-code-config/issues/477)) ([8af4b4c](https://github.com/jl-cmd/claude-code-config/commit/8af4b4c7e0e7b7e43c15d9d86724f2b58a3df596))

## [1.42.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.41.0...claude-dev-env-v1.42.0) (2026-05-19)


### Features

* **skills:** add /implement skill with append-note CLI ([#466](https://github.com/jl-cmd/claude-code-config/issues/466)) ([61ec3cf](https://github.com/jl-cmd/claude-code-config/commit/61ec3cf82ceb6cbb84e5eefe22e17183657476c1))
* **skills:** add /refine — interview-driven plan refiner with audit loop ([#468](https://github.com/jl-cmd/claude-code-config/issues/468)) ([e03b303](https://github.com/jl-cmd/claude-code-config/commit/e03b303203237a68aca01450949ca3cfb8614ebe))


### Bug Fixes

* **check_convergence:** recognize bugteam reviews by body header ([#465](https://github.com/jl-cmd/claude-code-config/issues/465)) ([86e7ef9](https://github.com/jl-cmd/claude-code-config/commit/86e7ef91a30df07862a031b813cdbd5ecf3c24ab))
* **permissions:** enforce agent-config carve-out via deny rules ([#467](https://github.com/jl-cmd/claude-code-config/issues/467)) ([68d2d93](https://github.com/jl-cmd/claude-code-config/commit/68d2d939165f2719e54d27762ce06b3c56e98e8c))
* **pr-converge:** use Path.absolute() for sys.path entries on UNC-mapped drives ([#469](https://github.com/jl-cmd/claude-code-config/issues/469)) ([6226107](https://github.com/jl-cmd/claude-code-config/commit/6226107de6a46bbbb58f282d8d322026d3a922cc))


### Documentation

* **claude-dev-env:** prefer subagents for codebase research ([#471](https://github.com/jl-cmd/claude-code-config/issues/471)) ([136b84d](https://github.com/jl-cmd/claude-code-config/commit/136b84d99eedf7ed76c6cf213efadfc2ec2124b0))

## [1.41.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.40.0...claude-dev-env-v1.41.0) (2026-05-19)


### Features

* **pr-converge:** enforce formal bugteam skill invocation at Step 5 ([#463](https://github.com/jl-cmd/claude-code-config/issues/463)) ([a8dad46](https://github.com/jl-cmd/claude-code-config/commit/a8dad4600775f25170584113201560759fac5282))

## [1.40.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.39.0...claude-dev-env-v1.40.0) (2026-05-18)


### Features

* **skills:** add CLAUDE_REVIEWS_DISABLED opt-out env var for PR-review skills ([#458](https://github.com/jl-cmd/claude-code-config/issues/458)) ([070787b](https://github.com/jl-cmd/claude-code-config/commit/070787bcf945116838546bb5b9856029c85312db))


### Bug Fixes

* **bugteam:** auto-toggle reviews-API auth on self-PR ([#456](https://github.com/jl-cmd/claude-code-config/issues/456)) ([1411c8a](https://github.com/jl-cmd/claude-code-config/commit/1411c8a981f851afa531dba967f82a3d316bc924))
* **pr-converge:** treat bugbot silent pass as clean review ([#461](https://github.com/jl-cmd/claude-code-config/issues/461)) ([a35426c](https://github.com/jl-cmd/claude-code-config/commit/a35426c11ac2bf466edf9896ad403dc7b4fe26e8))
* **pr-description-writer:** align with Anthropic claude-code PR shapes ([#460](https://github.com/jl-cmd/claude-code-config/issues/460)) ([21020dc](https://github.com/jl-cmd/claude-code-config/commit/21020dc3ddb80bc4f430e11f7ee609a65b73d81b))

## [1.39.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.38.1...claude-dev-env-v1.39.0) (2026-05-15)


### Features

* add pr-consistency-audit skill — 10-rule cross-file inconsistency detection ([#428](https://github.com/jl-cmd/claude-code-config/issues/428)) ([ab5505e](https://github.com/jl-cmd/claude-code-config/commit/ab5505e4757cf596962ed9ffb640de072f63d3a0))
* block @cursor/[@copilot](https://github.com/copilot) mentions in add_issue_comment via PreToolUse hook ([#432](https://github.com/jl-cmd/claude-code-config/issues/432)) ([8197474](https://github.com/jl-cmd/claude-code-config/commit/81974748112580601ff42232842ea9f66ce7e659))
* **hooks:** add md-to-html blocker PreToolUse hook ([#414](https://github.com/jl-cmd/claude-code-config/issues/414)) ([b5d164d](https://github.com/jl-cmd/claude-code-config/commit/b5d164d14ed26a97f9c76653b07773e4117cc451))
* **hooks:** add md-to-html companion PostToolUse hook ([#415](https://github.com/jl-cmd/claude-code-config/issues/415)) ([0a5a58f](https://github.com/jl-cmd/claude-code-config/commit/0a5a58fd2884edda76f79d0bdcda06a85db231e2))
* **hooks:** enforcement hardening — 7 new blocking checks, pyproject consolidation, doc updates ([#417](https://github.com/jl-cmd/claude-code-config/issues/417)) ([048bfd6](https://github.com/jl-cmd/claude-code-config/commit/048bfd68f3d463132e7dbad53b8c6bb44948db78))
* **pr-converge:** add bugbot-down detection after trigger post ([#413](https://github.com/jl-cmd/claude-code-config/issues/413)) ([46c2555](https://github.com/jl-cmd/claude-code-config/commit/46c255598b9c711c02c37ebfb9179acbb9694a45))
* **pr-loop:** add post_audit_thread.py for audit reviewers ([#445](https://github.com/jl-cmd/claude-code-config/issues/445)) ([8c8e2ef](https://github.com/jl-cmd/claude-code-config/commit/8c8e2ef1310cdc03f42ea7b29c27fdb4c2f5baa1))
* **pr-loop:** wire post_audit_thread.py into audit skills ([#453](https://github.com/jl-cmd/claude-code-config/issues/453)) ([f1a25e2](https://github.com/jl-cmd/claude-code-config/commit/f1a25e29dda9987750ca1952d3a67a24f2789913))
* **scripts:** add sweep-empty-dirs utility and scheduled-task installer ([#394](https://github.com/jl-cmd/claude-code-config/issues/394)) ([4e7e326](https://github.com/jl-cmd/claude-code-config/commit/4e7e326052229a5bb899c22a448691b8946426c2))
* **skills:** add code standards enforcer skill ([#408](https://github.com/jl-cmd/claude-code-config/issues/408)) ([6e6f84c](https://github.com/jl-cmd/claude-code-config/commit/6e6f84cf2fb785a1b306dd41e9c67912ea26b552))
* **skills:** add structure-prompt skill ([#399](https://github.com/jl-cmd/claude-code-config/issues/399)) ([c199ce7](https://github.com/jl-cmd/claude-code-config/commit/c199ce792cbba409ebb69efd8ce3b81ef27397fb))
* **skills:** session-log writes HTML and publishes via /doc-gist ([#423](https://github.com/jl-cmd/claude-code-config/issues/423)) ([72a4e7a](https://github.com/jl-cmd/claude-code-config/commit/72a4e7ac3c997ee73322075c10436030f1bf1365))


### Bug Fixes

* **bugteam:** correct script paths from _shared to bugteam/scripts ([#436](https://github.com/jl-cmd/claude-code-config/issues/436)) ([628022e](https://github.com/jl-cmd/claude-code-config/commit/628022e2927d8a429bdc59a18311922b6b7abc0c))
* **bugteam:** correct stale code_rules_gate path in CONSTRAINTS.md ([#437](https://github.com/jl-cmd/claude-code-config/issues/437)) ([bbcda8c](https://github.com/jl-cmd/claude-code-config/commit/bbcda8c2784d4b498ac6cf199c65257805cd77be))
* **bugteam:** extract shared scripts + convergence scripts + doc audit + fix paths ([3940066](https://github.com/jl-cmd/claude-code-config/commit/3940066577cae17296158f6ba4bc9523e7d9ad77))
* clarify bugbot trigger body must be exactly "bugbot run" ([#431](https://github.com/jl-cmd/claude-code-config/issues/431)) ([eb13ecc](https://github.com/jl-cmd/claude-code-config/commit/eb13ecc79e712b6449dd46c293d9c5d66d2bf503))
* **hooks:** catch inline-tuple and import-alias violations at write-time ([#421](https://github.com/jl-cmd/claude-code-config/issues/421)) ([c89c0c6](https://github.com/jl-cmd/claude-code-config/commit/c89c0c6075347801b03f5cdf92ec06f41ac7f37b))
* **hooks:** exempt convergence branch force-pushes from destructive blocker ([#434](https://github.com/jl-cmd/claude-code-config/issues/434)) ([0f919cf](https://github.com/jl-cmd/claude-code-config/commit/0f919cf7815bea0fd0bf7ff78fbdb095d1c07829))
* **hooks:** exempt plain-text bodies from gh-body-file blocker ([#433](https://github.com/jl-cmd/claude-code-config/issues/433)) ([27062b0](https://github.com/jl-cmd/claude-code-config/commit/27062b05f61baa1736a69c4719ed1e0dd7a547ee))
* **hooks:** pr-converge fix round — TYPE_CHECKING awareness, import-aware cast detection, aggregate cap, deduplication ([#418](https://github.com/jl-cmd/claude-code-config/issues/418)) ([202e10f](https://github.com/jl-cmd/claude-code-config/commit/202e10fa40fd4c8f278a09996031e57aa513ea85))
* **hooks:** remove dict from COLLECTION_TYPE_NAMES ([#438](https://github.com/jl-cmd/claude-code-config/issues/438)) ([56f9cb8](https://github.com/jl-cmd/claude-code-config/commit/56f9cb82ca23974d227abdb3ca0a20a69f1e29d5))
* **hooks:** resolve CODE_RULES violations in code_rules_enforcer.py self-audit ([#435](https://github.com/jl-cmd/claude-code-config/issues/435)) ([df301c7](https://github.com/jl-cmd/claude-code-config/commit/df301c7a47fae6e9fd99d6cd83c5910bbf0fe4dd))
* **launcher:** remove DeepSeek API key env-var fallback when cc is invoked without the deepseek argument ([#403](https://github.com/jl-cmd/claude-code-config/issues/403)) ([a466162](https://github.com/jl-cmd/claude-code-config/commit/a466162e7fee1987b6d52fa8c1e4488e144da9d5))
* **pr-converge:** add COPILOT_WAIT handler to prevent broken back-to-back-clean cycle ([#416](https://github.com/jl-cmd/claude-code-config/issues/416)) ([842fa29](https://github.com/jl-cmd/claude-code-config/commit/842fa294bffb67ffaabbd5b4e7db099225a70cc0))
* **pr-converge:** count ALL unresolved review threads regardless of author or staleness ([#439](https://github.com/jl-cmd/claude-code-config/issues/439)) ([6bb37df](https://github.com/jl-cmd/claude-code-config/commit/6bb37df307147537fb0abacbdf166dd14bb05b88))
* **pr-converge:** expand convergence-gates from 4 to 6 gates, align examples ([#409](https://github.com/jl-cmd/claude-code-config/issues/409)) ([ccfff2c](https://github.com/jl-cmd/claude-code-config/commit/ccfff2c659e1ab5e241df7f17d51fff286bdb517))
* **pr-converge:** harden convergence gates with Claude review, COPILOT_WAIT, thread resolution, and mandatory evidence ([#411](https://github.com/jl-cmd/claude-code-config/issues/411)) ([d7d3087](https://github.com/jl-cmd/claude-code-config/commit/d7d3087d12c01d387bc05ada48ee815058e7966d))
* **pr-converge:** harden ScheduleWakeup detection and add EnterWorktree isolation gate ([#430](https://github.com/jl-cmd/claude-code-config/issues/430)) ([fa178bf](https://github.com/jl-cmd/claude-code-config/commit/fa178bfca64e086e79829c8e3b6226cd8c5faff9))
* **pr-converge:** make HEAD re-resolution mandatory with 60s propagation delay ([#412](https://github.com/jl-cmd/claude-code-config/issues/412)) ([69788da](https://github.com/jl-cmd/claude-code-config/commit/69788dabe315ff8a6fe34fca30273fc9454cddcf))
* **pr-converge:** route multi-PR convergence through four-gate flow ([#410](https://github.com/jl-cmd/claude-code-config/issues/410)) ([4da4d7a](https://github.com/jl-cmd/claude-code-config/commit/4da4d7a5537f310d68e9680f975d703ecf63d7c1))


### Documentation

* **pr-loop:** add audit-reply-template canonical reference ([#440](https://github.com/jl-cmd/claude-code-config/issues/440)) ([0c0519f](https://github.com/jl-cmd/claude-code-config/commit/0c0519f51c4f230fae0bcba6f300c1ae13873127))


### Maintenance

* **agents:** remove 9 unused agents, 10 skills, and 1 command ([#425](https://github.com/jl-cmd/claude-code-config/issues/425)) ([36e0bef](https://github.com/jl-cmd/claude-code-config/commit/36e0bef3b0fab929ce9fd9e2a44759c0fcf947b8))


### Refactoring

* **doc-gist:** transport + sentinel marker hook + gallery, drop templates ([#419](https://github.com/jl-cmd/claude-code-config/issues/419)) ([6430ded](https://github.com/jl-cmd/claude-code-config/commit/6430ded7d88e8754efa2a658939d2e58ed545dbf))
* **skill-builder:** rewrite as best-practice-driven expert craftsman ([#406](https://github.com/jl-cmd/claude-code-config/issues/406)) ([42f5dbb](https://github.com/jl-cmd/claude-code-config/commit/42f5dbb40d231f0127e46e0a07543cc4f5533fcd))


### Tests

* **pr-loop:** expand post_audit_thread.py coverage to retry paths ([#452](https://github.com/jl-cmd/claude-code-config/issues/452)) ([7544827](https://github.com/jl-cmd/claude-code-config/commit/7544827a73163330dd7c351a21b27ee60d00c597))
* **pr-loop:** retarget post_audit_thread tests to JonEcho/tests with shared PR ([#451](https://github.com/jl-cmd/claude-code-config/issues/451)) ([6c252ee](https://github.com/jl-cmd/claude-code-config/commit/6c252eebd0df7ff09074e6109ef523c7f5da087a))

## [1.38.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.38.0...claude-dev-env-v1.38.1) (2026-05-09)


### Bug Fixes

* **hooks:** detect unused imports against full post-edit file content ([#401](https://github.com/jl-cmd/claude-code-config/issues/401)) ([1c313b4](https://github.com/jl-cmd/claude-code-config/commit/1c313b4cd5722118f1d50411121aad73c2a1c97f))

## [1.38.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.37.1...claude-dev-env-v1.38.0) (2026-05-08)


### Features

* **bugteam:** replace inline jq review posting with deterministic Python scripts ([#374](https://github.com/jl-cmd/claude-code-config/issues/374)) ([e88d8ad](https://github.com/jl-cmd/claude-code-config/commit/e88d8adca77cde327b468f395a4e9c47a7645971))
* **github-mcp:** migrate gh CLI calls to MCP tools across PR and bugteam workflows ([#376](https://github.com/jl-cmd/claude-code-config/issues/376)) ([58b7837](https://github.com/jl-cmd/claude-code-config/commit/58b7837de15a8c8ba80ebba68e7a1a719e58b004))
* **hooks:** add state-description-blocker for historical/comparative language ([#377](https://github.com/jl-cmd/claude-code-config/issues/377)) ([183fcf7](https://github.com/jl-cmd/claude-code-config/commit/183fcf7c75acd39d8d13c5b01207eba5829ff974))


### Bug Fixes

* **bugteam:** add bypass mode to pre-audit clean-coder and pr-description-writer spawns ([#382](https://github.com/jl-cmd/claude-code-config/issues/382)) ([11aba63](https://github.com/jl-cmd/claude-code-config/commit/11aba63cd9ce719dc7e98c77ea6d11228cd8a237))
* **bugteam:** spawn subagents with bypassPermissions mode ([#380](https://github.com/jl-cmd/claude-code-config/issues/380)) ([5aba811](https://github.com/jl-cmd/claude-code-config/commit/5aba8117e26864c1752807e4dea3f20b4c6ade64))
* **clean-coder:** add user-global rubric fallback for repos without in-tree audit directory ([#400](https://github.com/jl-cmd/claude-code-config/issues/400)) ([fc05296](https://github.com/jl-cmd/claude-code-config/commit/fc05296594dcc0444aed40bfefabbb38e4f8eaf8))
* **hook:** add constants-only config file exemption to TDD enforcer ([#378](https://github.com/jl-cmd/claude-code-config/issues/378)) ([5521087](https://github.com/jl-cmd/claude-code-config/commit/55210876e2e4e17190b3a9277b93ba68ccb6f4ef))
* **hooks:** improve hedging-language guardrail to surface user questions ([#397](https://github.com/jl-cmd/claude-code-config/issues/397)) ([fa2aec1](https://github.com/jl-cmd/claude-code-config/commit/fa2aec129b7eb356d8528916e9ba5f1232cc86f1))
* **hooks:** register code_rules_enforcer for Write/Edit PreToolUse ([#396](https://github.com/jl-cmd/claude-code-config/issues/396)) ([76f9c1a](https://github.com/jl-cmd/claude-code-config/commit/76f9c1a0048729b87c44626a3380dc840065c2fa))
* **skills:** add 5 constraint improvements from bugteam gap analysis ([#384](https://github.com/jl-cmd/claude-code-config/issues/384)) ([22c4ca9](https://github.com/jl-cmd/claude-code-config/commit/22c4ca97383a7350d392f0e79a4667a60729290a))
* **skills:** cross-loop regression check and verified-clean depth constraints ([#393](https://github.com/jl-cmd/claude-code-config/issues/393)) ([33aaf56](https://github.com/jl-cmd/claude-code-config/commit/33aaf56b300d98ad2c9a62508e822b4e182ffd5a))


### Documentation

* add Category K and reusable audit templates for 11 categories ([#398](https://github.com/jl-cmd/claude-code-config/issues/398)) ([94742e4](https://github.com/jl-cmd/claude-code-config/commit/94742e4f987775a32dee7b1482d6f0fefa52df71))
* **claude-md:** add zero-manual-steps execution directive ([#395](https://github.com/jl-cmd/claude-code-config/issues/395)) ([9c259df](https://github.com/jl-cmd/claude-code-config/commit/9c259dfe093cb47ab8bea25290c43964586b2df9))

## [1.37.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.37.0...claude-dev-env-v1.37.1) (2026-05-06)


### Bug Fixes

* **bugteam:** 10 haiku parallel auditors + opus validator replaces 3 opus ([#373](https://github.com/jl-cmd/claude-code-config/issues/373)) ([e814025](https://github.com/jl-cmd/claude-code-config/commit/e81402538929604330e54022aa289bf7f9407b02))
* **pr-converge:** harden single-PR fix routing — view_pr_context flags, clean-coder spawn, reply script ([#370](https://github.com/jl-cmd/claude-code-config/issues/370)) ([acb7b95](https://github.com/jl-cmd/claude-code-config/commit/acb7b954b096f0dda54ed032720848b26f23e461))


### Documentation

* **rules:** strip historical clutter from gh-paginate, add no-historical-clutter rule ([#371](https://github.com/jl-cmd/claude-code-config/issues/371)) ([ee32907](https://github.com/jl-cmd/claude-code-config/commit/ee3290784232828aac6373d56595ac4191667794))

## [1.37.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.36.3...claude-dev-env-v1.37.0) (2026-05-06)


### Features

* **bg-agent:** add bg-agent skill for delegating tasks to background agents ([#362](https://github.com/jl-cmd/claude-code-config/issues/362)) ([ac01573](https://github.com/jl-cmd/claude-code-config/commit/ac01573ac8be0d9dcda5c789b28b07bcc2e4ce25))
* **fresh-branch:** add fresh-branch skill for creating branches from origin/main ([#361](https://github.com/jl-cmd/claude-code-config/issues/361)) ([067a404](https://github.com/jl-cmd/claude-code-config/commit/067a4048d957d5b35189b0df02d86077f8edb453))
* **gotcha:** add gotcha skill for capturing obstacles and creating fix PRs ([#363](https://github.com/jl-cmd/claude-code-config/issues/363)) ([bb8af45](https://github.com/jl-cmd/claude-code-config/commit/bb8af45b7cdebfcc65c65b5c181a6f1f49fd4e12))


### Refactoring

* **bugteam:** migrate from orchestrated teams to background subagents ([#368](https://github.com/jl-cmd/claude-code-config/issues/368)) ([1e093a6](https://github.com/jl-cmd/claude-code-config/commit/1e093a67bb1023616866b7839b8b1d0ea23d1238))
* **pr-converge:** hub-and-spoke rewrite + Claude reviewer support ([#360](https://github.com/jl-cmd/claude-code-config/issues/360)) ([5461e0b](https://github.com/jl-cmd/claude-code-config/commit/5461e0b7dee87e7a4f6a586acefc39994aed7829))


### Performance

* **preflight:** replace rglob with git ls-files, add --ff and PR-scoped test selection ([#369](https://github.com/jl-cmd/claude-code-config/issues/369)) ([e65084b](https://github.com/jl-cmd/claude-code-config/commit/e65084bc760033a3c56b4485dacfb475a939ca43))

## [1.36.3](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.36.2...claude-dev-env-v1.36.3) (2026-05-04)


### Bug Fixes

* **bugteam:** repair command wrapping ([#353](https://github.com/jl-cmd/claude-code-config/issues/353)) ([1dcaada](https://github.com/jl-cmd/claude-code-config/commit/1dcaada10120cf3bbfce31bef1ce40b76954863b))
* **hooks:** address Copilot PR 318 review 4216464432 (unused imports) ([#346](https://github.com/jl-cmd/claude-code-config/issues/346)) ([1ebbc81](https://github.com/jl-cmd/claude-code-config/commit/1ebbc81ff9995ede85762dedd7113fd9a873896c))
* **pr-converge:** keep AHK pacer resilient without pwsh ([#355](https://github.com/jl-cmd/claude-code-config/issues/355)) ([14d9703](https://github.com/jl-cmd/claude-code-config/commit/14d9703fdb88bbe0786215bfd6f4d006ae12ca7c))
* **pr-converge:** preserve state path formatting ([#354](https://github.com/jl-cmd/claude-code-config/issues/354)) ([3ac1bcd](https://github.com/jl-cmd/claude-code-config/commit/3ac1bcdd3ff80741a776ac47e02f76cdc48f394e))
* **pr-converge:** repair and harden SKILL.md reflow ([#357](https://github.com/jl-cmd/claude-code-config/issues/357)) ([21e74d8](https://github.com/jl-cmd/claude-code-config/commit/21e74d875ced3d75d17eb02effe8f88681776f99))

## [1.36.2](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.36.1...claude-dev-env-v1.36.2) (2026-05-04)


### Bug Fixes

* **claude-dev-env:** include _shared/ in published npm tarball ([#352](https://github.com/jl-cmd/claude-code-config/issues/352)) ([1a9d0e4](https://github.com/jl-cmd/claude-code-config/commit/1a9d0e40ac056054814196ab6684125ac24a03b7))

## [1.36.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.36.0...claude-dev-env-v1.36.1) (2026-05-04)


### Refactoring

* **bugteam:** wrap SKILL.md to 80 columns with PR 349 reflow script ([#350](https://github.com/jl-cmd/claude-code-config/issues/350)) ([e56d741](https://github.com/jl-cmd/claude-code-config/commit/e56d7410276e8de2a85a3cacf3e5cc4833ee9f02))
* **pr-converge:** wrap SKILL.md to 80-character lines ([#349](https://github.com/jl-cmd/claude-code-config/issues/349)) ([c0c2032](https://github.com/jl-cmd/claude-code-config/commit/c0c2032588c2798c9d0d3b972643e18963b9b710))

## [1.36.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.35.0...claude-dev-env-v1.36.0) (2026-05-03)


### Features

* **_shared/pr-loop:** Phase 1 consolidation of shared PR-loop docs ([#289](https://github.com/jl-cmd/claude-code-config/issues/289)) ([4716035](https://github.com/jl-cmd/claude-code-config/commit/4716035868c3bc08c2a035647515bd8126222211))
* **cursor:** add parallel-debug skill for AHK-paced pr-converge loop ([#342](https://github.com/jl-cmd/claude-code-config/issues/342)) ([9223afe](https://github.com/jl-cmd/claude-code-config/commit/9223afe184a20be63354b57920f2a1786cf8a01b))
* **enforcer:** add CLI abbreviations to BANNED_IDENTIFIERS ([#314](https://github.com/jl-cmd/claude-code-config/issues/314)) ([1ec0407](https://github.com/jl-cmd/claude-code-config/commit/1ec0407a5839b1e3f7a9e45886fa4c55e7e81120))
* **enforcer:** block hardcoded user paths in production code ([#316](https://github.com/jl-cmd/claude-code-config/issues/316)) ([7dd4c1e](https://github.com/jl-cmd/claude-code-config/commit/7dd4c1e21ee450438edea3c508b94d6a62234a41))
* **enforcer:** exempt args from ban when RHS is parse_args() ([#334](https://github.com/jl-cmd/claude-code-config/issues/334)) ([f09c859](https://github.com/jl-cmd/claude-code-config/commit/f09c859bb525251557997bfb81aa09fe4275f2a2))
* **enforcer:** flag loop-var unpacking targets lacking each_ prefix ([#310](https://github.com/jl-cmd/claude-code-config/issues/310)) ([af852b9](https://github.com/jl-cmd/claude-code-config/commit/af852b96d48dea31e24b338c603d2270df9372c1))
* **enforcer:** flag stuttering all_/ALL_ collection prefix ([#313](https://github.com/jl-cmd/claude-code-config/issues/313)) ([0d122b7](https://github.com/jl-cmd/claude-code-config/commit/0d122b7f46b12863653ee9aa39a4dc36e9cff54b))
* **enforcer:** flag unused module-level imports in production code ([#318](https://github.com/jl-cmd/claude-code-config/issues/318)) ([50503f1](https://github.com/jl-cmd/claude-code-config/commit/50503f1c716baa20c38b6de08e830942d260bd0f))
* **enforcer:** require dedup guard around sys.path.insert ([#317](https://github.com/jl-cmd/claude-code-config/issues/317)) ([668199c](https://github.com/jl-cmd/claude-code-config/commit/668199c2ad673708cc658c30ee052d46ade0d2c0))
* **pr-converge:** add AHK auto-continue loop driver ([#326](https://github.com/jl-cmd/claude-code-config/issues/326)) ([7c86c79](https://github.com/jl-cmd/claude-code-config/commit/7c86c797ff2513991e989cd3cd4be81b2f445f5f))
* **pr-converge:** add mergeability + Copilot gates and post-convergence Copilot follow-up ([#337](https://github.com/jl-cmd/claude-code-config/issues/337)) ([cec288b](https://github.com/jl-cmd/claude-code-config/commit/cec288bc051748c485a5213ac7b832ce1976e31e))
* **pr-converge:** scripts, workflows, and AHK pacer lifecycle ([#332](https://github.com/jl-cmd/claude-code-config/issues/332)) ([1dd4773](https://github.com/jl-cmd/claude-code-config/commit/1dd477346b7c8935b27e66a93e86b67585bba4b1))
* **rules:** centralize gh-paginate rule and apply to pr-converge ([#301](https://github.com/jl-cmd/claude-code-config/issues/301)) ([c20cac4](https://github.com/jl-cmd/claude-code-config/commit/c20cac46610d8f6afc5ff7b6bfe5e1e421540b61))
* **skills:** add resume-review skill for structural resume audits ([#341](https://github.com/jl-cmd/claude-code-config/issues/341)) ([668412e](https://github.com/jl-cmd/claude-code-config/commit/668412e4184f8b639f88a04281b848a8fc9603d8))
* **skills:** decouple team lifecycle from bugteam invocation ([#344](https://github.com/jl-cmd/claude-code-config/issues/344)) ([2e96a88](https://github.com/jl-cmd/claude-code-config/commit/2e96a885c21664957959f75f877f82a9a5feae7a))
* **skills:** Phase 2 rewire bugteam/qbug to _shared/pr-loop/ scripts ([#290](https://github.com/jl-cmd/claude-code-config/issues/290)) ([c771418](https://github.com/jl-cmd/claude-code-config/commit/c7714186ebee84a56d1db5eb505e63d5ecdcced2))


### Bug Fixes

* **enforcer:** hardcoded user path Copilot follow-ups (PR [#316](https://github.com/jl-cmd/claude-code-config/issues/316) review) ([#339](https://github.com/jl-cmd/claude-code-config/issues/339)) ([1a207e2](https://github.com/jl-cmd/claude-code-config/commit/1a207e229db991a469cc0b96d0856e3551c1d2c1))
* **enforcer:** PR [#313](https://github.com/jl-cmd/claude-code-config/issues/313) follow-up — stuttering imports/classes + mypy path ([#335](https://github.com/jl-cmd/claude-code-config/issues/335)) ([e207777](https://github.com/jl-cmd/claude-code-config/commit/e2077779ddacf8c475fb57945679708298eae305))
* **hooks:** fail-safe PreToolUse stdin JSON for es and rmtree hooks ([#336](https://github.com/jl-cmd/claude-code-config/issues/336)) ([c7e1de5](https://github.com/jl-cmd/claude-code-config/commit/c7e1de50ddb39335ae76549dbc67cabe5558654b))
* **hooks:** harden es_exe_path_rewriter tool_input typing (PR [#336](https://github.com/jl-cmd/claude-code-config/issues/336) review) ([#347](https://github.com/jl-cmd/claude-code-config/issues/347)) ([6bf9d55](https://github.com/jl-cmd/claude-code-config/commit/6bf9d55200ac13ec7bbb587d0405167738db3ebe))
* **hooks:** use CREATE_NO_WINDOW so Stop-hook extractor does not flash a console ([#324](https://github.com/jl-cmd/claude-code-config/issues/324)) ([af0c0ae](https://github.com/jl-cmd/claude-code-config/commit/af0c0aec5bf7aacd1f5c349820cda9b65731bb79))
* **pr-loop:** follow-up for Copilot + Bugbot reviews on [#289](https://github.com/jl-cmd/claude-code-config/issues/289) ([#329](https://github.com/jl-cmd/claude-code-config/issues/329)) ([5125cd0](https://github.com/jl-cmd/claude-code-config/commit/5125cd05b8b5c462e80c35e93096a0871a1a7309))


### Documentation

* **agents:** align AGENTS.md with hook-enforced and canonical rules ([#300](https://github.com/jl-cmd/claude-code-config/issues/300)) ([b035d73](https://github.com/jl-cmd/claude-code-config/commit/b035d738d1b45573442131b064c6c1205e73c408))
* bugteam workflow split + pr-converge state schema ([#331](https://github.com/jl-cmd/claude-code-config/issues/331)) ([9be50cc](https://github.com/jl-cmd/claude-code-config/commit/9be50cc8444a2401e383663250405871eb87fbd6))
* **clean-coder:** align agent prompt with hook-enforced and canonical rules ([#302](https://github.com/jl-cmd/claude-code-config/issues/302)) ([ae702e6](https://github.com/jl-cmd/claude-code-config/commit/ae702e68e4963fe5fc406057ac664ec9680856be))
* **pr-converge:** skip duplicate bugbot run when eyes reaction present ([#327](https://github.com/jl-cmd/claude-code-config/issues/327)) ([4acb35b](https://github.com/jl-cmd/claude-code-config/commit/4acb35bef056c7e681727118d5e400679b8c0d97))


### Tests

* **enforcer:** add meta-test for check_* cap convention ([#315](https://github.com/jl-cmd/claude-code-config/issues/315)) ([9ce9839](https://github.com/jl-cmd/claude-code-config/commit/9ce9839f4ef9408dd324db0f9fc15a5080b4c56c))
* **enforcer:** address Copilot cap-meta review on PR [#333](https://github.com/jl-cmd/claude-code-config/issues/333) ([#338](https://github.com/jl-cmd/claude-code-config/issues/338)) ([d826b59](https://github.com/jl-cmd/claude-code-config/commit/d826b599e86d994648d4a3cb78fbcf0ad11bc5c4))
* **enforcer:** lock prefix-position requirement for boolean naming ([#312](https://github.com/jl-cmd/claude-code-config/issues/312)) ([b9d8d3d](https://github.com/jl-cmd/claude-code-config/commit/b9d8d3d1dc009c14469bb3868327cac4a0156eb7))
* **enforcer:** lock symmetric operand handling for constant-equality ([#311](https://github.com/jl-cmd/claude-code-config/issues/311)) ([5eed9bb](https://github.com/jl-cmd/claude-code-config/commit/5eed9bb56a7fa1fd6734f45521ecaa1082da78f4))
* **enforcer:** tighten cap meta allowlists for PR [#315](https://github.com/jl-cmd/claude-code-config/issues/315) Bugbot ([#333](https://github.com/jl-cmd/claude-code-config/issues/333)) ([3ef9ee8](https://github.com/jl-cmd/claude-code-config/commit/3ef9ee8981d9cb4429d7925a82d2f68977bf6ba2))

## [1.35.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.34.1...claude-dev-env-v1.35.0) (2026-05-01)


### Features

* **pr-converge:** walk bugbot reviews end-to-clean, not last-only ([#295](https://github.com/jl-cmd/claude-code-config/issues/295)) ([554cd2f](https://github.com/jl-cmd/claude-code-config/commit/554cd2f619967bfc6d8e872297c0239b613dcdf7))


### Bug Fixes

* **commands:** restore Bash for /readability-review, drop ghost skill ref ([#298](https://github.com/jl-cmd/claude-code-config/issues/298)) ([16ce658](https://github.com/jl-cmd/claude-code-config/commit/16ce658d74a6886e1f85c7825c9601815ed201dd))
* **enforcer:** close gate gaps so audits stop re-finding violations ([#291](https://github.com/jl-cmd/claude-code-config/issues/291)) ([368948b](https://github.com/jl-cmd/claude-code-config/commit/368948b2806a336859dccf82060c7512db574ad7))
* **enforcer:** scope body checks to bodies, exempt _, qualify typing.Optional (PR [#291](https://github.com/jl-cmd/claude-code-config/issues/291) follow-up) ([#299](https://github.com/jl-cmd/claude-code-config/issues/299)) ([5a65457](https://github.com/jl-cmd/claude-code-config/commit/5a654577715d0d25ac5ddf4651b80a144c75f519))


### Documentation

* **bugteam:** mark copilot-gap-analysis.md patch plan historical (PR [#292](https://github.com/jl-cmd/claude-code-config/issues/292) follow-up) ([#297](https://github.com/jl-cmd/claude-code-config/issues/297)) ([6b51a27](https://github.com/jl-cmd/claude-code-config/commit/6b51a27ff6d1ce30e6f5adb903fa50631511fad2))


### Maintenance

* remove 20 unused agents and clean dangling references ([#294](https://github.com/jl-cmd/claude-code-config/issues/294)) ([51b9ce6](https://github.com/jl-cmd/claude-code-config/commit/51b9ce6a341c5668d0c8008035cbfa67d8d6ecbc))


### Refactoring

* **bugteam:** remove K-N rubric categories from audit prompt ([#292](https://github.com/jl-cmd/claude-code-config/issues/292)) ([a3a483b](https://github.com/jl-cmd/claude-code-config/commit/a3a483bb3197381e6bd1b87a4c6f1f13937f1a28)), closes [#291](https://github.com/jl-cmd/claude-code-config/issues/291)

## [1.34.1](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.34.0...claude-dev-env-v1.34.1) (2026-04-30)


### Bug Fixes

* **skill/pr-converge:** run loop in main session, not background subagent ([#287](https://github.com/jl-cmd/claude-code-config/issues/287)) ([8ea8416](https://github.com/jl-cmd/claude-code-config/commit/8ea8416d9cd541b677016a6ae2d394dcd4baaf42))

## [1.34.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.33.0...claude-dev-env-v1.34.0) (2026-04-29)


### Features

* **hooks:** add InstructionsLoaded observability logger for rule audits ([#285](https://github.com/jl-cmd/claude-code-config/issues/285)) ([d4090cb](https://github.com/jl-cmd/claude-code-config/commit/d4090cb6313f8db47bec829ecfb94d6f51fc47e5))
* **rules:** pwsh-only shell-invocation policy + audit/migrate scripts ([#280](https://github.com/jl-cmd/claude-code-config/issues/280)) ([d992cdd](https://github.com/jl-cmd/claude-code-config/commit/d992cdd8f1f305f2f36cb9be7705f85f9c502267))
* **skills:** add caveman skill counterpart to caveman agent ([#279](https://github.com/jl-cmd/claude-code-config/issues/279)) ([316ee60](https://github.com/jl-cmd/claude-code-config/commit/316ee60bb6c879188f5e258fc454bfd9b302b101))
* **skills:** add pr-converge skill for bugbot ↔ bugteam convergence ([#281](https://github.com/jl-cmd/claude-code-config/issues/281)) ([ee115d8](https://github.com/jl-cmd/claude-code-config/commit/ee115d84200971a82c763a63490a1fe75885db42))


### Performance

* **rules:** add path-scoped frontmatter to domain-specific rules ([#284](https://github.com/jl-cmd/claude-code-config/issues/284)) ([3fd8017](https://github.com/jl-cmd/claude-code-config/commit/3fd8017dcde4ece98a2ccf512e099447958e3a3e))

## [1.33.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.32.0...claude-dev-env-v1.33.0) (2026-04-28)


### Features

* **bugteam:** close Copilot review gap with K-N rubric + post-merge fixes for [#270](https://github.com/jl-cmd/claude-code-config/issues/270)-[#273](https://github.com/jl-cmd/claude-code-config/issues/273) ([#276](https://github.com/jl-cmd/claude-code-config/issues/276)) ([ec5143f](https://github.com/jl-cmd/claude-code-config/commit/ec5143fe1b41ed6291b99af980179811e3ea99b6))


### Bug Fixes

* **bugteam:** evict cached config module before importing scripts/config/ ([#278](https://github.com/jl-cmd/claude-code-config/issues/278)) ([106841d](https://github.com/jl-cmd/claude-code-config/commit/106841d6f15a1d5da8f84af050a28349ccace1fc))

## [1.32.0](https://github.com/jl-cmd/claude-code-config/compare/claude-dev-env-v1.31.1...claude-dev-env-v1.32.0) (2026-04-28)


### Features

* **hooks:** block unsafe shutil.rmtree on Windows with force_rmtree replacement ([#273](https://github.com/jl-cmd/claude-code-config/issues/273)) ([aad3a77](https://github.com/jl-cmd/claude-code-config/commit/aad3a77d77eb142bf19c095c9fe8738ac8388e17))
* **skills:** add /rebase skill ([#270](https://github.com/jl-cmd/claude-code-config/issues/270)) ([3d60a8a](https://github.com/jl-cmd/claude-code-config/commit/3d60a8a6a53801391fcc76853647258fcc1df60a))


### Bug Fixes

* **hooks:** add SessionStart cleanup for Bash session-env directory on Windows ([#271](https://github.com/jl-cmd/claude-code-config/issues/271)) ([be62cd3](https://github.com/jl-cmd/claude-code-config/commit/be62cd33da4833ba2e00a83f303ba603dceeb356))


### Maintenance

* **bugteam:** auto-fix core.hooksPath override in preflight ([#272](https://github.com/jl-cmd/claude-code-config/issues/272)) ([bd1f94d](https://github.com/jl-cmd/claude-code-config/commit/bd1f94d57d1e1729049031af461dbc66a917939b))

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
