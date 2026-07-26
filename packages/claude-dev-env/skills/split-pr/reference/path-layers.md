# Path layers

Heuristics live in `scripts/split_pr_scripts_constants/config/categorize_constants.py` (`ALL_LAYER_PATH_RULES`). `assign_layer` walks that tuple top to bottom and returns the first layer whose pattern matches the lowercased POSIX path. An unmatched path falls through to `other`.

## Layer catalog

**This table is not the evaluation order.** It is grouped by **dependency order** — the order slices stack in, matching `ALL_LAYER_ORDER` — and serves as a reading aid for slice order only. To predict which layer a given path lands in, read [Match order](#match-order) below, which lists all 18 rules in the sequence `assign_layer` walks. The two orders differ: the tests and docs rules fire ahead of every database, contracts, and backend rule.

| Layer | Typical paths |
|---|---|
| `database` | `migrations/`, `prisma/`, `alembic/`, `flyway/`, `db/`, `*.sql` |
| `contracts` | `types/`, `contracts/`, `schemas/`, `*.proto` |
| `backend` | `api/`, `services/`, `server/`, `backend/`, `controllers/`, `middleware/`, `handlers/`, `hooks/<name>/`, `skills/<name>/scripts/`, `_shared/<name>/scripts/` |
| `frontend` | `components/`, `pages/`, `views/`, `ui/`, `frontend/`, `styles/`, `contexts/`, `screens/` |
| `tests` | `tests/`, `__tests__/`, `specs/`, `test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*` |
| `config` | `.github/`, `package.json`, lockfiles, `tsconfig*.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `requirements*.txt` |
| `docs` | `docs/`, `*.md`, `*.rst` |
| `other` | unmatched — re-bucket before proposal |

## Match order

`ALL_LAYER_PATH_RULES` is evaluated in this sequence, and the first hit wins:

| # | Layer | Pattern covers |
|---|---|---|
| 1 | `tests` | `tests/`, `test/`, `__tests__/`, `specs/`, `spec/` directories |
| 2 | `tests` | `test_*.py` |
| 3 | `tests` | `*.test.<ext>`, `*.spec.<ext>` |
| 4 | `tests` | `*_test.py` |
| 5 | `docs` | `docs/`, `doc/` directories |
| 6 | `docs` | `*.md`, `*.rst` |
| 7 | `database` | `migrations/`, `prisma/`, `alembic/`, `flyway/` |
| 8 | `database` | `db/` |
| 9 | `database` | `*.sql` |
| 10 | `contracts` | `types/`, `contracts/`, `schemas/` |
| 11 | `contracts` | `*.proto` |
| 12 | `backend` | `api/`, `services/`, `server/`, `backend/`, `controllers/`, `middleware/`, `handlers/` |
| 13 | `backend` | `hooks/<name>/` |
| 14 | `backend` | `skills/<name>/scripts/` |
| 15 | `backend` | `_shared/<name>/scripts/` |
| 16 | `frontend` | `components/`, `pages/`, `views/`, `ui/`, `frontend/`, `styles/`, `contexts/`, `screens/` |
| 17 | `config` | `.github/` |
| 18 | `config` | manifests and lockfiles |

Tests and docs rules sit at the top, so `services/tests/test_client.py` lands in `tests` and `api/docs/reference.md` lands in `docs`.

## Manual overrides

Edit `proposed_slices[].files` in the plan JSON, then re-run `verify_plan.py`. A path may appear in **exactly one** slice.
