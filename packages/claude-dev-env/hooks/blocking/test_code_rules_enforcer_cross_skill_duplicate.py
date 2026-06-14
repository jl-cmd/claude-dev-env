"""Tests for the cross-skill duplicate-helper advisory.

PR #233 on JonEcho/python-automation copied a Chrome-launch helper from the
``stp-recolor`` skill's ``scripts`` directory into the ``iconize-and-recolor-stp``
skill's ``scripts`` directory. The two skills install on their own, so a shared
module would couple them and break independent install; the copy is a defensible
skill-isolation tradeoff. ``advise_cross_skill_duplicate_helper`` surfaces that
copy as a non-blocking ``[CODE_RULES advisory]`` on stderr so a reviewer confirms
the copy was intentional, without denying the write.

The tests build a real ``skills/<name>/scripts`` layout on disk and run the
advisory against it, so they exercise the on-disk cross-skill scan rather than a
stubbed view of the filesystem.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys
import tempfile
from collections.abc import Iterator

import pytest

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_duplicate_body",
    _HOOK_DIRECTORY / "code_rules_duplicate_body.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
advise_cross_skill_duplicate_helper = _hook_module.advise_cross_skill_duplicate_helper


CHROME_HELPER_SOURCE = (
    "import winreg\n"
    "from pathlib import Path\n"
    "\n"
    "chrome_app_paths_key = r'SOFTWARE\\Microsoft\\App Paths\\chrome.exe'\n"
    "chrome_fallback_paths = ('C:/chrome.exe',)\n"
    "\n"
    "def _chrome_executable() -> Path | None:\n"
    "    for each_root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):\n"
    "        try:\n"
    "            registered = winreg.QueryValue(each_root, chrome_app_paths_key)\n"
    "        except OSError:\n"
    "            continue\n"
    "        registered_path = Path(registered)\n"
    "        if registered_path.exists():\n"
    "            return registered_path\n"
    "    for each_fallback in chrome_fallback_paths:\n"
    "        fallback_path = Path(each_fallback)\n"
    "        if fallback_path.exists():\n"
    "            return fallback_path\n"
    "    return None\n"
)


@pytest.fixture
def skills_root() -> Iterator[pathlib.Path]:
    base_directory = pathlib.Path(tempfile.mkdtemp())
    skills_directory = base_directory / "skills"
    skills_directory.mkdir()
    try:
        yield skills_directory
    finally:
        shutil.rmtree(base_directory, ignore_errors=False)


def _make_skill_scripts(skills_directory: pathlib.Path, skill_name: str) -> pathlib.Path:
    scripts_directory = skills_directory / skill_name / "scripts"
    scripts_directory.mkdir(parents=True)
    return scripts_directory


def test_advises_when_helper_copied_from_another_skill(
    skills_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_scripts = _make_skill_scripts(skills_root, "stp-recolor")
    (source_scripts / "palette_board.py").write_text(CHROME_HELPER_SOURCE, encoding="utf-8")
    target_scripts = _make_skill_scripts(skills_root, "iconize-and-recolor-stp")
    target_file = target_scripts / "combine_report.py"

    advise_cross_skill_duplicate_helper(CHROME_HELPER_SOURCE, str(target_file))

    captured = capsys.readouterr()
    assert "[CODE_RULES advisory]" in captured.err, (
        f"Expected a cross-skill advisory on stderr, got: {captured.err!r}"
    )
    assert "_chrome_executable" in captured.err, (
        f"Expected the duplicated function named, got: {captured.err!r}"
    )
    assert "stp-recolor" in captured.err, f"Expected the source skill named, got: {captured.err!r}"


def test_advisory_does_not_block(
    skills_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_scripts = _make_skill_scripts(skills_root, "stp-recolor")
    (source_scripts / "palette_board.py").write_text(CHROME_HELPER_SOURCE, encoding="utf-8")
    target_scripts = _make_skill_scripts(skills_root, "iconize-and-recolor-stp")
    target_file = target_scripts / "combine_report.py"

    returned = advise_cross_skill_duplicate_helper(CHROME_HELPER_SOURCE, str(target_file))

    assert returned is None, "The advisory returns nothing so it never enters the deny path"


def test_no_advisory_within_one_skill(
    skills_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts_directory = _make_skill_scripts(skills_root, "stp-recolor")
    (scripts_directory / "palette_board.py").write_text(CHROME_HELPER_SOURCE, encoding="utf-8")
    sibling_file = scripts_directory / "combine_report.py"

    advise_cross_skill_duplicate_helper(CHROME_HELPER_SOURCE, str(sibling_file))

    captured = capsys.readouterr()
    assert captured.err == "", (
        "Within one skill the blocking gate covers the copy; the cross-skill "
        f"advisory must stay silent, got: {captured.err!r}"
    )


def test_no_advisory_outside_a_skill_scripts_directory(
    skills_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_scripts = _make_skill_scripts(skills_root, "stp-recolor")
    (source_scripts / "palette_board.py").write_text(CHROME_HELPER_SOURCE, encoding="utf-8")
    non_skill_directory = skills_root.parent / "elsewhere"
    non_skill_directory.mkdir()
    target_file = non_skill_directory / "combine_report.py"

    advise_cross_skill_duplicate_helper(CHROME_HELPER_SOURCE, str(target_file))

    captured = capsys.readouterr()
    assert captured.err == "", (
        f"A file outside a skill scripts directory draws no advisory, got: {captured.err!r}"
    )
