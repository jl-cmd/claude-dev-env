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
