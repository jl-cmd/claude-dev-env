"""Behavioral tests for gh_artifact_upload.py using a stubbed GitHub CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import gh_artifact_upload as mod

_DEFAULT_READBACK_ASSET = {
    "name": "20260707_140233_contact_sheet.png",
    "url": (
        "https://github.com/owner/repo/releases/download/artifacts/"
        "20260707_140233_contact_sheet.png"
    ),
    "createdAt": "2026-07-07T14:02:33Z",
}


def _make_gh_stub(
    recorded_calls: list[list[str]],
    view_return_code: int,
    all_readback_assets: list[dict[str, str]] | None = None,
) -> object:
    readback_assets = (
        [_DEFAULT_READBACK_ASSET] if all_readback_assets is None else all_readback_assets
    )

    def fake_run(
        all_command_arguments: list[str],
        **_keyword_arguments: object,
    ) -> types.SimpleNamespace:
        recorded_calls.append(all_command_arguments)
        is_release_view = "view" in all_command_arguments
        is_asset_read_back = is_release_view and "assets" in all_command_arguments
        if is_asset_read_back:
            return types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"assets": readback_assets}),
                stderr="",
            )
        return_code = view_return_code if is_release_view else 0
        return types.SimpleNamespace(returncode=return_code, stdout="", stderr="")

    return fake_run


def test_timestamped_asset_name_prefixes_basename() -> None:
    asset_name = mod.timestamped_asset_name(r"C:\stage\contact_sheet.png")
    assert asset_name.endswith("_contact_sheet.png")
    assert len(asset_name) > len("_contact_sheet.png")


def test_upload_artifact_returns_the_readback_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "contact_sheet.png"
    source_file.write_bytes(b"binary")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0)
    )

    asset_url = mod.upload_artifact(str(source_file), "owner/repo")

    assert asset_url == _DEFAULT_READBACK_ASSET["url"]
    assert any("assets" in call for call in recorded_calls)


def test_upload_artifact_prints_the_sanitized_url_github_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "My Report.png"
    source_file.write_bytes(b"binary")
    sanitized_asset = {
        "name": "20260707_140233_My.Report.png",
        "url": (
            "https://github.com/owner/repo/releases/download/artifacts/"
            "20260707_140233_My.Report.png"
        ),
        "createdAt": "2026-07-07T14:02:33Z",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_stub([], view_return_code=0, all_readback_assets=[sanitized_asset]),
    )

    asset_url = mod.upload_artifact(str(source_file), "owner/repo")

    assert asset_url == sanitized_asset["url"]
    assert " " not in asset_url


def test_upload_artifact_returns_the_newest_asset_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "out.png"
    source_file.write_bytes(b"binary")
    older_asset = {
        "name": "20260707_140000_out.png",
        "url": "https://github.com/owner/repo/releases/download/artifacts/old.png",
        "createdAt": "2026-07-07T14:00:00Z",
    }
    newest_asset = {
        "name": "20260707_140233_out.png",
        "url": "https://github.com/owner/repo/releases/download/artifacts/new.png",
        "createdAt": "2026-07-07T14:02:33Z",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_stub(
            [], view_return_code=0, all_readback_assets=[older_asset, newest_asset]
        ),
    )

    asset_url = mod.upload_artifact(str(source_file), "owner/repo")

    assert asset_url == newest_asset["url"]


def test_upload_artifact_raises_when_asset_missing_on_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "out.png"
    source_file.write_bytes(b"binary")
    monkeypatch.setattr(
        subprocess, "run", _make_gh_stub([], view_return_code=0, all_readback_assets=[])
    )

    with pytest.raises(mod.ArtifactUploadError):
        mod.upload_artifact(str(source_file), "owner/repo")


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
