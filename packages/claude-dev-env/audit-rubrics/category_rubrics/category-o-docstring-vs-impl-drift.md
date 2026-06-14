# Category O — Docstring / fixture-prose vs implementation drift

**What this category audits:** module docstrings, fixture docstrings, helper-function docstrings, and free-form narrative prose inside docstrings (step ordering, named sentinels, predicate-breadth claims, list-of-responsibilities sentences) whose claims diverge from the implementation they describe. The gate-time `check_docstring_args_match_signature` validator covers only the `Args:` section parameter names; every other docstring claim — module-level `"This module detects X"`, fixture-level `"readability is disabled for these tests"`, predicate-level `"resolves to shared temp only"`, step-ordering narrative `"strip ceremony, then drop blockquotes"` — drifts past it.

**Examples of Category O findings:**
- A module docstring says the module recovers PR numbers, but a refactor split that logic into a sibling module.
- A fixture docstring asserts a global disable invariant that sibling tests in the same file explicitly violate.
- A predicate name and docstring promise a narrow check, but the body also matches a broader input class (HOME/TMP env vars when the docstring says shared-temp only).
- A docstring lists three responsibilities; only one is implemented, the other two live elsewhere.
- A docstring describes step ordering `A then B`; the body does `B then A`.
- A docstring references a sentinel marker (`# pragma: no-tdd-gate`) or filename shape (`test_code-rules-enforcer.py`) that the module body and the repo's naming convention do not use.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category O)

Decomposition is by the **kind of docstring claim** that needs to be cross-checked against the implementation.

| ID | Axis name | Concrete checks |
|---|---|---|
| O1 | Module-level responsibility verbs | A module docstring uses verbs (`detects`, `validates`, `enforces`, `recovers`, `parses`, `routes`) — every claimed responsibility is implemented by an exported symbol in the same module. Symbols absent from the module body should not appear as this module's responsibilities. |
| O2 | Fixture docstring vs sibling-test behavior | An autouse / module-scope fixture docstring asserts an invariant (`readability is disabled`, `network is mocked`, `tmp_path is empty`). No sibling test in the same module explicitly opts out of the invariant. |
| O3 | Predicate-name and -docstring vs body breadth | A boolean helper's name and docstring promise a narrow predicate. Walk the body's branches: every branch's `return True` path is consistent with the promised name. Bodies that accept inputs broader than the name (`_dir_value_resolves_to_shared_temp` also accepting HOME/TMP env-derived paths) are O3 findings. |
| O4 | Step-ordering narrative | A docstring describes processing as `A then B then C`. Walk the body and confirm the call order matches. Mismatched order is an O4 finding regardless of whether the final output is the same. |
| O5 | Named-sentinel / filename references | A docstring names a sentinel marker, environment variable, filename, or magic string. Confirm the named token actually exists in the module body or in the repo's naming convention. |
| O6 | Free-form `Args:`-adjacent claims | A docstring's `Returns:` / `Raises:` / `Note:` / `Example:` sections make claims (`returns shared-temp only`, `raises ValueError on missing key`). Verify each claim against the body. When a docstring enumerates the inputs a body counts (a "field counts as read when ..." list, a list of conditions treated as a match, a list of cases the body skips), list every union member and every suppressor the body applies (`read_names = a | b | c`, each early-return guard) and confirm each appears in the prose enumeration. A union member or suppressor the body applies but the prose omits is an O6 finding. A `Returns:` that names the mechanism, tool, or output format the function produces (`instructing a StructuredOutput summary`, `returns a YAML document`, `emits a JSON object`) matches the artifact the body actually builds: a prompt body that asks the agent to "Return strictly a JSON object" while the docstring claims it "instruct[s] a StructuredOutput" summary is an O6 finding, because the named tool appears nowhere in the emitted text. See `../../rules/docstring-prose-matches-implementation.md`. |
| O7 | Module-doc-vs-split-module after refactor | When a refactor moves a responsibility to a sibling module, the originating module's docstring and the receiving module's docstring both describe the home of that responsibility. A module docstring should describe only the responsibilities it owns. |

---

## Sample prompt

The reusable Variant C template for Category O is in [`../prompts/category-o-docstring-vs-impl-drift.md`](../prompts/category-o-docstring-vs-impl-drift.md). Inline every changed module's docstring (module-level + every helper-function docstring whose function body was touched + every fixture docstring) alongside the symbols defined in the same module under `## Source material`.

## Why Category O matters as its own bucket

Signature-shaped claims — parameter names, return types, exceptions in the `Raises:` block — have a gate-time validator (`check_docstring_args_match_signature`) and signature-oriented audit categories to catch them. Free-form narrative prose in docstrings is the other half of the docstring contract: the part that tells a reader what the module is for, what the fixture does, what the predicate means. When that prose drifts from the body, the gate cannot catch it because there is no signature to compare against. Category O forces the audit teammate to list docstring claims and verify each against the body, the same way signature claims are verified against the body.
