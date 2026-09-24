Audit [REPO/ARTIFACT] [TARGET_ID] for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J, L–P. Sub-bucket forced-exhaustion mode: Category K is decomposed into 11 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including the BEFORE state of changed surfaces, so the agent can compare before vs after]

- Title / one-line summary: [TITLE]
- Base ref / SHA (state BEFORE the change): [BASE_SHA]
- Head ref / SHA at audit time (state AFTER the change): [HEAD_SHA]
- Changed surfaces (file + line range + symbol/region name): [CHANGED_SURFACES]
- BEFORE state of each changed surface (the literal pre-change text the diff replaces): [BEFORE_SNIPPETS]
- AFTER state of each changed surface (the literal post-change text the diff installs): [AFTER_SNIPPETS]
- Stated intent of the change (what behavior the author intended to alter): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: describe what the diff changed in plain English, in terms narrow enough that a reader can hold the *contract* the diff is trying to enforce in their head while they read the unchanged code. State explicitly what the wider file / repo structure was left unchanged. Then state the audit goal: identify any unchanged parallel site whose existing wording / shape / behavior contradicts the new wording / shape / behavior so that the two reach the same downstream consumer (model, caller, runtime, schema, user, test) together.]

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL DIFF — including BOTH the changed lines AND surrounding context that shows what stayed the same.]

[ALSO INCLUDE any unchanged files in the codebase that the agent must search for parallel sites. For a small repo, inline a project tree. For a large repo, identify the most likely affected files via `git grep <renamed-symbol>` or equivalent and inline those.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**K1. Multi-site name renames**
- Did the diff rename any symbol (function, method, class, variable, kwarg, type alias, constant name, enum variant, CSS class, config key, env var, route name, API field, log key, error code, test fixture name)?
- If yes, enumerate every reference site (call sites, imports, type annotations, error messages, docstrings, README, ADRs, tests, fixtures, CI configs, dashboards, alert rules) — does each one use the new name?
- Adversarial probes when no rename is present: (a) scan for near-renames where casing / hyphenation / pluralization changed; (b) scan for symbols whose *meaning* shifted even though the spelling did not; (c) scan for shadowed-but-not-renamed identifiers introduced in the diff.

**K2. Duplicated constants / defaults**
- Did the diff change a value (number, string, regex, path, URL, timeout, threshold, default argument, magic literal)? Enumerate every duplicated occurrence of that value across the repo, in both code and config.
- Did the diff update one occurrence but leave the duplicates stale? Cite each unchanged duplicate as the conflict pair partner.
- Adversarial probes when no duplicates exist: (a) grep the exact literal across all files; (b) grep the semantic neighbors (`120`, `2 * 60`, `"2m"`, `"PT2M"`); (c) check sibling-language partners (PowerShell + Python, TS + Go, YAML + code).

**K3. Primary path vs fallback path** ⭐ canonical K case
- Identify the primary / happy path and any fallback / error / default-when-missing / no-feature-installed path the diff touches. Do they both flow into the same downstream consumer (same return value, same response field, same log line, same UI, same exception class, same exit code)?
- Did the diff update the primary path's contribution but leave the fallback path's contribution stale (or vice versa)? Cite both lines as the conflict pair.
- Adversarial probes when paths look symmetric: (a) trace each branch's output to the same sink; (b) walk every `else:`, `except:`, `default:`, `?:`, `||`, `??`, `or` operator the diff is adjacent to; (c) check for "skill not installed" / "feature flag off" / "fixture missing" / "network unavailable" branches that bypass the new code.

**K4. Feature flag / version gate consistency**
- Did the diff flip a flag, bump a version, or change behavior under one branch of a guard? Enumerate every other guard for the same flag/version across the repo — do they all reflect the new behavior?
- Adversarial probes when the diff adds no flag: (a) is there an *existing* flag that should now be deprecated because the diff makes its protected branch unreachable; (b) is there a version-gated import or feature shim that the diff should have updated; (c) does the diff cross a deprecation window where one half of a deprecation is now wrong?

**K5. Producer-vs-consumer type contracts**
- Did the diff widen / narrow / reshape a producer's output (return type, response shape, dict keys, tuple arity, list element type, optional vs required field)? Enumerate every consumer — do their type annotations / destructuring / parsing still match?
- Adversarial probes when types look stable: (a) check for `Any` / `unknown` / `dict[str, Any]` consumers that hide drift; (b) check for serializers (JSON, MessagePack, protobuf) whose schema lags the producer; (c) check for runtime validators (pydantic, zod, joi) whose rules now allow what should be rejected (or vice versa).

**K6. Code vs documentation sync (cross-surface)**
- Did the diff change observable behavior? Enumerate every doc surface that describes that behavior (README, ADR, design doc, CHANGELOG, API docs, error messages shown to the user, comments adjacent to the changed code; docstring-prose drift belongs to Category O).
- Adversarial probes when docs look fine: (a) check for "see also" cross-references that now point to outdated explanations; (b) check for examples in those doc surfaces that exercise the *old* behavior; (c) check for diagrams / state machines / sequence flows in those doc surfaces that depict the pre-diff path.

**K7. Code vs test sync**
- Did the diff change observable behavior? Enumerate every test that exercises that behavior — do positive, negative, edge, and regression tests all still express the post-diff contract?
- Adversarial probes when tests look green: (a) which tests pass *for the wrong reason* (assert on substring that survives the change but no longer represents the intent); (b) which tests are missing entirely (post-diff intent has no covering test); (c) which fixtures encode the old shape and would silently mask drift.

**K8. Cross-file / cross-language contract sync**
- Does the changed value or shape live in multiple languages (PowerShell + Python, TypeScript + Go, SQL + ORM model, Terraform + app config) or multiple file kinds (`.json` + `.yml`, `.proto` + generated stubs)? Enumerate every partner — do they all reflect the change?
- Adversarial probes when only one language is in play: (a) grep the value / shape in non-code surfaces (CI matrices, Docker env, Helm values, k8s manifests); (b) check for generated code that lags the source; (c) check for alternate spellings across language conventions (`snake_case` ↔ `camelCase` ↔ `kebab-case`).

**K9. Schema / data-shape propagation**
- Did the diff add / remove / rename a field, column, key, header, query parameter, message field, event payload field? Enumerate every site that constructs or consumes that shape — migrations, ORM models, serializers, fixtures, API docs, client SDKs, replay tooling, analytics emitters.
- Adversarial probes when no schema changed: (a) check for schemaless dicts that effectively define a shape; (b) check for ad-hoc `**kwargs` flows that propagate undeclared fields; (c) check for downstream stores (caches, queues, search indexes) whose schema now disagrees with the producer.

**K10. Intra-file sibling-helper pattern propagation**
- Did the diff add a new helper alongside an existing helper in the same module? List the defensive idioms the sibling helpers already use — None-guards, `getattr(..., default) or fallback`, scope-exit semantics, span construction — and verify the new helper inherits each one.
- When sibling helper A uses pattern P and the new helper B in the same file omits P, that omission is a K10 finding even when B is internally correct. Cite both helpers as the conflict pair.
- Adversarial probes: (a) diff the new helper's guard clauses against each sibling's guard clauses line-for-line; (b) check whether the new helper handles the same edge inputs (None, missing key, empty collection) the siblings handle; (c) check whether the new helper's return-shape and scope-exit behavior match the sibling cohort's contract.

**K11. Intra-document internal contradiction**
- Do two sections of the same document make contradictory claims about the same subject? For example: one paragraph says X is hook-enforced while another lists X as non-blocking; one table row labels the subject `Foo` while another row labels the same subject `Bar`; one example shows shape A while another shows shape B for the same input.
- The contradiction is a K11 finding even when each statement is locally coherent. Cite both sections as the conflict pair and describe the contradiction a reader sees.
- Adversarial probes: (a) build a claim-by-subject index across the whole document and flag any subject with two divergent claims; (b) cross-check every invariant stated in prose against every table row that classifies the same subject; (c) cross-check every worked example's input/output shape against the canonical shape the document states elsewhere.

## Cross-bucket questions to answer at the end

Q1: Is there a pattern in this diff where the primary site is updated but a parallel site (any sub-bucket) stays stale? Cite both the diff line that was changed AND the unchanged-but-should-have-changed line.

Q2: What's the worst contradiction introduced by this change — the one most likely to silently produce contradictory behavior at runtime when the parallel-but-unchanged site is exercised? Cite the changed line and the parallel unchanged line by `path:line`.

Q3: Which existing test, doc, or downstream consumer is the strongest witness to the contradiction — i.e., which surface passes / reads coherently *only because* the parallel site was not updated alongside the diff?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket K1-K11, produce Shape A or Shape B (with at least 3 probes). Each Shape A finding must cite BOTH the diff line that was changed AND the parallel line that was missed; the conflict lives in the pair of lines. Category K Shape A findings always cite TWO line locations: the changed line and the unchanged-but-should-have-changed line. The `failure_mode` should describe the contradiction between the two states. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
