"""Tests for environment-variable table row recognition.

Each test drives ``iter_env_var_table_rows`` against markdown text and asserts
the exact rows it yields. The behavior under test is table context: which
markdown tables read as environment-variable summaries, and which read as
source, constant, or component tables that name no environment consumer.
"""

from __future__ import annotations

from env_var_table_rows import iter_env_var_table_rows


def test_environment_variable_header_yields_data_rows() -> None:
    content = (
        "| Environment variable | Consumer |\n| --- | --- |\n| `UPLOAD_TOKEN` | `workflow.py` |\n"
    )
    assert list(iter_env_var_table_rows(content)) == [
        "| Environment variable | Consumer |",
        "| `UPLOAD_TOKEN` | `workflow.py` |",
    ]


def test_constant_table_yields_nothing() -> None:
    content = (
        "| Constant | Value | Source |\n"
        "| --- | --- | --- |\n"
        "| `UPLOAD_DELAY_SECONDS` | 5 | `workflow.py` |\n"
    )
    assert list(iter_env_var_table_rows(content)) == []


def test_component_table_yields_nothing() -> None:
    content = (
        "| Component | Location | Purpose |\n"
        "| --- | --- | --- |\n"
        "| `ACCOUNT_LINK_PRIMARY` | `workflow.py` | Selector |\n"
    )
    assert list(iter_env_var_table_rows(content)) == []


def test_generic_name_header_under_environment_heading_yields_rows() -> None:
    content = (
        "## Environment variables\n\n"
        "| Name | Consumer |\n"
        "| --- | --- |\n"
        "| `UPLOAD_TOKEN` | `workflow.py` |\n"
    )
    assert list(iter_env_var_table_rows(content)) == [
        "| Name | Consumer |",
        "| `UPLOAD_TOKEN` | `workflow.py` |",
    ]


def test_generic_name_header_without_environment_heading_yields_nothing() -> None:
    content = (
        "## Selectors\n\n"
        "| Name | Consumer |\n"
        "| --- | --- |\n"
        "| `ACCOUNT_LINK_PRIMARY` | `workflow.py` |\n"
    )
    assert list(iter_env_var_table_rows(content)) == []


def test_headerless_fragment_naming_a_variable_yields_the_row() -> None:
    content = "| `UPLOAD_TOKEN` | `workflow.py` |\n"
    assert list(iter_env_var_table_rows(content)) == ["| `UPLOAD_TOKEN` | `workflow.py` |"]


def test_rows_inside_a_code_fence_yield_nothing() -> None:
    content = (
        "```markdown\n"
        "| Environment variable | Consumer |\n"
        "| --- | --- |\n"
        "| `UPLOAD_TOKEN` | `workflow.py` |\n"
        "```\n"
    )
    assert list(iter_env_var_table_rows(content)) == []


def test_constant_table_after_an_environment_table_yields_nothing_extra() -> None:
    content = (
        "| Environment variable | Consumer |\n"
        "| --- | --- |\n"
        "| `UPLOAD_TOKEN` | `workflow.py` |\n\n"
        "| Constant | Source |\n"
        "| --- | --- |\n"
        "| `UPLOAD_DELAY_SECONDS` | `workflow.py` |\n"
    )
    assert list(iter_env_var_table_rows(content)) == [
        "| Environment variable | Consumer |",
        "| `UPLOAD_TOKEN` | `workflow.py` |",
    ]


def test_separator_row_is_never_yielded() -> None:
    content = (
        "| Environment variable | Consumer |\n| :--- | ---: |\n| `UPLOAD_TOKEN` | `workflow.py` |\n"
    )
    assert "| :--- | ---: |" not in list(iter_env_var_table_rows(content))
