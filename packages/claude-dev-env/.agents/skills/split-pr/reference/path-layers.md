# Path layers — context only

Path-layer labels (database, contracts, backend, frontend, tests, config) are
**judgment aids**, not hard gates. Vertical slice assignment overrides layer
buckets when tests must travel with the modules they cover.

| Layer hint | Typical paths |
|---|---|
| database | `**/migrations/**`, `**/schema.prisma` |
| contracts | `**/api/**/types*`, OpenAPI specs |
| backend | `**/services/**`, `**/handlers/**` |
| frontend | `**/components/**`, `**/*.tsx` |
| tests | `**/test_*.py`, `**/*_test.py`, `**/*.test.*` |
| config | lockfiles, `package.json`, CI workflows |

File count and layer count inform review; they never alone block a plan.
