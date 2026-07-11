"""Validate status enum values and write <bugteam_fix> XML at the canonical path.

Status enum (canonical source: `ALL_VALID_FIX_STATUSES` in
`packages/claude-dev-env/skills/_shared/pr-loop/scripts/skills_pr_loop_constants/path_resolver_constants.py`):
fixed | could_not_address | hook_blocked | unverified_fixed.

Each outcome's scalar fields become XML attributes on `<outcome>`; the
body fields named in `ALL_FIX_OUTCOME_BODY_ELEMENT_KEYS` (currently
`("reason", "hook_output")`) become child elements.

Usage:
  python scripts/write_fix_outcomes.py --pr-number 422 --loop 3 --commit-sha abc1234 --outcomes-json <PATH> --worktree-path <PATH>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _cli_utils import require_file
from _path_resolver import fix_outcome_xml_path
from _xml_utils import emit_pretty_xml
from skills_pr_loop_constants.path_resolver_constants import (
    ALL_FIX_OUTCOME_BODY_ELEMENT_KEYS,
    ALL_VALID_FIX_STATUSES,
)


def validate_fix_statuses(all_outcomes: list[dict[str, object]]) -> list[str]:
    """Validate that every outcome entry has a recognized status.

    Args:
        all_outcomes: List of outcome dicts, each expected to have a 'status' key.

    Returns:
        List of validation error messages (empty when valid).
    """
    valid_statuses = ALL_VALID_FIX_STATUSES
    errors: list[str] = []
    for each_index, each_outcome in enumerate(all_outcomes):
        status = each_outcome.get("status")
        if not isinstance(status, str):
            errors.append(f"outcome[{each_index}]: status missing or not a string")
            continue
        if status not in valid_statuses:
            errors.append(
                f"outcome[{each_index}]: invalid status '{status}' "
                f"(expected one of {sorted(valid_statuses)})"
            )
    return errors


def build_fix_xml(
    *,
    pr_number: int,
    loop: int,
    commit_sha: str,
    outcomes_json_path: Path,
) -> Element:
    """Build the <bugteam_fix> XML element from outcomes data.

    Args:
        pr_number: Pull request number.
        loop: Loop iteration number.
        commit_sha: Commit SHA of the fix commit.
        outcomes_json_path: Path to the outcomes JSON file.

    Returns:
        Root <bugteam_fix> element.

    Raises:
        SystemExit: When outcomes-json is not a JSON array of objects, or
            when status validation fails.
    """
    outcomes_data = json.loads(outcomes_json_path.read_text(encoding="utf-8"))
    if not isinstance(outcomes_data, list):
        print("outcomes-json must contain a JSON array", file=sys.stderr)
        raise SystemExit(1)
    for each_index, each_entry in enumerate(outcomes_data):
        if not isinstance(each_entry, dict):
            print(
                f"outcomes-json[{each_index}]: each entry must be a JSON object",
                file=sys.stderr,
            )
            raise SystemExit(1)
    errors = validate_fix_statuses(outcomes_data)
    if errors:
        for each_error in errors:
            print(each_error, file=sys.stderr)
        raise SystemExit(1)

    root = Element("bugteam_fix", {
        "pr": str(pr_number),
        "loop": str(loop),
        "commit_sha": commit_sha,
    })

    all_fix_outcome_body_element_keys = ALL_FIX_OUTCOME_BODY_ELEMENT_KEYS
    outcomes_elem = SubElement(root, "outcomes")
    for each_outcome in outcomes_data:
        outcome_elem = SubElement(outcomes_elem, "outcome")
        for each_key, each_field_detail in each_outcome.items():
            field_text = (
                str(each_field_detail) if each_field_detail is not None else ""
            )
            if each_key in all_fix_outcome_body_element_keys:
                child = SubElement(outcome_elem, each_key)
                child.text = field_text
            else:
                outcome_elem.set(each_key, field_text)
    return root


def write_fix_xml(
    *,
    pr_number: int,
    loop: int,
    commit_sha: str,
    outcomes_json_path: Path,
    worktree_path: Path,
) -> Path:
    """Write the <bugteam_fix> XML to the canonical outcome path.

    Args:
        pr_number: Pull request number.
        loop: Loop iteration number.
        commit_sha: Commit SHA of the fix commit.
        outcomes_json_path: Path to the outcomes JSON file.
        worktree_path: Path to the git worktree.

    Returns:
        Path to the written XML file.
    """
    root = build_fix_xml(
        pr_number=pr_number,
        loop=loop,
        commit_sha=commit_sha,
        outcomes_json_path=outcomes_json_path,
    )
    xml_string = emit_pretty_xml(root)

    output_path = fix_outcome_xml_path(worktree_path, pr_number, loop)
    output_path.write_text(xml_string, encoding="utf-8")
    return output_path


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with pr_number, loop, commit_sha, outcomes_json, and worktree_path.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--loop", type=int, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--outcomes-json", type=Path, required=True)
    parser.add_argument("--worktree-path", type=Path, required=True)
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point: write <bugteam_fix> XML at the canonical path.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on validation or write failure.
    """
    arguments = parse_arguments(all_arguments)
    outcomes_path = getattr(arguments, "outcomes_json")

    early_exit = require_file(outcomes_path, "outcomes-json")
    if early_exit is not None:
        return early_exit

    try:
        output_path = write_fix_xml(
            pr_number=getattr(arguments, "pr_number"),
            loop=arguments.loop,
            commit_sha=getattr(arguments, "commit_sha"),
            outcomes_json_path=outcomes_path,
            worktree_path=getattr(arguments, "worktree_path"),
        )
    except SystemExit:
        return 1
    except (json.JSONDecodeError, OSError) as exc:
        print(f"write_fix_xml failed: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))