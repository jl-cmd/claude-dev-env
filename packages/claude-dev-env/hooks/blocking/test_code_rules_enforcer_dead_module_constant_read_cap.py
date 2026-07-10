from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)


def _strip_read_only_and_retry(
    removal_function: Callable[[str], object],
    target_path: str,
    _exc_info: BaseException,
) -> None:
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


@pytest.fixture
def neutral_root() -> Iterator[Path]:
    """Yield a temp directory whose path carries no ``test_`` segment.

    ::

        tmp_path (pytest default)  -> embeds "test_..." in its name
                                        -> is_test_file() misreads every
                                           synthetic constants path
        mkdtemp(prefix="deadconst-") -> no "test_" segment
                                        -> reads as a production path  ok

    A ``.git`` marker is planted at the root so the cross-tree widening
    resolves the repository root to this synthetic tree.
    """
    neutral_directory = Path(tempfile.mkdtemp(prefix="deadconst-")).resolve()
    (neutral_directory / ".git").mkdir()
    try:
        yield neutral_directory
    finally:
        shutil.rmtree(neutral_directory, onexc=_strip_read_only_and_retry)


def _check(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_module_constants(source, file_path)


def _write_noise_modules(directory: Path, count: int) -> None:
    directory.mkdir(parents=True)
    for each_index in range(count):
        (directory / f"mod_{each_index}.py").write_text(
            "def noop() -> int:\n    return 1\n", encoding="utf-8"
        )


def test_widened_scan_bounds_total_disk_reads_on_noncandidate_flood(
    neutral_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-attempt cap stops the widened pass from reading every sibling.

    ::

        MAX_SCAN_ROOT_READ_COUNT = 3, 50 non-candidate noise files
        ok:   read_text() called a bounded number of times   (< 50)
        flag: read_text() called once per noise file          (== 50)

    Without the cap, ``_read_candidate_source`` opens and reads every
    repository ``.py`` file's full text before testing it for the module
    stem, so disk-read cost scales with repository size regardless of how
    quickly the file cap would otherwise stop the parse-and-collect work.
    """
    monkeypatch.setattr("code_rules_dead_module_constant.MAX_SCAN_ROOT_READ_COUNT", 3)
    package_directory = neutral_root / "pkg"
    package_directory.mkdir(parents=True)
    constants_body = 'DEAD_EXPORTED = "x"\n__all__ = ["DEAD_EXPORTED"]\n'
    constants_path = package_directory / "settings_constants.py"
    constants_path.write_text(constants_body, encoding="utf-8")
    _write_noise_modules(neutral_root / "noise", 50)
    read_count = 0
    original_read_text = Path.read_text

    def counting_read_text(self: Path, *positional: object, **keyword: object) -> str:
        nonlocal read_count
        read_count += 1
        return original_read_text(self, *positional, **keyword)  # type: ignore[arg-type]  # forwards positional/keyword args mypy cannot resolve

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    _check(constants_body, str(constants_path))
    assert read_count < 50, (
        "A read-count cap must stop the widened pass from reading every "
        f"non-candidate sibling's full text, got {read_count} reads across 50 noise files"
    )
