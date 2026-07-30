# Split-plan proposal format

Machine-readable plan documents use `schema_version` `1` with:

| Field | Meaning |
|---|---|
| `source_commit` | Exact SHA the changed-file list was taken from |
| `all_changed_paths` | Full path set for that commit |
| `all_slices` | Ordered slices after layer sort |

Each slice carries `id`, `title` (exactly one conventional prefix), `layer`
(one of `config` / `backend` / `frontend` / `tests` / `docs` / `other`), and
`all_paths`. Every path in `all_changed_paths` is assigned to exactly one
slice. Titles are normalized with `split_pr_title.normalize_split_title`.
Layer tokens follow `ALL_LAYER_ORDER` in `config/plan_constants.py`.
