"""Post a `bugbot run` comment to re-trigger a Cursor Bugbot review.

Writes the literal trigger phrase to a temp file (per the gh-body-file rule —
`gh pr comment --body "..."` may corrupt backticks), invokes
`gh pr comment --body-file`, and removes the temp file on success or failure.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    BUGBOT_RUN_TEMPFILE_PREFIX,
    BUGBOT_RUN_TEMPFILE_SUFFIX,
    BUGBOT_RUN_TRIGGER_PHRASE,
    GH_REPO_ARG_TEMPLATE,
)


def trigger_bugbot(*, owner: str, repo: str, number: int) -> str:
    """Post the bugbot re-trigger comment, return the comment URL gh emits."""
    file_descriptor, raw_path = tempfile.mkstemp(
        suffix=BUGBOT_RUN_TEMPFILE_SUFFIX, prefix=BUGBOT_RUN_TEMPFILE_PREFIX
    )
    try:
        os.close(file_descriptor)
        body_file_path = Path(raw_path)
        body_file_path.write_text(BUGBOT_RUN_TRIGGER_PHRASE, encoding="utf-8")
        repo_arg = GH_REPO_ARG_TEMPLATE.format(owner=owner, repo=repo)
        gh_command: list[str] = [
            "gh",
            "pr",
            "comment",
            str(number),
            "--repo",
            repo_arg,
            "--body-file",
            str(body_file_path),
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
    finally:
        Path(raw_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    comment_url = trigger_bugbot(
        owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number
    )
    sys.stdout.write(f"{comment_url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
