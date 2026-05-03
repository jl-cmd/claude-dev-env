"""Resolve the per-tick PR context (number, url, head sha, branch names, draft state).

Wraps `gh pr view --json ...` so the skill body emits one script invocation
instead of repeating the field list inline.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import PR_CONTEXT_FIELDS


def view_pr_context() -> dict[str, object]:
    """Return the parsed JSON object from `gh pr view --json <fields>`."""
    gh_command: list[str] = ["gh", "pr", "view", "--json", PR_CONTEXT_FIELDS]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    pr_context = view_pr_context()
    json.dump(pr_context, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
