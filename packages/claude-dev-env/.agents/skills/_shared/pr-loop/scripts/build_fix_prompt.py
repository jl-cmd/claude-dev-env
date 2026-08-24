"""Emit the complete FIX spawn prompt XML to stdout.

Populates <bug> entries from findings JSON, plus <execution> checklist
and <constraints>. <comment_posting> and <output_format> follow
``--flavor`` (agent or headless).

Usage:
  python scripts/build_fix_prompt.py --owner jl-cmd --repo claude-dev-env --pr-number 422 --loop 1 --head-ref feat/branch --base-ref main --worktree-path <PATH> --findings-json <PATH> [--flavor agent|headless]
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
from _path_resolver import fix_outcome_xml_path
from _xml_utils import emit_pretty_xml
from skills_pr_loop_constants.path_resolver_constants import (
    ALL_FIX_CONSTRAINT_TEXTS,
    ALL_FIX_CONSTRAINT_TEXTS_HEADLESS,
    ALL_FIX_EXECUTION_STEPS,
    ALL_FIX_EXECUTION_STEPS_HEADLESS,
    ALL_FIX_PROMPT_FLAVORS,
    FINDINGS_JSON_MUST_BE_LIST_MESSAGE,
    FIX_COMMENT_POSTING_AGENT_TEXT,
    FIX_COMMENT_POSTING_HEADLESS_TEXT,
    FIX_OUTPUT_FORMAT_AGENT_TEXT,
    FIX_OUTPUT_FORMAT_HEADLESS_TEMPLATE,
    FIX_PROMPT_FLAVOR_AGENT,
    FIX_PROMPT_FLAVOR_HEADLESS,
)


def _comment_posting_text(flavor: str) -> str:
    """Return the <comment_posting> body for the given prompt flavor.

    Args:
        flavor: ``agent`` or ``headless`` prompt flavor.

    Returns:
        Comment-posting instruction text for that flavor.
    """
    if flavor == FIX_PROMPT_FLAVOR_HEADLESS:
        return FIX_COMMENT_POSTING_HEADLESS_TEXT
    return FIX_COMMENT_POSTING_AGENT_TEXT


def _format_instruction_text(
    *,
    flavor: str,
    worktree_path: Path,
    pr_number: int,
    loop: int,
) -> str:
    """Return the <output_format> body for the given prompt flavor.

    Args:
        flavor: ``agent`` or ``headless`` prompt flavor.
        worktree_path: Path to the git worktree.
        pr_number: Pull request number.
        loop: Loop iteration number.

    Returns:
        Format-instruction text for that flavor.
    """
    if flavor == FIX_PROMPT_FLAVOR_HEADLESS:
        outcome_path = fix_outcome_xml_path(worktree_path, pr_number, loop)
        return FIX_OUTPUT_FORMAT_HEADLESS_TEMPLATE.format(
            outcome_path=outcome_path.as_posix(),
        )
    return FIX_OUTPUT_FORMAT_AGENT_TEXT


def _all_execution_steps(flavor: str) -> list[str]:
    """Return the execution checklist for the given prompt flavor.

    Args:
        flavor: ``agent`` or ``headless`` prompt flavor.

    Returns:
        Ordered execution step texts for that flavor.
    """
    if flavor == FIX_PROMPT_FLAVOR_HEADLESS:
        return list(ALL_FIX_EXECUTION_STEPS_HEADLESS)
    return list(ALL_FIX_EXECUTION_STEPS)


def _all_constraint_texts(flavor: str) -> list[str]:
    """Return the constraint texts for the given prompt flavor.

    Args:
        flavor: ``agent`` or ``headless`` prompt flavor.

    Returns:
        Ordered constraint texts for that flavor.
    """
    if flavor == FIX_PROMPT_FLAVOR_HEADLESS:
        return list(ALL_FIX_CONSTRAINT_TEXTS_HEADLESS)
    return list(ALL_FIX_CONSTRAINT_TEXTS)


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
    flavor: str = FIX_PROMPT_FLAVOR_AGENT,
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
        flavor: Prompt flavor — ``agent`` (in-agent commit/post) or
            ``headless`` (outcome file, lead-owned commit/post).

    Returns:
        Root <spawn_prompt> element.
    """
    findings_data = json.loads(findings_json_path.read_text(encoding="utf-8"))
    if not isinstance(findings_data, list):
        findings_type_name = type(findings_data).__name__
        raise TypeError(
            FINDINGS_JSON_MUST_BE_LIST_MESSAGE % findings_type_name
        )

    root = Element("spawn_prompt", {"role": "fix", "loop": str(loop)})

    context = SubElement(root, "context")
    SubElement(context, "owner").text = owner
    SubElement(context, "repo").text = repo
    SubElement(context, "pr_number").text = str(pr_number)
    SubElement(context, "head_ref").text = head_ref
    SubElement(context, "base_ref").text = base_ref
    SubElement(context, "worktree_path").text = worktree_path.as_posix()

    bugs_elem = SubElement(root, "bugs")
    for each_finding in findings_data:
        if isinstance(each_finding, dict):
            bug = SubElement(bugs_elem, "bug")
            for each_key, each_field_detail in each_finding.items():
                child = SubElement(bug, each_key)
                child.text = (
                    str(each_field_detail) if each_field_detail is not None else ""
                )

    execution = SubElement(root, "execution")
    for each_step in _all_execution_steps(flavor):
        SubElement(execution, "step").text = each_step

    constraints = SubElement(root, "constraints")
    for each_constraint in _all_constraint_texts(flavor):
        SubElement(constraints, "constraint").text = each_constraint

    comment_posting = SubElement(root, "comment_posting")
    comment_posting.text = _comment_posting_text(flavor)

    format_section = SubElement(root, "output_format")
    format_section.text = _format_instruction_text(
        flavor=flavor,
        worktree_path=worktree_path,
        pr_number=pr_number,
        loop=loop,
    )

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
    flavor: str = FIX_PROMPT_FLAVOR_AGENT,
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
        flavor: Prompt flavor — ``agent`` or ``headless``.

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
        flavor=flavor,
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
    parser.add_argument(
        "--flavor",
        choices=sorted(ALL_FIX_PROMPT_FLAVORS),
        default=FIX_PROMPT_FLAVOR_AGENT,
    )
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
            flavor=arguments.flavor,
        )
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        print(f"emit_fix_prompt failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(xml_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
