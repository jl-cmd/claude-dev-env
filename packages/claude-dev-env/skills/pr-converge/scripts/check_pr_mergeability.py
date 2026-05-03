"""Resolve the per-tick mergeability state of an explicitly-targeted PR.

Wraps ``gh pr view <number> --repo <owner>/<repo> --json mergeable,mergeStateStatus,headRefOid``
so the skill body emits one script invocation. Single-object endpoint - no
pagination. Explicit ``--owner``/``--repo``/``--number`` targeting matches every
sibling convergence-gate script (``fetch_*_reviews.py``,
``fetch_*_inline_comments.py``, ``request_copilot_review.py``,
``mark_pr_ready.py``); under multi-PR orchestration or after
``open_followup_copilot_pr.py`` switches the checkout, the gate is guaranteed
to query the intended PR rather than whichever PR the current git context
points at.

The returned dict gates pr-converge's mark-ready step against PRs whose base
branch state is DIRTY (conflicts) or otherwise non-CLEAN.
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

from config.pr_converge_constants import GH_REPO_ARG_TEMPLATE, MERGEABILITY_FIELDS


def check_pr_mergeability(
    *,
    owner: str,
    repo: str,
    number: int,
) -> dict[str, object]:
    """Return ``{mergeable, mergeStateStatus, headRefOid}`` from ``gh pr view`` for the targeted PR."""
    repo_arg = GH_REPO_ARG_TEMPLATE.format(owner=owner, repo=repo)
    gh_command: list[str] = [
        "gh",
        "pr",
        "view",
        str(number),
        "--repo",
        repo_arg,
        "--json",
        MERGEABILITY_FIELDS,
    ]
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
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    mergeability_state = check_pr_mergeability(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
    )
    json.dump(mergeability_state, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
