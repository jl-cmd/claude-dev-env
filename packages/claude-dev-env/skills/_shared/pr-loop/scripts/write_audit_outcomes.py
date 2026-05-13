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
    """
    findings_data = json.loads(findings_json_path.read_text(encoding="utf-8"))
    root = Element("bugteam_audit", {
        "pr": str(pr_number),
        "loop": str(loop),
    })
    review_elem = SubElement(root, "review_url")
    review_elem.text = review_url

    findings_elem = SubElement(root, "findings")
    _populate_findings(findings_elem, findings_data)
    return root


def _populate_findings(parent: Element, findings_data: object) -> None:
    """Recursively populate findings from JSON into XML elements.

    Args:
        parent: Parent XML element.
        findings_data: Findings data (list of dicts or dict).
    """
    if isinstance(findings_data, list):
        for each_item in findings_data:
            if isinstance(each_item, dict):
                finding_elem = SubElement(parent, "finding")
                for each_key, each_field_detail in each_item.items():
                    child = SubElement(finding_elem, each_key)
                    if isinstance(each_field_detail, (list, dict)):
                        _populate_findings(child, each_field_detail)
                    else:
                        child.text = (
                            str(each_field_detail)
                            if each_field_detail is not None
                            else ""
                        )
            else:
                item_elem = SubElement(parent, "item")
                item_elem.text = str(each_item) if each_item is not None else ""
    elif isinstance(findings_data, dict):
        for each_key, each_field_detail in findings_data.items():
            child = SubElement(parent, each_key)
            if isinstance(each_field_detail, (list, dict)):
                _populate_findings(child, each_field_detail)
            else:
                child.text = (
                    str(each_field_detail) if each_field_detail is not None else ""
                )
    else:
        parent.text = str(findings_data) if findings_data is not None else ""


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
    except (json.JSONDecodeError, OSError) as exc:
        print(f"write_audit_xml failed: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))