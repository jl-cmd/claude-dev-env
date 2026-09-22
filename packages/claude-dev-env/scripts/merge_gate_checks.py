#!/usr/bin/env python3
"""Hold a merge policy document to the branch ruleset it describes.

A policy document names the checks a pull request passes before it merges.
Those names go stale the moment the branch ruleset stops requiring one of
them, and the document then promises a gate that never runs.

The document carries one fenced block whose info string is
``required-status-checks``. Each line inside it is one check context, spelled
the way the ruleset spells it.

::

    ```required-status-checks
    instruction-pairs / instruction-pairs
    ```
    ok:   the ruleset requires that context      -> exit 0
    flag: the ruleset dropped that context       -> exit 1, one line naming it

The ruleset arrives two ways. A checked-in snapshot keeps the comparison
offline, which is what the paired test suite reads. ``--live`` reads the
ruleset from the GitHub API, and ``--refresh`` writes the live answer back to
the snapshot file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TextIO

from dev_env_scripts_constants.merge_gate_check_constants import (
    ALL_GITHUB_TOKEN_VARIABLES,
    FENCE_MARKER,
    JSON_INDENT_WIDTH,
    MERGE_GATE_CLEAN_EXIT_CODE,
    MERGE_GATE_MISSING_CHECK_EXIT_CODE,
    REQUIRED_CHECK_BLOCK_INFO_STRING,
    REQUIRED_STATUS_CHECKS_RULE_TYPE,
    RULE_CONTEXT_KEY,
    RULE_PARAMETERS_KEY,
    RULE_TYPE_KEY,
    RULESET_API_ACCEPT_HEADER,
    RULESET_API_TEMPLATE,
    RULESET_REQUEST_TIMEOUT_SECONDS,
    UTF8_ENCODING,
)


def parse_declared_contexts(document_text: str) -> list[str]:
    """Read the check contexts a policy document declares, in document order.

    ::

        parse_declared_contexts("```required-status-checks\\nRuff\\n```\\n")
        ok: ["Ruff"]

    A document with no such block declares nothing.

    Args:
        document_text: The whole policy document.

    Returns:
        The contexts inside the ``required-status-checks`` block, in the order
        the document lists them, and an empty list when the block is absent.
    """
    all_stripped_lines = [each_line.strip() for each_line in document_text.splitlines()]
    opening_fence = FENCE_MARKER + REQUIRED_CHECK_BLOCK_INFO_STRING
    if opening_fence not in all_stripped_lines:
        return []
    block_body_index = all_stripped_lines.index(opening_fence) + 1
    all_declared_contexts: list[str] = []
    for each_line in all_stripped_lines[block_body_index:]:
        if each_line == FENCE_MARKER:
            break
        if each_line:
            all_declared_contexts.append(each_line)
    return all_declared_contexts


def ruleset_contexts(ruleset_payload: object) -> set[str]:
    """Read every status-check context a branch ruleset requires.

    A rule of another type carries no context and is passed over.

    Args:
        ruleset_payload: The list of rules the branch-rules endpoint returns.

    Returns:
        Every context named by a ``required_status_checks`` rule.
    """
    all_required_contexts: set[str] = set()
    for each_rule in _required_status_check_rules(ruleset_payload):
        all_required_contexts.update(_rule_contexts(each_rule))
    return all_required_contexts


def missing_contexts(document_text: str, ruleset_payload: object) -> list[str]:
    """Name the declared contexts the ruleset stopped requiring.

    An empty list means the ruleset requires every check the document names,
    so the document's promise holds.

    Args:
        document_text: The whole policy document.
        ruleset_payload: The list of rules the branch-rules endpoint returns.

    Returns:
        The declared contexts the ruleset leaves out, in document order.
    """
    all_required_contexts = ruleset_contexts(ruleset_payload)
    return [
        each_context
        for each_context in parse_declared_contexts(document_text)
        if each_context not in all_required_contexts
    ]


def main(all_arguments: Sequence[str]) -> int:
    """Compare the document against the snapshot, or against the live ruleset.

    Args:
        all_arguments: The command-line arguments after the program name.

    Returns:
        ``0`` when the ruleset requires every declared context, and ``1`` with
        one line per context the ruleset leaves out.
    """
    parser = _build_parser()
    parsed_arguments = parser.parse_args(all_arguments)
    wants_live_ruleset = parsed_arguments.live or parsed_arguments.refresh
    if wants_live_ruleset and not parsed_arguments.repository:
        parser.error("--live and --refresh need --repository")
    ruleset_payload = _resolve_ruleset(parsed_arguments)
    document_text = parsed_arguments.document.read_text(encoding=UTF8_ENCODING)
    return _report_missing(
        parsed_arguments.document,
        missing_contexts(document_text, ruleset_payload),
        sys.stdout,
    )


def _required_status_check_rules(
    ruleset_payload: object,
) -> Iterator[dict[str, object]]:
    if not isinstance(ruleset_payload, list):
        return
    for each_rule in ruleset_payload:
        if isinstance(each_rule, dict) and (
            each_rule.get(RULE_TYPE_KEY) == REQUIRED_STATUS_CHECKS_RULE_TYPE
        ):
            yield each_rule


def _rule_contexts(all_rule_fields: dict[str, object]) -> set[str]:
    parameters = all_rule_fields.get(RULE_PARAMETERS_KEY)
    if not isinstance(parameters, dict):
        return set()
    all_declared_checks = parameters.get(REQUIRED_STATUS_CHECKS_RULE_TYPE)
    if not isinstance(all_declared_checks, list):
        return set()
    return {
        each_check[RULE_CONTEXT_KEY]
        for each_check in all_declared_checks
        if isinstance(each_check, dict)
        and isinstance(each_check.get(RULE_CONTEXT_KEY), str)
    }


def _read_github_token() -> str | None:
    for each_variable_name in ALL_GITHUB_TOKEN_VARIABLES:
        token = os.environ.get(each_variable_name)
        if token:
            return token
    return None


def _fetch_ruleset(repository: str, branch: str) -> object:
    request = urllib.request.Request(
        RULESET_API_TEMPLATE.format(repository=repository, branch=branch),
        headers={"Accept": RULESET_API_ACCEPT_HEADER},
    )
    token = _read_github_token()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(
        request, timeout=RULESET_REQUEST_TIMEOUT_SECONDS
    ) as api_reply:
        return json.loads(api_reply.read().decode(UTF8_ENCODING))


def _resolve_ruleset(parsed_arguments: argparse.Namespace) -> object:
    if not (parsed_arguments.live or parsed_arguments.refresh):
        return json.loads(parsed_arguments.ruleset.read_text(encoding=UTF8_ENCODING))
    ruleset_payload = _fetch_ruleset(
        parsed_arguments.repository, parsed_arguments.branch
    )
    if parsed_arguments.refresh:
        parsed_arguments.ruleset.write_text(
            json.dumps(ruleset_payload, indent=JSON_INDENT_WIDTH) + "\n",
            encoding=UTF8_ENCODING,
        )
    return ruleset_payload


def _report_missing(
    document_path: Path, all_absent_contexts: Sequence[str], stream: TextIO
) -> int:
    if not all_absent_contexts:
        stream.write(f"{document_path}: the ruleset requires every named check\n")
        return MERGE_GATE_CLEAN_EXIT_CODE
    stream.writelines(
        f"{document_path}: the branch ruleset does not require {each_context!r}\n"
        for each_context in all_absent_contexts
    )
    return MERGE_GATE_MISSING_CHECK_EXIT_CODE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check a merge policy document.")
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--ruleset", required=True, type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
