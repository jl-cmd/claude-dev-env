#!/usr/bin/env python3
"""PreToolUse hook: keep verified-commit exemption messages accurate.

The verified-commit gate exempts a branch surface only when every changed path
matches one of two narrow rules, implemented in ``is_verification_exempt_diff``:

1. file extension in ``DOCS_ONLY_EXTENSIONS`` (docs and image extensions), or
2. a ``.py`` file whose docstring/comment-stripped AST is unchanged.

A comment-only change to a non-Python, non-doc file (for example ``.sh``,
``.json``, ``.yaml``) is therefore NOT exempt: comments are ignored for
exemption purposes only inside Python files via the AST path. A corrective or
guard message that claims comment-only or docs-only surfaces are blanket exempt
overstates the rule and misleads users into expecting such a change to skip
verification.

This hook fires on Write/Edit of any verified-commit constants module and denies
content whose exemption-claim wording asserts a blanket comment-only or docs-only
exemption. It guards the message constants at authoring time, before the change
reaches review.
"""

import json
import os
import re
import sys


def is_guarded_file(file_path: str) -> bool:
    """Return True for any verified-commit constants module carrying messages."""
    all_guarded_file_names = frozenset({"verified_commit_constants.py"})
    return os.path.basename(file_path) in all_guarded_file_names


def join_adjacent_string_literals(written_text: str) -> str:
    """Collapse a closing quote, inter-literal whitespace, and an opening quote.

    Write/Edit content carries the message constant as it appears in source: a
    long sentence split across adjacent Python string literals. Between two
    literals sit a closing quote, a newline, indentation, and an opening quote.
    Replacing that run with a single space rejoins the prose so a phrase wrapped
    across a literal boundary — for example ``exempt "`` then ``"automatically``
    — reads as one continuous clause for matching.
    """
    inter_literal_noise_pattern = re.compile(r"[\"']\s*[\"']")
    return inter_literal_noise_pattern.sub(" ", written_text)


def claims_blanket_comment_exemption(written_text: str) -> bool:
    """Return True when the text claims comment surfaces are blanket-exempt.

    Rejoins source-wrapped string literals first, then matches only a genuine
    blanket form in which a comment surface is the grammatical subject of
    "exempt automatically". A comment surface is the bare noun ``comments`` or
    the ``comment-only`` category — never the ``comment`` stem inside an
    unrelated word such as ``commentary`` or the ``comment-stripped`` AST
    qualifier.

    Two blanket shapes match. The direct shape names a comment surface as the
    immediate subject of "(are|is) exempt automatically" across a bridge that
    crosses no period, semicolon, or comma, so an intervening predicate (for
    example "Comments are handled, and docs are exempt automatically") leaves
    docs, not comments, as the exemption subject and does not match. The
    enumerated shape names a comment item inside an "...-only surfaces are
    exempt automatically" list (for example "Docs-, comment-, and test-only
    surfaces are exempt automatically").

    An accurate sentence whose true exemption subject is docs, or that qualifies
    comments as the stripped input to the AST comparison, does not match. This
    isolates the overstated form the verified-commit gate does not honor for
    non-Python files.
    """
    comment_surface = r"comments?-only|comments?\b(?!-)"
    blanket_direct_claim = (
        "(?:" + comment_surface + r")(?:[^.;,]*?\b)?(?:are|is)\s+exempt\s+automatically"
    )
    blanket_enumerated_claim = (
        "(?:" + comment_surface + "|comment-)"
        r"[^.;]*?-only\s+surfaces\s+are\s+exempt\s+automatically"
    )
    blanket_exemption_claim_pattern = re.compile(
        "(?:" + blanket_direct_claim + ")|(?:" + blanket_enumerated_claim + ")",
        re.IGNORECASE,
    )
    joined_text = join_adjacent_string_literals(written_text)
    return bool(blanket_exemption_claim_pattern.search(joined_text))


def build_corrective_message() -> str:
    """Return the deny reason explaining the real, narrower exemption rules."""
    accurate_exemption_phrasing = (
        "Docs and images are exempt by extension, and Python files whose "
        "docstring- and comment-stripped AST is unchanged; a comment-only "
        "change to a non-Python file still needs a verdict."
    )
    return (
        "BLOCKED [verified-commit-message-accuracy]: this exemption message "
        "claims comment-only surfaces are exempt automatically, but the "
        "verified-commit gate exempts comments only inside Python files (via the "
        "docstring/comment stripped AST path). A comment-only change to a "
        "non-Python file is NOT exempt and still needs a verifier verdict, so "
        "the blanket wording misleads users.\n\nDescribe the real exemption "
        "rules instead, for example:\n  " + accurate_exemption_phrasing
    )


def extract_written_text(all_written_fields: dict[str, str]) -> str:
    """Return the Write ``content`` and Edit ``new_string`` joined for scanning."""
    return (
        all_written_fields.get("content", "")
        + "\n"
        + all_written_fields.get("new_string", "")
    )


def main() -> None:
    all_write_edit_tools = frozenset({"Write", "Edit"})
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in all_write_edit_tools:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    if not is_guarded_file(file_path):
        sys.exit(0)

    written_text = extract_written_text(tool_input)
    if not claims_blanket_comment_exemption(written_text):
        sys.exit(0)

    deny_response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": build_corrective_message(),
        }
    }
    print(json.dumps(deny_response))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
