"""Resolve the current HEAD SHA of a pull request.

Calls the single-object PR endpoint (`repos/{owner}/{repo}/pulls/{number}`) which
is NOT paginated, so `--paginate` / `--slurp` are unnecessary and `gh`'s
built-in `--jq` is safe to use here.
"""

import argparse
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import GH_PR_OBJECT_PATH_TEMPLATE


def resolve_pr_head(*, owner: str, repo: str, number: int) -> str:
    """Return the head_sha for the given PR."""
    pr_endpoint = GH_PR_OBJECT_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    gh_command: list[str] = [
        "gh",
        "api",
        pr_endpoint,
        "--jq",
        ".head.sha",
    ]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    head_sha = resolve_pr_head(owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number)
    sys.stdout.write(f"{head_sha}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
