"""Tests for unused module-level import detection.

Bot reviewers on PR #257 and PR #289 flagged FLAG_INCREMENTAL,
ALL_REPOSITORY_ROOT_MARKER_FILENAMES, VENV_DIRECTORY_NAME and other
imports that survived into a PR without ever being referenced.

The detector is intentionally narrow: it only flags `from X import Y`
or `import X` where Y/X is never referenced in the file body, the file
does not declare `__all__`, and the file does not use TYPE_CHECKING
conditional imports. The narrow scope keeps false positives low.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_unused_module_level_imports = _hook_module.check_unused_module_level_imports


PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/tests/test_loader.py"


def test_should_flag_unused_from_import() -> None:
    source = (
        "from config.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("VENV_DIRECTORY_NAME" in each_issue for each_issue in issues), (
        f"Expected VENV_DIRECTORY_NAME flagged, got: {issues}"
    )


def test_should_not_flag_used_from_import() -> None:
    source = (
        "from config.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "def run() -> str:\n"
        "    return VENV_DIRECTORY_NAME\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Used import must not be flagged, got: {issues}"


def test_should_flag_unused_plain_import() -> None:
    source = "import json\n\ndef run() -> None:\n    return None\n"
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("json" in each_issue for each_issue in issues), (
        f"Expected unused 'import json' flagged, got: {issues}"
    )


def test_should_not_flag_when_alias_is_used() -> None:
    source = "import json as _json\n\ndef run() -> str:\n    return _json.dumps({})\n"
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Aliased import referenced via alias must not flag, got: {issues}"
    )


def test_should_skip_file_with_dunder_all() -> None:
    source = (
        "from config.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "__all__ = ['something']\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Files declaring __all__ may re-export — skip to avoid false positives, got: {issues}"
    )


def test_should_skip_file_with_dunder_all_annotated_assignment() -> None:
    source = (
        "from config.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        '__all__: list[str] = ["VENV_DIRECTORY_NAME"]\n'
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "Annotated __all__ must skip unused-import scan like plain __all__, "
        f"got: {issues}"
    )


def test_should_skip_file_using_type_checking_block() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "from config.constants import UNUSED_NAME\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from somewhere import OtherName\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"TYPE_CHECKING-using files have annotation-only imports — skip, got: {issues}"
    )


def test_should_skip_test_files() -> None:
    source = (
        "from config.constants import UNUSED_NAME\n"
        "\n"
        "def test_thing() -> None:\n"
        "    assert True\n"
    )
    issues = check_unused_module_level_imports(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "from config import (\n  not python\n"
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Parse failure must return empty, got: {issues}"


def test_should_include_line_number_in_issue() -> None:
    source = (
        "\n"
        "from config.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("Line 2" in each_issue for each_issue in issues), (
        f"Expected line 2 reference, got: {issues}"
    )


def test_should_flag_each_unused_in_multi_import() -> None:
    source = (
        "from config.constants import USED_ONE, UNUSED_TWO\n"
        "\n"
        "def run() -> str:\n"
        "    return USED_ONE\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("UNUSED_TWO" in each_issue for each_issue in issues), (
        f"Expected UNUSED_TWO flagged independently, got: {issues}"
    )
    assert not any("USED_ONE" in each_issue for each_issue in issues), (
        f"USED_ONE is referenced — must not flag, got: {issues}"
    )


def test_should_not_flag_when_referenced_in_annotation() -> None:
    source = (
        "from typing import List\n\ndef run(xs: List[int]) -> None:\n    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"List used in annotation must count as a reference, got: {issues}"
    )


def test_should_skip_noqa_marked_imports() -> None:
    source = (
        "from config.constants import UNUSED_BUT_DELIBERATE  # noqa: F401\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"noqa-marked imports are deliberate side-effect imports, skip, got: {issues}"
    )


def test_should_skip_noqa_on_from_keyword_line_for_multiline_import() -> None:
    source = (
        "from config.constants import (  # noqa: F401\n"
        "    SOME_CONSTANT,\n"
        "    ANOTHER_CONSTANT,\n"
        ")\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"noqa on the from-keyword line must suppress every alias in the block, got: {issues}"
    )


def test_should_skip_future_annotations_import() -> None:
    source = (
        "from __future__ import annotations\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"__future__ imports are behavior-changing side-effect imports whose "
        f"binding name is never referenced — skip, got: {issues}"
    )


def test_should_skip_all_future_imports_regardless_of_name() -> None:
    source = (
        "from __future__ import annotations, division\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"All __future__ imports must be skipped regardless of binding name, got: {issues}"
    )


def test_should_skip_star_import() -> None:
    source = (
        "from os.path import *\n"
        "\n"
        "def run() -> str:\n"
        "    return join('a', 'b')\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Star imports cannot be meaningfully tracked - skip to avoid false positives, got: {issues}"
    )


def test_should_flag_when_name_only_appears_in_comment() -> None:
    source = (
        "import json\n"
        "\n"
        "# json reserved for later\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("json" in each_issue for each_issue in issues), (
        f"Mentions in comments must not count as references, got: {issues}"
    )


def test_should_not_skip_when_type_checking_only_in_string_constant() -> None:
    source = (
        'from config.constants import UNUSED_NAME\n'
        '\n'
        'HELP_TEXT = "See TYPE_CHECKING docs"\n'
        '\n'
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("UNUSED_NAME" in each_issue for each_issue in issues), (
        f"Substring TYPE_CHECKING in prose must not skip the scan, got: {issues}"
    )


def test_should_flag_when_noqa_lists_only_non_f401_codes() -> None:
    source = (
        "from config.constants import UNUSED  # noqa: E402\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("UNUSED" in each_issue for each_issue in issues), (
        f"E402-only noqa must not suppress unused-import findings, got: {issues}"
    )


def test_should_skip_when_noqa_is_bare() -> None:
    source = (
        "from config.constants import UNUSED  # noqa\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Bare noqa must suppress unused import, got: {issues}"


def test_should_flag_import_when_only_shadowed_local_name_is_loaded() -> None:
    source = (
        "import json\n"
        "\n"
        "def run(json: object) -> object:\n"
        "    return json\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("json" in each_issue for each_issue in issues), (
        f"Local shadow bindings must not count as import references, got: {issues}"
    )


def test_should_skip_when_type_checking_uses_imported_alias() -> None:
    source = (
        "from typing import TYPE_CHECKING as IS_TYPE_CHECKING\n"
        "from config.constants import UNUSED_NAME\n"
        "\n"
        "if IS_TYPE_CHECKING:\n"
        "    from somewhere import OtherName\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"TYPE_CHECKING imported aliases must skip annotation-only files, got: {issues}"
    )


def test_should_skip_when_type_checking_uses_module_alias() -> None:
    source = (
        "import typing as t\n"
        "from config.constants import UNUSED_NAME\n"
        "\n"
        "if t.TYPE_CHECKING:\n"
        "    from somewhere import OtherName\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"TYPE_CHECKING module aliases must skip annotation-only files, got: {issues}"
    )


def test_should_not_flag_when_referenced_in_quoted_annotation() -> None:
    source = (
        "from typing import List\n"
        "\n"
        "def run(xs: \"List[int]\") -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Quoted annotations must count as import references, got: {issues}"
    )


def test_should_flag_when_noqa_only_appears_inside_string_literal() -> None:
    source = (
        "from config.constants import UNUSED; MARKER = '# noqa: F401'\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert any("UNUSED" in each_issue for each_issue in issues), (
        f"String literal noqa text must not suppress unused imports, got: {issues}"
    )


def test_should_not_flag_when_class_body_binding_matches_import_used_in_method() -> None:
    source = (
        "import os\n"
        "\n"
        "class Foo:\n"
        "    os = 'linux'\n"
        "\n"
        "    def bar(self) -> str:\n"
        "        return os.path.join('a', 'b')\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Class body bindings must not shadow module-level imports inside methods, got: {issues}"
    )


def test_should_not_flag_when_comprehension_variable_matches_import_used_after() -> None:
    source = (
        "import os\n"
        "\n"
        "def run() -> str:\n"
        "    result = [x for os in [1, 2, 3]]\n"
        "    return os.path.join('a', 'b')\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Comprehension iteration variables must not shadow enclosing scope bindings, got: {issues}"
    )
