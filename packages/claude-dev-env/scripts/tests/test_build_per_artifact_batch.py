"""Behavioral tests for build_per_artifact_batch.py against the real consumer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_per_artifact_batch as mod
import spawn_grok_batch as batch_mod
from dev_env_scripts_constants.grok_worker_constants import (
    TOOL_PROFILE_BUILD,
    UTF8_ENCODING,
)


def _write_text(path: Path, body: str = "body\n") -> Path:
    path.write_text(body, encoding=UTF8_ENCODING)
    return path


def test_build_round_trips_through_load_batch_spec(tmp_path: Path) -> None:
    brief_path = _write_text(tmp_path / "brief.md", "# brief\n")
    evidence_a = _write_text(tmp_path / "evidence-a.md", "facts a\n")
    evidence_b = _write_text(tmp_path / "evidence-b.md", "facts b\n")
    work_cwd = tmp_path / "worktree"
    work_cwd.mkdir()
    out_path = tmp_path / "batch.json"

    batch_spec = mod.build_per_artifact_batch(
        brief_path=brief_path,
        all_artifacts=[
            ("artifact-a", evidence_a),
            ("artifact-b", evidence_b),
        ],
        cwd=work_cwd,
    )
    out_path.write_text(
        json.dumps(batch_spec, indent=2) + "\n",
        encoding=UTF8_ENCODING,
    )

    loaded = batch_mod.load_batch_spec(out_path)

    assert len(loaded.all_workers) == 2
    first_worker, second_worker = loaded.all_workers
    assert first_worker.role_name == "artifact-a"
    assert second_worker.role_name == "artifact-b"
    assert first_worker.tool_profile == TOOL_PROFILE_BUILD
    assert second_worker.tool_profile == TOOL_PROFILE_BUILD
    assert first_worker.all_prompt_part_paths == (
        brief_path.resolve(),
        evidence_a.resolve(),
    )
    assert second_worker.all_prompt_part_paths == (
        brief_path.resolve(),
        evidence_b.resolve(),
    )
    assert first_worker.working_directory == work_cwd.resolve()
    assert second_worker.working_directory == work_cwd.resolve()


def test_build_is_deterministic(tmp_path: Path) -> None:
    brief_path = _write_text(tmp_path / "brief.md")
    evidence_a = _write_text(tmp_path / "a.md")
    evidence_b = _write_text(tmp_path / "b.md")
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()
    shared_kwargs = {
        "brief_path": brief_path,
        "all_artifacts": [("a", evidence_a), ("b", evidence_b)],
        "cwd": work_cwd,
    }

    first_build = mod.build_per_artifact_batch(**shared_kwargs)
    second_build = mod.build_per_artifact_batch(**shared_kwargs)

    assert first_build == second_build


def test_missing_evidence_raises_batch_build_error(tmp_path: Path) -> None:
    brief_path = _write_text(tmp_path / "brief.md")
    missing_evidence = tmp_path / "missing.md"
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()

    with pytest.raises(mod.BatchBuildError):
        mod.build_per_artifact_batch(
            brief_path=brief_path,
            all_artifacts=[("gone", missing_evidence)],
            cwd=work_cwd,
        )


def test_empty_artifacts_raises_batch_build_error(tmp_path: Path) -> None:
    brief_path = _write_text(tmp_path / "brief.md")
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()

    with pytest.raises(mod.BatchBuildError):
        mod.build_per_artifact_batch(
            brief_path=brief_path,
            all_artifacts=[],
            cwd=work_cwd,
        )


def test_cli_writes_out_file_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    brief_path = _write_text(tmp_path / "brief.md")
    evidence_path = _write_text(tmp_path / "evidence.md")
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()
    out_path = tmp_path / "out" / "batch.json"

    exit_code = mod.main(
        [
            "--brief",
            str(brief_path),
            "--cwd",
            str(work_cwd),
            "--out",
            str(out_path),
            "--artifact",
            f"one={evidence_path}",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert out_path.is_file()
    assert str(out_path.resolve()) in captured.out
    loaded = batch_mod.load_batch_spec(out_path)
    assert len(loaded.all_workers) == 1
    assert loaded.all_workers[0].role_name == "one"


def test_cli_returns_one_when_evidence_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    brief_path = _write_text(tmp_path / "brief.md")
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()
    missing_evidence = tmp_path / "no-such.md"

    exit_code = mod.main(
        [
            "--brief",
            str(brief_path),
            "--cwd",
            str(work_cwd),
            "--artifact",
            f"broken={missing_evidence}",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err
