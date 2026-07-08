"""Behavioral tests for gh_artifact_upload.py using a stubbed GitHub CLI."""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import gh_artifact_upload as mod


def _make_gh_stub(recorded_calls: list[list[str]], view_return_code: int) -> object:
    def fake_run(
        all_command_arguments: list[str],
        **_keyword_arguments: object,
    ) -> types.SimpleNamespace:
        recorded_calls.append(all_command_arguments)
        is_release_view = "view" in all_command_arguments
        return_code = view_return_code if is_release_view else 0
        return types.SimpleNamespace(returncode=return_code, stdout="", stderr="")

    return fake_run


def test_timestamped_asset_name_prefixes_basename() -> None:
    asset_name = mod.timestamped_asset_name(r"C:\stage\contact_sheet.png")
    assert asset_name.endswith("_contact_sheet.png")
    assert len(asset_name) > len("_contact_sheet.png")


def test_build_asset_url_uses_release_tag() -> None:
    asset_url = mod.build_asset_url("owner/repo", "20260707_140233_sheet.png")
    assert asset_url == (
        "https://github.com/owner/repo/releases/download/artifacts/20260707_140233_sheet.png"
    )


def test_upload_artifact_returns_permanent_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "contact_sheet.png"
    source_file.write_bytes(b"binary")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0)
    )

    asset_url = mod.upload_artifact(str(source_file), "owner/repo")

    assert asset_url.startswith(
        "https://github.com/owner/repo/releases/download/artifacts/"
    )
    assert asset_url.endswith("_contact_sheet.png")


def test_upload_artifact_uploads_to_tag_without_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "out.png"
    source_file.write_bytes(b"binary")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0)
    )

    mod.upload_artifact(str(source_file), "owner/repo")

    upload_call = next(call for call in recorded_calls if "upload" in call)
    assert "artifacts" in upload_call
    assert "--clobber" not in upload_call


def test_upload_artifact_creates_release_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "out.png"
    source_file.write_bytes(b"binary")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=1)
    )

    mod.upload_artifact(str(source_file), "owner/repo")

    assert any("create" in call for call in recorded_calls)


def test_artifacts_release_exists_true_when_view_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _make_gh_stub([], view_return_code=0))
    assert mod.artifacts_release_exists("owner/repo") is True


def test_artifacts_release_exists_false_when_view_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _make_gh_stub([], view_return_code=1))
    assert mod.artifacts_release_exists("owner/repo") is False


def test_ensure_artifacts_release_skips_create_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0)
    )
    mod.ensure_artifacts_release("owner/repo")
    assert not any("create" in call for call in recorded_calls)


def test_upload_artifact_missing_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _make_gh_stub([], view_return_code=0))
    with pytest.raises(mod.ArtifactUploadError):
        mod.upload_artifact("does_not_exist_9f3a.png", "owner/repo")
