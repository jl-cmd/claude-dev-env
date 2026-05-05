"""Fetch GitHub Copilot reviewer reviews newest-first, classified as dirty or clean.

Thin wrapper around ``reviewer_fetch_core.fetch_reviewer_reviews`` parameterised
by ``copilot_spec``. Classification follows the review's ``state`` field
(``APPROVED`` -> clean; ``CHANGES_REQUESTED`` -> dirty; ``COMMENTED`` with
non-empty body -> dirty; everything else -> clean) - see ``reviewer_specs``.

Wraps the gh CLI invocation required by the gh-paginate rule:
``gh api '...?per_page=100' --paginate --slurp`` piped through external Python
JSON handling (instead of ``gh --jq``, which runs per-page and breaks
cross-page operations like sort/reverse - see GitHub CLI issue 10459).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from reviewer_fetch_core import fetch_reviewer_reviews
from reviewer_specs import copilot_spec


def fetch_copilot_reviews(
    *,
    owner: str,
    repo: str,
    number: int,
) -> list[dict[str, object]]:
    """Return Copilot reviews newest-first, each with a classification."""
    return fetch_reviewer_reviews(
        copilot_spec, owner=owner, repo=repo, number=number
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    all_reviews = fetch_copilot_reviews(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
    )
    json.dump(all_reviews, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
