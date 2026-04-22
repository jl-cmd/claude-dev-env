"""Exclude validator fixture files from pytest collection.

Files in this directory are inputs for a skip-detection validator (see
packages/claude-dev-env/hooks/validators/), not real tests. Each file
demonstrates a skip/xfail pattern the validator must detect. Collecting
them as real tests produces spurious skipped/xfailed counts in the suite.
"""

collect_ignore_glob = ["test_*.py"]
