"""Golden differential and behavior tests for the PostToolUse dispatcher.

The golden differential test runs a payload through every hosted PostToolUse
hook as its own subprocess (the production path), records each hook's block
decision, computes the expected aggregate, then runs the dispatcher on the same
payload and asserts an equal block-or-allow decision and the union of reasons.

Three focused tests pin the side-effecting behavior the dispatcher must not
change: the formatter formats only on a Write of a file git does not yet track
and never blocks; the type-checker still blocks on a real type error when run
through the dispatcher; and non-block stdout from side-effect hooks (such as
the doc-gist htmlpreview URL) survives on both the allow and block paths.

Crash and early-exit tests exercise the aggregator directly: an early hook
crash before mypy does not drop mypy's block, a non-blocking hook crash leaves
the decision allow, and a blocking hook crash surfaces a block.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

_VALIDATION_DIR_STR = str(Path(__file__).resolve().parent)
if _VALIDATION_DIR_STR not in sys.path:
    sys.path.insert(0, _VALIDATION_DIR_STR)

from hooks_constants.post_tool_use_dispatcher_constants import (  # noqa: E402, I001
    ALL_POST_HOSTED_HOOK_ENTRIES,
    BLOCK_DECISION,
    EMPTY_REASON_BLOCK_FALLBACK,
    PLUGIN_ROOT_PLACEHOLDER,
    PostHostedHookEntry,
)
from post_tool_use_dispatcher import (  # noqa: E402, I001
    PostHostedHookResult,
    aggregate_post_hosted_hook_results,
)

_VALIDATION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _VALIDATION_DIR.parent
_PLUGIN_ROOT = _HOOKS_ROOT.parent
_DISPATCHER_SCRIPT = str(_VALIDATION_DIR / "post_tool_use_dispatcher.py")

_WRITE_TOOL_NAME = "Write"
_EDIT_TOOL_NAME = "Edit"


def _resolve_extra_arguments(each_entry: PostHostedHookEntry) -> list[str]:
    """Resolve a hook entry's relative argument paths to absolute argv values.

    Args:
        each_entry: The hosted hook entry whose extra arguments to resolve.

    Returns:
        The resolved argument list. The plugin-root placeholder resolves to the
        plugin root absolute path; every other entry resolves relative to it.
    """
    resolved_arguments: list[str] = []
    for each_relative_path in each_entry.extra_argument_relative_paths:
        if each_relative_path == PLUGIN_ROOT_PLACEHOLDER:
            resolved_arguments.append(str(_PLUGIN_ROOT))
        else:
            resolved_arguments.append(str(_PLUGIN_ROOT / each_relative_path))
    return resolved_arguments


def _run_hook_subprocess(
    each_entry: PostHostedHookEntry, payload_text: str
) -> subprocess.CompletedProcess[str]:
    """Run one hosted hook script as a subprocess, returning the completed process.

    Args:
        each_entry: The hosted hook entry naming the script and its arguments.
        payload_text: The JSON payload to send on stdin.

    Returns:
        The completed subprocess result with stdout and stderr captured.
    """
    script_path = str(_HOOKS_ROOT / each_entry.script_relative_path)
    command = [sys.executable, script_path, *_resolve_extra_arguments(each_entry)]
    return subprocess.run(
        command,
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _run_dispatcher(payload_text: str) -> subprocess.CompletedProcess[str]:
    """Run the PostToolUse dispatcher as a subprocess.

    Args:
        payload_text: The JSON payload to send on stdin.

    Returns:
        The completed subprocess result with stdout and stderr captured.
    """
    return subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT, str(_PLUGIN_ROOT)],
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _parse_block_decision(completed_process: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    """Parse one hook's subprocess result into (is_block, reason_text).

    Args:
        completed_process: The completed subprocess from running a hook.

    Returns:
        A (is_block, reason_text) pair where is_block is True when the hook
        emitted a PostToolUse block decision, and reason_text carries the
        block reason.
    """
    stdout_text = completed_process.stdout.strip()
    if not stdout_text:
        return False, ""
    try:
        parsed_output = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False, ""
    if not isinstance(parsed_output, dict):
        return False, ""
    is_block = parsed_output.get("decision") == BLOCK_DECISION
    reason_text = parsed_output.get("reason", "")
    return is_block, reason_text if isinstance(reason_text, str) else ""


def _compute_expected_aggregate(payload_text: str) -> tuple[bool, list[str]]:
    """Run each hosted hook individually and compute the expected aggregate.

    Args:
        payload_text: The JSON payload text to send to each hook.

    Returns:
        A (should_block, all_block_reasons) pair where should_block is True when
        any hook blocks, and all_block_reasons collects every blocking reason.
    """
    all_block_reasons: list[str] = []
    for each_entry in ALL_POST_HOSTED_HOOK_ENTRIES:
        completed_process = _run_hook_subprocess(each_entry, payload_text)
        is_block, reason_text = _parse_block_decision(completed_process)
        if is_block and reason_text:
            all_block_reasons.append(reason_text)
    return bool(all_block_reasons), all_block_reasons


def _write_payload(file_path: str, content: str) -> str:
    """Build a Write tool payload JSON string.

    Args:
        file_path: The target file path.
        content: The file content written.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": _WRITE_TOOL_NAME,
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


def _edit_payload(file_path: str, old_string: str, new_string: str) -> str:
    """Build an Edit tool payload JSON string.

    Args:
        file_path: The target file path.
        old_string: The text replaced.
        new_string: The replacement text.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": _EDIT_TOOL_NAME,
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )


def _assert_dispatcher_matches_individual_hooks(payload_text: str) -> None:
    """Assert the dispatcher's decision matches the union of individual hook decisions.

    Runs each hosted hook individually, computes the expected aggregate (block
    if any blocks, union of every blocking reason), then runs the dispatcher and
    asserts an equal outcome.

    Args:
        payload_text: The JSON payload text.
    """
    expected_block, all_expected_reasons = _compute_expected_aggregate(payload_text)
    dispatcher_result = _run_dispatcher(payload_text)
    dispatcher_is_block, dispatcher_reason = _parse_block_decision(dispatcher_result)
    assert dispatcher_is_block == expected_block, (
        f"dispatcher block={dispatcher_is_block} but expected block={expected_block}. "
        f"Dispatcher reason: {dispatcher_reason!r}. "
        f"Expected reasons: {all_expected_reasons!r}"
    )
    for each_expected_reason in all_expected_reasons:
        assert each_expected_reason in dispatcher_reason, (
            f"Missing reason in dispatcher output.\n"
            f"Expected to find: {each_expected_reason!r}\n"
            f"Dispatcher reason: {dispatcher_reason!r}"
        )


def test_clean_edit_of_plain_text_allows() -> None:
    """Dispatcher allows an Edit of a non-Python plain-text file (no hook blocks)."""
    plain_text_path = str(_VALIDATION_DIR / "CLAUDE.md")
    payload_text = _edit_payload(plain_text_path, "old line", "new line")
    _assert_dispatcher_matches_individual_hooks(payload_text)


def test_clean_write_of_nonexistent_path_allows() -> None:
    """Dispatcher allows a Write whose path does not exist (mypy and doc-gist skip)."""
    missing_path = str(_VALIDATION_DIR / "does_not_exist_dispatcher_probe.txt")
    payload_text = _write_payload(missing_path, "hello world\n")
    _assert_dispatcher_matches_individual_hooks(payload_text)


def test_edit_of_non_html_skips_doc_gist_allows() -> None:
    """Dispatcher allows an Edit of an existing non-HTML file with no sentinel."""
    existing_path = str(Path(__file__).resolve())
    payload_text = _edit_payload(existing_path, "old", "new")
    _assert_dispatcher_matches_individual_hooks(payload_text)


def test_malformed_payload_allows_fail_open() -> None:
    """Dispatcher allows when the payload is malformed, matching fail-open posture."""
    dispatcher_result = _run_dispatcher("not valid json {{{")
    is_block, _reason = _parse_block_decision(dispatcher_result)
    assert not is_block, "Dispatcher must allow on malformed payload (fail-open)"
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0 on malformed payload, got {dispatcher_result.returncode}"
    )


def test_empty_payload_allows_fail_open() -> None:
    """Dispatcher allows when stdin is empty, matching fail-open posture."""
    dispatcher_result = _run_dispatcher("")
    is_block, _reason = _parse_block_decision(dispatcher_result)
    assert not is_block, "Dispatcher must allow on empty payload (fail-open)"
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0 on empty payload, got {dispatcher_result.returncode}"
    )


def test_type_checker_still_blocks_on_type_error_through_dispatcher() -> None:
    """The type-checker's block on a real type error survives through the dispatcher.

    Writes a Python file with a genuine type error inside this repository so
    mypy_validator discovers the project root and blocks, then runs the same
    payload through the dispatcher and asserts the dispatcher emits the block.
    """
    type_error_file = _VALIDATION_DIR / "dispatcher_type_error_probe.py"
    type_error_file.write_text(
        "def add_one(value: int) -> int:\n    return value + 1\n\n\nadd_one('not an int')\n",
        encoding="utf-8",
    )
    try:
        payload_text = _write_payload(str(type_error_file), type_error_file.read_text())
        direct_block, direct_reason = _parse_block_decision(
            _run_hook_subprocess(ALL_POST_HOSTED_HOOK_ENTRIES[0], payload_text)
        )
        assert direct_block, (
            "Precondition failed: mypy_validator did not block a real type error "
            f"directly. Reason: {direct_reason!r}. Is mypy installed and the file "
            "inside the git project?"
        )
        dispatcher_result = _run_dispatcher(payload_text)
        dispatcher_is_block, dispatcher_reason = _parse_block_decision(dispatcher_result)
        assert dispatcher_is_block, (
            "Dispatcher must block when the type-checker blocks on a type error. "
            f"Dispatcher stdout: {dispatcher_result.stdout!r}"
        )
        assert direct_reason in dispatcher_reason, (
            "Dispatcher block reason must carry the type-checker's reason.\n"
            f"Expected: {direct_reason!r}\n"
            f"Dispatcher reason: {dispatcher_reason!r}"
        )
    finally:
        type_error_file.unlink(missing_ok=True)


def test_formatter_formats_only_untracked_write_and_never_blocks(tmp_path: Path) -> None:
    """The formatter acts only on an untracked-file Write and never blocks.

    Writes an unformatted Python file into a git repo at tmp_path so the file is
    untracked, runs a Write payload through the dispatcher, and asserts the file
    is formatted on disk and the dispatcher does not block. Then runs an Edit
    payload for the same path and asserts the formatter leaves an unformatted
    file untouched, proving the Write-untracked gate still holds through the
    dispatcher.

    Args:
        tmp_path: Pytest temp directory hosting the throwaway git repository.
    """
    subprocess.run(
        ["git", "init", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    unformatted_source = "x=1\ny  =  2\n"
    untracked_file = tmp_path / "untracked_module.py"
    untracked_file.write_text(unformatted_source, encoding="utf-8")

    write_payload_text = _write_payload(str(untracked_file), unformatted_source)
    dispatcher_result = _run_dispatcher(write_payload_text)
    is_block, _reason = _parse_block_decision(dispatcher_result)
    assert not is_block, "Formatter must never block a Write through the dispatcher"
    formatted_source = untracked_file.read_text(encoding="utf-8")
    assert formatted_source != unformatted_source, (
        "Formatter must reformat an untracked-file Write through the dispatcher.\n"
        f"On-disk content unchanged: {formatted_source!r}"
    )

    untracked_file.write_text(unformatted_source, encoding="utf-8")
    edit_payload_text = _edit_payload(str(untracked_file), "x=1", "x = 1")
    edit_dispatcher_result = _run_dispatcher(edit_payload_text)
    edit_is_block, _edit_reason = _parse_block_decision(edit_dispatcher_result)
    assert not edit_is_block, "Formatter must never block an Edit through the dispatcher"
    after_edit_source = untracked_file.read_text(encoding="utf-8")
    assert after_edit_source == unformatted_source, (
        "Formatter must not reformat on an Edit (it acts only on an untracked Write).\n"
        f"On-disk content changed to: {after_edit_source!r}"
    )


def test_non_block_stdout_preserved_in_aggregator_allow_path() -> None:
    """Aggregator preserves non-block hook stdout on the allow path.

    A side-effect hook (such as doc_gist_auto_publish) writes informational
    text to stdout without emitting a block decision. The aggregator must carry
    that text into all_non_block_stdout so the dispatcher can write it to the
    real stdout on the allow path.
    """
    informational_text = "https://htmlpreview.github.io/?https://gist.github.com/abc/123"
    all_results = [
        PostHostedHookResult(captured_stdout="", did_crash=False, is_blocking=True),
        PostHostedHookResult(
            captured_stdout=informational_text, did_crash=False, is_blocking=False
        ),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert not aggregated_decision.should_block, (
        "Aggregator must allow when no hook blocks"
    )
    assert informational_text in aggregated_decision.all_non_block_stdout, (
        "Aggregator must preserve non-block hook stdout in all_non_block_stdout.\n"
        f"Expected to find: {informational_text!r}\n"
        f"Got: {aggregated_decision.all_non_block_stdout!r}"
    )


def test_non_block_stdout_preserved_in_aggregator_block_path() -> None:
    """Aggregator preserves non-block hook stdout even when another hook blocks.

    When mypy_validator blocks and doc_gist_auto_publish wrote informational
    text, both the block reason and the informational text survive in the
    aggregated decision so _emit_block_decision can forward both to stdout.
    """
    mypy_block_json = json.dumps({"decision": BLOCK_DECISION, "reason": "[MYPY] Type errors: x"})
    informational_text = "https://htmlpreview.github.io/?https://gist.github.com/abc/456"
    all_results = [
        PostHostedHookResult(captured_stdout=mypy_block_json, did_crash=False, is_blocking=True),
        PostHostedHookResult(
            captured_stdout=informational_text, did_crash=False, is_blocking=False
        ),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert aggregated_decision.should_block, (
        "Aggregator must block when mypy_validator blocks"
    )
    assert informational_text in aggregated_decision.all_non_block_stdout, (
        "Aggregator must preserve non-block hook stdout even on the block path.\n"
        f"Expected to find: {informational_text!r}\n"
        f"Got: {aggregated_decision.all_non_block_stdout!r}"
    )


def test_early_hook_crash_does_not_drop_later_blocking_hook_block() -> None:
    """A crash in an early hook does not prevent a later blocking hook's block.

    Simulates a scenario where a non-blocking hook crashes before mypy_validator
    runs and blocks. The aggregated decision must still block, proving the
    dispatcher continues past a crash to collect all results.
    """
    mypy_block_json = json.dumps(
        {"decision": BLOCK_DECISION, "reason": "[MYPY] Type errors: y"}
    )
    all_results = [
        PostHostedHookResult(captured_stdout="", did_crash=True, is_blocking=False),
        PostHostedHookResult(
            captured_stdout=mypy_block_json, did_crash=False, is_blocking=True
        ),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert aggregated_decision.should_block, (
        "An early non-blocking hook crash must not prevent mypy_validator's block "
        "from reaching the aggregated decision"
    )
    assert any("[MYPY]" in each_reason for each_reason in aggregated_decision.all_block_reasons), (
        "The mypy block reason must survive in the aggregated decision.\n"
        f"Block reasons: {aggregated_decision.all_block_reasons!r}"
    )


def test_non_blocking_hook_crash_leaves_decision_allow() -> None:
    """A crash in a non-blocking hook does not change an allow to a block.

    A side-effect hook such as auto_formatter or doc_gist_auto_publish carries
    is_blocking=False. Its crash must not surface a blocking signal — the
    aggregated decision stays allow.
    """
    all_results = [
        PostHostedHookResult(captured_stdout="", did_crash=True, is_blocking=False),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert not aggregated_decision.should_block, (
        "A non-blocking hook crash must not change an allow to a block"
    )


def test_empty_reason_block_still_blocks_with_fallback_reason() -> None:
    """A block decision carrying an empty reason still blocks with a fallback reason.

    A blocking hook that emits decision=block with an empty reason string must
    still block. The aggregator substitutes EMPTY_REASON_BLOCK_FALLBACK so the
    block is not silently downgraded to allow.
    """
    empty_reason_block_json = json.dumps({"decision": BLOCK_DECISION, "reason": ""})
    all_results = [
        PostHostedHookResult(
            captured_stdout=empty_reason_block_json, did_crash=False, is_blocking=True
        ),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert aggregated_decision.should_block, (
        "An empty-reason block must still block, not downgrade to allow"
    )
    assert EMPTY_REASON_BLOCK_FALLBACK in aggregated_decision.all_block_reasons, (
        "The aggregator must substitute a fallback reason for an empty-reason block.\n"
        f"Got block reasons: {aggregated_decision.all_block_reasons!r}"
    )
    assert empty_reason_block_json not in aggregated_decision.all_non_block_stdout, (
        "An empty-reason block's raw JSON must not leak into the informational stdout"
    )


def test_block_path_emits_single_parseable_json_object_on_stdout() -> None:
    """On the block path the dispatcher emits a single parseable JSON object on stdout.

    Writes a Python file with a real type error inside this repository so
    mypy_validator discovers the project root and blocks, then asserts the
    dispatcher's whole stdout parses as one JSON block object — no leading
    informational text mixed onto the same stream.
    """
    type_error_file = _VALIDATION_DIR / "dispatcher_block_stdout_probe.py"
    type_error_file.write_text(
        "def add_one(value: int) -> int:\n    return value + 1\n\n\nadd_one('not an int')\n",
        encoding="utf-8",
    )
    try:
        payload_text = _write_payload(str(type_error_file), type_error_file.read_text())
        direct_block, _direct_reason = _parse_block_decision(
            _run_hook_subprocess(ALL_POST_HOSTED_HOOK_ENTRIES[0], payload_text)
        )
        assert direct_block, (
            "Precondition failed: mypy_validator did not block a real type error directly. "
            "Is mypy installed and the file inside the git project?"
        )

        dispatcher_result = _run_dispatcher(payload_text)
        parsed_stdout = json.loads(dispatcher_result.stdout.strip())
        assert isinstance(parsed_stdout, dict), (
            "Dispatcher stdout on the block path must be a single JSON object.\n"
            f"Got: {dispatcher_result.stdout!r}"
        )
        assert parsed_stdout.get("decision") == BLOCK_DECISION, (
            "The single JSON object on stdout must carry the block decision.\n"
            f"Got: {parsed_stdout!r}"
        )
    finally:
        type_error_file.unlink(missing_ok=True)


def test_blocking_hook_crash_surfaces_a_block() -> None:
    """A crash in a blocking hook surfaces a block with a crash reason.

    When a blocking hook (such as mypy_validator) crashes before emitting any
    output, the aggregator must still block so a bad write does not silently
    pass. The block reason must reference the dispatcher's crash signal.
    """
    all_results = [
        PostHostedHookResult(captured_stdout="", did_crash=True, is_blocking=True),
    ]
    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    assert aggregated_decision.should_block, (
        "A blocking hook crash must surface a block"
    )
    assert aggregated_decision.all_block_reasons, (
        "The block reasons list must be non-empty after a blocking hook crash"
    )
    assert "dispatcher" in aggregated_decision.all_block_reasons[0].lower(), (
        "The block reason from a blocking hook crash must reference the dispatcher.\n"
        f"Got: {aggregated_decision.all_block_reasons[0]!r}"
    )
