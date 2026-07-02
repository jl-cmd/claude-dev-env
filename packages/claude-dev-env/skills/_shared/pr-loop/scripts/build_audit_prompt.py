"""Emit the complete AUDIT spawn prompt XML to stdout.

Builds <context> and <scope> from CLI args; <bug_categories>,
<rubric_reference>, and <constraints> come from the shared constants in
skills_pr_loop_constants; <comment_posting> and <output_format> are built
inline. <pr_description> carries the PR body text read from --pr-body-file,
and stays empty when that argument is absent or the file cannot be read.

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
    AUDIT_RUBRIC_REFERENCE_TEXT,
)


def read_pr_body_text(pr_body_file: Path | None) -> str | None:
    """Read the PR description body from a file when given and readable.

    Args:
        pr_body_file: Path to a file holding the PR description body, or None.

    Returns:
        The file's text when the path is given and readable, otherwise None.
    """
    if pr_body_file is None:
        return None
    try:
        return pr_body_file.read_text(encoding="utf-8")
    except OSError:
        return None


def _append_pr_description(root: Element, pr_body_text: str | None) -> None:
    """Append a <pr_description> element carrying the PR body text.

    Args:
        root: Root element the <pr_description> child is appended to.
        pr_body_text: PR description body text, or None when unavailable.

    Returns:
        None.
    """
    pr_description = SubElement(root, "pr_description")
    if pr_body_text:
        pr_description.text = pr_body_text


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
    pr_body_text: str | None = None,
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
        pr_body_text: PR description body text, or None when unavailable.

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
    SubElement(context, "worktree_path").text = worktree_path.as_posix()
    SubElement(context, "run_temp_dir").text = run_temp_dir.as_posix()

    scope = SubElement(root, "scope")
    scope.text = (
        f"Audit the full diff of {owner}/{repo}#{pr_number} "
        f"({head_ref} against {base_ref}) for CODE_RULES violations, "
        f"bugs, and anti-patterns. Work in {worktree_path.as_posix()}."
    )

    _append_pr_description(root, pr_body_text)

    bug_categories = SubElement(root, "bug_categories")
    for each_category_id, each_category_label in ALL_AUDIT_CATEGORY_ENTRIES:
        cat_elem = SubElement(bug_categories, "category", {"id": each_category_id})
        cat_elem.text = each_category_label

    rubric_reference = SubElement(root, "rubric_reference")
    rubric_reference.text = AUDIT_RUBRIC_REFERENCE_TEXT

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
    pr_body_text: str | None = None,
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
        pr_body_text: PR description body text, or None when unavailable.

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
        pr_body_text=pr_body_text,
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
    parser.add_argument("--pr-body-file", type=Path, default=None)
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
        pr_number=arguments.pr_number,
        loop=arguments.loop,
        head_ref=arguments.head_ref,
        base_ref=arguments.base_ref,
        worktree_path=arguments.worktree_path,
        run_temp_dir=arguments.run_temp_dir,
        pr_body_text=read_pr_body_text(arguments.pr_body_file),
    )
    sys.stdout.write(xml_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
