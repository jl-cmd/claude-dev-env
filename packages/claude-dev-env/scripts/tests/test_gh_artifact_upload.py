"""Behavioral tests for gh_artifact_upload.py using a stubbed GitHub CLI."""

from __future__ import annotations

import json
import shutil
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


_REAL_WHICH = shutil.which
_REAL_RUN = subprocess.run


@pytest.fixture(autouse=True)
def oxipng_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "oxipng")


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


def test_upload_artifact_sends_the_oxipng_shrunk_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_module = pytest.importorskip("PIL.Image")
    if _REAL_WHICH("oxipng") is None:
        pytest.skip("oxipng is not on PATH")
    monkeypatch.setattr(shutil, "which", _REAL_WHICH)
    source_file = tmp_path / "contact_sheet.png"
    image_module.new("RGB", (64, 64), (200, 40, 40)).save(
        source_file, format="PNG", compress_level=0
    )
    source_bytes = source_file.read_bytes()
    all_uploaded_sizes: list[int] = []
    gh_stub = _make_gh_stub([], view_return_code=0)

    def gh_stub_beside_live_oxipng(
        all_command_arguments: list[str], **keyword_arguments: object
    ) -> object:
        if all_command_arguments[0] != "gh":
            return _REAL_RUN(all_command_arguments, **keyword_arguments)
        if "upload" in all_command_arguments:
            staged_path = Path(all_command_arguments[4])
            all_uploaded_sizes.append(staged_path.stat().st_size)
            with image_module.open(staged_path) as uploaded:
                assert uploaded.convert("RGB").tobytes() == bytes((200, 40, 40)) * 4096
        return gh_stub(all_command_arguments, **keyword_arguments)

    monkeypatch.setattr(subprocess, "run", gh_stub_beside_live_oxipng)

    mod.upload_artifact(str(source_file), "owner/repo")

    assert all_uploaded_sizes and all_uploaded_sizes[0] < len(source_bytes)
    assert source_file.read_bytes() == source_bytes


def test_upload_artifact_refuses_a_png_when_oxipng_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "out.png"
    source_file.write_bytes(b"binary")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0))

    with pytest.raises(mod.ArtifactUploadError, match="oxipng"):
        mod.upload_artifact(str(source_file), "owner/repo")

    assert not any("upload" in call for call in recorded_calls)


def test_optimize_png_losslessly_leaves_other_formats_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "trace.zip"
    source_file.write_bytes(b"PK archive")
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(subprocess, "run", _make_gh_stub(recorded_calls, view_return_code=0))

    mod.optimize_png_losslessly(source_file)

    assert source_file.read_bytes() == b"PK archive"
    assert recorded_calls == []
