"""Behavioral tests for the grok batch scaffold generator.

The scaffold writes the fixed report contract, per-worker brief and task-body
part files, and a batch-spec skeleton whose worker entries load cleanly through
the production ``spawn_grok_batch.load_batch_spec`` reader. The scripts
directory is placed on ``sys.path`` by the sibling ``conftest.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import grok_batch_scaffold as scaffold
import pytest
import spawn_grok_batch as batch
from dev_env_scripts_constants.grok_scaffold_constants import (
    BATCH_SPEC_FILENAME,
    BUILD_BRIEF_TEMPLATE,
    CLI_WORKER_FLAG,
    READONLY_BRIEF_TEMPLATE,
    REPORT_CONTRACT_FILENAME,
    REPORT_CONTRACT_TEMPLATE,
    SCAFFOLD_ERROR_STDERR_PREFIX,
    SCAFFOLD_RESULT_REPORT_CONTRACT_FILE_KEY,
    SCAFFOLD_RESULT_SPEC_FILE_KEY,
    SCAFFOLD_RESULT_WORKERS_KEY,
    SCAFFOLD_WORKER_BRIEF_FILE_KEY,
    SCAFFOLD_WORKER_ROLE_NAME_KEY,
    SCAFFOLD_WORKER_TASK_BODY_FILE_KEY,
)
from dev_env_scripts_constants.grok_worker_constants import (
    BATCH_SPEC_WORKERS_KEY,
    CLI_RUN_STATE_DIR_FLAG,
    DEFAULT_ROLE,
    TOOL_PROFILE_BUILD,
    TOOL_PROFILE_READONLY,
    UTF8_ENCODING,
    WORKER_SPEC_PROMPT_PARTS_KEY,
)


def test_parse_worker_token_returns_role_and_profile() -> None:
    parsed_worker = scaffold.parse_worker_token(
        f"map-callsites:{TOOL_PROFILE_READONLY}"
    )
    assert parsed_worker.role_name == "map-callsites"
    assert parsed_worker.tool_profile == TOOL_PROFILE_READONLY


def test_parse_worker_token_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError):
        scaffold.parse_worker_token("map-callsites:sideways")


def test_parse_worker_token_rejects_non_slug_role_name() -> None:
    with pytest.raises(ValueError):
        scaffold.parse_worker_token(f"Bad Role:{TOOL_PROFILE_BUILD}")


def test_parse_worker_token_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        scaffold.parse_worker_token("noseparator")


def test_scaffold_writes_report_contract_verbatim(tmp_path: Path) -> None:
    scaffold.scaffold_batch(
        run_state_directory=tmp_path,
        all_workers=(scaffold.ScaffoldWorker("probe", TOOL_PROFILE_READONLY),),
        role=DEFAULT_ROLE,
    )
    contract_path = tmp_path / REPORT_CONTRACT_FILENAME
    assert contract_path.read_text(encoding=UTF8_ENCODING) == REPORT_CONTRACT_TEMPLATE


def test_scaffold_brief_matches_profile_template(tmp_path: Path) -> None:
    scaffold_outcome = scaffold.scaffold_batch(
        run_state_directory=tmp_path,
        all_workers=(
            scaffold.ScaffoldWorker("reader", TOOL_PROFILE_READONLY),
            scaffold.ScaffoldWorker("builder", TOOL_PROFILE_BUILD),
        ),
        role=DEFAULT_ROLE,
    )
    by_role = {worker.role_name: worker for worker in scaffold_outcome.all_worker_paths}
    assert (
        by_role["reader"].brief_path.read_text(encoding=UTF8_ENCODING)
        == READONLY_BRIEF_TEMPLATE
    )
    assert (
        by_role["builder"].brief_path.read_text(encoding=UTF8_ENCODING)
        == BUILD_BRIEF_TEMPLATE
    )


def test_scaffold_wires_prompt_parts_in_brief_task_contract_order(
    tmp_path: Path,
) -> None:
    scaffold_outcome = scaffold.scaffold_batch(
        run_state_directory=tmp_path,
        all_workers=(scaffold.ScaffoldWorker("reader", TOOL_PROFILE_READONLY),),
        role=DEFAULT_ROLE,
    )
    spec_payload = json.loads(
        scaffold_outcome.spec_path.read_text(encoding=UTF8_ENCODING)
    )
    worker_entry = spec_payload[BATCH_SPEC_WORKERS_KEY][0]
    prompt_parts = worker_entry[WORKER_SPEC_PROMPT_PARTS_KEY]
    contract_path = tmp_path / REPORT_CONTRACT_FILENAME
    assert prompt_parts == [
        str(scaffold_outcome.all_worker_paths[0].brief_path),
        str(scaffold_outcome.all_worker_paths[0].task_body_path),
        str(contract_path),
    ]
    assert all(Path(each_part).is_absolute() for each_part in prompt_parts)


def test_scaffolded_spec_loads_through_production_reader(tmp_path: Path) -> None:
    scaffold_outcome = scaffold.scaffold_batch(
        run_state_directory=tmp_path,
        all_workers=(
            scaffold.ScaffoldWorker("reader", TOOL_PROFILE_READONLY),
            scaffold.ScaffoldWorker("builder", TOOL_PROFILE_BUILD),
        ),
        role=DEFAULT_ROLE,
    )
    loaded_spec = batch.load_batch_spec(scaffold_outcome.spec_path)
    assert loaded_spec.role == DEFAULT_ROLE
    assert tuple(worker.tool_profile for worker in loaded_spec.all_workers) == (
        TOOL_PROFILE_READONLY,
        TOOL_PROFILE_BUILD,
    )


def test_scaffold_result_as_dict_reports_written_paths(tmp_path: Path) -> None:
    scaffold_outcome = scaffold.scaffold_batch(
        run_state_directory=tmp_path,
        all_workers=(scaffold.ScaffoldWorker("reader", TOOL_PROFILE_READONLY),),
        role=DEFAULT_ROLE,
    )
    summary_payload = scaffold.scaffold_outcome_as_dict(scaffold_outcome)
    assert summary_payload[SCAFFOLD_RESULT_SPEC_FILE_KEY] == str(
        scaffold_outcome.spec_path
    )
    assert summary_payload[SCAFFOLD_RESULT_REPORT_CONTRACT_FILE_KEY] == str(
        tmp_path / REPORT_CONTRACT_FILENAME
    )
    worker_row = summary_payload[SCAFFOLD_RESULT_WORKERS_KEY][0]
    assert worker_row[SCAFFOLD_WORKER_ROLE_NAME_KEY] == "reader"
    assert worker_row[SCAFFOLD_WORKER_BRIEF_FILE_KEY] == str(
        scaffold_outcome.all_worker_paths[0].brief_path
    )
    assert worker_row[SCAFFOLD_WORKER_TASK_BODY_FILE_KEY] == str(
        scaffold_outcome.all_worker_paths[0].task_body_path
    )


def test_main_writes_files_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = scaffold.main(
        [
            CLI_RUN_STATE_DIR_FLAG,
            str(tmp_path),
            CLI_WORKER_FLAG,
            f"reader:{TOOL_PROFILE_READONLY}",
            CLI_WORKER_FLAG,
            f"builder:{TOOL_PROFILE_BUILD}",
        ]
    )
    assert exit_code == 0
    printed_summary = json.loads(capsys.readouterr().out)
    assert (tmp_path / BATCH_SPEC_FILENAME).is_file()
    assert (tmp_path / REPORT_CONTRACT_FILENAME).is_file()
    printed_roles = {
        worker_row[SCAFFOLD_WORKER_ROLE_NAME_KEY]
        for worker_row in printed_summary[SCAFFOLD_RESULT_WORKERS_KEY]
    }
    assert printed_roles == {"reader", "builder"}


def test_main_rejects_bad_worker_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = scaffold.main(
        [
            CLI_RUN_STATE_DIR_FLAG,
            str(tmp_path),
            CLI_WORKER_FLAG,
            "reader:sideways",
        ]
    )
    assert exit_code == 1
    assert SCAFFOLD_ERROR_STDERR_PREFIX in capsys.readouterr().err
    assert not (tmp_path / BATCH_SPEC_FILENAME).exists()
