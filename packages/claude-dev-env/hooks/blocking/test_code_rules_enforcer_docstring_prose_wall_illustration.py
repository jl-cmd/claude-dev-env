"""Behavioural checks for the show-don't-tell narrative gate.

A readable summary earns its place by painting a concrete scene: a sample
input, an annotated outcome, an OK/FLAG contrast a reader pictures at once. A
summary that runs many short sentences with no worked example tells without
showing. The gate flags that wall in a top-level, class, or callable summary,
and stays quiet the moment the narrative carries a '::' listing or a '>>>'
doctest.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)


def _load_enforcer_module() -> ModuleType:
    enforcer_module_name = "code_rules_enforcer"
    enforcer_path = Path(__file__).parent / (enforcer_module_name + ".py")
    spec = importlib.util.spec_from_file_location(enforcer_module_name, enforcer_path)
    assert spec is not None
    assert spec.loader is not None
    loaded_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded_module)
    return loaded_module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_prose_wall_without_illustration(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_prose_wall_without_illustration(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/tally.py"
SUITE_FILE_PATH = "/project/src/test_tally.py"
INFRA_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _fixture_top_level_wall() -> str:
    return (
        '"""Assemble the nightly voyage tally from the harbor scans.\n'
        "\n"
        "A scan names one vessel and where it dropped anchor.\n"
        "The tally walks the scans in arrival order and keeps that order.\n"
        "A calm voyage ends well for every vessel it carried.\n"
        "A halted voyage marks the vessel it was near when the storm arrived.\n"
        "A wrecked voyage marks the vessel that sank and stops the walk there.\n"
        "The tally groups the vessels by their final port for the harbor.\n"
        "The harbor reads the tally and sees every arrival at a glance.\n"
        '"""\n'
        "\n"
        "def emit_tally() -> None:\n"
        "    return None\n"
    )


def _fixture_callable_wall() -> str:
    return (
        "def emit_tally() -> None:\n"
        '    """Post the voyage tally to the harbor board.\n'
        "\n"
        "    A scan names one vessel and where it dropped anchor.\n"
        "    The tally walks the scans in arrival order and keeps that order.\n"
        "    A calm voyage ends well for every vessel it carried.\n"
        "    A halted voyage marks the vessel it was near when the storm arrived.\n"
        "    A wrecked voyage marks the vessel that sank and stops the walk there.\n"
        "    The tally groups the vessels by their final port for the reader.\n"
        "    The reader reads the whole tally at a single glance.\n"
        '    """\n'
        "    return None\n"
    )


def _fixture_wall_with_listing() -> str:
    return (
        "def emit_tally() -> None:\n"
        '    """Post the voyage tally to the harbor board.\n'
        "\n"
        "    A scan names one vessel and where it dropped anchor::\n"
        "\n"
        "        vessel 42 -- halted -> marked mid-voyage\n"
        "        OK:   a calm voyage ends well for every vessel\n"
        "        FLAG: a wrecked voyage reads the same as a calm one\n"
        "\n"
        "    The reader reads the whole tally at a single glance.\n"
        '    """\n'
        "    return None\n"
    )


def _fixture_wall_with_doctest() -> str:
    return (
        "def emit_tally() -> None:\n"
        '    """Post the voyage tally to the harbor board.\n'
        "\n"
        "    A calm voyage ends well for every vessel it carried.\n"
        "    A halted voyage marks the vessel it was near when the storm arrived.\n"
        "    A wrecked voyage marks the vessel that sank and stops the walk there.\n"
        "\n"
        "    >>> emit_tally()\n"
        "    vessel 42 halted\n"
        "    vessel 43 calm\n"
        "\n"
        "    The reader reads the whole tally at a single glance.\n"
        '    """\n'
        "    return None\n"
    )


def _fixture_short_summary() -> str:
    return (
        "def emit_tally() -> None:\n"
        '    """Post the voyage tally to the harbor board.\n'
        "\n"
        "    A scan names one vessel and where it dropped anchor.\n"
        "    A calm voyage ends well for every vessel it carried.\n"
        "    A halted voyage marks the vessel it was near when it stopped.\n"
        "    The reader reads the whole tally at a single glance.\n"
        '    """\n'
        "    return None\n"
    )


def test_should_flag_prose_wall_with_no_illustration() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_top_level_wall(), PRODUCTION_FILE_PATH
    )
    assert any("worked example" in each for each in issues), (
        f"A top-level wall must flag, got: {issues!r}"
    )
    assert any("module" in each for each in issues)
    assert len(issues) == 1


def test_should_flag_function_prose_wall() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_callable_wall(), PRODUCTION_FILE_PATH
    )
    assert any("emit_tally" in each for each in issues), (
        f"A callable wall must flag, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_wall_with_literal_block() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_wall_with_listing(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A '::' listing must pass, got: {issues!r}"


def test_should_not_flag_wall_with_doctest() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_wall_with_doctest(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A '>>>' doctest must pass, got: {issues!r}"


def test_should_not_flag_short_narrative() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_short_summary(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A summary at the sentence limit must pass, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_docstring_prose_wall_without_illustration(_fixture_top_level_wall(), SUITE_FILE_PATH)
    assert issues == [], f"A suite path stays exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_prose_wall_without_illustration(
        _fixture_top_level_wall(), INFRA_PATH
    )
    assert issues == [], f"An infra path stays exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_prose_wall_without_illustration("def broken(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"A syntax error yields no issues, got: {issues!r}"


def test_validate_content_surfaces_prose_wall() -> None:
    issues = validate_content(_fixture_top_level_wall(), PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "worked example" in each]
    assert matching_issues, f"validate_content must surface the wall, got: {issues!r}"
