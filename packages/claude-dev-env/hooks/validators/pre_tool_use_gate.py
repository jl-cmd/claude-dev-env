"""The PreToolUse gate: deny only newly-introduced violations, failing closed."""

import json
import sys
from typing import Dict, List, Optional

from blocking.code_rules_shared import is_ephemeral_path
from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.multi_edit_reconstruction import apply_edits, edits_for_tool

from .baseline_diff import _baseline_violation_identities, _scope_new_and_preexisting
from .file_content_io import _read_target_file_content
from .file_scoped_runners import validate_proposed_file
from .validator_result import ValidatorResult
from .violation_parsing import _failed_results


def reconstruct_proposed_content(
    tool_name: str, tool_input: Dict[str, object]
) -> Optional[str]:
    """Return the post-edit content one Write, Edit, or MultiEdit payload leaves on disk.

    ::

        Write     -> tool_input["content"] verbatim
        Edit      -> existing file, each old_string rewritten to new_string
        MultiEdit -> existing file, each edit applied in order

    The Edit and MultiEdit reconstruction reuses the shared applier so this gate
    judges the same post-edit content the standalone blockers judge.

    Args:
        tool_name: The intercepted tool — Write, Edit, or MultiEdit.
        tool_input: The tool's input payload.

    Returns:
        The proposed post-edit content, or None when the payload carries no
        readable target for an edit or no string content for a write.
    """
    if tool_name == "Write":
        written_content = tool_input.get("content", "")
        return written_content if isinstance(written_content, str) else None
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    existing_content = _read_target_file_content(file_path)
    if existing_content is None:
        return None
    return apply_edits(existing_content, edits_for_tool(tool_name, dict(tool_input)))


def _validator_summaries(results: List[ValidatorResult]) -> str:
    """Join one ``name (checks): output`` summary per result with a separator.

    Args:
        results: The validator results to summarize.

    Returns:
        The joined summary text shared by the deny reason and the warning.
    """
    validator_summary_separator = " | "
    return validator_summary_separator.join(
        f"{each_result.name} (checks {each_result.checks}): {each_result.output.strip()}"
        for each_result in results
    )


def _proposed_content_deny_reason(failed_results: List[ValidatorResult]) -> str:
    """Compose the deny reason naming each failing validator and its output.

    Args:
        failed_results: The validator results that did not pass.

    Returns:
        The composed ``permissionDecisionReason`` text.
    """
    return (
        f"BLOCKED: [validators] {len(failed_results)} "
        f"validator(s) failed: {_validator_summaries(failed_results)}"
    )


def _emit_pre_tool_use_deny(deny_reason: str) -> None:
    """Write one PreToolUse deny JSON payload carrying *deny_reason* to stdout."""
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name="run_all_validators.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    sys.stdout.write(json.dumps(deny_payload) + "\n")
    sys.stdout.flush()


def _emit_pre_existing_warning(all_preexisting_results: List[ValidatorResult]) -> None:
    """Write a stderr advisory naming each pre-existing violation left in place."""
    advisory_summaries = _validator_summaries(all_preexisting_results)
    sys.stderr.write(
        "[run_all_validators] allowed with warning: "
        f"pre-existing violation(s) unchanged: {advisory_summaries}\n"
    )
    sys.stderr.flush()


def _decide_pre_tool_use(file_path: str, proposed_content: str) -> None:
    """Deny only violations absent from the baseline; warn on the ones that persist.

    Args:
        file_path: The write's target path.
        proposed_content: The reconstructed post-edit content of that file.
    """
    all_proposed_failed = _failed_results(
        validate_proposed_file(file_path, proposed_content)
    )
    if not all_proposed_failed:
        return
    baseline_identities = _baseline_violation_identities(file_path)
    all_new_results, all_preexisting_results = _scope_new_and_preexisting(
        all_proposed_failed, proposed_content, baseline_identities
    )
    if all_preexisting_results:
        _emit_pre_existing_warning(all_preexisting_results)
    if all_new_results:
        _emit_pre_tool_use_deny(_proposed_content_deny_reason(all_new_results))


def _evaluate_pre_tool_use_payload() -> None:
    """Read the PreToolUse payload from stdin and deny only newly-introduced violations.

    The path-based exemption decision runs against the real target path from the
    payload, so an ephemeral scratch or session scratchpad target passes without
    validation before any baseline-scoped decision runs. For a non-exempt target,
    each located violation is keyed by validator name, enclosing function, and
    message, then counted against the on-disk baseline. A violation beyond the
    baseline's budget for its key denies the write; one the baseline already
    carries passes with a stderr advisory. Writes nothing for a clean file, an
    exempt target, or an unparseable payload.
    """
    pre_tool_use_payload = json.load(sys.stdin)
    if not isinstance(pre_tool_use_payload, dict):
        return
    tool_name = pre_tool_use_payload.get("tool_name", "")
    tool_input = pre_tool_use_payload.get("tool_input", {})
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return
    if is_ephemeral_path(file_path, pre_tool_use_payload):
        return
    proposed_content = reconstruct_proposed_content(tool_name, tool_input)
    if not proposed_content:
        return
    _decide_pre_tool_use(file_path, proposed_content)


def run_pre_tool_use_gate() -> int:
    """Run the PreToolUse gate, failing closed on any internal fault.

    A block is signaled through a deny payload rather than an exit code, so the
    gate always returns 0. A malformed hook payload is not a write to gate and
    passes silently. Any other fault emits a deny naming the gate, so an
    unrecoverable internal error blocks the write rather than letting it through
    unchecked.

    Returns:
        Always 0 — a block is signaled through the deny payload, not an exit code.
    """
    try:
        _evaluate_pre_tool_use_payload()
    except json.JSONDecodeError:
        return 0
    except Exception as error:
        _emit_pre_tool_use_deny(
            f"BLOCKED: [validators] pre-tool-use gate faulted; write blocked: {error}"
        )
    return 0
