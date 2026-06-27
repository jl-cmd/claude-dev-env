"""Tests for check_module_docstring_scope_omits_data_schema_constants (Category O).

A module whose one-line docstring scopes its contents to user-facing text while
the body also defines serialization field keys, run-metadata schema keys, or
runtime config under-describes the module — the Category O module-responsibility
drift. The gate fires only when the docstring claims a user-facing-text scope and
acknowledges no data-schema or runtime-config category, so broadening the summary
to name the data-schema keys and runtime config clears it.
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


def check_scope(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_module_docstring_scope_omits_data_schema_constants(
        content, file_path
    )


PRODUCTION_FILE_PATH = "/project/stp_contrast_fix/config/messages.py"
TEST_FILE_PATH = "/project/stp_contrast_fix/config/test_messages.py"

USER_FACING_SUMMARY = '"""User-facing strings: CLI flag names, help text, and log messages."""\n'
DATA_SCHEMA_BODY = (
    "from typing import Final\n"
    'CLI_FLAG_EXECUTE: Final[str] = "--execute"\n'
    'JSONL_FIELD_STP_PATH: Final[str] = "stp_path"\n'
    'RUN_METADATA_CLI_ARG_KEY_LIMIT: Final[str] = "limit"\n'
    'STDOUT_ENCODING: Final[str] = "utf-8"\n'
    'MAIN_LOGGING_FORMAT_STRING: Final[str] = "%(message)s"\n'
)


def test_flags_user_facing_summary_over_data_schema_constants() -> None:
    issues = check_scope(USER_FACING_SUMMARY + DATA_SCHEMA_BODY, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "JSONL_FIELD_STP_PATH" in issues[0]
    assert "RUN_METADATA_CLI_ARG_KEY_LIMIT" in issues[0]
    assert "module-responsibility drift" in issues[0]


def test_passes_when_summary_acknowledges_data_schema_scope() -> None:
    acknowledging_summary = (
        '"""User-facing strings plus per-theme JSONL field keys, run-metadata '
        'schema keys, and runtime config."""\n'
    )
    assert check_scope(acknowledging_summary + DATA_SCHEMA_BODY, PRODUCTION_FILE_PATH) == []


def test_passes_when_module_has_no_data_schema_constants() -> None:
    strings_only_body = (
        "from typing import Final\n"
        'CLI_FLAG_EXECUTE: Final[str] = "--execute"\n'
        'CLI_FLAG_LIMIT: Final[str] = "--limit"\n'
    )
    assert check_scope(USER_FACING_SUMMARY + strings_only_body, PRODUCTION_FILE_PATH) == []


def test_passes_when_summary_does_not_claim_user_facing_scope() -> None:
    non_user_facing_summary = '"""Theme-database column names and SQL templates."""\n'
    assert check_scope(non_user_facing_summary + DATA_SCHEMA_BODY, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    assert check_scope(USER_FACING_SUMMARY + DATA_SCHEMA_BODY, TEST_FILE_PATH) == []
