"""Contract: code-verifier cannot message a warm session-advisor."""

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_CODE_VERIFIER_AGENT_PATH = _PACKAGE_ROOT / "agents" / "code-verifier.md"
_FRONTMATTER_OPEN = "---\n"
_FRONTMATTER_CLOSE = "\n---\n"
_TOOLS_PREFIX = "tools:"
_SEND_MESSAGE_TOOL_NAME = "SendMessage"


def test_code_verifier_tools_exclude_sendmessage() -> None:
    """tools frontmatter must not list SendMessage (warm-advisor path closed)."""
    agent_text = _CODE_VERIFIER_AGENT_PATH.read_text(encoding="utf-8")
    assert agent_text.startswith(_FRONTMATTER_OPEN), "missing frontmatter open"
    frontmatter_end = agent_text.find(_FRONTMATTER_CLOSE, len(_FRONTMATTER_OPEN))
    assert frontmatter_end > 0, "missing frontmatter close"
    frontmatter_body = agent_text[len(_FRONTMATTER_OPEN) : frontmatter_end]
    all_tools_lines = [
        each_line
        for each_line in frontmatter_body.splitlines()
        if each_line.startswith(_TOOLS_PREFIX)
    ]
    assert len(all_tools_lines) == 1, all_tools_lines
    tools_value = all_tools_lines[0].removeprefix(_TOOLS_PREFIX).strip()
    all_tool_names = {each_name.strip() for each_name in tools_value.split(",")}
    assert _SEND_MESSAGE_TOOL_NAME not in all_tool_names, all_tool_names
