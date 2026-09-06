from __future__ import annotations

import io
from pathlib import Path

import pytest
import verification_notice


def _record_notice_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[io.StringIO, list[object]]:
    notice_context = object()
    all_started_contexts: list[object] = []
    monkeypatch.setattr(
        verification_notice,
        "_load_notice_context",
        lambda event, repository: notice_context,
    )
    monkeypatch.setattr(
        verification_notice,
        "build_verification_notice",
        lambda context: "notice\n",
    )
    monkeypatch.setattr(
        verification_notice,
        "start_automatic_advisory",
        all_started_contexts.append,
    )
    return io.StringIO(), all_started_contexts


def test_notice_only_prints_without_starting_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    standard_output, all_started_contexts = _record_notice_execution(monkeypatch)

    exit_code = verification_notice.main(
        ["--event", "commit", "--notice-only", "--repo", str(tmp_path)],
        stdout=standard_output,
    )

    assert exit_code == 0
    assert standard_output.getvalue() == "notice\n"
    assert all_started_contexts == []


def test_default_notice_prints_and_starts_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    standard_output, all_started_contexts = _record_notice_execution(monkeypatch)

    exit_code = verification_notice.main(
        ["--event", "commit", "--repo", str(tmp_path)],
        stdout=standard_output,
    )

    assert exit_code == 0
    assert standard_output.getvalue() == "notice\n"
    assert len(all_started_contexts) == 1
