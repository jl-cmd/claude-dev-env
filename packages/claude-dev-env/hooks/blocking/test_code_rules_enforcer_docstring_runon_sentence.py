"""Tests for check_docstring_runon_sentence — the plain-illustrative-docstrings backstop.

A readable docstring breaks its narrative into short sentences a general developer
follows on first read. The one mechanical mark of a dense wall is a single run-on
sentence: many words strung together with an em-dash or a semicolon. This check
flags that mark in module, class, and public-function docstring narrative prose,
and leaves the "is it illustrative" judgment to the audit lane.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_runon_sentence(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_runon_sentence(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/run_lifecycle.py"
TEST_FILE_PATH = "/project/src/test_run_lifecycle.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _run_lifecycle_module() -> str:
    return (
        '"""Generic run-lifecycle plumbing for the STP version promoter run.\n'
        "\n"
        "Owns the SIGINT install/restore/installability check, the atexit terminal-record\n"
        "registration, and the interrupted-run finalizer — the non-promoter-specific\n"
        "machinery that brackets a run so the JSONL artifact always carries a terminal\n"
        "record and an in-flight theme record on interrupt.\n"
        '"""\n'
        "\n"
        "def install_signal_handler() -> None:\n"
        "    return None\n"
    )


def _approved_bar_module() -> str:
    return (
        '"""Make sure a run\'s log always records how it ended.\n'
        "\n"
        "So when you reopen the report, the last line tells you the truth: the run\n"
        "finished cleanly, or you hit Ctrl-C while theme 42 was processing, or it died\n"
        "on an unexpected error. Without this, a killed run looks identical to a clean\n"
        "one — and you're debugging blind.\n"
        '"""\n'
        "\n"
        "def describe_outcome() -> None:\n"
        "    return None\n"
    )


def _class_docstring_runon() -> str:
    return (
        "class RunRecorder:\n"
        '    """Owns the SIGINT install and restore step, the atexit record hook, and the\n'
        "    interrupted-run finalizer — the plumbing that brackets a run so the artifact\n"
        "    always carries a terminal record and an in-flight theme record on interrupt.\n"
        '    """\n'
        "\n"
        "    def record(self) -> None:\n"
        "        return None\n"
    )


def _normal_short_docstring() -> str:
    return (
        "def summarize_run() -> str:\n"
        '    """Write the run summary.\n'
        "\n"
        "    Each line names one theme and its final outcome.\n"
        '    """\n'
        '    return ""\n'
    )


def _long_args_line_outside_narrative() -> str:
    return (
        "def configure_run(option_name: str) -> None:\n"
        '    """Set one option for the run.\n'
        "\n"
        "    Args:\n"
        "        option_name: the name of the option to set, described here in a needlessly\n"
        "            long sentence that runs far past thirty words and even carries an\n"
        "            em-dash — yet the check stays silent because every word here sits after\n"
        "            the Args header and therefore outside the inspected narrative entirely.\n"
        '    """\n'
        "    return None\n"
    )


def _private_function_runon() -> str:
    return (
        "def _install_handlers() -> None:\n"
        '    """Owns the SIGINT install and restore step, the atexit record hook, and the\n'
        "    interrupted-run finalizer — the plumbing that brackets a run so the artifact\n"
        "    always carries a terminal record and an in-flight theme record on interrupt.\n"
        '    """\n'
        "    return None\n"
    )


def _property_method_runon() -> str:
    return (
        "class Widget:\n"
        "    @property\n"
        "    def label(self) -> str:\n"
        '        """Owns the SIGINT install and restore step, the atexit record hook, and the\n'
        "        interrupted-run finalizer — the plumbing that brackets a run so the artifact\n"
        "        always carries a terminal record and an in-flight theme record on interrupt.\n"
        '        """\n'
        '        return "label"\n'
    )


def test_should_flag_run_lifecycle_module_docstring_wall() -> None:
    issues = check_docstring_runon_sentence(_run_lifecycle_module(), PRODUCTION_FILE_PATH)
    assert any("run-on" in each for each in issues), (
        f"Expected the module-docstring wall to flag, got: {issues!r}"
    )
    assert any("module" in each for each in issues)
    assert len(issues) == 1


def test_should_not_flag_approved_bar_module_docstring() -> None:
    issues = check_docstring_runon_sentence(_approved_bar_module(), PRODUCTION_FILE_PATH)
    assert issues == [], f"The approved bar must pass clean, got: {issues!r}"


def test_should_flag_class_docstring_wall() -> None:
    issues = check_docstring_runon_sentence(_class_docstring_runon(), PRODUCTION_FILE_PATH)
    assert any("RunRecorder" in each for each in issues), (
        f"Expected the class-docstring wall to flag, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_normal_short_docstring() -> None:
    issues = check_docstring_runon_sentence(_normal_short_docstring(), PRODUCTION_FILE_PATH)
    assert issues == [], f"A short multi-sentence docstring must not flag, got: {issues!r}"


def test_should_not_flag_long_args_line_outside_narrative() -> None:
    issues = check_docstring_runon_sentence(
        _long_args_line_outside_narrative(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"The Args section is outside the narrative, got: {issues!r}"


def test_should_skip_private_function() -> None:
    issues = check_docstring_runon_sentence(_private_function_runon(), PRODUCTION_FILE_PATH)
    assert issues == [], f"Private functions are out of scope, got: {issues!r}"


def test_should_skip_property_method() -> None:
    issues = check_docstring_runon_sentence(_property_method_runon(), PRODUCTION_FILE_PATH)
    assert issues == [], f"@property methods are exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_docstring_runon_sentence(_run_lifecycle_module(), TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_runon_sentence(_run_lifecycle_module(), HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_runon_sentence("def broken(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_docstring_runon_wall() -> None:
    issues = validate_content(_run_lifecycle_module(), PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "run-on" in each]
    assert matching_issues, f"Expected validate_content to surface the run-on wall, got: {issues!r}"
