"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""

import re

MAX_VIOLATIONS_PER_CHECK: int = 3

GATE_ERROR_EXIT_CODE: int = 2

EMPTY_FILE_SET_EXIT_CODE: int = 3

EMPTY_FILE_SET_MESSAGE: str = (
    "code_rules_gate: the resolved file set is empty; nothing was inspected."
)

INSPECTED_COUNT_MESSAGE: str = "code_rules_gate: inspected {inspected_count} file(s)."

FUNCTION_LENGTH_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(defined at line (\d+)\) is (\d+) lines"
)
FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX: int = 1
FUNCTION_LENGTH_SPAN_GROUP_INDEX: int = 2

ISOLATION_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(defined at line (\d+), spanning (\d+) lines\)"
)
ISOLATION_DEFINITION_LINE_GROUP_INDEX: int = 1
ISOLATION_SPAN_GROUP_INDEX: int = 2

BANNED_NOUN_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(binding span at line (\d+), spanning (\d+) lines\)"
)
BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX: int = 1
BANNED_NOUN_SPAN_GROUP_INDEX: int = 2

DUPLICATE_BODY_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(duplicate body span at line (\d+), spanning (\d+) lines\)"
)
DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX: int = 1
DUPLICATE_BODY_SPAN_GROUP_INDEX: int = 2

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset({".py", ".js", ".ts", ".tsx", ".jsx"})

TESTS_PATH_SEGMENT: str = "/tests/"

ALL_TEST_FILENAME_SUFFIXES: tuple[str, ...] = ("_test.py",)

ALL_TEST_FILENAME_GLOB_SUFFIXES: tuple[str, ...] = (
    ".test.",
    ".spec.",
)

TEST_CONFTEST_FILENAME: str = "conftest.py"

TEST_FILENAME_PREFIX: str = "test_"

GIT_NAME_STATUS_ADDED_PREFIX: str = "A"

GIT_NAME_STATUS_RENAMED_PREFIX: str = "R"

EXPECTED_RENAME_COLUMN_COUNT: int = 3

EXPECTED_NON_RENAME_COLUMN_COUNT: int = 2

PYTHON_FILE_EXTENSION: str = ".py"

ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--name-only",
    "-z",
)

ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX: tuple[str, ...] = (
    "git",
    "diff",
    "--name-only",
    "-z",
)

ALL_GIT_LS_FILES_UNTRACKED_NULL_TERMINATED_COMMAND: tuple[str, ...] = (
    "git",
    "ls-files",
    "--others",
    "--exclude-standard",
    "-z",
)


ALL_PYTEST_MODULE_INVOCATION: tuple[str, ...] = (
    "-m",
    "pytest",
    "-q",
)

CODE_RULES_GATE_PYTHON_ENV_VAR: str = "CODE_RULES_GATE_PYTHON"

CODE_RULES_GATE_PYTHONPATH_ENV_VAR: str = "CODE_RULES_GATE_PYTHONPATH"

PYTHONPATH_ENV_VAR: str = "PYTHONPATH"

ALL_VENV_DIRECTORY_NAMES: tuple[str, ...] = (".venv", "venv")

ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS: tuple[str, ...] = (
    "Scripts",
    "python.exe",
)

ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS: tuple[str, ...] = ("bin", "python")

STAGED_PYTEST_TIMEOUT_SECONDS: int = 600

MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS: int = 24000

COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH: int = 1

STAGED_TEST_FAILURE_HEADER: str = (
    "code_rules_gate: staged test file(s) failed under pytest; commit blocked."
)

PYTEST_INI_FILENAME: str = "pytest.ini"

PYPROJECT_TOML_FILENAME: str = "pyproject.toml"

SETUP_CFG_FILENAME: str = "setup.cfg"

TOX_INI_FILENAME: str = "tox.ini"

PYPROJECT_PYTEST_CONFIG_SECTION: str = "[tool.pytest.ini_options]"

SETUP_CFG_PYTEST_CONFIG_SECTION: str = "[tool:pytest]"

TOX_INI_PYTEST_CONFIG_SECTION: str = "[pytest]"

ALL_PYTEST_CONFIG_FILE_SECTIONS: tuple[tuple[str, str | None], ...] = (
    (PYTEST_INI_FILENAME, None),
    (PYPROJECT_TOML_FILENAME, PYPROJECT_PYTEST_CONFIG_SECTION),
    (SETUP_CFG_FILENAME, SETUP_CFG_PYTEST_CONFIG_SECTION),
    (TOX_INI_FILENAME, TOX_INI_PYTEST_CONFIG_SECTION),
)

STAGED_TEST_GROUP_FAILURE_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} failed under pytest; commit blocked."
)

MINIMUM_STAGED_PYTEST_PYTHON_MAJOR: int = 3

MINIMUM_STAGED_PYTEST_PYTHON_MINOR: int = 12

JUNIT_XML_FLAG_PREFIX: str = "--junitxml="

JUNIT_XML_TESTCASE_TAG: str = "testcase"

JUNIT_XML_FAILURE_TAG: str = "failure"

JUNIT_XML_ERROR_TAG: str = "error"

JUNIT_XML_CLASSNAME_ATTRIBUTE: str = "classname"

JUNIT_XML_NAME_ATTRIBUTE: str = "name"

JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK: str = ""

REGRESSION_JUNIT_TEMP_DIRECTORY_PREFIX: str = "code_rules_gate_junit_"

REGRESSION_STAGED_JUNIT_SUBDIRECTORY_NAME: str = "staged"

REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME: str = "baseline"

REGRESSION_BASELINE_WORKTREE_TEMP_DIRECTORY_PREFIX: str = "code_rules_gate_baseline_"

REGRESSION_BASELINE_WORKTREE_DIRECTORY_NAME: str = "tree"

GIT_HEAD_REVISION: str = "HEAD"

ALL_GIT_HEAD_EXISTS_ARGS: tuple[str, ...] = ("rev-parse", "--verify", "HEAD")

ALL_GIT_WORKTREE_ADD_DETACH_ARGS: tuple[str, ...] = (
    "worktree",
    "add",
    "--detach",
    "--quiet",
)

ALL_GIT_WORKTREE_REMOVE_FORCE_ARGS: tuple[str, ...] = ("worktree", "remove", "--force")

ALL_GIT_WORKTREE_PRUNE_ARGS: tuple[str, ...] = ("worktree", "prune")

REGRESSION_NO_BASELINE_MESSAGE: str = (
    "code_rules_gate: no prior commit to compare against (first commit on this branch); "
    "every staged test failure blocks."
)

REGRESSION_WORKTREE_ADD_FAILED_MESSAGE: str = (
    "code_rules_gate: could not open a detached HEAD worktree for the pre-staged baseline "
    "(git worktree add --detach failed); falling back to blocking on every staged test "
    "failure."
)

REGRESSION_WORKTREE_REMOVE_FAILED_MESSAGE: str = (
    "code_rules_gate: git worktree remove --force failed after the baseline check — your "
    "staged changes are untouched in this worktree. Run 'git worktree list' and "
    "'git worktree prune' if a temporary baseline tree remains registered."
)

REGRESSION_PRE_EXISTING_FAILURE_BYPASSED_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} has {count} failure(s) "
    "already present before this change (not caused by it); not blocking."
)

REGRESSION_GROUP_FAILURE_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} has {count} failure(s) "
    "this change introduces; commit blocked."
)

BASELINE_LEAK_PLUGIN_DIRECTORY_NAME: str = "baseline_import_plugin"

BASELINE_LEAK_PLUGIN_MODULE_NAME: str = "code_rules_gate_baseline_import_plugin"

BASELINE_LEAK_REPORT_FILENAME: str = "imported_from_primary_tree.json"

BASELINE_PRIMARY_ROOT_ENV_VAR: str = "CODE_RULES_GATE_BASELINE_PRIMARY_ROOT"

BASELINE_LEAK_REPORT_ENV_VAR: str = "CODE_RULES_GATE_BASELINE_LEAK_REPORT"

PYTEST_PLUGINS_ENV_VAR: str = "PYTEST_PLUGINS"

PYTEST_PLUGINS_SEPARATOR: str = ","

BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS: int = 120

PYTHON_INTERPRETER_COMMAND_FLAG: str = "-c"

BASELINE_IMPORT_ROOT_PROBE_SOURCE: str = (
    "import json\n"
    "import sys\n"
    "from pathlib import Path\n"
    "all_roots = [each_entry for each_entry in sys.path if each_entry]\n"
    "for each_finder in list(sys.meta_path):\n"
    "    owning_module = sys.modules.get(getattr(each_finder, '__module__', '') or '')\n"
    "    for each_attribute in ('MAPPING', 'NAMESPACES'):\n"
    "        mapping = getattr(owning_module, each_attribute, None)\n"
    "        if not isinstance(mapping, dict):\n"
    "            continue\n"
    "        for each_name, each_target in mapping.items():\n"
    "            all_targets = each_target if isinstance(each_target, list) else [each_target]\n"
    "            for each_package_directory in all_targets:\n"
    "                try:\n"
    "                    all_roots.append(\n"
    "                        str(Path(each_package_directory).parents[str(each_name).count('.')])\n"
    "                    )\n"
    "                except (IndexError, TypeError, OSError):\n"
    "                    continue\n"
    "print(json.dumps(all_roots))\n"
)

BASELINE_LEAK_PLUGIN_SOURCE: str = '''"""Report every module the baseline pytest run imported out of the user's own tree."""

import json
import os
import sys
import sysconfig
from pathlib import Path

PRIMARY_ROOT_ENV_VAR = "{primary_root_env_var}"
REPORT_PATH_ENV_VAR = "{report_path_env_var}"


def _resolved(path_text):
    if not path_text:
        return None
    try:
        return Path(path_text).resolve()
    except OSError:
        return None


def _is_under(candidate, root):
    return candidate == root or root in candidate.parents


def _interpreter_roots():
    all_texts = [sys.prefix, sys.base_prefix, *sysconfig.get_paths().values()]
    all_roots = [_resolved(each_text) for each_text in all_texts]
    return [each_root for each_root in all_roots if each_root is not None]


def _already_reported(report_path):
    try:
        return set(json.loads(report_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _imported_from_primary_tree(primary_root, report_path):
    all_interpreter_roots = _interpreter_roots()
    all_leaked = _already_reported(report_path)
    for each_module in list(sys.modules.values()):
        module_path = _resolved(getattr(each_module, "__file__", None))
        if module_path is None or not _is_under(module_path, primary_root):
            continue
        if any(_is_under(module_path, each_root) for each_root in all_interpreter_roots):
            continue
        all_leaked.add(str(module_path))
    return sorted(all_leaked)


def pytest_sessionfinish(session, exitstatus):
    primary_root = _resolved(os.environ.get(PRIMARY_ROOT_ENV_VAR))
    report_path = _resolved(os.environ.get(REPORT_PATH_ENV_VAR))
    if primary_root is None or report_path is None:
        return
    report_path.write_text(
        json.dumps(_imported_from_primary_tree(primary_root, report_path)), encoding="utf-8"
    )
'''

REGRESSION_BASELINE_IMPORT_LEAK_MESSAGE: str = (
    "code_rules_gate: the HEAD baseline run for the group rooted at {group_root} imported "
    "{count} module(s) from your working tree, starting with {first_module}. It measured the "
    "staged code, not HEAD, so that baseline is not trusted and every staged failure in this "
    "group blocks. An editable install whose import hook runs ahead of the path scan is the "
    "usual cause."
)

REGRESSION_BASELINE_LEAK_UNREPORTED_MESSAGE: str = (
    "code_rules_gate: the HEAD baseline run for the group rooted at {group_root} wrote no "
    "import-origin report, so whether it loaded your working-tree code is unknown. That "
    "baseline is not trusted and every staged failure in this group blocks."
)
