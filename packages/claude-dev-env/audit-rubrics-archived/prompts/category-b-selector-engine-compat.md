Audit [REPO/ARTIFACT] [TARGET_ID] for **Category B only** (selector / query / engine compatibility). Skip A, C–P. Sub-bucket forced-exhaustion mode: Category B is decomposed into 7 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA: repo, ref/SHA, PR or commit range, file count, language matrix, declared engine/runtime/browser/DB targets — fill before running.]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — see ../source-material-section-types.md for chunking guidance.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**B1. CSS / DOM selector vs target browser engine**
- Every CSS selector in the diff — verify pseudo-class support (`:has()`, `:is()`, `:where()`, `:focus-visible`, `:focus-within`) against every browser engine in the declared support matrix; flag any selector that requires an engine version newer than the declared minimum.
- Every attribute selector, `::part()`, `::slotted()`, and shadow-DOM piercing pattern — verify the target engine exposes the matching DOM (e.g. shadow boundaries, scoped styles).
- Every selector fed to `document.querySelector` / `querySelectorAll` / jQuery `$()` / Selenium `By.css_selector` / Playwright `page.locator` — verify the **runtime** selector engine matches the **target browser** engine; a Node-side jsdom selector parse can succeed where the browser fails (or vice versa).
- Every CSS feature query (`@supports`), media query level, and container query — verify availability across the declared engine matrix and that fallback paths exist for engines that do not parse the syntax.
- Every test-runner DOM assertion (snapshot, `outerHTML`/`innerHTML` equality, computed-style read) — verify the runner uses the same engine as the production target, or document the divergence.
- Cross-engine quirks: WebKit-only `-webkit-` prefixes, Gecko-only `-moz-`, IE/Edge legacy filters; flag any production reliance on a single-engine prefix without a standard fallback.

**B2. SQL syntax vs database version**
- Every SQL string literal, ORM-generated query, and migration — verify CTE (`WITH … AS`) support against the declared minimum DB version (MySQL ≥ 8.0, MariaDB ≥ 10.2, SQLite ≥ 3.8.3, etc.).
- Every window function (`OVER`, `PARTITION BY`, `ROWS BETWEEN`), `LATERAL` join, `FILTER` clause, and `MERGE`/`UPSERT` syntax — verify the target dialect and version supports it.
- Every JSON operator (`->`, `->>`, `@>`, `?`, `jsonb_path_query`, `JSON_VALUE`, `JSON_EXTRACT`) — verify dialect-specific syntax matches the declared engine.
- Every full-text search clause (`MATCH … AGAINST`, `to_tsvector`, `CONTAINS`, `FREETEXT`) and every spatial / geometry function — verify engine and version availability.
- Every dialect-specific function (`GROUP_CONCAT` vs `STRING_AGG` vs `LISTAGG`, `IFNULL` vs `NVL` vs `COALESCE`, `LIMIT n` vs `TOP n` vs `FETCH FIRST n ROWS`).
- Every migration's reversibility and online-DDL safety on the target version (ALGORITHM/LOCK hints, transactional DDL availability).

**B3. Regex syntax vs engine flavor**
- Every regex in the diff — verify lookbehind support (POSIX ERE has none; Python `re` requires fixed-width lookbehind; Python `regex`, PCRE, Perl, .NET, JS V8 ≥ 2018 allow variable-width).
- Every named group — verify `(?P<name>…)` (Python) vs `(?<name>…)` (PCRE/JS/.NET) vs `(?'name'…)` (.NET only) matches the engine in use.
- Every backreference, recursion (`(?R)`, `(?0)`), conditional (`(?(1)yes|no)`), atomic group (`(?>…)`), possessive quantifier (`*+`, `++`) — verify engine support.
- Every Unicode character class (`\p{L}`, `\p{Script=Greek}`) and Unicode flag (`u`, `re.UNICODE`) — verify the engine has Unicode tables compiled in and the flag is honored.
- Every regex passed across boundaries (Python → JS via JSON, server → client) — verify the consumer engine accepts the same flavor; flag any flavor-translation gap.
- Every f-string- or template-built regex — verify interpolated values are escaped (`re.escape`, `RegExp.escape` proposal, manual literal-quote helpers) so user-supplied input cannot inject metacharacters.

**B4. Shell / CLI / cmdlet syntax vs runtime version**
- Every PowerShell cmdlet — verify availability across the declared edition matrix (Windows PowerShell 5.1 ↔ PowerShell 7+ ↔ PowerShell on Linux/macOS) and version-specific parameter sets.
- Every shebang (`#!/usr/bin/env pwsh`, `#!/bin/bash`, `#!/usr/bin/env python3`) vs the interpreter resolved at runtime — flag mismatches between declared and invoked interpreter (e.g. shebang says `pwsh` but Python `subprocess.run(["powershell", …])` resolves to PS 5.1 on Windows).
- Every parameter set in a `param(...)` block — verify `[CmdletBinding(DefaultParameterSetName=…)]` is set when ambiguity is possible; missing default = `Parameter set cannot be resolved` at runtime.
- Every cmdlet flag combination — verify both flags belong to the same parameter set per Microsoft docs (e.g. `-RepetitionInterval` is an `-Once` parameter, NOT `-Daily`).
- Every bash-ism — `[[ ... ]]` (bash 3+ only, not POSIX `sh`), arrays, process substitution `<(…)`, `${var,,}` lower-case expansion (bash 4+), associative arrays — verify against the declared minimum shell.
- Every CLI flag deprecation across versions (`gh` flag changes, `git` porcelain v2, `docker` deprecated commands) — verify the declared minimum tool version still accepts the syntax in use.
- Every `Get-Command`, `command -v`, `which` lookup — verify error-handling parity (`-ErrorAction SilentlyContinue` on the failing path, `|| true`, `2>/dev/null`) so a missing dependency degrades gracefully across versions.

**B5. JSON path / XPath / structural query vs library**
- Every JSONPath expression — verify the target library's flavor (`jq` vs Python `jsonpath-ng` vs `jsonpath-rw` vs JS `jsonpath-plus` vs Goessner reference). Filter syntax (`[?(@.foo)]`), recursive descent (`..`), and slicing differ.
- Every XPath expression — verify XPath 1.0 vs 2.0 vs 3.0 functions (`matches()`, `tokenize()`, `string-join()` are 2.0+); flag any 2.0+ function fed to a 1.0-only engine like `lxml.etree`'s default.
- Every JSON Pointer (`/foo/bar/0`), JSON Patch op, and JMESPath query — verify library version and edge cases (escaped `~` and `/`).
- Every YAML/TOML structural query (`yq`, `tomlq`) — verify version flavor (`yq` v3 Python ↔ v4 Go are incompatible).
- Every cross-library round-trip: `jq` filter handed to a Python jsonpath consumer, or XPath compiled in lxml then serialized for libxslt — verify each consumer accepts the source flavor.

**B6. Search query DSL vs engine**
- Every Lucene/Elasticsearch query string — verify field syntax (`field:value`), required/excluded operators (`+`, `-`), fuzzy (`term~2`), proximity (`"a b"~5`), and wildcard rules (`*`, `?`) match the engine version's parser.
- Every Elasticsearch query DSL object (`match`, `bool`, `should`, `must`, `filter`, `term`, `terms`) — verify removed/renamed clauses across major versions (e.g. `query_string` defaults, `term` vs `match` for `text` fields, mapping-type removal in ES 7+).
- Every Sourcegraph / OpenSearch / Solr query — verify dialect-specific operators and that the deployment has the relevant features enabled (e.g. ES `query_string` may be disabled for security).
- Every escaping rule for special characters in the DSL (`+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /`) — verify the producer escapes them before handing to the engine; flag any user-supplied input concatenated raw.
- Every analyzer assumption (whitespace, standard, keyword, ngram) — verify the index mapping matches what the query string assumes.

**B7. ORM vs raw SQL semantic differences**
- Every ORM filter expression — verify SQLAlchemy `.filter()` (Core/ORM expression) vs `.filter_by()` (kwargs only, equality only) usage; flag any `.filter_by()` passed boolean operators it does not support.
- Every Django Q expression, F expression, `Subquery`, `OuterRef`, `Exists` — verify the ORM version supports the construct (e.g. `FilteredRelation` is Django 2.0+, `Window` is 2.0+).
- Every lazy vs eager loading decision (`select_related`, `prefetch_related`, SQLAlchemy `joinedload`/`selectinload`/`subqueryload`) — verify N+1 risk and that the chosen strategy matches the dialect's join semantics.
- Every transaction context manager (`with session.begin():`, `@transaction.atomic`, `db.session.commit()`) — verify isolation level, autocommit behavior, and savepoint support match the declared DB version.
- Every raw SQL escape hatch (`session.execute(text(...))`, `cursor.execute()`, `RawSQL`) — verify it bypasses the ORM's dialect-rewriting and ensure the literal SQL still satisfies B2 (engine version) constraints.
- Every model field type (`JSONField`, `ArrayField`, `HStoreField`) — verify the backing DB version supports the underlying column type and operators.

## Cross-bucket questions to answer at the end

Q1: Are there any compatibility constraints that span two sub-buckets that single-bucket analysis would miss? (E.g. a query string that crosses B3 regex flavor + B6 search DSL escaping; a script that crosses B4 cmdlet syntax + B3 format-string interpolation; an ORM expression that crosses B7 lazy-load semantics + B2 dialect SQL.)

Q2: What's the worst engine-incompatibility hazard introduced by this artifact? Cite file:line. Rank by (a) likelihood the deployment hits the incompatible engine, (b) severity when it does, (c) detectability before production.

Q3: Where would a future engine/library upgrade most likely break a selector, query, cmdlet, or interpolated pattern in this artifact? Name the most fragile lines and the upgrade path that would break them (browser version bump, DB major upgrade, PowerShell edition change, ORM major version, search-engine major version).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket B1-B7, produce Shape A (at least 1 finding) or Shape B (proof-of-absence with at least 3 distinct adversarial probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities, undeclared engine targets, or cases where the declared support matrix is incomplete. Read-only. No edits, no commits.
