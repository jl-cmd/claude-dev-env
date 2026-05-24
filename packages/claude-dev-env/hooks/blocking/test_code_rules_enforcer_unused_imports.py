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
prior_and_post_edit_content = _hook_module.prior_and_post_edit_content


PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/tests/test_loader.py"


def test_should_flag_unused_from_import() -> None:
    source = (
        "from hooks_constants.preflight_constants import VENV_DIRECTORY_NAME\n"
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
        "from hooks_constants.preflight_constants import VENV_DIRECTORY_NAME\n"
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
        "from hooks_constants.preflight_constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "__all__ = ['something']\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Files declaring __all__ may re-export — skip to avoid false positives, got: {issues}"
    )


def test_should_skip_file_with_dunder_all_annotated_assignment() -> None:
    source = (
        "from hooks_constants.preflight_constants import VENV_DIRECTORY_NAME\n"
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
        "from hooks_constants.constants import UNUSED_NAME\n"
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
        "from hooks_constants.constants import UNUSED_NAME\n"
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
        "from hooks_constants.preflight_constants import VENV_DIRECTORY_NAME\n"
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
        "from hooks_constants.constants import USED_ONE, UNUSED_TWO\n"
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
        "from hooks_constants.constants import UNUSED_BUT_DELIBERATE  # noqa: F401\n"
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
        "from hooks_constants.constants import (  # noqa: F401\n"
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
        'from hooks_constants.constants import UNUSED_NAME\n'
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
        "from hooks_constants.constants import UNUSED  # noqa: E402\n"
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
        "from hooks_constants.constants import UNUSED  # noqa\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Bare noqa must suppress unused import, got: {issues}"


def test_should_not_flag_imports_referenced_only_in_full_file_content() -> None:
    fragment = "from hooks_constants.constants import NEW_NAME\n"
    full_file = (
        "from hooks_constants.constants import NEW_NAME\n"
        "\n"
        "def existing_function() -> str:\n"
        "    return NEW_NAME\n"
    )
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file,
    )
    assert issues == [], (
        f"When the post-edit file references the import, it must not flag, got: {issues}"
    )


def test_should_flag_imports_unused_in_full_file_content() -> None:
    fragment = "from hooks_constants.constants import TRULY_UNUSED\n"
    full_file = (
        "from hooks_constants.constants import TRULY_UNUSED\n"
        "\n"
        "def existing_function() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file,
    )
    assert any("TRULY_UNUSED" in each_issue for each_issue in issues), (
        f"Imports unused in the post-edit file must still flag, got: {issues}"
    )


def test_should_only_flag_imports_in_fragment_not_full_file() -> None:
    fragment = "from hooks_constants.constants import FRAGMENT_IMPORT\n"
    full_file = (
        "from hooks_constants.other import PRE_EXISTING_UNUSED\n"
        "from hooks_constants.constants import FRAGMENT_IMPORT\n"
        "\n"
        "def existing_function() -> str:\n"
        "    return FRAGMENT_IMPORT\n"
    )
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file,
    )
    assert issues == [], (
        "Pre-existing imports outside the fragment must not be flagged on Edit; "
        f"got: {issues}"
    )


def test_should_skip_when_full_file_declares_dunder_all() -> None:
    fragment = "from hooks_constants.constants import NEW_NAME\n"
    full_file = (
        "from hooks_constants.constants import NEW_NAME\n"
        "\n"
        "__all__ = ['NEW_NAME']\n"
    )
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file,
    )
    assert issues == [], (
        "__all__ in the post-edit file must skip the scan even when the fragment "
        f"itself does not contain __all__, got: {issues}"
    )


def test_should_skip_when_full_file_uses_type_checking_gate() -> None:
    fragment = "from hooks_constants.constants import NEW_NAME\n"
    full_file = (
        "from typing import TYPE_CHECKING\n"
        "from hooks_constants.constants import NEW_NAME\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from somewhere import OtherName\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file,
    )
    assert issues == [], (
        "TYPE_CHECKING gate in the post-edit file must skip the scan, "
        f"got: {issues}"
    )


def test_should_fall_back_to_content_when_full_file_content_is_none() -> None:
    source = (
        "from hooks_constants.constants import VENV_DIRECTORY_NAME\n"
        "\n"
        "def run() -> None:\n"
        "    return None\n"
    )
    issues = check_unused_module_level_imports(source, PRODUCTION_FILE_PATH, full_file_content=None)
    assert any("VENV_DIRECTORY_NAME" in each_issue for each_issue in issues), (
        f"Backward-compat: with full_file_content=None, behavior must match "
        f"the existing single-argument scan, got: {issues}"
    )


def test_should_fall_back_when_full_file_content_has_syntax_error() -> None:
    fragment = "from hooks_constants.constants import NEW_NAME\n"
    full_file_with_syntax_error = "from config import (\n  not python\n"
    issues = check_unused_module_level_imports(
        fragment, PRODUCTION_FILE_PATH, full_file_content=full_file_with_syntax_error,
    )
    assert issues == [], (
        "When the reconstructed post-edit content cannot be parsed, return empty "
        f"rather than raising, got: {issues}"
    )


def test_reconstruct_post_edit_returns_replaced_content(tmp_path: pathlib.Path) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("ALPHA = 1\nBETA = 2\n", encoding="utf-8")
    prior_content, post_edit = prior_and_post_edit_content(
        str(target_file), "BETA = 2", "BETA = 22\nGAMMA = 3",
    )
    assert prior_content == "ALPHA = 1\nBETA = 2\n"
    assert post_edit == "ALPHA = 1\nBETA = 22\nGAMMA = 3\n", (
        f"Helper must return the file body with the first occurrence replaced, got: {post_edit!r}"
    )


def test_reconstruct_post_edit_returns_none_when_file_missing(tmp_path: pathlib.Path) -> None:
    missing_file = tmp_path / "does_not_exist.py"
    prior_content, post_edit = prior_and_post_edit_content(
        str(missing_file), "any_old", "any_new",
    )
    assert prior_content is None
    assert post_edit is None, (
        f"Missing file must yield None so the caller treats it as 'no full-file context', got: {post_edit!r}"
    )


def test_reconstruct_post_edit_returns_none_when_old_string_absent(tmp_path: pathlib.Path) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("ALPHA = 1\n", encoding="utf-8")
    prior_content, post_edit = prior_and_post_edit_content(
        str(target_file), "ZETA = 9", "OMEGA = 0",
    )
    assert prior_content is None
    assert post_edit is None, (
        f"Absent old_string means the Edit will not apply cleanly — return None, got: {post_edit!r}"
    )


def test_reconstruct_post_edit_replaces_only_first_occurrence(tmp_path: pathlib.Path) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("X = 1\nX = 1\n", encoding="utf-8")
    prior_content, post_edit = prior_and_post_edit_content(
        str(target_file), "X = 1", "X = 2",
    )
    assert prior_content == "X = 1\nX = 1\n"
    assert post_edit == "X = 2\nX = 1\n", (
        "Edit replaces only the first occurrence; helper must mirror that, got: "
        f"{post_edit!r}"
    )


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
        "from hooks_constants.constants import UNUSED_NAME\n"
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
        "from hooks_constants.constants import UNUSED_NAME\n"
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
        "from hooks_constants.constants import UNUSED; MARKER = '# noqa: F401'\n"
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
