"""Validate workflow-generated plan packets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from anthropic_plan_scripts_constants.validate_packet_constants import (
    ALL_REQUIRED_RELATIVE_PATHS,
    EXIT_CODE_VALIDATION_FAILED,
    MARKDOWN_FILE_SUFFIX,
)


def required_relative_paths() -> tuple[str, ...]:
    """Return every required packet file path relative to the packet root.

    Returns:
        Every required packet file path, relative to the packet root.
    """
    return ALL_REQUIRED_RELATIVE_PATHS


def markdown_relative_paths() -> list[str]:
    """Return required markdown packet files.

    Returns:
        Each required packet file path that names a markdown file.
    """
    return [
        each_relative_path
        for each_relative_path in required_relative_paths()
        if each_relative_path.endswith(MARKDOWN_FILE_SUFFIX)
    ]


def validate_packet(packet_directory: Path) -> list[str]:
    """Return validation errors for a packet directory.

    Args:
        packet_directory: Directory that should contain a complete packet.

    Returns:
        Every validation error found, or an empty list when the packet is valid.
    """
    all_errors: list[str] = []
    all_errors.extend(missing_file_errors(packet_directory))
    all_errors.extend(markdown_content_errors(packet_directory))
    all_errors.extend(packet_json_errors(packet_directory))
    all_errors.extend(source_map_errors(packet_directory))
    all_errors.extend(tdd_plan_errors(packet_directory))
    all_errors.extend(implementation_step_errors(packet_directory))
    all_errors.extend(build_prompt_errors(packet_directory))
    return all_errors


def missing_file_errors(packet_directory: Path) -> list[str]:
    """Return one error for each missing required packet file.

    Args:
        packet_directory: Directory that should contain a complete packet.

    Returns:
        One error string for each required file absent from the directory.
    """
    return [
        f"missing required file: {each_relative_path}"
        for each_relative_path in required_relative_paths()
        if not (packet_directory / each_relative_path).is_file()
    ]


def markdown_content_errors(packet_directory: Path) -> list[str]:
    """Return errors for invalid markdown packet content.

    Args:
        packet_directory: Directory that should contain markdown packet files.

    Returns:
        One error string for each markdown file with placeholder or open-question text.
    """
    all_errors: list[str] = []
    for each_relative_path in markdown_relative_paths():
        packet_file = packet_directory / each_relative_path
        if not packet_file.is_file():
            continue
        markdown_text = packet_file.read_text(encoding="utf-8")
        if has_placeholder_text(markdown_text):
            all_errors.append(f"{each_relative_path} contains placeholder text")
        if has_open_questions_heading(markdown_text):
            all_errors.append(f"{each_relative_path} contains an Open Questions heading")
    return all_errors


def packet_json_errors(packet_directory: Path) -> list[str]:
    """Return errors for the machine-readable packet manifest.

    Args:
        packet_directory: Directory that should contain packet.json.

    Returns:
        One error string for each packet.json field that is missing or inconsistent.
    """
    packet_file = packet_directory / "packet.json"
    if not packet_file.is_file():
        return []
    try:
        payload_object: object = json.loads(packet_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as packet_error:
        return [f"packet.json is invalid JSON: {packet_error.msg}"]
    if not isinstance(payload_object, dict):
        return ["packet.json must contain an object"]

    all_errors: list[str] = []
    if payload_object.get("schemaVersion") != 1:
        all_errors.append("packet.json schemaVersion must be 1")
    if not isinstance(payload_object.get("slug"), str) or not payload_object.get("slug"):
        all_errors.append("packet.json slug must be a non-empty string")
    all_source_files = payload_object.get("sourceFiles")
    if not isinstance(all_source_files, list) or not all_source_files:
        all_errors.append("packet.json sourceFiles must be a non-empty list")
    stored_packet_path = payload_object.get("packetPath", "")
    if not is_same_packet_path(packet_directory, stored_packet_path):
        all_errors.append("packet.json packetPath must match the validated packet directory")
    if not isinstance(payload_object.get("validator"), dict):
        all_errors.append("packet.json validator must be an object")
    return all_errors


def is_same_packet_path(packet_directory: Path, stored_packet_path: object) -> bool:
    """Return whether a stored packetPath names the validated packet directory.

    Args:
        packet_directory: Directory passed to the validator on the command line.
        stored_packet_path: The packetPath value read from packet.json.

    Returns:
        True when both paths resolve to the same directory regardless of
        separator style, trailing separators, or relative-versus-absolute form,
        otherwise False.
    """
    if not isinstance(stored_packet_path, str) or not stored_packet_path:
        return False
    return packet_directory.resolve() == Path(stored_packet_path).resolve()


def source_map_errors(packet_directory: Path) -> list[str]:
    """Return errors for weak source-map grounding.

    Args:
        packet_directory: Directory that should contain context/source-map.md.

    Returns:
        An error string when the source map lacks source-grounded rows, else an empty list.
    """
    source_map_file = packet_directory / "context" / "source-map.md"
    if not source_map_file.is_file():
        return []
    source_map_text = source_map_file.read_text(encoding="utf-8")
    if not has_source_table_row(source_map_text):
        return ["source-map.md must include source-grounded rows"]
    return []


def tdd_plan_errors(packet_directory: Path) -> list[str]:
    """Return errors for a weak TDD plan.

    Args:
        packet_directory: Directory that should contain implementation/tdd-plan.md.

    Returns:
        One error string for each TDD-plan requirement the file fails to state.
    """
    tdd_file = packet_directory / "implementation" / "tdd-plan.md"
    if not tdd_file.is_file():
        return []
    tdd_text = tdd_file.read_text(encoding="utf-8").lower()
    if "failing test" not in tdd_text and not re.search(r"\bred\b", tdd_text):
        return ["tdd-plan.md must name failing tests"]
    if "production" not in tdd_text and "green" not in tdd_text:
        return ["tdd-plan.md must state the production-code step after red"]
    return []


def implementation_step_errors(packet_directory: Path) -> list[str]:
    """Return errors for implementation steps without test coverage.

    Args:
        packet_directory: Directory that should contain implementation/steps.md.

    Returns:
        An error string when a numbered step names no test or non-code reason, else an empty list.
    """
    steps_file = packet_directory / "implementation" / "steps.md"
    if not steps_file.is_file():
        return []
    step_lines = [
        each_line.strip()
        for each_line in steps_file.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\d+\.\s+", each_line.strip())
    ]
    missing_test_lines = [
        each_line
        for each_line in step_lines
        if not step_line_has_test_contract(each_line)
    ]
    if missing_test_lines:
        return ["implementation/steps.md has steps without a test or non-code reason"]
    return []


def build_prompt_errors(packet_directory: Path) -> list[str]:
    """Return errors for a handoff prompt that depends on chat history.

    Args:
        packet_directory: Directory that should contain handoff/build-prompt.md.

    Returns:
        One error string for each standalone-handoff requirement the prompt fails.
    """
    build_prompt_file = packet_directory / "handoff" / "build-prompt.md"
    if not build_prompt_file.is_file():
        return []
    build_prompt_text = build_prompt_file.read_text(encoding="utf-8").lower()
    if any(each_phrase in build_prompt_text for each_phrase in forbidden_chat_phrases()):
        return ["build-prompt.md must stand alone without chat history"]
    if "use only this packet" not in build_prompt_text:
        return ["build-prompt.md must tell the build agent to use only this packet"]
    return []


def has_placeholder_text(markdown_text: str) -> bool:
    """Return whether markdown contains unresolved placeholder text.

    Args:
        markdown_text: Markdown content to inspect.

    Returns:
        True when the markdown contains placeholder tokens, otherwise False.
    """
    placeholder_pattern = re.compile(
        r"\b(?:todo|tbd|fixme|replace_me|placeholder|fill this in)\b|{{|}}",
        re.IGNORECASE,
    )
    return bool(placeholder_pattern.search(markdown_text))


def has_open_questions_heading(markdown_text: str) -> bool:
    """Return whether markdown contains an Open Questions heading.

    Args:
        markdown_text: Markdown content to inspect.

    Returns:
        True when the markdown contains an Open Questions heading, otherwise False.
    """
    heading_pattern = re.compile(
        r"^\s*(?:#{1,6}\s+|\*\*\s*|__\s*)open[\s_-]+questions(?:[^A-Za-z0-9]|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(heading_pattern.search(strip_markdown_code(markdown_text)))


def strip_markdown_code(markdown_text: str) -> str:
    """Return markdown with code spans and fenced blocks removed.

    Args:
        markdown_text: Markdown content to strip.

    Returns:
        The markdown content with fenced blocks and inline code spans removed.
    """
    without_fences = re.sub(r"```[\s\S]*?```", "", markdown_text)
    return re.sub(r"``[^`\n]+``|`[^`\n]+`", "", without_fences)


def has_source_table_row(source_map_text: str) -> bool:
    """Return whether source-map.md has at least one concrete source row.

    Args:
        source_map_text: The source map markdown content.

    Returns:
        True when at least one table row names a concrete source path, otherwise False.
    """
    source_file_token_pattern = re.compile(
        r"[\w-]+\.(?:py|pyi|js|mjs|cjs|jsx|ts|tsx|mts|cts|json|jsonc|ya?ml|toml|ini|cfg"
        r"|mdx?|rst|txt|sh|bash|ps[dm]?1|sql|html?|s?css|sass|less|go|rs|java|kts?|rb|php"
        r"|cc?|cpp|h|hpp|cs|swift|scala|lua|vue|svelte|xml|env|lock|dockerfile|mk|gradle"
        r"|proto|gr?aphql|gql)\b",
        re.IGNORECASE,
    )
    for each_line in source_map_text.splitlines():
        normalized_line = each_line.strip()
        if not normalized_line.startswith("|"):
            continue
        if set(normalized_line.replace("|", "").strip()) <= {"-", ":"}:
            continue
        if "source" in normalized_line.lower() and "facts" in normalized_line.lower():
            continue
        if "/" in normalized_line or "\\" in normalized_line:
            return True
        if source_file_token_pattern.search(normalized_line):
            return True
    return False


def step_line_has_test_contract(step_line: str) -> bool:
    """Return whether a step names test coverage or a non-code reason.

    Args:
        step_line: Numbered implementation step line.

    Returns:
        True when the step names a test or a non-code reason, otherwise False.
    """
    normalized_line = step_line.lower()
    return (
        "test" in normalized_line
        or "non-code" in normalized_line
        or "covered by" in normalized_line
    )


def forbidden_chat_phrases() -> tuple[str, ...]:
    """Return phrases that make a handoff prompt depend on chat history.

    Returns:
        Each phrase that signals a handoff prompt depends on chat history.
    """
    return (
        "as discussed above",
        "from our chat",
        "previous conversation",
        "earlier in this thread",
    )


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        The parsed command-line arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Validate a plan packet directory.")
    parser.add_argument("packet_directory", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run the packet validator CLI.

    Returns:
        Zero when the packet is valid, or a non-zero exit code when validation errors are found.
    """
    parsed_arguments = parse_arguments()
    packet_directory = parsed_arguments.packet_directory
    all_errors = validate_packet(packet_directory)
    if all_errors:
        for each_error in all_errors:
            print(each_error, file=sys.stderr)
        return EXIT_CODE_VALIDATION_FAILED
    print("packet validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
