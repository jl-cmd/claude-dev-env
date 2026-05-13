"""Probe one detector inside code_rules_enforcer.py against a fixture file.

Loads ~/.claude/hooks/blocking/code_rules_enforcer.py dynamically and invokes
the requested check function (e.g. check_collection_prefix, check_library_print)
against the contents of a target fixture file. Prints the returned issue list.

Used as a verification shape during the historical Copilot gap-analysis
investigation (see reference/copilot-gap-analysis.md). This script replaces the
inline python -c probe that the doc used to embed.

Usage:
    python probe_code_rules_enforcer_check.py <check_function> <fixture_path> [reported_path]
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from config.probe_code_rules_enforcer_check_constants import (
    DEFAULT_REPORTED_PATH,
    ENFORCER_MODULE_NAME,
    ENFORCER_RELATIVE_PATH,
    EXIT_CODE_USAGE_ERROR,
    MAXIMUM_ARGUMENT_COUNT,
    MINIMUM_ARGUMENT_COUNT,
)


def _load_enforcer_module() -> ModuleType:
    enforcer_path = Path.home() / ENFORCER_RELATIVE_PATH
    spec = importlib.util.spec_from_file_location(
        ENFORCER_MODULE_NAME, str(enforcer_path)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load enforcer at {enforcer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_probe(
    check_function_name: str, fixture_path: str, reported_path: str
) -> list[str]:
    """Load an enforcer check function and run it against a fixture file.

    Args:
        check_function_name: Name of the check function in code_rules_enforcer.
        fixture_path: Absolute path to the fixture file to check.
        reported_path: Path string to pass as the file_path parameter.

    Returns:
        List of issue strings returned by the check function.

    Raises:
        AttributeError: When the named check function is not found in the enforcer.
        RuntimeError: When the enforcer module cannot be loaded.
    """
    enforcer_module = _load_enforcer_module()
    check_function = getattr(enforcer_module, check_function_name, None)
    if check_function is None:
        raise AttributeError(f"{check_function_name} not found in code_rules_enforcer")
    fixture_content = Path(fixture_path).read_text(encoding="utf-8")
    return check_function(fixture_content, reported_path)


def _print_usage_to_stderr() -> None:
    sys.stderr.write(
        "usage: python probe_code_rules_enforcer_check.py "
        "<check_function> <fixture_path> [reported_path]\n"
    )


def main(all_arguments: list[str]) -> int:
    """Invoke the probe with command-line arguments and print results.

    Args:
        all_arguments: Command-line arguments including script name,
                       check function name, fixture path, and optional reported path.

    Returns:
        Exit code 0 on success, EXIT_CODE_USAGE_ERROR on invalid arguments.
    """
    argument_count = len(all_arguments)
    if (
        argument_count < MINIMUM_ARGUMENT_COUNT
        or argument_count > MAXIMUM_ARGUMENT_COUNT
    ):
        _print_usage_to_stderr()
        return EXIT_CODE_USAGE_ERROR
    check_function_name = all_arguments[1]
    fixture_path = all_arguments[2]
    reported_path = (
        all_arguments[3]
        if argument_count == MAXIMUM_ARGUMENT_COUNT
        else DEFAULT_REPORTED_PATH
    )
    issues = run_probe(check_function_name, fixture_path, reported_path)
    for each_issue in issues:
        print(each_issue)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
