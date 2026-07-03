# log-audit/scripts

The collect, cluster, and mine scripts for the `log-audit` skill, plus their constants package.

## Files

| File | Purpose |
|---|---|
| `collect_log_window.py` | Tails the JSON-lines hook block log and prints the block records inside a time window as JSON. |
| `test_collect_log_window.py` | Tests for `collect_log_window.py`. |
| `cluster_recurrences.py` | Groups block records by a normalized signature, ranks them by recency-weighted count, and flags timing regressions. |
| `test_cluster_recurrences.py` | Tests for `cluster_recurrences.py`. |
| `mine_copilot_findings.py` | Sorts reviewer-bot comments into defect classes and prints one skill-edit proposal per class. |
| `test_mine_copilot_findings.py` | Tests for `mine_copilot_findings.py`. |

## Subdirectories

| Directory | Role |
|---|---|
| `log_audit_constants/` | Named constants imported by the three scripts. |

## Running

```
python collect_log_window.py --hours 24 | python cluster_recurrences.py
python mine_copilot_findings.py --repo owner/name
```
