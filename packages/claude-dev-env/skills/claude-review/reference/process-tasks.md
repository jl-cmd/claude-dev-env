# Process task seeds

Register each line as a session task (`TaskCreate` / `TodoWrite`) at skill start.
Mark complete only with evidence. Do not use markdown checkboxes as the live board.

1. Confirm git worktree cwd and HEAD (and clean porcelain for standalone runs).
2. Run static sweep when the caller is a converge loop; re-run until clean or stop.
3. Run `claude_usage_probe.py`; record `session_has_usage_left` / `probe_ok` (or `usage_probe: unavailable`).
4. Run `invoke_code_review.py` with `--cwd`, `--session-model`, and `--session-has-usage-left`.
5. On `in_session`, execute `/code-review xhigh --fix` with no path args on opus.
6. Read JSON outcome: mode, served_command, returncode, dirty_tree.
7. Classify failed vs dirty vs clean per full-diff-and-clean-stamp.md.
8. On dirty tree from a converge caller, invoke `pr-fix-protocol` (or refuse if missing).
9. On clean, run the clean-comment poster script (best-effort; soft-fail).
10. Report outcome to the caller without inventing a clean stamp on failed serve.
