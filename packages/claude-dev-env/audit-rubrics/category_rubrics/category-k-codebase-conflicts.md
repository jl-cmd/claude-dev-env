# Category K — Codebase conflicts (incomplete propagation)

**What this category audits:** changes that update one site of a pattern but leave parallel sites stale, producing contradictory behavior between the new and old code paths. Common when a name is renamed in one file, a default is changed in one constant but duplicated as a literal elsewhere, a fallback path is updated but the primary path isn't (or vice versa), or a feature flag is flipped in one branch of conditional code but missed in others.

**Why this category is narrow but recurrent:** the change *itself* is internally consistent — the diff looks correct in isolation. The bug only surfaces when you compare the diff against the *unchanged* parts of the codebase that share a contract with what was changed. Linters and unit tests rarely catch these; reviewers only catch them by mentally cross-referencing the change against every parallel site.

**Canonical example:** [jl-cmd/claude-code-config PR #397, comment r3210166636](https://github.com/jl-cmd/claude-code-config/pull/397#discussion_r3210166636). The PR updated an instruction at line 137 to direct the model to use `AskUserQuestion` instead of bailing out with "I don't know." But the fallback `skill_reference` string at lines 123–127 in the same file *still* told the model to "reply 'I don't know'." Both strings interpolate into the same `reason` field, giving the model contradictory guidance — the exact escape hatch the PR was meant to close remained available through the unchanged path.

## Other typical patterns

- A function signature renamed in the definition; one of three call sites still uses the old kwarg name.
- A CSS class renamed in the stylesheet; templates still reference the old name.
- A config key renamed in `defaults.yml`; a fallback in the loader still reads the old key.
- A feature flag deprecated; one conditional branch still checks the old flag.
- An enum variant renamed; documentation, error messages, or test fixtures still reference the old name.
- A constant updated in one constants file; a duplicated literal remains in a sibling file.
- A type signature widened in the producer; a consumer's type annotation still claims the narrower type.
- A migration that adds a column; ORM model file gets the column but a raw-SQL migration query elsewhere doesn't.
- An API endpoint version bumped; the SDK in the same repo still hits the old version.
- A README section and the implementation it describes disagree after a behavior change — one surface carries the new contract, the other still describes the old one.

- A module's existing `_resolve_base_ref` guards a missing remote with `getattr(remote, "name", "") or DEFAULT_REMOTE`; the diff adds `_resolve_head_ref` beside it that dereferences `remote.name` bare, crashing on the detached-HEAD case its sibling survives.
- A rules reference whose enforcement table marks letter J with ⚡ (blocking hook) while its audit-surface section three paragraphs later lists J under "non-blocking, multi-file reasoning" — one letter, two contradictory enforcement claims in one document.
- A hooks.json with the same hook registered in two parallel matcher blocks (Write|Edit + MultiEdit) when an existing Write|Edit|MultiEdit block already handles the same surface.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category K)

Decomposition is by the **kind of parallel site** that needs to stay in sync with what the diff changed.

| ID | Axis name | Concrete checks |
|---|---|---|
| K1 | Multi-site name renames | A renamed symbol — every reference (call sites, imports, type annotations, error messages, docs, tests) updated? |
| K2 | Duplicated constants / defaults | A value changed in one source-of-truth — every duplicated literal in sibling files / cross-language partners updated? |
| K3 | Primary path vs fallback path | A behavior changed on the happy path — does the fallback / error path produce consistent behavior? |
| K4 | Feature flag / version gate consistency | A flag flipped or version bumped — every guard, conditional branch, and consumer checked? |
| K5 | Producer-vs-consumer type contracts | A producer's output shape changed — every consumer's expected shape still matches? |
| K6 | Code vs documentation sync (cross-surface) | An implementation behavior changed — README, ADRs, skill docs, comments still describe the new behavior? Docstring-prose drift belongs to Category O (docstring / fixture-prose vs implementation drift); K6 owns documentation surfaces outside docstrings. |
| K7 | Code vs test sync | An implementation behavior changed — every test (positive, negative, edge) still expresses the right contract? |
| K8 | Cross-file / cross-language contract sync | A value or shape that lives in multiple languages or files (e.g., PowerShell + Python) — both sides reflect the change? |
| K9 | Schema / data-shape propagation | A schema field added/removed/renamed — migrations, ORM, serializers, fixtures, API docs all updated? |
| K10 | Intra-file sibling-helper pattern propagation | When the diff adds a new helper alongside an existing helper in the same module, the new helper inherits the established defensive idioms (None-guards, `getattr(..., default) or fallback`, scope-exit semantics, span construction). When sibling helper A uses pattern P and newly-added helper B in the same file omits P, that omission is a K10 finding regardless of whether B is internally correct. |
| K11 | Intra-document internal contradiction | When two sections of the same document make contradictory claims about the same subject (one paragraph says X is hook-enforced, another lists X as non-blocking; one table row says label is `Foo`, another row labels the same subject `Bar`; one example shows shape A, another shows shape B for the same input), the contradiction is a K11 finding even when each statement is locally coherent. |

Customize per-artifact: for a single-file change with no parallel sites, Category K reduces to "verify there are no parallel sites we missed." For a cross-cutting change (e.g., renaming a public API), Category K may need 8+ sub-buckets to enumerate every consumer surface.

---

## Sample prompt

The reusable Variant C template for Category K is in [`../prompts/category-k-codebase-conflicts.md`](../prompts/category-k-codebase-conflicts.md). Unlike other categories, the Category K source-material block needs to include both the diff AND the unchanged parallel files the agent must cross-reference.

## Why Category K matters as its own bucket

Categories A–J describe failure modes within a single change. Category K describes the failure mode that emerges *between* the change and what didn't change. A reviewer walking only A–J reads the diff and judges it on its own merits — they can miss K entirely because the diff is internally consistent. K forces the reviewer to read the unchanged code with the diff in hand and look for sites that *should* have been touched.

The PR #397 case demonstrates the cost of not running K: a security-related instruction (close the "I don't know" escape hatch) was correctly updated in the primary path but left wide open in the fallback, defeating the purpose of the change. The diff looked clean. Only by reading lines 123–127 *with* the new line 137 in mind could the contradiction surface.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category K walks for that diff:
- K2: `[int]$AgeSeconds = 120` (PowerShell installer) duplicates `DEFAULT_AGE_SECONDS = 120` (`config/sweep_config.py`). Both files are new in the same PR, so there's no "stale parallel site" yet — but a future change to one without the other would land squarely in K2.
- K8: same as K2, framed as cross-language contract.
- K1, K3–K7, K9: not applicable to this PR (no renames, no schema changes, no feature flags). Verified clean.
