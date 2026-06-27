"""Tests for check_docstring_raises_unraisable_largezipfile — O6 Raises drift.

A function's docstring Raises clause lists ``zipfile.LargeZipFile`` while the
function opens its ``zipfile.ZipFile`` writer with ZIP64 permitted (``allowZip64``
left at its default of True). The stdlib raises ``LargeZipFile`` only when an
entry needs ZIP64 AND ``allowZip64`` is False; with ZIP64 permitted the writer
transparently uses it and never raises. The Raises entry therefore documents an
exception the body cannot produce — the deterministic slice of Category O6
docstring-prose-vs-implementation drift where a writer-opened-with-default-ZIP64
disagrees with a LargeZipFile Raises clause.
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


def check_docstring_raises_unraisable_largezipfile(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_raises_unraisable_largezipfile(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/stp_archive.py"
TEST_FILE_PATH = "/project/src/test_stp_archive.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _default_zip64_writer_documenting_largezipfile() -> str:
    return (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def rewrite_stp_member_atomically(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Rewrite one member of an STP in place via a temp sibling.\n'
        "\n"
        "    Raises:\n"
        "        OSError: When the streaming write or the rename fails.\n"
        "        zipfile.BadZipFile: When the source archive is not a valid ZIP.\n"
        "        zipfile.LargeZipFile: When an entry needs ZIP64 the writer forbids.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path, 'r') as source_archive:\n"
        "        with zipfile.ZipFile(stp_path, 'w', zipfile.ZIP_DEFLATED) as target_archive:\n"
        "            target_archive.writestr('IM/a.png', member_bytes)\n"
    )


def test_should_flag_largezipfile_over_a_default_zip64_writer() -> None:
    issues = check_docstring_raises_unraisable_largezipfile(
        _default_zip64_writer_documenting_largezipfile(), PRODUCTION_FILE_PATH
    )
    assert any("LargeZipFile" in each for each in issues), (
        f"A LargeZipFile Raises entry over a default-ZIP64 writer must flag, got: {issues!r}"
    )


def test_should_report_category_o6_in_the_message() -> None:
    issues = check_docstring_raises_unraisable_largezipfile(
        _default_zip64_writer_documenting_largezipfile(), PRODUCTION_FILE_PATH
    )
    assert any("O6" in each for each in issues), (
        f"Expected the Category O6 label in the message, got: {issues!r}"
    )


def test_should_not_flag_when_writer_forbids_zip64_via_keyword() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def rewrite(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Rewrite one member of an STP, forbidding ZIP64.\n'
        "\n"
        "    Raises:\n"
        "        zipfile.LargeZipFile: When an entry needs ZIP64 the writer forbids.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path, 'w', allowZip64=False) as target_archive:\n"
        "        target_archive.writestr('IM/a.png', member_bytes)\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A writer that forbids ZIP64 can raise LargeZipFile, so the clause is valid, got: {issues!r}"
    )


def test_should_not_flag_when_writer_forbids_zip64_positionally() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def rewrite(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Rewrite one member of an STP, forbidding ZIP64.\n'
        "\n"
        "    Raises:\n"
        "        zipfile.LargeZipFile: When an entry needs ZIP64 the writer forbids.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path, 'w', zipfile.ZIP_DEFLATED, False) as target_archive:\n"
        "        target_archive.writestr('IM/a.png', member_bytes)\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A positional allowZip64=False keeps the clause valid, got: {issues!r}"


def test_should_not_flag_when_function_opens_no_zip_writer() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def patch_via_helper(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Patch one member through a helper writer.\n'
        "\n"
        "    Raises:\n"
        "        zipfile.LargeZipFile: When the helper writer forbids ZIP64.\n"
        '    """\n'
        "    write_member(stp_path, member_bytes)\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"With no visible writer the exception may propagate from a callee, got: {issues!r}"
    )


def test_should_not_flag_read_only_open() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def read_member(stp_path: Path) -> bytes:\n"
        '    """Read one member of an STP.\n'
        "\n"
        "    Raises:\n"
        "        zipfile.LargeZipFile: When an entry needs ZIP64 the writer forbids.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path) as source_archive:\n"
        "        return source_archive.read('IM/a.png')\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A read-only open has no write-mode writer, so it is left alone, got: {issues!r}"
    )


def test_should_not_flag_when_raises_omits_largezipfile() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def rewrite(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Rewrite one member of an STP in place.\n'
        "\n"
        "    Raises:\n"
        "        OSError: When the streaming write or the rename fails.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path, 'w', zipfile.ZIP_DEFLATED) as target_archive:\n"
        "        target_archive.writestr('IM/a.png', member_bytes)\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A Raises clause without LargeZipFile must not flag, got: {issues!r}"


def test_should_flag_when_mode_passed_by_keyword() -> None:
    source = (
        "import zipfile\n"
        "from pathlib import Path\n"
        "\n"
        "def rewrite(stp_path: Path, member_bytes: bytes) -> None:\n"
        '    """Rewrite one member of an STP in place.\n'
        "\n"
        "    Raises:\n"
        "        zipfile.LargeZipFile: When an entry needs ZIP64 the writer forbids.\n"
        '    """\n'
        "    with zipfile.ZipFile(stp_path, mode='w') as target_archive:\n"
        "        target_archive.writestr('IM/a.png', member_bytes)\n"
    )
    issues = check_docstring_raises_unraisable_largezipfile(source, PRODUCTION_FILE_PATH)
    assert any("LargeZipFile" in each for each in issues), (
        f"A keyword mode='w' writer with default ZIP64 must flag, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    issues = check_docstring_raises_unraisable_largezipfile(
        _default_zip64_writer_documenting_largezipfile(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_raises_unraisable_largezipfile(
        _default_zip64_writer_documenting_largezipfile(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_raises_unraisable_largezipfile("def rewrite(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_largezipfile_drift() -> None:
    issues = validate_content(
        _default_zip64_writer_documenting_largezipfile(),
        PRODUCTION_FILE_PATH,
        old_content="",
    )
    matching_issues = [each for each in issues if "LargeZipFile" in each and "O6" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 LargeZipFile drift, got: {issues!r}"
    )
