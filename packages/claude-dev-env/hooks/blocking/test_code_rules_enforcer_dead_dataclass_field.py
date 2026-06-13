from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer", ENFORCER_PATH
)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/report.py"
TEST_FILE_PATH = "packages/app/services/test_report.py"
MIGRATION_FILE_PATH = "packages/app/migrations/0001_initial.py"
WORKFLOW_FILE_PATH = "packages/app/skills/thing/workflow/render_report.py"


def _check(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_dataclass_fields(source, file_path)


def test_should_flag_dataclass_field_assigned_but_never_read() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    number: int\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(number=1, url='x')\n"
        "\n"
        "def render(metadata: PrMetadata) -> int:\n"
        "    return metadata.number\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any(
        "'url'" in each_issue and "PrMetadata" in each_issue for each_issue in issues
    ), f"Expected dead 'url' field flagged, got: {issues}"
    assert not any(
        "'number'" in each_issue for each_issue in issues
    ), f"Read field 'number' must not be flagged, got: {issues}"


def test_should_not_flag_field_read_via_attribute_access() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
        "\n"
        "def render(metadata: PrMetadata) -> str:\n"
        "    return metadata.url\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_when_class_never_constructed_in_file() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PublicConfig:\n"
        "    url: str\n"
        "    number: int\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_non_dataclass_class() -> None:
    source = "class Plain:\n    url: str\n\ndef build() -> Plain:\n    return Plain()\n"
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_classvar_field() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "@dataclass\n"
        "class Counter:\n"
        "    label: ClassVar[str] = 'count'\n"
        "    total: int\n"
        "\n"
        "def build() -> Counter:\n"
        "    return Counter(total=1)\n"
        "\n"
        "def read(counter: Counter) -> int:\n"
        "    return counter.total\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_field_read_via_literal_getattr() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> Row:\n"
        "    return Row(url='x')\n"
        "\n"
        "def read(row: Row) -> str:\n"
        "    return getattr(row, 'url')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_non_literal_getattr_present() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> Row:\n"
        "    return Row(url='x')\n"
        "\n"
        "def read(row: Row, field_name: str) -> str:\n"
        "    return getattr(row, field_name)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_handle_called_dataclass_decorator() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any(
        "'url'" in each_issue for each_issue in issues
    ), f"Expected dead field flagged on called-decorator dataclass, got: {issues}"


def test_should_handle_dotted_dataclasses_decorator() -> None:
    source = (
        "import dataclasses\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any(
        "'url'" in each_issue for each_issue in issues
    ), f"Expected dead field flagged on dotted-decorator dataclass, got: {issues}"


def test_should_be_silent_for_test_files() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    assert _check(source, TEST_FILE_PATH) == []


def test_should_be_silent_for_migration_files() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    assert _check(source, MIGRATION_FILE_PATH) == []


def test_should_flag_dead_field_in_workflow_path() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    issues = _check(source, WORKFLOW_FILE_PATH)
    assert any(
        "'url'" in each_issue for each_issue in issues
    ), f"Workflow-path files are subject to dead-code detection, got: {issues}"


def test_should_tolerate_syntax_error() -> None:
    assert _check("@dataclass\nclass Broken(:\n", PRODUCTION_FILE_PATH) == []


def test_validate_content_runs_dead_field_check() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(url='x')\n"
    )
    issues = code_rules_enforcer.validate_content(source, PRODUCTION_FILE_PATH)
    assert any(
        "'url'" in each_issue for each_issue in issues
    ), f"Expected the enforcer dispatch to surface the dead field, got: {issues}"


def test_should_suppress_check_when_asdict_consumes_instance() -> None:
    source = (
        "from dataclasses import dataclass, asdict\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> dict:\n"
        "    return asdict(Row(url='x'))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_astuple_consumes_instance() -> None:
    source = (
        "from dataclasses import dataclass, astuple\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> tuple:\n"
        "    return astuple(Row(url='x'))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_vars_consumes_instance() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> dict:\n"
        "    return vars(Row(url='x'))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_replace_consumes_instance() -> None:
    source = (
        "from dataclasses import dataclass, replace\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> Row:\n"
        "    return replace(Row(url='x'), url='y')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_dotted_replace_consumes_instance() -> None:
    source = (
        "import dataclasses\n"
        "\n"
        "@dataclasses.dataclass(frozen=True)\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> Row:\n"
        "    return dataclasses.replace(Row(url='x'), url='y')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_instance_dict_consumes_instance() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def build() -> dict:\n"
        "    return Row(url='x').__dict__\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_field_read_via_multi_argument_attrgetter() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "from operator import attrgetter\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    first: int\n"
        "    second: int\n"
        "\n"
        "def build() -> tuple:\n"
        "    return attrgetter('first', 'second')(Row(first=1, second=2))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_two_instances_compared_for_equality() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def are_same(left: Row, right: Row) -> bool:\n"
        "    return Row(url='a') == Row(url='b')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_ordered_instances_compared() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass(order=True)\n"
        "class Row:\n"
        "    priority: int\n"
        "\n"
        "def is_earlier() -> bool:\n"
        "    return Row(priority=1) < Row(priority=2)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_instances_placed_in_set() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def unique_rows() -> set:\n"
        "    return {Row(url='a'), Row(url='b')}\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_whole_instance_stringified() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def describe() -> str:\n"
        "    return str(Row(url='x'))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_field_read_via_match_class_pattern() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def read(row: Row) -> str:\n"
        "    match row:\n"
        "        case Row(url=found):\n"
        "            return found\n"
        "    return ''\n"
        "\n"
        "def build() -> Row:\n"
        "    return Row(url='x')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_check_when_fields_reflection_consumes_instance() -> None:
    source = (
        "import dataclasses\n"
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    url: str\n"
        "\n"
        "def field_names() -> list:\n"
        "    return [each_field.name for each_field in dataclasses.fields(Row(url='x'))]\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_field_read_via_augmented_assignment() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Row:\n"
        "    counter: int\n"
        "\n"
        "def bump(row: Row) -> None:\n"
        "    row.counter += 1\n"
        "\n"
        "def build() -> Row:\n"
        "    return Row(counter=0)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_evaluate_full_file_content_when_supplied() -> None:
    fragment = "    return metadata.number\n"
    full_file = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class PrMetadata:\n"
        "    number: int\n"
        "    url: str\n"
        "\n"
        "def build() -> PrMetadata:\n"
        "    return PrMetadata(number=1, url='x')\n"
        "\n"
        "def render(metadata: PrMetadata) -> int:\n"
        "    return metadata.number\n"
    )
    issues = code_rules_enforcer.check_dead_dataclass_fields(
        fragment, PRODUCTION_FILE_PATH, full_file
    )
    assert any(
        "'url'" in each_issue for each_issue in issues
    ), f"Expected the reconstructed whole-file content to govern, got: {issues}"
    assert not any(
        "'number'" in each_issue for each_issue in issues
    ), f"Read field 'number' must not be flagged, got: {issues}"
