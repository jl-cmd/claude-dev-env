"""Tests for the agent_model_pin_blocker hook's evaluate() orchestration.

The pin-detection truth table lives beside the detector in
hooks_constants/test_agent_model_pin_detection.py. These tests cover the hook's
own decisions: tool-name and path gating, post-edit content reconstruction, and
the deny/allow routing (including the malformed-model-line fallback).
"""

from pathlib import Path

import pytest

try:
    from agent_model_pin_blocker import evaluate
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent_model_pin_blocker import evaluate

PACKAGE_AGENT_PATH = "packages/claude-dev-env/agents/clean-coder.md"
INSTALLED_AGENT_PATH = "/home/user/.claude/agents/clean-coder.md"
WINDOWS_AGENT_PATH = r"C:\repo\packages\claude-dev-env\agents\clean-coder.md"
NON_AGENT_PATH = "packages/claude-dev-env/docs/notes.md"
DOC_FILE_PATH = "packages/claude-dev-env/agents/CLAUDE.md"


def _write_payload(file_path: str, content: str) -> dict[str, object]:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


def _pinned_agent_file(model_line: str) -> str:
    return f"---\nname: sample\n{model_line}\n---\n\nBody text.\n"


def _agent_file_on_disk(tmp_path: Path, model_line: str) -> Path:
    agents_directory = tmp_path / ".claude" / "agents"
    agents_directory.mkdir(parents=True, exist_ok=True)
    agent_file = agents_directory / "probe.md"
    agent_file.write_text(_pinned_agent_file(model_line), encoding="utf-8")
    return agent_file


@pytest.mark.parametrize(
    "agent_file_path",
    [PACKAGE_AGENT_PATH, INSTALLED_AGENT_PATH, WINDOWS_AGENT_PATH],
)
def test_evaluate_denies_pinned_model_on_agent_write(agent_file_path: str) -> None:
    payload = _write_payload(agent_file_path, _pinned_agent_file("model: opus"))
    deny_reason = evaluate(payload)
    assert deny_reason is not None
    assert agent_file_path in deny_reason
    assert "pins a concrete model" in deny_reason


def test_evaluate_allows_inherit_model_on_agent_write() -> None:
    payload = _write_payload(PACKAGE_AGENT_PATH, _pinned_agent_file("model: inherit"))
    assert evaluate(payload) is None


def test_evaluate_allows_agent_write_without_model_key() -> None:
    payload = _write_payload(
        PACKAGE_AGENT_PATH, "---\nname: sample\ncolor: green\n---\n\nBody.\n"
    )
    assert evaluate(payload) is None


def test_evaluate_ignores_column_zero_model_line_in_body() -> None:
    content = (
        "---\nname: sample\ncolor: green\n---\n\n"
        "Body prose about configuration.\nmodel: opus\nMore prose.\n"
    )
    assert evaluate(_write_payload(PACKAGE_AGENT_PATH, content)) is None


def test_evaluate_ignores_non_agent_markdown() -> None:
    payload = _write_payload(NON_AGENT_PATH, _pinned_agent_file("model: opus"))
    assert evaluate(payload) is None


def test_evaluate_ignores_doc_file_quoting_bad_example() -> None:
    doc_content = (
        "# agents\n\nAvoid a pinned model:\n\n"
        "```yaml\n---\nname: sample\nmodel: opus\n---\n```\n"
    )
    assert evaluate(_write_payload(DOC_FILE_PATH, doc_content)) is None


def test_evaluate_ignores_non_write_tool() -> None:
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": PACKAGE_AGENT_PATH},
    }
    assert evaluate(payload) is None


def test_evaluate_allows_null_model() -> None:
    content = "---\nname: sample\nmodel: null\n---\n\nBody.\n"
    assert evaluate(_write_payload(PACKAGE_AGENT_PATH, content)) is None


def test_evaluate_denies_unterminated_quote_as_malformed() -> None:
    content = "---\nname: sample\nmodel: 'opus\n---\n\nBody.\n"
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "malformed model line" in deny_reason


def test_evaluate_denies_content_after_closing_quote_as_malformed() -> None:
    content = '---\nname: sample\nmodel: "inherit"opus\n---\n\nBody.\n'
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "malformed model line" in deny_reason


def test_evaluate_denies_block_scalar_as_malformed() -> None:
    content = "---\nname: sample\nmodel: |\n---\n\nBody.\n"
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "malformed model line" in deny_reason


def test_evaluate_denies_space_before_colon_pin() -> None:
    content = "---\nname: sample\nmodel : opus\n---\n\nBody.\n"
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "pins a concrete model (opus)" in deny_reason


def test_evaluate_denies_no_space_colon_pin() -> None:
    content = "---\nname: sample\nmodel:opus\n---\n\nBody.\n"
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "pins a concrete model (opus)" in deny_reason


def test_evaluate_denies_pin_after_byte_order_mark() -> None:
    content = "\ufeff---\nname: sample\nmodel: opus\n---\n\nBody.\n"
    deny_reason = evaluate(_write_payload(PACKAGE_AGENT_PATH, content))
    assert deny_reason is not None
    assert "pins a concrete model (opus)" in deny_reason


def test_evaluate_denies_edit_flipping_inherit_to_concrete(tmp_path: Path) -> None:
    agent_file = _agent_file_on_disk(tmp_path, "model: inherit")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(agent_file),
            "old_string": "model: inherit",
            "new_string": "model: opus",
        },
    }
    deny_reason = evaluate(payload)
    assert deny_reason is not None
    assert "pins a concrete model" in deny_reason


def test_evaluate_allows_edit_leaving_inherit(tmp_path: Path) -> None:
    agent_file = _agent_file_on_disk(tmp_path, "model: inherit")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(agent_file),
            "old_string": "Body text.",
            "new_string": "Updated body.",
        },
    }
    assert evaluate(payload) is None


def test_evaluate_denies_multiedit_flipping_inherit_to_concrete(tmp_path: Path) -> None:
    agent_file = _agent_file_on_disk(tmp_path, "model: inherit")
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(agent_file),
            "edits": [
                {"old_string": "model: inherit", "new_string": "model: haiku"},
            ],
        },
    }
    deny_reason = evaluate(payload)
    assert deny_reason is not None
    assert "pins a concrete model" in deny_reason
