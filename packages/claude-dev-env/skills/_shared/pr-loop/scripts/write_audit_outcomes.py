"""Validate Shape A/B contract and write <bugteam_audit> XML at the canonical path.

Usage:
  python scripts/write_audit_outcomes.py --pr-number 422 --loop 3 --review-url <URL> --findings-json <PATH> --worktree-path <PATH>
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
from _path_resolver import outcome_xml_path
from _xml_utils import emit_pretty_xml
from skills_pr_loop_constants.path_resolver_constants import ALL_FINDING_BODY_ELEMENT_KEYS


def build_audit_xml(
    *,
    pr_number: int,
    loop: int,
    review_url: str,
    findings_json_path: Path,
) -> Element:
    """Build the <bugteam_audit> XML element from findings data.

    Args:
        pr_number: Pull request number.
        loop: Loop iteration number.
        review_url: URL of the GitHub review.
        findings_json_path: Path to the findings JSON file.

    Returns:
        Root <bugteam_audit> element.

    Raises:
        SystemExit: When findings-json is not a JSON array of objects.
    """
    findings_data = json.loads(findings_json_path.read_text(encoding="utf-8"))
    if not isinstance(findings_data, list):
        print("findings-json must contain a JSON array", file=sys.stderr)
        raise SystemExit(1)
    for each_index, each_finding in enumerate(findings_data):
        if not isinstance(each_finding, dict):
            print(
                f"findings-json[{each_index}]: each entry must be a JSON object",
                file=sys.stderr,
            )
            raise SystemExit(1)
    root = Element("bugteam_audit", {
        "pr": str(pr_number),
        "loop": str(loop),
        "review_url": review_url,
    })

    findings_elem = SubElement(root, "findings")
    _populate_findings(findings_elem, findings_data)
    return root


def _populate_findings(parent: Element, findings_data: list[dict[str, object]]) -> None:
    """Populate <finding> elements from a validated list of finding dicts.

    Scalar finding fields become XML attributes on `<finding>`; the
    body fields named in `ALL_FINDING_BODY_ELEMENT_KEYS` (defined in
    `packages/claude-dev-env/skills/_shared/pr-loop/scripts/skills_pr_loop_constants/path_resolver_constants.py`
    and currently `("title", "excerpt", "description")`) become child elements.
    Nested dicts or lists in scalar slots are flattened to string form
    so attribute serialization stays well-defined.

    Args:
        parent: Parent XML element (typically `<findings>`).
        findings_data: Validated list of finding dicts (caller must have
            confirmed each entry is a dict via the build_audit_xml gate).
    """
    all_finding_body_element_keys = ALL_FINDING_BODY_ELEMENT_KEYS
    for each_finding in findings_data:
        finding_elem = SubElement(parent, "finding")
        for each_key, each_field_detail in each_finding.items():
            field_text = (
                str(each_field_detail) if each_field_detail is not None else ""
            )
            if each_key in all_finding_body_element_keys:
                child = SubElement(finding_elem, each_key)
                child.text = field_text
            else:
                finding_elem.set(each_key, field_text)


def write_audit_xml(
    *,
    pr_number: int,
    loop: int,
    review_url: str,
    findings_json_path: Path,
    worktree_path: Path,
) -> Path:
    """Write the <bugteam_audit> XML to the canonical outcome path.

    Args:
        pr_number: Pull request number.
        loop: Loop iteration number.
        review_url: URL of the GitHub review.
        findings_json_path: Path to the findings JSON file.
        worktree_path: Path to the git worktree.

    Returns:
        Path to the written XML file.
    """
    root = build_audit_xml(
        pr_number=pr_number,
        loop=loop,
        review_url=review_url,
        findings_json_path=findings_json_path,
    )
    xml_string = emit_pretty_xml(root)

    output_path = outcome_xml_path(worktree_path, pr_number, loop)
    output_path.write_text(xml_string, encoding="utf-8")
    return output_path


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with pr_number, loop, review_url, findings_json, and worktree_path.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--loop", type=int, required=True)
    parser.add_argument("--review-url", required=True)
    parser.add_argument("--findings-json", type=Path, required=True)
    parser.add_argument("--worktree-path", type=Path, required=True)
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point: write <bugteam_audit> XML at the canonical path.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on validation or write failure.
    """
    arguments = parse_arguments(all_arguments)
    findings_path = getattr(arguments, "findings_json")

    early_exit = require_file(findings_path, "findings-json")
    if early_exit is not None:
        return early_exit

    try:
        output_path = write_audit_xml(
            pr_number=getattr(arguments, "pr_number"),
            loop=arguments.loop,
            review_url=getattr(arguments, "review_url"),
            findings_json_path=findings_path,
            worktree_path=getattr(arguments, "worktree_path"),
        )
    except SystemExit:
        return 1
    except (json.JSONDecodeError, OSError) as exc:
        print(f"write_audit_xml failed: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))