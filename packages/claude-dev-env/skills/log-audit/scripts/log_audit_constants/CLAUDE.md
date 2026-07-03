# log-audit/scripts/log_audit_constants

Named constants imported by the `log-audit` scripts. Each module holds the tunables for one script, keeping magic values out of the scripts.

## Files

| File | What it holds |
|---|---|
| `__init__.py` | Package marker. |
| `collect_log_window_constants.py` | The hook-block-log path, default window, block level label, and the input and output record key names for `collect_log_window.py`. |
| `cluster_recurrences_constants.py` | The signature-stripping regexes, recency decay, and timing-regression thresholds for `cluster_recurrences.py`. |
| `mine_copilot_findings_constants.py` | The reviewer-bot logins, the recent-pulls and per-pull comments endpoint templates, the recent-pull count, and the defect-class keyword and proposal maps for `mine_copilot_findings.py`. |
