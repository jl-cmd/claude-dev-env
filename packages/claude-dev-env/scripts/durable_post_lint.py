"""Validate durable GitHub post inputs before publication."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from durable_post_lint_config.config.constants import (
    ACTION_PR_CREATE,
    ACTION_PR_EDIT,
    ALL_BARE_VOLATILE_PATH_MARKERS,
    ALL_BODY_REQUIRED_ACTIONS,
    ALL_PATH_ANCHORED_VOLATILE_PATH_MARKERS,
    ALL_POST_ACTIONS,
    ALL_PR_DESCRIPTION_ACTIONS,
    ALL_RELEASE_BODY_MARKERS,
    ALL_REQUIRED_PR_DESCRIPTION_HEADINGS,
    ALL_TITLE_ACTIONS,
    BODY_FILE_ENCODING,
    BODY_FILE_UNREADABLE_MESSAGE,
    BODY_MUST_NOT_BE_EMPTY_MESSAGE,
    BODY_REQUIRED_MESSAGE,
    CLEAN_EXIT_CODE,
    CONTENT_FINDING_EXIT_CODE,
    CONVENTIONAL_TITLE_PATTERN,
    EDIT_INPUT_REQUIRED_MESSAGE,
    EMPTY_BODY_CODE,
    INPUT_ERROR_EXIT_CODE,
    INVALID_ACTION_MESSAGE,
    INVALID_TITLE_CODE,
    INVALID_TITLE_MESSAGE,
    MISSING_HEADING_CODE,
    MISSING_HEADING_MESSAGE_TEMPLATE,
    PATH_ANCHOR_CHARACTER,
    PATH_SEGMENT_START_CHARACTERS,
    RELEASE_BRANCH_PREFIX,
    REWRITTEN_RELEASE_BODY_CODE,
    REWRITTEN_RELEASE_BODY_MESSAGE,
    TITLE_NOT_ALLOWED_MESSAGE,
    TITLE_REQUIRED_MESSAGE,
    VOLATILE_PATH_CODE,
    VOLATILE_PATH_MESSAGE,
)


class DurablePostUsageError(ValueError):
    """Report an invalid GitHub post request shape."""


class DurablePostInputError(OSError):
    """Report an unreadable GitHub post input file."""


@dataclass(frozen=True)
class DurablePostFinding:
    """One GitHub post content finding."""

    code: str
    message: str


def _character_starts_path_segment(character: str) -> bool:
    return bool(character) and (
        character.isalnum() or character in PATH_SEGMENT_START_CHARACTERS
    )


def _text_has_anchored_marker(normalized_text: str, marker: str) -> bool:
    search_start = 0
    while True:
        found_index = normalized_text.find(marker, search_start)
        if found_index < 0:
            return False
        preceding_character = normalized_text[found_index - 1 : found_index]
        following_index = found_index + len(marker)
        following_character = normalized_text[following_index : following_index + 1]
        if (
            preceding_character == PATH_ANCHOR_CHARACTER
            or _character_starts_path_segment(following_character)
        ):
            return True
        search_start = found_index + 1


def find_volatile_path_marker(body_text: str) -> str | None:
    """Return the first volatile path marker in a GitHub post body."""
    normalized_text = body_text.replace("\\", PATH_ANCHOR_CHARACTER).lower()
    for each_marker in ALL_PATH_ANCHORED_VOLATILE_PATH_MARKERS:
        if _text_has_anchored_marker(normalized_text, each_marker):
            return each_marker
    for each_marker in ALL_BARE_VOLATILE_PATH_MARKERS:
        if each_marker in normalized_text:
            return each_marker
    return None


def read_body_file(body_file: Path) -> str:
    """Read one UTF-8 body file without exposing its contents on failure."""
    try:
        return body_file.read_text(encoding=BODY_FILE_ENCODING)
    except (OSError, UnicodeError) as error:
        raise DurablePostInputError(BODY_FILE_UNREADABLE_MESSAGE) from error


def _validate_request_shape(
    action: str,
    title: str | None,
    body_text: str | None,
) -> None:
    if action not in ALL_POST_ACTIONS:
        raise DurablePostUsageError(INVALID_ACTION_MESSAGE)
    if action in ALL_BODY_REQUIRED_ACTIONS and body_text is None:
        raise DurablePostUsageError(BODY_REQUIRED_MESSAGE)
    if action == ACTION_PR_CREATE and not title:
        raise DurablePostUsageError(TITLE_REQUIRED_MESSAGE)
    if action == ACTION_PR_EDIT and title is None and body_text is None:
        raise DurablePostUsageError(EDIT_INPUT_REQUIRED_MESSAGE)
    if title is not None and action not in ALL_TITLE_ACTIONS:
        raise DurablePostUsageError(TITLE_NOT_ALLOWED_MESSAGE)


def _description_heading_findings(body_text: str) -> list[DurablePostFinding]:
    all_body_lines = {each_line.strip() for each_line in body_text.splitlines()}
    return [
        DurablePostFinding(
            code=MISSING_HEADING_CODE,
            message=MISSING_HEADING_MESSAGE_TEMPLATE.format(heading=each_heading),
        )
        for each_heading in ALL_REQUIRED_PR_DESCRIPTION_HEADINGS
        if f"## {each_heading}" not in all_body_lines
    ]


def _title_findings(title: str | None) -> list[DurablePostFinding]:
    if title is None or CONVENTIONAL_TITLE_PATTERN.fullmatch(title) is not None:
        return []
    return [DurablePostFinding(code=INVALID_TITLE_CODE, message=INVALID_TITLE_MESSAGE)]


def _is_release_automation_branch(head_branch: str | None) -> bool:
    return head_branch is not None and head_branch.startswith(RELEASE_BRANCH_PREFIX)


def _release_body_findings(body_text: str) -> list[DurablePostFinding]:
    if all(each_marker in body_text for each_marker in ALL_RELEASE_BODY_MARKERS):
        return []
    return [
        DurablePostFinding(
            code=REWRITTEN_RELEASE_BODY_CODE,
            message=REWRITTEN_RELEASE_BODY_MESSAGE,
        )
    ]


def _body_findings(
    action: str,
    body_text: str | None,
    head_branch: str | None = None,
) -> list[DurablePostFinding]:
    if body_text is None:
        return []
    all_findings: list[DurablePostFinding] = []
    if not body_text.strip():
        all_findings.append(
            DurablePostFinding(
                code=EMPTY_BODY_CODE,
                message=BODY_MUST_NOT_BE_EMPTY_MESSAGE,
            )
        )
    if _is_release_automation_branch(head_branch):
        all_findings.extend(_release_body_findings(body_text))
    elif action in ALL_PR_DESCRIPTION_ACTIONS:
        all_findings.extend(_description_heading_findings(body_text))
    if find_volatile_path_marker(body_text) is not None:
        all_findings.append(
            DurablePostFinding(
                code=VOLATILE_PATH_CODE,
                message=VOLATILE_PATH_MESSAGE,
            )
        )
    return all_findings


def lint_durable_post(
    action: str,
    title: str | None,
    body_text: str | None,
    head_branch: str | None = None,
) -> tuple[DurablePostFinding, ...]:
    """Return content findings for one locally valid GitHub post request."""
    _validate_request_shape(action, title, body_text)
    return (
        *_title_findings(title),
        *_body_findings(action, body_text, head_branch),
    )


def _parse_arguments(all_arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--action", required=True)
    parser.add_argument("--title")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--head-branch")
    return parser.parse_args(list(all_arguments))


def main(all_arguments: Sequence[str]) -> int:
    """Validate one GitHub post and return its result status."""
    arguments = _parse_arguments(all_arguments)
    try:
        body_text = (
            read_body_file(arguments.body_file)
            if arguments.body_file is not None
            else None
        )
        all_findings = lint_durable_post(
            action=arguments.action,
            title=arguments.title,
            body_text=body_text,
            head_branch=arguments.head_branch,
        )
    except (DurablePostInputError, DurablePostUsageError) as error:
        sys.stderr.write(f"{error}\n")
        return INPUT_ERROR_EXIT_CODE
    for each_finding in all_findings:
        sys.stderr.write(f"{each_finding.message}\n")
    return CONTENT_FINDING_EXIT_CODE if all_findings else CLEAN_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
