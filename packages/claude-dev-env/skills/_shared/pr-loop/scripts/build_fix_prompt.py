"""Emit the complete FIX spawn prompt XML to stdout.

Populates <bug> entries from findings JSON, plus <execution> checklist
and <constraints>.

Usage:
  python scripts/build_fix_prompt.py --owner jl-cmd --repo claude-code-config --pr-number 422 --loop 1 --head-ref feat/branch --base-ref main --worktree-path <PATH> --findings-json <PATH>
"""

from __future__ import annotations

import argparse
import json
import sys
from xml.etree.ElementTree import Element, SubElement
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _cli_utils import require_file
from _xml_utils import emit_pretty_xml
from skills_pr_loop_constants.path_resolver_constants import (
    ALL_FIX_CONSTRAINT_TEXTS,
    ALL_FIX_EXECUTION_STEPS,
)


def build_fix_prompt_xml(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    loop: int,
    head_ref: str,
    base_ref: str,
    worktree_path: Path,
    findings_json_path: Path,
) -> Element:
    """Build the complete FIX spawn prompt XML.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.
        loop: Loop iteration number.
        head_ref: Head branch ref.
        base_ref: Base branch ref.
        worktree_path: Path to the git worktree.
        findings_json_path: Path to the findings JSON file.

    Returns:
        Root <spawn_prompt> element.
    """
    findings_data = json.loads(findings_json_path.read_text(encoding="utf-8"))

    root = Element("spawn_prompt", {"role": "fix", "loop": str(loop)})

    context = SubElement(root, "context")
    SubElement(context, "owner").text = owner
    SubElement(context, "repo").text = repo
    SubElement(context, "pr_number").text = str(pr_number)
    SubElement(context, "head_ref").text = head_ref
    SubElement(context, "base_ref").text = base_ref
    SubElement(context, "worktree_path").text = str(worktree_path)

    bugs_elem = SubElement(root, "bugs")
    if isinstance(findings_data, list):
        for each_finding in findings_data:
            if isinstance(each_finding, dict):
                bug = SubElement(bugs_elem, "bug")
                for each_key, each_field_detail in each_finding.items():
                    child = SubElement(bug, each_key)
                    child.text = (
                        str(each_field_detail) if each_field_detail is not None else ""
                    )

    execution = SubElement(root, "execution")
    for each_step in ALL_FIX_EXECUTION_STEPS:
        SubElement(execution, "step").text = each_step

    constraints = SubElement(root, "constraints")
    for each_constraint in ALL_FIX_CONSTRAINT_TEXTS:
        SubElement(constraints, "constraint").text = each_constraint

    return root


def emit_fix_prompt(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    loop: int,
    head_ref: str,
    base_ref: str,
    worktree_path: Path,
    findings_json_path: Path,
) -> str:
    """Build and serialize the FIX spawn prompt to a pretty-printed XML string.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.
        loop: Loop iteration number.
        head_ref: Head branch ref.
        base_ref: Base branch ref.
        worktree_path: Path to the git worktree.
        findings_json_path: Path to the findings JSON file.

    Returns:
        Pretty-printed XML string.
    """
    root = build_fix_prompt_xml(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        loop=loop,
        head_ref=head_ref,
        base_ref=base_ref,
        worktree_path=worktree_path,
        findings_json_path=findings_json_path,
    )
    return emit_pretty_xml(root)


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with all required fix prompt parameters.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--loop", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--worktree-path", type=Path, required=True)
    parser.add_argument("--findings-json", type=Path, required=True)
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point: emit FIX spawn prompt XML to stdout.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on failure.
    """
    arguments = parse_arguments(all_arguments)
    findings_path = getattr(arguments, "findings_json")

    early_exit = require_file(findings_path, "findings-json")
    if early_exit is not None:
        return early_exit

    try:
        xml_output = emit_fix_prompt(
            owner=arguments.owner,
            repo=arguments.repo,
            pr_number=getattr(arguments, "pr_number"),
            loop=arguments.loop,
            head_ref=getattr(arguments, "head_ref"),
            base_ref=getattr(arguments, "base_ref"),
            worktree_path=getattr(arguments, "worktree_path"),
            findings_json_path=findings_path,
        )
    except (json.JSONDecodeError, OSError) as exc:
        print(f"emit_fix_prompt failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(xml_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
