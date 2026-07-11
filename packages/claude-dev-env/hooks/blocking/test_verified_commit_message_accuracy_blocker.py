"""Unit tests for the verified-commit-message-accuracy PreToolUse hook."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "verified_commit_message_accuracy_blocker",
    _HOOK_DIR / "verified_commit_message_accuracy_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
is_guarded_file = hook_module.is_guarded_file
claims_blanket_comment_exemption = hook_module.claims_blanket_comment_exemption
extract_written_text = hook_module.extract_written_text
build_corrective_message = hook_module.build_corrective_message

OFFENDING_MESSAGE = (
    "CORRECTIVE_MESSAGE = (\n"
    '    "BLOCKED: [VERIFIED_COMMIT_GATE] This branch surface has no passing "\n'
    '    "verification verdict. Spawn the code-verifier agent (Agent tool, "\n'
    "    \"subagent_type 'code-verifier') with the task texts, the diff scope, \"\n"
    '    "and recorded baselines; when it finishes with a clean verdict the "\n'
    '    "SubagentStop hook mints the verdict and this command will pass. Any "\n'
    '    "file change after verification invalidates the verdict, so verify "\n'
    '    "last. Docs-, docstring-, comment-, and test-only surfaces are exempt "\n'
    '    "automatically."\n'
    ")\n"
)
ACCURATE_DOCS_EXEMPTION_MENTIONING_COMMENTS = (
    "Comments inside Python files are stripped; docs are exempt "
    "automatically by extension."
)
ACCURATE_MESSAGE = (
    "CORRECTIVE_MESSAGE = (\n"
    '    "BLOCKED: [VERIFIED_COMMIT_GATE] ... Docs and images are exempt by "\n'
    '    "extension, and Python files whose docstring- and comment-stripped AST "\n'
    '    "is unchanged."\n'
    ")\n"
)


def test_constants_file_is_guarded() -> None:
    assert is_guarded_file(
        "/repo/.claude/hooks/blocking/config/verified_commit_constants.py"
    )


def test_unrelated_file_is_not_guarded() -> None:
    assert not is_guarded_file("/repo/.claude/hooks/blocking/gh_body_arg_blocker.py")


def test_blanket_comment_exemption_claim_is_detected() -> None:
    assert claims_blanket_comment_exemption(OFFENDING_MESSAGE)


def test_blanket_claim_detected_regardless_of_leading_words() -> None:
    assert claims_blanket_comment_exemption(
        "Comment-only surfaces are exempt automatically."
    )


def test_accurate_exemption_wording_passes() -> None:
    assert not claims_blanket_comment_exemption(ACCURATE_MESSAGE)


def test_accurate_docs_exemption_mentioning_comments_passes() -> None:
    assert not claims_blanket_comment_exemption(
        ACCURATE_DOCS_EXEMPTION_MENTIONING_COMMENTS
    )


def test_comma_joined_docs_exemption_mentioning_comments_passes() -> None:
    assert not claims_blanket_comment_exemption(
        "Comments are handled, and docs are exempt automatically."
    )


def test_python_ast_clause_mentioning_comments_passes() -> None:
    assert not claims_blanket_comment_exemption(
        "Python comment-stripped AST changes and docs are exempt automatically "
        "by extension"
    )


def test_single_clause_python_ast_exemption_passes() -> None:
    assert not claims_blanket_comment_exemption(
        "Python files whose comment-stripped AST is unchanged are exempt "
        "automatically."
    )


def test_commentary_word_stem_passes() -> None:
    assert not claims_blanket_comment_exemption(
        "Our commentary on the approach is exempt automatically from blame."
    )


def test_corrective_message_names_only_the_two_real_exemptions() -> None:
    corrective_message = build_corrective_message()
    assert "exempt by extension" in corrective_message
    assert "docstring- and comment-stripped AST" in corrective_message
    assert "test file" not in corrective_message
    assert "by name convention" not in corrective_message


def test_message_without_exemption_claim_passes() -> None:
    assert not claims_blanket_comment_exemption(
        'CORRECTIVE_MESSAGE = "Spawn the code-verifier agent to earn a verdict."'
    )


def test_write_content_is_extracted() -> None:
    written_text = extract_written_text({"content": OFFENDING_MESSAGE})
    assert claims_blanket_comment_exemption(written_text)


def test_edit_new_string_is_extracted() -> None:
    written_text = extract_written_text({"new_string": OFFENDING_MESSAGE})
    assert claims_blanket_comment_exemption(written_text)


def test_edit_new_string_with_accurate_wording_is_clean() -> None:
    written_text = extract_written_text({"new_string": ACCURATE_MESSAGE})
    assert not claims_blanket_comment_exemption(written_text)
