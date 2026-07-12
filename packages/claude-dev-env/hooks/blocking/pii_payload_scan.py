#!/usr/bin/env python3
"""Scan Write/Edit payloads and durable post bodies for high-confidence PII.

Reused by ``pii_prevention_blocker``: ``build_deny_reason`` composes the deny
message, and ``evaluate_write_edit_payload`` / ``evaluate_post_body_texts`` judge
new file content and durable GitHub post bodies against the pure scanners in
``pii_scanner``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from pii_scanner import (  # noqa: E402
    PiiFinding,
    is_path_exempt_from_pii_scan,
    scan_text_for_pii,
)

from hooks_constants.multi_edit_reconstruction import edits_for_tool  # noqa: E402
from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    CORRECTIVE_MESSAGE_FOOTER,
    CORRECTIVE_MESSAGE_HEADER,
    EDIT_TOOL_NAME,
    FINDING_LINE_TEMPLATE,
    MESSAGE_LINE_SEPARATOR,
    MULTI_EDIT_TOOL_NAME,
    WRITE_TOOL_NAME,
)


def build_deny_reason(all_findings: list[PiiFinding], gate_surface: str) -> str:
    """Return the deny message listing each finding for *gate_surface*.

    Args:
        all_findings: Findings returned by ``scan_text_for_pii``.
        gate_surface: Human-readable surface (write, post body, staged commit).

    Returns:
        Multi-line deny reason for ``permissionDecisionReason``.
    """
    all_lines = [
        CORRECTIVE_MESSAGE_HEADER,
        f"Surface: {gate_surface}",
    ]
    for each_finding in all_findings:
        all_lines.append(
            FINDING_LINE_TEMPLATE.format(
                category=each_finding.category,
                preview=each_finding.preview,
            )
        )
    all_lines.append(CORRECTIVE_MESSAGE_FOOTER)
    message_line_separator = MESSAGE_LINE_SEPARATOR
    return message_line_separator.join(all_lines)


def _collect_write_edit_texts(
    tool_name: str, all_tool_input: dict[str, object]
) -> tuple[str, list[str]]:
    raw_file_path = all_tool_input.get("file_path", "")
    file_path = raw_file_path if isinstance(raw_file_path, str) else ""
    if is_path_exempt_from_pii_scan(file_path):
        return file_path, []
    if tool_name == WRITE_TOOL_NAME:
        write_content = all_tool_input.get("content", "")
        if isinstance(write_content, str) and write_content:
            return file_path, [write_content]
        return file_path, []
    if tool_name in (EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME):
        all_texts: list[str] = []
        for each_edit in edits_for_tool(tool_name, all_tool_input):
            if not isinstance(each_edit, dict):
                continue
            new_string = each_edit.get("new_string", "")
            if isinstance(new_string, str) and new_string:
                all_texts.append(new_string)
        return file_path, all_texts
    return file_path, []


def _first_findings_in_texts(all_texts: list[str]) -> list[PiiFinding]:
    for each_text in all_texts:
        all_findings = scan_text_for_pii(each_text)
        if all_findings:
            return all_findings
    return []


def evaluate_write_edit_payload(
    tool_name: str, all_tool_input: dict[str, object]
) -> str | None:
    """Return a deny reason when Write/Edit/MultiEdit content carries PII.

    Args:
        tool_name: The intercepted tool name.
        all_tool_input: The tool input mapping.

    Returns:
        Deny reason text, or None when the write is clean or out of scope.
    """
    if tool_name not in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return None
    file_path, all_texts = _collect_write_edit_texts(tool_name, all_tool_input)
    all_findings = _first_findings_in_texts(all_texts)
    if not all_findings:
        return None
    gate_surface = f"file write ({file_path or 'unknown path'})"
    return build_deny_reason(all_findings, gate_surface)


def evaluate_post_body_texts(all_body_texts: list[str]) -> str | None:
    """Return a deny reason when any durable post body carries PII.

    Args:
        all_body_texts: Body strings extracted from a gh or MCP post tool.

    Returns:
        Deny reason text, or None when every body is clean.
    """
    all_findings = _first_findings_in_texts(all_body_texts)
    if not all_findings:
        return None
    return build_deny_reason(all_findings, "durable GitHub post body")
