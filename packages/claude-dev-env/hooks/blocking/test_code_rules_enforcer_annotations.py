from __future__ import annotations

from pathlib import Path
import importlib.util

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer", ENFORCER_PATH
)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"


def test_should_flag_parameter_without_annotation() -> None:
    source = "def consume(value) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert any("value" in each_issue for each_issue in issues), (
        f"Expected unannotated parameter flagged, got: {issues}"
    )


def test_should_not_flag_annotated_parameters() -> None:
    source = (
        "def consume(value: int, label: str = 'default') -> None:\n    return None\n"
    )
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no issues for annotated params, got: {issues}"


def test_should_exempt_self_and_cls_parameters() -> None:
    source = (
        "class Foo:\n"
        "    def method(self, value: int) -> None:\n"
        "        return None\n"
        "    @classmethod\n"
        "    def factory(cls, value: int) -> 'Foo':\n"
        "        return cls()\n"
    )
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"self/cls must be exempt from annotation requirement, got: {issues}"
    )


def test_should_flag_class_method_parameter_without_annotation() -> None:
    source = "class Foo:\n    def method(self, value) -> None:\n        return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert any("value" in each_issue for each_issue in issues), (
        f"Expected method param flagged, got: {issues}"
    )


def test_should_skip_parameter_check_in_test_files() -> None:
    source = "def consume(value) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues}"


def test_should_flag_function_without_return_annotation() -> None:
    source = "def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert any("fetch" in each_issue for each_issue in issues), (
        f"Expected function without return type flagged, got: {issues}"
    )


def test_should_not_flag_function_with_return_annotation() -> None:
    source = "def fetch(url: str) -> str:\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Function with return type must not be flagged, got: {issues}"


def test_should_flag_async_function_without_return_annotation() -> None:
    source = "async def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert any("fetch" in each_issue for each_issue in issues), (
        f"Expected async function without return type flagged, got: {issues}"
    )


def test_should_skip_return_check_in_test_files() -> None:
    source = "def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues}"


def test_should_flag_unannotated_known_fixture_in_test_file() -> None:
    source = "def test_board(tmp_path):\n    assert tmp_path.exists()\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"Expected unannotated tmp_path fixture flagged, got: {issues}"


def test_should_not_flag_annotated_known_fixture_in_test_file() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_board(tmp_path: Path) -> None:\n"
        "    assert tmp_path.exists()\n"
    )
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], f"Annotated tmp_path must not be flagged, got: {issues}"


def test_should_not_flag_ordinary_test_parameter() -> None:
    source = "def test_thing(some_value):\n    assert some_value\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"Ordinary test params stay exempt; only known fixtures are checked, "
        f"got: {issues}"
    )


def test_should_not_flag_known_fixture_name_outside_test_files() -> None:
    source = "def build(monkeypatch):\n    return monkeypatch\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Non-test files are covered by the broad parameter check, not this one, "
        f"got: {issues}"
    )


def test_should_flag_unannotated_monkeypatch_fixture() -> None:
    source = "def test_env(monkeypatch):\n    monkeypatch.setenv('A', 'B')\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "monkeypatch" in each_issue and "MonkeyPatch" in each_issue
        for each_issue in issues
    ), f"Expected unannotated monkeypatch fixture flagged, got: {issues}"


def test_should_not_flag_known_fixture_in_non_test_helper() -> None:
    source = "def render_view(request):\n    return request.path\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"Ordinary helper (non-test, non-fixture) must not be flagged, got: {issues}"
    )


def test_should_flag_unannotated_fixture_in_decorated_fixture() -> None:
    source = (
        "import pytest\n"
        "@pytest.fixture\n"
        "def board(tmp_path):\n"
        "    return tmp_path\n"
    )
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"Expected unannotated tmp_path in @pytest.fixture-decorated function flagged, got: {issues}"


def test_should_flag_known_fixture_with_wrong_annotation() -> None:
    source = "def test_board(tmp_path: str):\n    assert tmp_path\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"Expected wrongly annotated tmp_path: str flagged, got: {issues}"


def test_should_flag_known_fixture_with_unrelated_annotation() -> None:
    source = "def test_board(tmp_path: int):\n    assert tmp_path\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"Expected wrongly annotated tmp_path: int flagged, got: {issues}"


def test_should_not_flag_correctly_annotated_qualified_fixture() -> None:
    source = (
        "import pytest\n"
        "def test_env(monkeypatch: pytest.MonkeyPatch) -> None:\n"
        "    monkeypatch.setenv('A', 'B')\n"
    )
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"Correctly annotated monkeypatch must not be flagged, got: {issues}"
    )


def test_should_not_flag_dotted_pathlib_path_fixture_annotation() -> None:
    source = (
        "import pathlib\n"
        "def test_board(tmp_path: pathlib.Path) -> None:\n"
        "    assert tmp_path.exists()\n"
    )
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"tmp_path: pathlib.Path is an equally-correct spelling, got: {issues}"
    )


def test_should_not_flag_bare_tail_of_qualified_fixture_annotation() -> None:
    source = (
        "from pytest import MonkeyPatch\n"
        "def test_env(monkeypatch: MonkeyPatch) -> None:\n"
        "    monkeypatch.setenv('A', 'B')\n"
    )
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"monkeypatch: MonkeyPatch matches the qualified expected tail, got: {issues}"
    )


def test_should_not_flag_forward_reference_fixture_annotation() -> None:
    source = 'def test_board(tmp_path: "Path") -> None:\n    assert tmp_path\n'
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f'A forward-ref "Path" annotation must not be flagged, got: {issues}'
    )


def test_should_not_flag_star_arg_fixture_name() -> None:
    source = "def test_board(*tmp_path):\n    assert tmp_path\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A *vararg sharing a fixture name is not an injection site, got: {issues}"
    )


def test_should_not_flag_double_star_arg_fixture_name() -> None:
    source = "def test_env(**monkeypatch):\n    assert monkeypatch\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A **kwarg sharing a fixture name is not an injection site, got: {issues}"
    )


def test_should_not_flag_positional_only_fixture_name() -> None:
    source = "def test_board(tmp_path, /):\n    pass\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A positional-only param cannot receive a keyword-injected fixture, got: {issues}"
    )


def test_should_flag_keyword_only_fixture_name() -> None:
    source = "def test_board(*, tmp_path):\n    pass\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"A keyword-only fixture is still an injection site, got: {issues}"


def test_should_not_flag_defaulted_fixture_name() -> None:
    source = "def test_board(tmp_path=None):\n    pass\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A defaulted param is not fixture-injected and must not be flagged, got: {issues}"
    )


def test_should_not_flag_defaulted_keyword_only_fixture_name() -> None:
    source = "def test_board(*, tmp_path=None):\n    pass\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A defaulted keyword-only param is not fixture-injected, got: {issues}"
    )


def test_should_flag_undefaulted_fixture_before_defaulted_one() -> None:
    source = "def test_board(tmp_path, capsys=None):\n    pass\n"
    issues = code_rules_enforcer.check_known_pytest_fixture_annotations(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue and "Path" in each_issue for each_issue in issues
    ), f"An undefaulted leading fixture stays an injection site, got: {issues}"
    assert not any("capsys" in each_issue for each_issue in issues), (
        f"The trailing defaulted param must not be flagged, got: {issues}"
    )


def test_should_flag_unused_known_fixture_parameter_in_test_file() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_omits_config(tmp_path: Path) -> None:\n"
        "    command = build_command('module.py', None)\n"
        "    assert command[-1] == 'module.py'\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert any(
        "tmp_path" in each_issue for each_issue in issues
    ), f"Expected unused tmp_path fixture parameter flagged, got: {issues}"


def test_should_not_flag_used_known_fixture_parameter() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_includes_config(tmp_path: Path) -> None:\n"
        "    config_file = tmp_path / 'pyproject.toml'\n"
        "    assert config_file.name == 'pyproject.toml'\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A referenced fixture parameter must not be flagged, got: {issues}"
    )


def test_should_not_flag_unused_ordinary_test_parameter() -> None:
    source = "def test_thing(some_value):\n    return 1\n"
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"Only known pytest fixtures are checked, not arbitrary params, got: {issues}"
    )


def test_should_not_flag_unused_fixture_outside_test_files() -> None:
    source = "def build(tmp_path):\n    return 1\n"
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"This check applies to test files only, got: {issues}"
    )


def test_should_flag_unused_monkeypatch_fixture_parameter() -> None:
    source = (
        "import pytest\n"
        "def test_env(monkeypatch: pytest.MonkeyPatch) -> None:\n"
        "    assert build_command('m.py', None)[-1] == 'm.py'\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert any(
        "monkeypatch" in each_issue for each_issue in issues
    ), f"Expected unused monkeypatch fixture parameter flagged, got: {issues}"


def test_should_count_attribute_access_as_fixture_use() -> None:
    source = (
        "import pytest\n"
        "def test_env(monkeypatch: pytest.MonkeyPatch) -> None:\n"
        "    monkeypatch.setenv('A', 'B')\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"Attribute access on the fixture counts as a use, got: {issues}"
    )


def test_should_count_nested_function_reference_as_fixture_use() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_board(tmp_path: Path) -> None:\n"
        "    def inner() -> Path:\n"
        "        return tmp_path\n"
        "    assert inner().name\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A reference inside a nested function counts as a use, got: {issues}"
    )


def test_should_not_flag_unused_fixture_in_decorated_fixture_function() -> None:
    source = (
        "import pytest\n"
        "from pathlib import Path\n"
        "@pytest.fixture\n"
        "def board(tmp_path: Path) -> int:\n"
        "    return 1\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A fixture composing another fixture by injection alone is intentional "
        f"and must not be flagged, got: {issues}"
    )


def test_should_count_comprehension_reference_as_fixture_use() -> None:
    source = (
        "import pytest\n"
        "def test_log_lines(caplog: pytest.LogCaptureFixture) -> None:\n"
        "    messages = [each_record.message for each_record in caplog.records]\n"
        "    assert messages == []\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A reference inside a comprehension counts as a use, got: {issues}"
    )


def test_should_not_flag_unused_fixture_in_decorated_test_named_function() -> None:
    source = (
        "import pytest\n"
        "from pathlib import Path\n"
        "@pytest.fixture\n"
        "def test_board(tmp_path: Path) -> int:\n"
        "    return 1\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A @pytest.fixture-decorated function named test_* is a fixture, not a "
        f"test, and must not be flagged, got: {issues}"
    )


def test_should_not_flag_fixture_param_on_nested_test_named_helper() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_outer(tmp_path: Path) -> None:\n"
        "    assert tmp_path\n"
        "    def test_inner(tmp_path) -> None:\n"
        "        return None\n"
        "    test_inner(tmp_path)\n"
    )
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A fixture-named parameter on a function nested inside a test body is a "
        f"local helper argument pytest never injects, got: {issues}"
    )


def test_should_count_augmented_assignment_as_fixture_reference() -> None:
    source = "def test_aug(request) -> None:\n    request += 1\n"
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"An augmented assignment to the fixture references it, got: {issues}"
    )


def test_should_count_del_as_fixture_reference() -> None:
    source = "def test_d(tmp_path: Path) -> None:\n    del tmp_path\n"
    issues = code_rules_enforcer.check_unused_known_pytest_fixture_parameters(
        source, TEST_FILE_PATH
    )
    assert issues == [], (
        f"A del of the fixture references it, got: {issues}"
    )


