# Category B — Selector / query / engine compatibility

**What this category audits:** CSS selectors, SQL queries, regex patterns, JSON-path / XPath, search-DSL queries, CLI / cmdlet syntax — looking for incompatibility with the specific engine, runtime version, or dialect in use.

**Examples of Category B findings:**
- A CSS selector uses a pseudo-class the target browser engine lacks (e.g. `:has()` on Firefox before 121).
- A SQL `WITH ... AS (... )` CTE on a MySQL version older than 8.0.
- A regex lookbehind in POSIX ERE (which has no lookbehind support).
- A PowerShell cmdlet parameter that exists in PS 7+ but not in Windows PowerShell 5.1.
- A Lucene query syntax fragment fed to an Elasticsearch endpoint that disabled query_string.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category B)

| ID | Axis name | Concrete checks |
|---|---|---|
| B1 | CSS / DOM selector vs target browser engine | Pseudo-class support; attribute selectors; `:has()`, `:is()`, `:where()` availability across the supported engine matrix. |
| B2 | SQL syntax vs database version | Window functions, CTEs, JSON operators, dialect-specific functions vs the declared minimum DB version. |
| B3 | Regex syntax vs engine flavor | Lookbehind / lookahead support; named groups (`(?P<…>)` vs `(?<…>)`); backreferences; Unicode character classes. |
| B4 | Shell / CLI / cmdlet syntax vs runtime version | PowerShell 5.1 vs 7+; bash 3 vs 5; cmdlet parameters added in later versions; CLI flag deprecations. |
| B5 | JSON path / XPath / structural query vs library | jq vs Python jsonpath-ng vs JavaScript jsonpath syntax; XPath 1.0 vs 2.0/3.0 functions. |
| B6 | Search query DSL vs engine | Lucene / Elasticsearch / Zoekt / OpenSearch syntax; differences in escaping, fuzzy matching, multi-field queries. |
| B7 | ORM vs raw SQL semantic differences | SQLAlchemy `.filter()` vs `.filter_by()`; Django Q expressions vs raw SQL; lazy vs eager evaluation. |

Use 5–10 sub-buckets for any single audit. For an audit that doesn't touch SQL or web frontends, drop B1 / B2 entirely and split B4 across the relevant runtimes.

---

## Sample prompt

The reusable Variant C template for Category B is in [`../prompts/category-b-selector-engine-compat.md`](../prompts/category-b-selector-engine-compat.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's compat targets.

For a literal worked example using PR #394 inlined verbatim (Python + PowerShell scheduled-task installer), see [`category-a-api-contracts.md`](category-a-api-contracts.md) — the diff there is the canonical sample artifact. To audit the same PR for Category B specifically, copy the diff section from [`../prompts/category-a-api-contracts.md`](../prompts/category-a-api-contracts.md) and paste it under `## Source material` in the Category B prompt; the relevant Category B sub-buckets for PR #394 are B4 (PowerShell cmdlet version compat — `Get-ScheduledTask`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskAction` are Windows-only and require PS 5.1+) and B3 (the `(Get-Item '{path}')` pattern in the test helper).
