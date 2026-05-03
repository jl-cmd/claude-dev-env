"""Open a follow-up draft PR addressing Copilot findings from the parent PR.

Subprocess sequence:

1. ``gh pr view <parent_number> --json baseRefName`` to resolve the parent's base ref.
2. ``git fetch origin <head_sha>`` to make the SHA available locally.
3. ``git switch -c <new_branch> <head_sha>`` to create the follow-up branch off ``head_sha``.
4. ``git push -u origin <new_branch>`` to publish it.
5. ``gh pr create --draft --base <base_ref> --head <new_branch> --title <...> --body-file <findings_file>``
   per the gh-body-file rule.

Returns the trimmed PR URL emitted by ``gh pr create`` on stdout.
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
    COPILOT_FOLLOWUP_BRANCH_TEMPLATE,
    COPILOT_FOLLOWUP_PR_TITLE_TEMPLATE,
    COPILOT_FOLLOWUP_SHORT_SHA_LENGTH,
    GH_REPO_ARG_TEMPLATE,
    PR_BASE_REF_FIELDS,
)


def open_followup_copilot_pr(
    *,
    owner: str,
    repo: str,
    parent_number: int,
    head: str,
    findings_file: Path,
) -> str:
    """Create the follow-up branch + draft PR; return the new PR URL."""
    repo_arg = GH_REPO_ARG_TEMPLATE.format(owner=owner, repo=repo)
    parent_base_ref = _resolve_parent_base_ref(
        parent_number=parent_number, repo_arg=repo_arg
    )
    short_sha = head[:COPILOT_FOLLOWUP_SHORT_SHA_LENGTH]
    new_branch_name = COPILOT_FOLLOWUP_BRANCH_TEMPLATE.format(
        parent_number=parent_number, short_sha=short_sha
    )
    _run_checked(["git", "fetch", "origin", head])
    _run_checked(["git", "switch", "-c", new_branch_name, head])
    _run_checked(["git", "push", "-u", "origin", new_branch_name])
    pr_title = COPILOT_FOLLOWUP_PR_TITLE_TEMPLATE.format(parent_number=parent_number)
    completed = _run_checked(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo_arg,
            "--draft",
            "--base",
            parent_base_ref,
            "--head",
            new_branch_name,
            "--title",
            pr_title,
            "--body-file",
            str(findings_file),
        ]
    )
    return completed.stdout.strip()


def _resolve_parent_base_ref(*, parent_number: int, repo_arg: str) -> str:
    completed = _run_checked(
        [
            "gh",
            "pr",
            "view",
            str(parent_number),
            "--repo",
            repo_arg,
            "--json",
            PR_BASE_REF_FIELDS,
        ]
    )
    parent_pr_metadata = json.loads(completed.stdout)
    base_ref_name_field = parent_pr_metadata.get("baseRefName")
    if not isinstance(base_ref_name_field, str):
        raise TypeError(
            f"gh pr view baseRefName field is not str: {type(base_ref_name_field).__name__}"
        )
    return base_ref_name_field


def _run_checked(all_command_arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        all_command_arguments,
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
    parser.add_argument(
        "--parent-number", required=True, type=int, dest="parent_number"
    )
    parser.add_argument("--head", required=True)
    parser.add_argument(
        "--findings-file", required=True, type=Path, dest="findings_file"
    )
    parsed_arguments = parser.parse_args()
    new_pr_url = open_followup_copilot_pr(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        parent_number=parsed_arguments.parent_number,
        head=parsed_arguments.head,
        findings_file=parsed_arguments.findings_file,
    )
    sys.stdout.write(f"{new_pr_url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
