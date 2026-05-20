"""Emit the complete AUDIT spawn prompt XML to stdout.

Substitutes <context>, <scope>, <bug_categories>, <constraints>,
<comment_posting>, and <output_format> blocks from CLI args.

Usage:
  python scripts/build_audit_prompt.py --owner jl-cmd --repo claude-code-config --pr-number 422 --loop 1 --head-ref feat/branch --base-ref main --worktree-path <PATH> --run-temp-dir <PATH>
"""

from __future__ import annotations

import argparse
import sys
from xml.etree.ElementTree import Element, SubElement
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _xml_utils import emit_pretty_xml
from skills_pr_loop_constants.path_resolver_constants import (
    ALL_AUDIT_CATEGORY_ENTRIES,
    ALL_AUDIT_CONSTRAINT_TEXTS,
)


def build_audit_prompt_xml(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    loop: int,
    head_ref: str,
    base_ref: str,
    worktree_path: Path,
    run_temp_dir: Path,
) -> Element:
    """Build the complete AUDIT spawn prompt XML.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.
        loop: Loop iteration number.
        head_ref: Head branch ref.
        base_ref: Base branch ref.
        worktree_path: Path to the git worktree.
        run_temp_dir: Path to the run temp directory.

    Returns:
        Root <spawn_prompt> element.
    """
    root = Element("spawn_prompt", {"role": "audit", "loop": str(loop)})

    context = SubElement(root, "context")
    SubElement(context, "owner").text = owner
    SubElement(context, "repo").text = repo
    SubElement(context, "pr_number").text = str(pr_number)
    SubElement(context, "head_ref").text = head_ref
    SubElement(context, "base_ref").text = base_ref
    SubElement(context, "worktree_path").text = str(worktree_path)
    SubElement(context, "run_temp_dir").text = str(run_temp_dir)

    scope = SubElement(root, "scope")
    scope.text = (
        f"Audit the full diff of {owner}/{repo}#{pr_number} "
        f"({head_ref} against {base_ref}) for CODE_RULES violations, "
        f"bugs, and anti-patterns. Work in {worktree_path}."
    )

    bug_categories = SubElement(root, "bug_categories")
    for each_category_id, each_category_label in ALL_AUDIT_CATEGORY_ENTRIES:
        cat_elem = SubElement(bug_categories, "category", {"id": each_category_id})
        cat_elem.text = each_category_label

    constraints = SubElement(root, "constraints")
    for each_constraint in ALL_AUDIT_CONSTRAINT_TEXTS:
        SubElement(constraints, "constraint").text = each_constraint

    comment_posting = SubElement(root, "comment_posting")
    comment_posting.text = (
        "Post findings as inline review comments on the PR via "
        "the GitHub MCP add_comment_to_pending_review tool. "
        "Group related findings into a single pending review."
    )

    output_format = SubElement(root, "output_format")
    output_format.text = (
        "Emit findings as JSON array of objects with keys: "
        "severity (P0/P1/P2), file, line, category, message, suggestion."
    )

    return root


def emit_audit_prompt(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    loop: int,
    head_ref: str,
    base_ref: str,
    worktree_path: Path,
    run_temp_dir: Path,
) -> str:
    """Build and serialize the AUDIT spawn prompt to a pretty-printed XML string.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.
        loop: Loop iteration number.
        head_ref: Head branch ref.
        base_ref: Base branch ref.
        worktree_path: Path to the git worktree.
        run_temp_dir: Path to the run temp directory.

    Returns:
        Pretty-printed XML string.
    """
    root = build_audit_prompt_xml(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        loop=loop,
        head_ref=head_ref,
        base_ref=base_ref,
        worktree_path=worktree_path,
        run_temp_dir=run_temp_dir,
    )
    return emit_pretty_xml(root)


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with all required audit prompt parameters.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--loop", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--worktree-path", type=Path, required=True)
    parser.add_argument("--run-temp-dir", type=Path, required=True)
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point: emit AUDIT spawn prompt XML to stdout.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success.
    """
    arguments = parse_arguments(all_arguments)
    xml_output = emit_audit_prompt(
        owner=arguments.owner,
        repo=arguments.repo,
        pr_number=getattr(arguments, "pr_number"),
        loop=arguments.loop,
        head_ref=getattr(arguments, "head_ref"),
        base_ref=getattr(arguments, "base_ref"),
        worktree_path=getattr(arguments, "worktree_path"),
        run_temp_dir=getattr(arguments, "run_temp_dir"),
    )
    sys.stdout.write(xml_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
