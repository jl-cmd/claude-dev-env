"""Single source of truth for the code-review enforcement gate family.

Holds the stamp directory name, the ordered effort tokens (``low`` under
``medium`` under ``high`` under ``xhigh`` under ``max``, with ``ultra`` kept
out because it needs an interactive terminal), the effort a push and a
pull-request creation each require, the stamp record keys, the gate and
write-blocker messages, the store-forge shell patterns, the MCP create-PR
tool name, and the effort comparison every gate and the stamp store share so
the thresholds never drift between them.
"""

from __future__ import annotations

STAMP_DIRECTORY_NAME = "code-review-stamps"
ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER = ("low", "medium", "high", "xhigh", "max")
PUSH_REQUIRED_EFFORT = "low"
PR_CREATE_REQUIRED_EFFORT = "xhigh"
STAMP_KEY_EFFORT = "effort"
STAMP_KEY_MANIFEST_SHA256 = "manifest_sha256"
STAMP_KEY_RECORDED_AT_EPOCH = "recorded_at_epoch"
CODE_REVIEW_BYPASS_MARKER = "# code-review-skip"
GATED_PUSH_SUBCOMMANDS = frozenset({"push"})
ALL_GATED_SHELL_TOOL_NAMES = ("Bash", "PowerShell")
ALL_WRITE_EDIT_TOOL_NAMES = ("Write", "Edit", "MultiEdit")
MCP_CREATE_PULL_REQUEST_TOOL_NAME = "mcp__plugin_github_github__create_pull_request"
HASH_PREVIEW_LENGTH = 16
PRE_TOOL_USE_HOOK_EVENT_NAME = "PreToolUse"
DENY_PERMISSION_DECISION = "deny"
PUSH_GATE_HOOK_MODULE_NAME = "code_review_push_gate.py"
PR_CREATE_GATE_HOOK_MODULE_NAME = "code_review_pr_create_gate.py"
STAMP_WRITE_BLOCKER_HOOK_MODULE_NAME = "code_review_stamp_directory_write_blocker.py"
SANCTIONED_STAMP_MINTER_FLAG = "--record-stamp"
PUSH_GATE_CORRECTIVE_MESSAGE = (
    "BLOCKED: [CODE_REVIEW_PUSH_GATE] This branch surface has no clean "
    "code-review stamp at effort 'low' or higher. Run "
    "`python invoke_code_review.py --record-stamp --cwd <dir> "
    "--session-model <alias> low` (or a higher effort) so a clean review "
    "mints the stamp before `git push`; any file change after minting "
    "invalidates it. Append `# code-review-skip` as a trailing shell comment "
    "only when the verified-commit gate's verify-skip rule for a same-surface "
    "re-land applies. Exempt automatically: docs/image files, pytest test "
    "files, and Python files whose docstring- and comment-stripped AST is "
    "unchanged."
)
PR_CREATE_GATE_CORRECTIVE_MESSAGE = (
    "BLOCKED: [CODE_REVIEW_PR_CREATE_GATE] This branch surface has no clean "
    "code-review stamp at effort 'xhigh' or higher. Run "
    "`python invoke_code_review.py --record-stamp --cwd <dir> "
    "--session-model <alias> xhigh` (or max) so a clean review mints the "
    "stamp before `gh pr create` or the MCP create_pull_request tool. Any "
    "file change after minting invalidates the stamp."
)
STAMP_DIRECTORY_GUARD_MESSAGE = (
    "BLOCKED: [CODE_REVIEW_STAMP_DIRECTORY_GUARD] Access to the code-review "
    "stamp directory (~/.claude/code-review-stamps/) is denied. Only "
    "invoke_code_review.py --record-stamp mints stamp files; a shell or "
    "Write/Edit forge here would defeat the push and PR-create gates. "
    "Earn a stamp by running a clean /code-review through the invoker."
)
RELATIVE_STAMP_DIRECTORY_PATTERN = r"(?:^|(?<=[\s;&|(='\"]))code-review-stamps[\\/]"
STAMP_DIRECTORY_CHANGE_TARGET_PATTERN = r"[ \t]+['\"]?code-review-stamps[\\/]?['\"]?(?=[\s;&|]|$)"
STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN = r"(?:^|(?<=[\s;&|(='\"\\/]))"
STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN = r"[\\/][0-9a-f]{%d}\.json"
GH_PR_CREATE_INVOCATION_PATTERN = (
    r"(?:^|[;&|\n`({]|\$\()[ \t]*"
    r"(?:(?:if|then|else|elif|while|until|do|!)[ \t]+)*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S+[ \t]+)*"
    r"gh(?:[ \t]+(?:--[A-Za-z][\w-]*(?:=\S+)?|-[A-Za-z])(?:[ \t]+(?!-)\S+)?)*"
    r"[ \t]+pr[ \t]+create\b"
)
ALL_STAMP_PATH_SEGMENT_NAMES = (".claude", "code-review-stamps")
ALL_STAMP_PATH_SEGMENT_BODIES = ("claude", "code-review-stamps")
STAMP_STORE_MODULE_NAME = "code_review_stamp_store"
STAMP_MINT_FUNCTION_NAME = "record_clean_stamp"
ALL_STAMP_STORE_FORGE_PATTERNS = (
    rf"\bimport\s+{STAMP_STORE_MODULE_NAME}\b",
    rf"\bfrom\s+{STAMP_STORE_MODULE_NAME}\s+import\b",
    rf"\b{STAMP_MINT_FUNCTION_NAME}\s*\(",
)


def effort_meets_threshold(candidate_effort: str, required_effort: str) -> bool:
    """Decide whether a recorded effort satisfies a required threshold.

    ::

        effort_meets_threshold("xhigh", "low")  -> True   xhigh outranks low
        effort_meets_threshold("low", "xhigh")  -> False  low sits below xhigh
        effort_meets_threshold("ultra", "low")  -> False  ultra is unranked

    A candidate satisfies the threshold when it sits at or above the required
    token in the ascending order. A token outside the known order — ``ultra``
    among them — satisfies nothing, so an unrecognized stored effort clears no
    gate.

    Args:
        candidate_effort: The effort a recorded stamp was earned at.
        required_effort: The effort the gate demands for the action.

    Returns:
        True when both tokens are known and the candidate ranks at or above the
        required token; False otherwise.
    """
    if candidate_effort not in ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER:
        return False
    if required_effort not in ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER:
        return False
    candidate_rank = ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER.index(candidate_effort)
    required_rank = ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER.index(required_effort)
    return candidate_rank >= required_rank
