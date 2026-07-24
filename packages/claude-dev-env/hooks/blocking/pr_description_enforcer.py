"""PreToolUse hook gating gh pr create/edit/comment bodies and gh pr ready.

Reads a PreToolUse JSON payload on stdin, audits body-carrying gh pr
create/edit/comment invocations against the Anthropic claude-code style
rules, denies a create or edit body that hand-types a pytest count, runs
the proof-of-work audit on proof-shaped comment bodies, and denies gh pr
ready while the PR carries no passing proof comment. Each subcommand flag
is read from the same logical line the audited body comes from, so a later
segment of a chained command never decides which rules apply.
Readability-management CLI flags short-circuit the stdin path to adjust
the persisted readability state.
"""

import json
import os
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.pr_description_body_audit import (  # noqa: E402
    _body_contains_any_header,
    _compute_pr_body_shape,
    _count_substantive_prose_chars,
    _extract_vague_scan_text,
    _iter_section_headers,
    _matches_self_closing_reference,
    _opens_with_this_pr_phrase,
    contains_hardcoded_test_count_claim,
)
from blocking._gh_body_arg_utils import (  # noqa: E402
    get_logical_first_line,
)
from blocking.pr_description_command_parser import (  # noqa: E402
    extract_body_from_command,
)
from blocking.pr_description_pr_number import (  # noqa: E402
    _command_carries_body_flag,
    _extract_pr_number_from_command,
)
from blocking.pr_description_proof_of_work import (  # noqa: E402
    audit_proof_comment_body,
    evaluate_pr_ready_gate,
    is_pr_ready_command,
    is_proof_shaped_body,
)
from blocking.pr_description_readability import (  # noqa: E402
    _build_readability_escape_hatch_message,
    _dispatch_cli_flag,
    _evaluate_readability_metrics,
    _extract_readability_target_text,
    _increment_strike_count,
    _is_readability_enabled,
    _load_readability_thresholds,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    ALL_HEAVY_OPENING_HEADERS,
    ALL_HEAVY_TESTING_HEADERS,
    ALL_READABILITY_CLI_FLAG_TOKENS,
    HARDCODED_TEST_COUNT_MESSAGE,
    HEAVY_SHAPE,
    MINIMUM_SUBSTANTIVE_PROSE_CHARS,
    PR_GUIDE_PATH,
    READABILITY_STRIKE_THRESHOLD,
    SELF_CLOSING_REFERENCE_MESSAGE_PREFIX,
    SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX,
    TRIVIAL_BODY_CHAR_THRESHOLD,
    VAGUE_LANGUAGE_PATTERN,
)


def validate_pr_body(body: str, pr_number: int | None = None) -> list[str]:
    """Audit a PR body against the Anthropic claude-code style rules.

    Args:
        body: The PR body markdown text to audit.
        pr_number: The PR number when known (gh pr edit / gh pr comment); None at gh pr create time.

    Returns:
        A list of human-readable violation messages. Empty when the body passes.
    """
    violations: list[str] = []

    substantive_chars = _count_substantive_prose_chars(body)
    if substantive_chars < MINIMUM_SUBSTANTIVE_PROSE_CHARS:
        violations.append(
            "PR body lacks substantive prose -- include a Why paragraph or "
            "substantive explanation, not only headers and bullets"
        )

    body_shape = _compute_pr_body_shape(body)

    if body_shape == HEAVY_SHAPE:
        if not _body_contains_any_header(body, ALL_HEAVY_OPENING_HEADERS):
            violations.append(
                f"Heavy PR body missing required opening header -- add one of "
                f"{sorted(ALL_HEAVY_OPENING_HEADERS)}"
            )
        if not _body_contains_any_header(body, ALL_HEAVY_TESTING_HEADERS):
            violations.append(
                f"Heavy PR body missing required testing-category header -- add one of "
                f"{sorted(ALL_HEAVY_TESTING_HEADERS)}"
            )

    body_has_any_header = len(_iter_section_headers(body)) > 0
    body_is_trivial_sized = substantive_chars < TRIVIAL_BODY_CHAR_THRESHOLD
    if body_has_any_header and body_is_trivial_sized:
        violations.append(
            "Trivial PR body contains a ceremony header -- drop every header "
            "and write the one-sentence body directly"
        )

    if pr_number is not None and _matches_self_closing_reference(body, pr_number):
        violations.append(
            f"{SELF_CLOSING_REFERENCE_MESSAGE_PREFIX}{pr_number}{SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX}"
        )

    if _opens_with_this_pr_phrase(body):
        violations.append(
            "PR body opens with 'This PR ...' -- open with an imperative verb "
            "(Adds, Fixes, Updates, Removes, Tightens, Ports)"
        )

    vague_scan_text = _extract_vague_scan_text(body)
    vague_matches = VAGUE_LANGUAGE_PATTERN.findall(vague_scan_text)
    if vague_matches:
        violations.append(
            f"Vague language detected: {', '.join(vague_matches)} -- "
            "be specific about what changed and why"
        )

    if _is_readability_enabled():
        thresholds = _load_readability_thresholds()
        target_text = _extract_readability_target_text(body)
        metric_violations = _evaluate_readability_metrics(target_text, thresholds)
        if metric_violations:
            post_increment_count = _increment_strike_count()
            if post_increment_count >= READABILITY_STRIKE_THRESHOLD:
                violations.append(_build_readability_escape_hatch_message())
            else:
                violations.extend(metric_violations)

    return violations


def _emit_denial(denial_reason: str) -> None:
    """Print the PreToolUse deny payload for a violation and log the block.

    Args:
        denial_reason: The permissionDecisionReason text for the deny payload.
    """
    denial_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": denial_reason,
        }
    }
    log_hook_block(
        calling_hook_name="pr_description_enforcer.py",
        hook_event="PreToolUse",
        block_reason=denial_reason,
    )
    print(json.dumps(denial_payload))
    sys.stdout.flush()


def main() -> None:
    for each_argv_token in sys.argv[1:]:
        if each_argv_token in ALL_READABILITY_CLI_FLAG_TOKENS:
            _dispatch_cli_flag(
                each_argv_token,
                output_stream=sys.stdout,
                error_stream=sys.stderr,
            )
            return

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    if is_pr_ready_command(command):
        ready_denial_reason = evaluate_pr_ready_gate(command)
        if ready_denial_reason is not None:
            _emit_denial(ready_denial_reason)
            sys.exit(0)

    body_owning_invocation = get_logical_first_line(command)
    has_any_body_flag = _command_carries_body_flag(body_owning_invocation)
    is_pr_create = "gh pr create" in body_owning_invocation and has_any_body_flag
    is_pr_edit = "gh pr edit" in body_owning_invocation and has_any_body_flag
    is_pr_comment = "gh pr comment" in body_owning_invocation and has_any_body_flag

    if not (is_pr_create or is_pr_edit or is_pr_comment):
        sys.exit(0)

    body = extract_body_from_command(command)

    if body is None:
        sys.exit(0)

    extracted_pr_number = None
    if is_pr_edit or is_pr_comment:
        extracted_pr_number = _extract_pr_number_from_command(command)

    violations = validate_pr_body(body, pr_number=extracted_pr_number)

    if (is_pr_create or is_pr_edit) and contains_hardcoded_test_count_claim(body):
        violations.append(HARDCODED_TEST_COUNT_MESSAGE)

    if is_pr_comment and is_proof_shaped_body(body):
        violations.extend(audit_proof_comment_body(body, extracted_pr_number))

    if violations:
        violation_list = "; ".join(violations)
        pr_guide_reference = f" @{PR_GUIDE_PATH}" if os.path.exists(PR_GUIDE_PATH) else ""
        _emit_denial(
            f"BLOCKED: [PR_DESCRIPTION] {violation_list}. "
            f"Rewrite the body yourself in Anthropic claude-code style. "
            f"Guide:{pr_guide_reference}"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
