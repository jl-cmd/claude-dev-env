# Category O — Docstring / fixture-prose vs implementation drift

**What this category audits:** module docstrings, fixture docstrings, helper-function docstrings, and free-form narrative prose inside docstrings (step ordering, named sentinels, predicate-breadth claims, list-of-responsibilities sentences) whose claims diverge from the implementation they describe. The gate-time `check_docstring_args_match_signature` validator covers only the `Args:` section parameter names; every other docstring claim — module-level `"This module detects X"`, fixture-level `"readability is disabled for these tests"`, predicate-level `"resolves to shared temp only"`, step-ordering narrative `"strip ceremony, then drop blockquotes"` — drifts past it.

**Examples of Category O findings:**
- A module docstring says the module recovers PR numbers, but a refactor split that logic into a sibling module.
- A fixture docstring asserts a global disable invariant that sibling tests in the same file explicitly violate.
- A predicate name and docstring promise a narrow check, but the body also matches a broader input class (HOME/TMP env vars when the docstring says shared-temp only).
- A docstring lists three responsibilities; only one is implemented, the other two live elsewhere.
- A docstring describes step ordering `A then B`; the body does `B then A`.
- A docstring references a sentinel marker (`# pragma: no-tdd-gate`) or filename shape (`test_code-rules-enforcer.py`) that the module body and the repo's naming convention do not use.

## Division of labor

This file is the **single thick source** for Category O judgment (sub-buckets O1–O9, the write-time gate inventory, free-form checklists, and worked examples).

| Surface | Role |
|---|---|
| `packages/claude-dev-env/rules/docstring-prose-matches-implementation.md` | Always-on write-time policy: the policy sentence, a compact checklist a writer applies at Write/Edit, and a pointer here. |
| **This rubric** | On-demand thick home. The code-quality agent loads it per category. Holds every judgment standard, gate inventory, and worked example. |
| `packages/claude-dev-env/audit-rubrics/prompts/category-o-docstring-vs-impl-drift.md` | Variant C audit template: source-material slots, forced-exhaustion protocol, adversarial probes, cross-bucket questions, output shape, and a PR worked example. Points here for the judgment standard. |

Plainness for a general developer (diagram-first shape) also lives under O9; the write-time companion rule for that slice is `packages/claude-dev-env/rules/plain-illustrative-docstrings.md`.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category O)

Decomposition is by the **kind of docstring claim** that needs to be cross-checked against the implementation.

| ID | Axis name | Concrete checks |
|---|---|---|
| O1 | Module-level responsibility verbs | A module docstring uses verbs (`detects`, `validates`, `enforces`, `recovers`, `parses`, `routes`) — every claimed responsibility is implemented by an exported symbol in the same module. Symbols absent from the module body should not appear as this module's responsibilities. A module whose one-line docstring scopes its contents to user-facing text (`User-facing strings: CLI flag names, help text, and log messages`) also names every category of constant the body holds. When the body also defines serialization field keys (`JSONL_FIELD_*`), run-metadata schema keys (`RUN_METADATA_CLI_ARG_KEY_*`), or runtime config (`STDOUT_ENCODING`, `MAIN_LOGGING_FORMAT_STRING`), the strings-only summary under-describes the module. Broaden the summary to name the data-schema keys and runtime config. The `check_module_docstring_scope_omits_data_schema_constants` gate blocks this drift at Write/Edit time when the summary claims a user-facing-text scope and names no data-schema or runtime-config category. |
| O2 | Fixture docstring vs sibling-test behavior | An autouse / module-scope fixture docstring asserts an invariant (`readability is disabled`, `network is mocked`, `tmp_path is empty`). No sibling test in the same module explicitly opts out of the invariant. |
| O3 | Predicate-name and -docstring vs body breadth | A boolean helper's name and docstring promise a narrow predicate. Walk the body's branches: every branch's `return True` path is consistent with the promised name. Bodies that accept inputs broader than the name (`_dir_value_resolves_to_shared_temp` also accepting HOME/TMP env-derived paths) are O3 findings. |
| O4 | Step-ordering narrative | A docstring describes processing as `A then B then C`. Walk the body and confirm the call order matches. Mismatched order is an O4 finding regardless of whether the final output is the same. A docstring step enumeration that names the body's linear steps but omits a corrective workflow step the body guards inside an `if`/`elif` branch (`if not await cancel_and_reinitiate_update(...): return`) is also an O4 finding: the reader trusts the step list to be complete and misses the conditional path. The branch-guarded-dispatch shape of this drift — a docstring that names two or more linear-step callees while the body guards a two-or-more-token dispatch callee inside a branch whose name the prose never spells out — is gated deterministically at Write/Edit time by `check_docstring_step_enumeration_dispatch_coverage` (`packages/claude-dev-env/hooks/blocking/code_rules_docstrings.py`), so the audit lane focuses on the step-ordering shapes the gate cannot match (re-ordered steps, plain unguarded steps the prose omits). |
| O5 | Named-sentinel / filename references | A docstring names a sentinel marker, environment variable, filename, or magic string. Confirm the named token actually exists in the module body or in the repo's naming convention. |
| O6 | Free-form `Args:`-adjacent claims | A docstring's `Returns:` / `Raises:` / `Note:` / `Example:` sections make claims (`returns shared-temp only`, `raises ValueError on missing key`). Verify each claim against the body. When a docstring enumerates the inputs a body counts (a "field counts as read when ..." list, a list of conditions treated as a match, a list of cases the body skips), list every union member and every suppressor the body applies (`read_names = a \| b \| c`, each early-return guard) and confirm each appears in the prose enumeration. A union member or suppressor the body applies but the prose omits is an O6 finding. When a docstring sentence excludes a named category of input from what the function flags (`X are not dispatch steps`, `Y is not a match`), confirm the axis the prose excludes on is the axis the body's branch condition actually keys on. A body that flags a call when it sits inside an `If.test` guard, paired with prose that excludes by the call's receiver shape (`method-on-local calls inside a branch are not dispatch steps`), is an O6 finding: a guarded method-on-local call is flagged even though the prose lists it as excluded — the exclusion is keyed to the wrong axis. A thin delegating method whose docstring names its actions and points at the home of the real body lists the same actions the delegated function's own summary lists; when an edit moves one action out of the delegated body, the same edit rewords both summaries (`check_docstring_delegation_summary_enumeration_drift`). A conditional bullet in the delegated prose also names every exception the body honors — that conditional-completeness slice stays a judgment call for this lane. A `Returns:` that names the mechanism, tool, or output format the function produces (`instructing a StructuredOutput summary`, `returns a YAML document`, `emits a JSON object`) matches the artifact the body actually builds. A dataclass or `TypedDict` field documented in the class `Attributes:` block states what the field means for one record; when the code sets that field the same way for every record (a run-mode flag such as `is_dry_run = not is_execute`), the description states the run-mode meaning, not a per-record outcome (`check_docstring_field_runmode_outcome` covers the single-file shape). Many deterministic O6 shapes are gated at Write/Edit time — see **Write-time gate inventory** below — so the audit lane focuses on the free-form shapes the gates cannot match. |
| O7 | Module-doc-vs-split-module after refactor | When a refactor moves a responsibility to a sibling module, the originating module's docstring and the receiving module's docstring both describe the home of that responsibility. A module docstring should describe only the responsibilities it owns. |
| O8 | Companion-doc ordering/content vs producer | When a PR changes a producer function's ordering or union, read that skill's companion `SKILL.md` and sibling `.md` docs for any sentence naming the same produced artifact (a file path, a JSON key, a named list). A doc sentence that claims the artifact is `sorted` / `alphabetical` / `in sorted order`, or holds `just the at-risk names` / `only the current set`, while the producer merges stored names with new names and appends — preserving file order, not re-sorting the union — is an O8 finding on both counts (wrong order claim, hidden merged-in entries). The finding stands even when the PR diff never touched the `.md` file, because the behavior change orphaned the doc claim. A producer docstring asserting that no consumer reads its output yet (`producer-only artifact`, `no submission-run consumer reads it yet`) is the deterministic slice of this companion-doc producer/consumer drift (`check_docstring_no_consumer_claim`). |
| O9 | Python docstring plainness for a general developer | A changed module / class / public-function docstring's narrative prose — the summary and description before the first `Args:` / `Returns:` / `Raises:` / `Yields:` section — reads plainly and paints a concrete scene a general developer follows on first read. Flag a narrative that stacks abstract machinery nouns into a wall (`the SIGINT install/restore/installability check, the atexit terminal-record registration, and the interrupted-run finalizer`), that defines a thing by what it is not (`the non-promoter-specific machinery`), or that runs one sentence long while joining clauses with an em-dash or a semicolon. The diagram-first shape carries this best: a summary line, then a `::` example block or a doctest that shows a concrete input and its marked outcome, then a couple of short prose lines. The deterministic run-on mark is gated at Write/Edit time by `check_docstring_runon_sentence` in `code_rules_docstrings.py`, and a narrative that runs more than six prose lines with no such block is gated by `check_docstring_prose_wall_without_illustration` in the same module, so this lane carries the judgment the gates cannot: whether a stranger to the code pictures the moment, the input, and the outcome after one read, and whether the diagram truly illustrates — a real input, a marked outcome, an `ok:` / `flag:` contrast a reader learns from. See `../../rules/plain-illustrative-docstrings.md`. |

---

## Write-time gate inventory

Deterministic slices of Category O that fire at Write/Edit. The free-form rest stays judgment (this rubric + the audit prompt).

### Python — `packages/claude-dev-env/hooks/blocking/code_rules_docstrings.py`

| Gate | Drift it blocks |
|---|---|
| `check_docstring_args_match_signature` | `Args:` section parameter names vs the signature. |
| `check_docstring_delegation_summary_enumeration_drift` | Thin wrapper summary enumerates actions the same-named sibling summary omits (both save directions). |
| `check_docstring_names_absent_type_checking_gate` | Docstring names a `TYPE_CHECKING` gate or `type-checking-gate` helper family while no identifier in the module carries the `type_checking` marker. |
| `check_docstring_length_constant_superlative_vs_exact_gate` | Module docstring describes an integer `*_LENGTH` constant with a superlative or range word while every consumer compares `len(...)` with `==`/`!=` (exact-length gate). Scans the constant module's package tree. |
| `check_docstring_fallback_branch_coverage` | Summary scopes a fallback to one condition while the body routes to that fallback from two or more early-return guards. |
| `check_class_docstring_names_public_methods` | Class docstring is a single summary line while the class exposes two or more public methods the summary never names. |
| `check_docstring_no_consumer_claim` | Producer docstring asserts no consumer reads its output yet. |
| `check_docstring_returns_plural_cardinality` | `Returns:` names a dict-key prefix family with a plural noun while the returned dict holds exactly one key in that family. |
| `check_docstring_args_single_line_scope_vs_span` | `Args:` scopes a finding to one named line while the body scopes through a `range(...)` span-intersection. |
| `check_docstring_cardinal_count_matches_constant_family` | Docstring states a cardinal count of an outcome family and lists members, while the module references more members of the same `UPPER_SNAKE` family than the count names. Runs on test modules as well as production. |
| `check_docstring_raises_unraisable_largezipfile` | `Raises:` names `zipfile.LargeZipFile` while the writer opens with `allowZip64` at its default of True. |
| `check_docstring_no_network_claim_with_metadata_access` | Docstring promises a path returns without touching the network while the body calls path-metadata methods (`is_file`, `is_dir`, `exists`, `stat`, `lstat`). |
| `check_docstring_step_enumeration_dispatch_coverage` | Step-enumeration docstring omits a two-or-more-token dispatch step the body guards inside a branch. |
| `check_docstring_unguarded_malformed_payload_claim` | Docstring promises a malformed payload resolves to None while a payload subscript sits outside the try/except whose handler returns None. |
| `check_docstring_field_runmode_outcome` | `Attributes:` entry for a run-mode flag field (name carrying `dry_run`) whose description carries a per-record write-outcome phrase and no run-mode phrase. |
| `check_module_docstring_scope_omits_data_schema_constants` | Module summary claims user-facing-text scope while the body also defines data-schema or runtime-config constants. |
| `check_module_docstring_names_public_checks` | One-line check-registry module docstring omits a public `check_*` function the module dispatches. |
| `check_docstring_tuple_enumeration_match` | Docstring enumerates inline-code tokens that drift from the literal string tuple the body reads (a listed token the tuple lacks, or a tuple member the prose omits). |
| `check_docstring_punctuation_mark_enumeration_coverage` | Docstring names some marks of a punctuation-glyph tuple by their English names but omits one the tuple holds. |
| `check_docstring_no_inline_literal_claim` | Constants-module docstring asserts no literals appear inline in a companion file. |
| `check_docstring_names_undefined_constant` | Docstring names an `UPPER_SNAKE` constant identifier nothing in the module backs. |
| `check_docstring_runon_sentence` | Narrative run-on mark (O9 backstop). |
| `check_docstring_prose_wall_without_illustration` | Narrative longer than six prose lines with no `::` / doctest illustration (O9 backstop). |

### JavaScript / `.mjs` — `packages/claude-dev-env/hooks/blocking/code_rules_imports_logging.py`

These are the `.mjs` slice of the same Category O standard. The Python AST docstring gates never inspect JavaScript source.

| Gate | Drift it blocks |
|---|---|
| `check_js_resume_task_enumeration_coverage` | A `spawn<Role>Agent` JSDoc enumerates sibling `resume<Role>Agent` resume tasks and omits a `task === '<name>'` branch the resume body dispatches on. |
| `check_js_returns_object_schemaless_branch` | `@returns {Promise<object>}` JSDoc whose body returns the same agent-spawn helper both with a `schema` options object and without one (schema-less branch resolves to a transcript string). |
| `check_js_sibling_return_object_key_drift` | A `return { ... }` object literal whose key set misses exactly one key of a sibling return in the same function or module scope. Discriminated-union variants and two-or-more-key exit shapes are left alone. |
| `check_js_bare_flag_return_directive` | A `return <name>: true`/`false` prose directive anywhere in the file that repeats a status flag a stated full-result contract rules out (no proximity or ordering check between the two). |

---

## Free-form judgment checklist (write time and audit)

Read the body and the docstring side by side. Apply each check that matches the prose. When the body changes the set of behaviors it applies, the same edit updates the prose enumeration.

- **Read-source / match-source unions.** A body that computes `read_names = a | b | c` (or any union of "what counts") names each union member in the prose enumeration.
- **Suppressor / skip lists.** A body with several early returns that suppress the check names each suppressor in the prose.
- **Shared fallback routes.** A summary that scopes a fallback call to one condition names every condition that reaches that call. Gated form: `check_docstring_fallback_branch_coverage`.
- **Step order.** A docstring that says `A then B then C` matches the call order in the body. A step enumeration that names the body's linear steps also names every corrective step the body guards inside an `if`/`elif` branch. Gated form: `check_docstring_step_enumeration_dispatch_coverage`.
- **Delegation pointer summaries.** A thin delegating method whose docstring names its actions and points at the home of the real body lists the same actions the delegated function's own summary lists. Gated form: `check_docstring_delegation_summary_enumeration_drift`. A conditional bullet in the delegated prose also names every exception the body honors — judgment for this lane.
- **JS/`.mjs` resume-task, `@returns` object, sibling return keys, bare-flag directives.** See the JavaScript gate inventory above.
- **Returns-clause cardinality.** A `Returns:` clause that names a dict-key prefix family with a plural noun matches the count of keys in that family in the returned dict literal. Gated form: `check_docstring_returns_plural_cardinality`.
- **Length-constant superlative vs exact gate.** A module docstring that describes an integer `*_LENGTH` constant with a superlative or range word matches how the code consumes the constant. Gated form: `check_docstring_length_constant_superlative_vs_exact_gate`.
- **Args single-line scope vs span body.** An `Args:` entry that scopes a finding to one named line matches the line breadth the body scopes by. Gated form: `check_docstring_args_single_line_scope_vs_span`.
- **Cardinal-count enumerations.** A docstring that states a count of an outcome family and lists those members names every member of that family the module references. Gated form: `check_docstring_cardinal_count_matches_constant_family`.
- **Raises-clause reachability for `LargeZipFile`.** A `Raises:` clause that names `zipfile.LargeZipFile` matches a writer the body opens with ZIP64 forbidden. Gated form: `check_docstring_raises_unraisable_largezipfile`.
- **Module summary scope versus data-schema constants.** A module whose one-line docstring scopes its contents to user-facing text names every category of constant the body holds. Gated form: `check_module_docstring_scope_omits_data_schema_constants`.
- **Field meaning: run mode versus per record.** A dataclass or `TypedDict` field documented in the class `Attributes:` block states what the field means for one record. When the code sets that field the same way for every record, the description states the run-mode meaning. Gated form: `check_docstring_field_runmode_outcome` (single-file shape); assignment in another module stays judgment.
- **Predicate breadth.** A boolean helper whose prose promises a narrow check accepts only the inputs the prose names — no broader input class the name and prose do not mention.
- **Exclusion-clause distinguisher.** A docstring sentence that says a named category of input "are not" / "is not" the thing the function flags keys the exclusion to the same axis the body's classification keys on. Read the body's actual branch condition, then state the exclusion on that same axis.
- **Companion-doc ordering and content claims.** A `SKILL.md` (or sibling `.md`) sentence that names a produced artifact and claims its order or its content matches the producer function's docstring and body for that same artifact. The two move together in one commit, even when the producer edit does not touch the `.md` file.
- **TYPE_CHECKING gate claim vs code.** A docstring that names a `TYPE_CHECKING` gate-detection step matches a module whose code handles TYPE_CHECKING. Gated form: `check_docstring_names_absent_type_checking_gate`.

---

## Worked example (union enumeration)

A `@dataclass` dead-field check builds its set of "field counts as read" sources by union:

```python
read_names = (
    attribute_read_names
    | dynamic_literal_names
    | _match_pattern_attribute_names(tree)
    | _exported_names(tree)
)
```

A docstring that enumerates "attribute read, augmented-assignment target, class-pattern keyword, literal `getattr`/`attrgetter`" but omits the `__all__` source (`_exported_names`) is drifted: a field whose name appears in `__all__` is treated as read, and the prose hides that. The fix adds the missing source to the enumeration so the list matches the union.

---

## Sample prompt

The reusable Variant C template for Category O is in [`../prompts/category-o-docstring-vs-impl-drift.md`](../prompts/category-o-docstring-vs-impl-drift.md). Inline every changed module's docstring (module-level + every helper-function docstring whose function body was touched + every fixture docstring) alongside the symbols defined in the same module under `## Source material`.

## Why Category O matters as its own bucket

Signature-shaped claims — parameter names, return types, exceptions in the `Raises:` block — have a gate-time validator (`check_docstring_args_match_signature`) and signature-oriented audit categories to catch them. Free-form narrative prose in docstrings is the other half of the docstring contract: the part that tells a reader what the module is for, what the fixture does, what the predicate means. When that prose drifts from the body, the gate cannot catch it because there is no signature to compare against. Category O forces the audit teammate to list docstring claims and verify each against the body, the same way signature claims are verified against the body.

A docstring enumeration earns its place by being trustworthy. A complete list lets a reader reason about the function without scanning the body; a list missing one item is worse than no list, because it asserts completeness it does not have.
