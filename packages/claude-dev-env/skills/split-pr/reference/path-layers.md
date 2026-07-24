# Path layers

Heuristics live in `scripts/split_pr_scripts_constants/categorize_constants.py` (`ALL_LAYER_PATH_RULES`). First match wins on a lowercased POSIX path.

| Layer | Typical paths |
|---|---|
| `database` | `prisma/`, `migrations/`, `alembic/`, `*.sql`, `db/` |
| `contracts` | `types/`, `contracts/`, `schemas/`, `*.proto` |
| `backend` | `api/`, `services/`, `server/`, `middleware/`, `controllers/` |
| `frontend` | `components/`, `hooks/`, `pages/`, `styles/`, `ui/` |
| `tests` | `tests/`, `__tests__/`, `test_*.py`, `*.test.*`, `*.spec.*` |
| `config` | `.github/`, lockfiles, `package.json`, `tsconfig*`, `pyproject.toml` |
| `docs` | `docs/`, `*.md`, `*.rst` |
| `other` | unmatched — re-bucket before proposal |

## Manual overrides

Edit `proposed_slices[].files` in the plan JSON, then re-run `verify_plan.py`. A path may appear in **exactly one** slice.
