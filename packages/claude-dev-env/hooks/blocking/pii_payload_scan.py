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

try:
    _blocking_directory = str(Path(__file__).resolve().parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from pii_prevention_blocker_parts.repository_exemption import (
        repository_allowlisted_values,
    )
    from pii_scanner import (
        PiiFinding,
        is_path_exempt_from_pii_scan,
        scan_text_for_pii,
    )
    from precommit_code_rules_gate import resolve_repository_root

    from hooks_constants.local_identity import pii_allowlisted_values_by_repository
    from hooks_constants.multi_edit_reconstruction import edits_for_tool
    from hooks_constants.pii_prevention_constants import (
        ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
        CORRECTIVE_MESSAGE_FOOTER,
        CORRECTIVE_MESSAGE_HEADER,
        EDIT_TOOL_NAME,
        FINDING_LINE_TEMPLATE,
        MESSAGE_LINE_SEPARATOR,
        MULTI_EDIT_TOOL_NAME,
        WRITE_TOOL_NAME,
    )
except ImportError as import_error:
    raise ImportError(
        "pii_payload_scan: cannot import its sibling modules; "
        "ensure the blocking and hooks directories are importable."
    ) from import_error


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


def _new_strings_from_edits(
    tool_name: str, all_tool_input: dict[str, object]
) -> list[str]:
    """Return each non-empty ``new_string`` from an Edit/MultiEdit payload."""
    all_texts: list[str] = []
    for each_edit in edits_for_tool(tool_name, all_tool_input):
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str) and new_string:
            all_texts.append(new_string)
    return all_texts


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
        return file_path, _new_strings_from_edits(tool_name, all_tool_input)
    return file_path, []


def _findings_after_allowlist(
    text: str, all_allowlisted_values: frozenset[str]
) -> list[PiiFinding]:
    """Return PII findings in *text* whose matched text is not allowlisted."""
    return [
        each_finding
        for each_finding in scan_text_for_pii(text)
        if each_finding.matched_text not in all_allowlisted_values
    ]


def _first_findings_in_texts(
    all_texts: list[str], all_allowlisted_values: frozenset[str] = frozenset()
) -> list[PiiFinding]:
    for each_text in all_texts:
        all_findings = _findings_after_allowlist(each_text, all_allowlisted_values)
        if all_findings:
            return all_findings
    return []


def _existing_ancestor_directory(file_path: str) -> str | None:
    """Return the nearest existing ancestor directory of *file_path*, or None.

    PreToolUse runs before Write creates nested parents, so the immediate parent
    may not exist yet; git resolution needs a directory that is already on disk.
    """
    starting_directory = Path(file_path).parent
    for each_ancestor in (starting_directory, *starting_directory.parents):
        if each_ancestor.exists():
            return str(each_ancestor)
    return None


def _write_path_allowlisted_values(file_path: str) -> frozenset[str]:
    """Return the exact values allowlisted for the repository *file_path* sits in.

    ::

        no path, or no allowlist configured  ->  frozenset()  (no git call)
        path inside an allowlisted repo tree  ->  that repo's frozenset of values

    Args:
        file_path: The write target path whose repository keys the allowlist.

    Returns:
        The exact values the repository allows past the scan, or an empty set.
    """
    if not file_path:
        return frozenset()
    if not pii_allowlisted_values_by_repository():
        return frozenset()
    resolution_directory = _existing_ancestor_directory(file_path)
    if resolution_directory is None:
        return frozenset()
    repository_root = resolve_repository_root(resolution_directory)
    if repository_root is None:
        return frozenset()
    return repository_allowlisted_values(repository_root)


def evaluate_write_edit_payload(
    tool_name: str,
    all_tool_input: dict[str, object],
    all_allowlisted_values: frozenset[str] = frozenset(),
) -> str | None:
    """Return a deny reason when Write/Edit/MultiEdit content carries PII.

    A value in the target repository's PII allowlist is dropped from the
    findings, so a write under that repository's tree may carry it. Repository
    resolution for that allowlist runs only after a raw PII hit.

    Args:
        tool_name: The intercepted tool name.
        all_tool_input: The tool input mapping.
        all_allowlisted_values: Extra exact values allowed past the scan,
            unioned with the target repository's own allowlist.

    Returns:
        Deny reason text, or None when the write is clean or out of scope.
    """
    if tool_name not in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return None
    file_path, all_texts = _collect_write_edit_texts(tool_name, all_tool_input)
    resolved_allowlisted_values: frozenset[str] | None = None
    for each_text in all_texts:
        all_raw_findings = scan_text_for_pii(each_text)
        if not all_raw_findings:
            continue
        if resolved_allowlisted_values is None:
            resolved_allowlisted_values = (
                all_allowlisted_values | _write_path_allowlisted_values(file_path)
            )
        all_findings = [
            each_finding
            for each_finding in all_raw_findings
            if each_finding.matched_text not in resolved_allowlisted_values
        ]
        if all_findings:
            gate_surface = f"file write ({file_path or 'unknown path'})"
            return build_deny_reason(all_findings, gate_surface)
    return None


def evaluate_post_body_texts(
    all_body_texts: list[str],
    all_allowlisted_values: frozenset[str] = frozenset(),
) -> str | None:
    """Return a deny reason when any durable post body carries PII.

    Args:
        all_body_texts: Body strings extracted from a gh or MCP post tool.
        all_allowlisted_values: Exact values the caller's repository allows;
            a finding matching one is not a finding. Callers that pass
            nothing keep every post fully scanned.

    Returns:
        Deny reason text, or None when every body is clean.
    """
    all_findings = _first_findings_in_texts(all_body_texts, all_allowlisted_values)
    if not all_findings:
        return None
    return build_deny_reason(all_findings, "durable GitHub post body")
