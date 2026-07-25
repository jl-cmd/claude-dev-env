# split-pr

Autonomous file-based split of one large GitHub PR into a stacked draft chain.

## Layout

| Path | Role |
|---|---|
| `SKILL.md` | Hub workflow |
| `reference/` | Principles, layers, proposal format, task seeds, split-further loop |
| `templates/` | PR body, family-tree body, supersede body, and example plan |
| `scripts/analyze_pr.py` | Build plan JSON from `gh pr view` |
| `scripts/categorize_files.py` | Path-layer heuristics and slice builder |
| `scripts/verify_plan.py` | Exact file coverage gate |
| `scripts/execute_split.py` | Create stacked branches, draft PRs, family-tree comments, stack labels, supersede |
| `scripts/family_tree_comments.py` | Post full linked family tree on each child PR |
| `scripts/stack_labels.py` | Apply discovery labels `split-pr` and `split-stack:<source>` |
| `scripts/gh_body_comment.py` | Shared ``gh pr comment --body-file`` helpers |
| `scripts/supersede_source_pr.py` | Comment merge order and close source_pr_number after full stack |
| `scripts/split_pr_scripts_constants/` | `UPPER_SNAKE` constants |
| `scripts/test_*.py` | Paired behavioral tests |

## Run tests

From the monorepo root, run pytest on this skill's `scripts` directory (`-q`).

Named constants live under `scripts/split_pr_scripts_constants/config/`.
