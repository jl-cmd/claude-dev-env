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


def test_should_flag_bare_set_parameter_without_all_prefix() -> None:
    source = "def consume(numbers: set[int]) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected bare set[int] parameter flagged, got: {issues}"
    )


def test_should_flag_pep604_union_set_with_none_right() -> None:
    source = "def consume(numbers: set[int] | None = None) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected set[int] | None parameter flagged, got: {issues}"
    )


def test_should_flag_pep604_union_set_with_none_left() -> None:
    source = "def consume(numbers: None | set[int] = None) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected None | set[int] parameter flagged, got: {issues}"
    )


def test_should_flag_optional_set_parameter() -> None:
    source = (
        "from typing import Optional\n"
        "\n"
        "def consume(numbers: Optional[set[int]] = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected Optional[set[int]] parameter flagged, got: {issues}"
    )


def test_should_flag_union_set_with_none_parameter() -> None:
    source = (
        "from typing import Union\n"
        "\n"
        "def consume(numbers: Union[set[int], None] = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected Union[set[int], None] parameter flagged, got: {issues}"
    )


def test_should_flag_pep604_union_dict_parameter() -> None:
    source = (
        "from pathlib import Path\n"
        "\n"
        "def consume(per_path: dict[Path, set[int]] | None = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("per_path" in each_issue for each_issue in issues), (
        f"Expected dict[..] | None parameter flagged, got: {issues}"
    )


def test_should_not_flag_pep604_union_when_param_has_all_prefix() -> None:
    source = (
        "def consume(all_numbers: set[int] | None = None) -> None:\n    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert not any("all_numbers" in each_issue for each_issue in issues), (
        f"all_-prefixed parameter must not be flagged, got: {issues}"
    )


def test_should_not_flag_optional_when_param_uses_x_by_y_pattern() -> None:
    source = (
        "from typing import Optional\n"
        "\n"
        "def consume(price_by_product: Optional[dict[str, int]] = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert not any("price_by_product" in each_issue for each_issue in issues), (
        f"X_by_Y-pattern parameter must not be flagged, got: {issues}"
    )


def test_should_flag_qualified_typing_optional_set_parameter() -> None:
    source = (
        "import typing\n"
        "\n"
        "def consume(numbers: typing.Optional[set[int]] = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected typing.Optional[set[int]] (ast.Attribute outer subscript) flagged, got: {issues}"
    )


def test_should_flag_qualified_typing_union_with_none_parameter() -> None:
    source = (
        "import typing\n"
        "\n"
        "def consume(numbers: typing.Union[set[int], None] = None) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("numbers" in each_issue for each_issue in issues), (
        f"Expected typing.Union[set[int], None] (ast.Attribute outer subscript) flagged, got: {issues}"
    )


def test_should_flag_module_level_qualified_typing_optional_constant() -> None:
    source = (
        "import typing\n"
        "\n"
        "RAW_NUMBERS: typing.Optional[set[int]] = None\n"
    )
    issues = code_rules_enforcer.check_collection_prefix(source, PRODUCTION_FILE_PATH)
    assert any("RAW_NUMBERS" in each_issue for each_issue in issues), (
        f"Expected typing.Optional[set[int]] module-level constant flagged, got: {issues}"
    )


def test_should_flag_function_local_double_all_prefix() -> None:
    source = (
        "def grant() -> None:\n"
        "    all_all_permission_rules = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_permission_rules" in each_issue for each_issue in issues), (
        f"PR #289 finding: stuttering all_all_ must be flagged, got: {issues}"
    )


def test_should_flag_module_level_double_all_uppercase() -> None:
    source = "ALL_ALL_PROVIDERS = []\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("ALL_ALL_PROVIDERS" in each_issue for each_issue in issues), (
        f"Stuttering ALL_ALL_ at module scope must be flagged, got: {issues}"
    )


def test_should_flag_triple_all_prefix_stuttering() -> None:
    source = (
        "def consume() -> None:\n"
        "    all_all_all_things = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_all_things" in each_issue for each_issue in issues), (
        f"Triple all_ stuttering must be flagged, got: {issues}"
    )


def test_should_not_flag_single_all_prefix() -> None:
    source = (
        "def consume() -> None:\n"
        "    all_users = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Single all_ prefix is correct usage, must not flag, got: {issues}"
    )


def test_should_flag_stuttering_in_function_parameter() -> None:
    source = (
        "def consume(all_all_users: list) -> None:\n"
        "    return None\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_users" in each_issue for each_issue in issues), (
        f"Stuttering parameter name must be flagged, got: {issues}"
    )


def test_should_skip_stuttering_check_in_test_files() -> None:
    source = (
        "def test_something() -> None:\n"
        "    all_all_results = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, "packages/app/tests/test_foo.py"
    )
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_not_flag_all_all_when_used_as_substring() -> None:
    source = (
        "def consume() -> None:\n"
        "    install_all_users = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"'all_all_' as substring inside install_all_users must not flag, got: {issues}"
    )


def test_should_flag_underscore_prefixed_uppercase_double_all() -> None:
    source = "_ALL_ALL_PROVIDERS = []\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("_ALL_ALL_PROVIDERS" in each_issue for each_issue in issues), (
        f"Stuttering _ALL_ALL_ private constant must be flagged (regex symmetry), got: {issues}"
    )


def test_should_flag_underscore_prefixed_lowercase_double_all() -> None:
    source = (
        "def grant() -> None:\n"
        "    _all_all_permission_rules = []\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("_all_all_permission_rules" in each_issue for each_issue in issues), (
        f"Stuttering _all_all_ private local must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_function_name() -> None:
    source = "def all_all_process() -> None:\n    return None\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_process" in each_issue for each_issue in issues), (
        f"Stuttering function name must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_async_function_name() -> None:
    source = "async def all_all_fetch() -> None:\n    return None\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_fetch" in each_issue for each_issue in issues), (
        f"Stuttering async function name must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_walrus_target() -> None:
    source = (
        "def grant() -> None:\n"
        "    if (all_all_result := compute()):\n"
        "        return None\n"
        "def compute() -> int:\n"
        "    return 0\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_result" in each_issue for each_issue in issues), (
        f"Stuttering walrus target must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_comprehension_target() -> None:
    source = (
        "def grant() -> list[int]:\n"
        "    return [all_all_item for all_all_item in range(10)]\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_item" in each_issue for each_issue in issues), (
        f"Stuttering comprehension target must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_import_as_alias() -> None:
    source = "import collections as all_all_collections\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_collections" in each_issue for each_issue in issues), (
        f"Stuttering import-as alias must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_from_import_as_alias() -> None:
    source = "from collections import OrderedDict as all_all_ordered\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_ordered" in each_issue for each_issue in issues), (
        f"Stuttering from-import as alias must be flagged, got: {issues}"
    )


def test_should_flag_stuttering_class_name() -> None:
    source = (
        "class all_all_models:\n"
        "    value = 1\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, PRODUCTION_FILE_PATH
    )
    assert any("all_all_models" in each_issue for each_issue in issues), (
        f"Stuttering class name must be flagged, got: {issues}"
    )
