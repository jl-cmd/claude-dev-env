"""Create a loop-state.json file for a bugteam run.

Usage:
  python scripts/init_loop_state.py --pr-number 422 --head-ref feat/branch --starting-sha abc1234 [--is-multi-pr]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _path_resolver import (
    build_run_name,
    per_pr_workspace,
    resolve_run_temp_dir,
)
from skills_pr_loop_constants.path_resolver_constants import LOOP_STATE_JSON_INDENT


def create_loop_state(
    *,
    pr_number: int,
    head_ref: str,
    starting_sha: str,
    is_multi_pr: bool = False,
) -> Path:
    """Create the loop-state.json file and return its path.

    The written state dict carries the subset of the keys documented
    in `_shared/pr-loop/state-schema.md` common-fields table that are
    initialized at loop creation. Fields populated only during the loop
    (e.g. `audit_log`) are added by later steps and are not written
    here:

      - `loop_count: 0` (int counter, bumps on each AUDIT or tick)
      - `last_action: "fresh"` (enum: fresh | audited | fixed)
      - `last_findings: {p0: 0, p1: 0, p2: 0, total: 0}` (count dict
        populated by AUDIT)
      - `starting_sha: <str>` (the SHA passed in)
      - `loop_comment_index: {}` (dict keyed by finding_id; AUDIT
        populates `finding_comment_id`, `finding_comment_url`, and
        `thread_node_id` per entry when it posts the per-loop review,
        and FIX sets `fix_status` when its commit lands)

    Args:
        pr_number: Pull request number.
        head_ref: Head branch ref.
        starting_sha: Starting commit SHA.
        is_multi_pr: Whether multi-PR mode is active.

    Returns:
        Path to the created loop-state.json file.
    """
    run_name = build_run_name(pr_number, head_ref, is_multi_pr=is_multi_pr)
    run_temp_dir = resolve_run_temp_dir(run_name)
    workspace = per_pr_workspace(run_temp_dir, "", "", pr_number)
    worktree_path = workspace["worktree"]
    assert isinstance(worktree_path, Path)

    worktree_path.mkdir(parents=True, exist_ok=True)
    state_path = worktree_path / "loop-state.json"

    state = {
        "loop_count": 0,
        "last_action": "fresh",
        "last_findings": {"p0": 0, "p1": 0, "p2": 0, "total": 0},
        "starting_sha": starting_sha,
        "loop_comment_index": {},
    }

    state_path.write_text(
        json.dumps(state, indent=LOOP_STATE_JSON_INDENT) + "\n",
        encoding="utf-8",
    )
    return state_path


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with pr_number, head_ref, starting_sha, and is_multi_pr.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--starting-sha", required=True)
    parser.add_argument(
        "--is-multi-pr",
        action="store_true",
        default=False,
    )
    return parser.parse_args(all_argv)


def main(
    all_arguments: list[str], *, is_multi_pr: bool | None = None
) -> int:
    """Entry point: create loop-state.json and print its path.

    Args:
        all_arguments: Command-line arguments.
        is_multi_pr: Override for multi-PR mode (default: from CLI).

    Returns:
        0 on success.
    """
    arguments = parse_arguments(all_arguments)
    if arguments.starting_sha is None:
        return 1
    state_path = create_loop_state(
        pr_number=getattr(arguments, "pr_number"),
        head_ref=getattr(arguments, "head_ref"),
        starting_sha=arguments.starting_sha,
        is_multi_pr=(
            arguments.is_multi_pr if is_multi_pr is None else is_multi_pr
        ),
    )
    print(state_path)
    return 0


if __name__ == "__main__":
    all_argv = sys.argv[1:]
    arguments = parse_arguments(all_argv)
    raise SystemExit(main(all_argv, is_multi_pr=arguments.is_multi_pr))
