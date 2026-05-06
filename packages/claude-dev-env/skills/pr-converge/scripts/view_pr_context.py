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

from config.pr_converge_constants import (
    GH_REPO_ARG_TEMPLATE,
    GH_REPO_FLAG,
    PR_CONTEXT_FIELDS,
    PR_DETACHED_HEAD_ARGS_ERROR,
    PR_NUMBER_ARG_FLAG,
    PR_NUMBER_ARG_HELP,
    PR_OWNER_ARG_FLAG,
    PR_OWNER_ARG_HELP,
    PR_REPO_ARG_FLAG,
    PR_REPO_ARG_HELP,
)


def view_pr_context(
    number: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
) -> dict[str, object]:
    """Return the parsed JSON object from `gh pr view --json <fields>`."""
    gh_command: list[str] = ["gh", "pr", "view", "--json", PR_CONTEXT_FIELDS]
    if owner and repo and number:
        gh_command.append(number)
        gh_command.append(GH_REPO_FLAG)
        gh_command.append(GH_REPO_ARG_TEMPLATE.format(owner=owner, repo=repo))
    elif number:
        gh_command.append(number)
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
    parser.add_argument(PR_NUMBER_ARG_FLAG, default=None, help=PR_NUMBER_ARG_HELP)
    parser.add_argument(PR_OWNER_ARG_FLAG, default=None, help=PR_OWNER_ARG_HELP)
    parser.add_argument(PR_REPO_ARG_FLAG, default=None, help=PR_REPO_ARG_HELP)
    parsed = parser.parse_args()
    number = (parsed.number.strip() or None) if parsed.number else None
    owner = (parsed.owner.strip() or None) if parsed.owner else None
    repo = (parsed.repo.strip() or None) if parsed.repo else None
    needs_repo = owner is not None or repo is not None
    has_all = number is not None and owner is not None and repo is not None
    if needs_repo and not has_all:
        parser.error(PR_DETACHED_HEAD_ARGS_ERROR)
    pr_context = view_pr_context(number=number, owner=owner, repo=repo)
    json.dump(pr_context, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
