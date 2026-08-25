"""Behavior tests for atomic hook-state text replacement."""

import sys
from pathlib import Path

import pytest

_hooks_directory = str(Path(__file__).resolve().parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

import atomic_file_writer
from atomic_file_writer import write_text_atomically


def test_write_text_atomically_creates_parent_and_replaces_complete_text(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "state" / "cache.json"

    write_text_atomically(
        target_path,
        '{"complete": true}',
        encoding="utf-8",
        temporary_prefix=".cache-",
        temporary_suffix=".tmp",
        should_reap_orphans=False,
    )

    assert target_path.read_text(encoding="utf-8") == '{"complete": true}'


def test_write_text_atomically_preserves_target_and_cleans_temp_after_replace_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_path = tmp_path / "cache.json"
    target_path.write_text("stable", encoding="utf-8")

    def _raise_replace_error(source_path: object, destination_path: object) -> None:
        del source_path, destination_path
        raise OSError("replace failed")

    monkeypatch.setattr(atomic_file_writer.os, "replace", _raise_replace_error)

    with pytest.raises(OSError, match="replace failed"):
        write_text_atomically(
            target_path,
            "replacement",
            encoding="utf-8",
            temporary_prefix=".cache-",
            temporary_suffix=".tmp",
            should_reap_orphans=False,
        )

    assert target_path.read_text(encoding="utf-8") == "stable"
    assert list(tmp_path.glob(".cache-*.tmp")) == []


def test_write_text_atomically_reaps_orphans(tmp_path: Path) -> None:
    target_path = tmp_path / "cache.json"
    orphan_path = tmp_path / ".cache-orphan.tmp"
    orphan_path.write_text("orphan", encoding="utf-8")

    write_text_atomically(
        target_path,
        "replacement",
        encoding="utf-8",
        temporary_prefix=".cache-",
        temporary_suffix=".tmp",
        should_reap_orphans=True,
    )

    assert not orphan_path.exists()
