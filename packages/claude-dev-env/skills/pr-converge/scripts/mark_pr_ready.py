"""Mark a draft PR as ready for review.

Convergence action invoked by pr-converge when both bugbot and bugteam are
clean against the same HEAD.
"""

import argparse
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import GH_REPO_ARG_TEMPLATE


def mark_pr_ready(*, owner: str, repo: str, number: int) -> None:
    """Run `gh pr ready <number> --repo <owner>/<repo>`."""
    repo_arg = GH_REPO_ARG_TEMPLATE.format(owner=owner, repo=repo)
    gh_command: list[str] = [
        "gh",
        "pr",
        "ready",
        str(number),
        "--repo",
        repo_arg,
    ]
    subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    mark_pr_ready(owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number)
    return 0


if __name__ == "__main__":
    sys.exit(main())
