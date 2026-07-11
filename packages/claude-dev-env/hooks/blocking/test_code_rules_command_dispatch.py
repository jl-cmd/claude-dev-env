"""Behavioral tests for the unanchored command-dispatch meta-gate."""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from code_rules_command_dispatch import (  # noqa: E402
    check_unanchored_command_dispatch,
)

GATE_PATH = "packages/claude-dev-env/hooks/blocking/conventional_pr_title_gate.py"

UNANCHORED_SOURCE = (
    "import re\n"
    "def run(tool_input):\n"
    '    command_text = tool_input["command"]\n'
    '    if re.search(r"gh\\s+pr\\s+(create|edit)", command_text):\n'
    "        return True\n"
    "    return False\n"
)


def test_flags_unanchored_multi_word_command_pattern() -> None:
    issues = check_unanchored_command_dispatch(UNANCHORED_SOURCE, GATE_PATH)
    assert len(issues) == 1
    assert "gh" in issues[0]


def test_accepts_anchored_command_pattern() -> None:
    source = (
        "import re\n"
        "def run(tool_input):\n"
        '    command_text = tool_input["command"]\n'
        '    if re.search(r"^gh\\s+pr\\s+(create|edit)", command_text):\n'
        "        return True\n"
        "    return False\n"
    )
    assert check_unanchored_command_dispatch(source, GATE_PATH) == []


def test_accepts_pattern_when_first_word_is_tokenized() -> None:
    source = (
        "import re\n"
        "import shlex\n"
        "def run(tool_input):\n"
        '    command_text = tool_input["command"]\n'
        "    first_word = shlex.split(command_text)[0]\n"
        '    if first_word == "gh" and re.search(r"gh\\s+pr\\s+create", command_text):\n'
        "        return True\n"
        "    return False\n"
    )
    assert check_unanchored_command_dispatch(source, GATE_PATH) == []


def test_ignores_file_that_does_not_read_a_command_key() -> None:
    source = (
        "import re\n"
        "def run(text):\n"
        '    if re.search(r"gh\\s+pr\\s+create", text):\n'
        "        return True\n"
        "    return False\n"
    )
    assert check_unanchored_command_dispatch(source, GATE_PATH) == []


def test_ignores_single_word_command_literal() -> None:
    source = (
        "import re\n"
        "def run(tool_input):\n"
        '    command_text = tool_input["command"]\n'
        '    if re.search(r"gh", command_text):\n'
        "        return True\n"
        "    return False\n"
    )
    assert check_unanchored_command_dispatch(source, GATE_PATH) == []


def test_ignores_file_outside_hooks_blocking() -> None:
    other_path = "packages/claude-dev-env/skills/thing/helper.py"
    assert check_unanchored_command_dispatch(UNANCHORED_SOURCE, other_path) == []


def test_ignores_test_file() -> None:
    test_path = "packages/claude-dev-env/hooks/blocking/test_conventional_pr_title_gate.py"
    assert check_unanchored_command_dispatch(UNANCHORED_SOURCE, test_path) == []


def test_scoped_to_changed_lines() -> None:
    unchanged = check_unanchored_command_dispatch(UNANCHORED_SOURCE, GATE_PATH, {1, 2, 3})
    assert unchanged == []
    on_pattern_line = check_unanchored_command_dispatch(UNANCHORED_SOURCE, GATE_PATH, {4})
    assert len(on_pattern_line) == 1
