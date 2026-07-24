"""Behavioral tests for the gate's empty-file-set loudness and inspected-count report.

Covers the three acceptance criteria of the loud-empty change:
- A run whose resolved file set is empty exits non-zero and says so; a set
  emptied only by the ``--only-under`` scope exits clean with the loud count.
- A run over new, untracked modules inspects them.
- Every run reports how many files it inspected.
"""

import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_gate.py"
    spec = importlib.util.spec_from_file_location(
        "code_rules_gate_empty_set_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate_module = _load_gate_module()


def _control_violation_module_content() -> str:
    """Return module content the enforcer must block.

    The control violation is a formatted-string logging call. The source
    fragment is assembled from pieces so this test file itself does not
    carry the flagged pattern.
    """
    formatted_call = "logger.info(" + 'f"announcing {name}")'
    return (
        '"""Fresh module with a logging violation."""\n'
        "import logging\n\n"
        'logger = logging.getLogger("fresh_violation")\n\n\n'
        "def announce(name: str) -> None:\n"
        f"    {formatted_call}\n"
    )


def run_git_in_repository(repository_root: Path, *arguments: str) -> str:
    completion = subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        env=gate_module.repository_environment(),
    )
    return completion.stdout


def initialize_git_repository(repository_root: Path) -> None:
    run_git_in_repository(repository_root, "init", "--initial-branch=main")
    run_git_in_repository(repository_root, "config", "user.email", "test@example.com")
    run_git_in_repository(repository_root, "config", "user.name", "Test")
    run_git_in_repository(repository_root, "config", "commit.gpgsign", "false")
    disabled_hooks_directory = repository_root / "disabled-git-hooks"
    disabled_hooks_directory.mkdir()
    run_git_in_repository(
        repository_root, "config", "core.hooksPath", str(disabled_hooks_directory)
    )


def commit_all_files(repository_root: Path, commit_message: str) -> None:
    run_git_in_repository(repository_root, "add", "-A")
    run_git_in_repository(repository_root, "commit", "-m", commit_message)


@pytest.fixture(autouse=True)
def isolated_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for each_variable_name in list(os.environ):
        if each_variable_name.startswith("GIT_"):
            monkeypatch.delenv(each_variable_name, raising=False)


@pytest.fixture()
def temporary_git_repository(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repository_under_test"
    repository_root.mkdir()
    initialize_git_repository(repository_root)
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    commit_all_files(repository_root, "seed commit")
    return repository_root


def test_diff_mode_with_empty_file_set_exits_non_zero_and_says_so(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """HEAD == base and nothing untracked: the gate refuses to vouch for nothing.

    A diff that resolves zero candidate files means the gate inspected
    nothing — a bad merge base or a wrong directory looks exactly like this.
    Issue #62's contract: that run exits non-zero and says so, because a
    silent pass over zero files is trusted like a real pass.
    """
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["--base", "HEAD"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "inspected 0 file(s)" in captured.err
    assert "empty" in captured.err.lower()


def test_diff_mode_changes_outside_only_under_prefixes_exit_clean_and_report(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Changes exist but none under the given prefixes: a scoped no-op exits 0.

    The candidate set is non-empty, so the gate's wiring is proven live; the
    ``--only-under`` scope legitimately excludes every candidate. That run
    reports the zero count loudly and exits clean, so scoped gate loops keep
    converging on branches whose changes sit outside the scoped tree.
    """
    (temporary_git_repository / "notes.txt").write_text("note\n", encoding="utf-8")
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["--base", "HEAD", "--only-under", "src"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "inspected 0 file(s)" in captured.err


def test_diff_mode_inspects_untracked_module_and_reports_count(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A brand-new untracked module joins the file set and is validated."""
    untracked_module = temporary_git_repository / "fresh_module.py"
    untracked_module.write_text(
        '"""Fresh module."""\n\n\ndef greet() -> str:\n    return "hello"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["--base", "HEAD"])

    captured = capsys.readouterr()
    assert "inspected 1 file(s)" in captured.err
    assert exit_code == 0


def test_diff_mode_blocks_violation_in_untracked_module(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An untracked module whose content the enforcer rejects fails the gate."""
    untracked_module = temporary_git_repository / "fresh_violation.py"
    untracked_module.write_text(
        _control_violation_module_content(),
        encoding="utf-8",
    )
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["--base", "HEAD"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "inspected 1 file(s)" in captured.err
    assert "fresh_violation.py" in captured.err


def test_explicit_paths_run_reports_inspected_count(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The count line appears on explicit-path runs too, so a caller always sees it."""
    module_path = temporary_git_repository / "explicit_module.py"
    module_path.write_text(
        '"""Explicit module."""\n\n\ndef ping() -> str:\n    return "pong"\n',
        encoding="utf-8",
    )
    commit_all_files(temporary_git_repository, "add explicit module")
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["explicit_module.py"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "inspected 1 file(s)" in captured.err


def test_staged_mode_with_nothing_staged_reports_zero_inspected(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Staged mode keeps its exit contract for an empty commit but names the count."""
    monkeypatch.chdir(temporary_git_repository)

    exit_code = gate_module.main(["--staged"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "inspected 0 file(s)" in captured.err


def test_untracked_paths_helper_lists_only_untracked_files(
    temporary_git_repository: Path,
) -> None:
    tracked_path = temporary_git_repository / "tracked.py"
    tracked_path.write_text('"""Tracked."""\n', encoding="utf-8")
    commit_all_files(temporary_git_repository, "add tracked module")
    untracked_path = temporary_git_repository / "untracked.py"
    untracked_path.write_text('"""Untracked."""\n', encoding="utf-8")

    resolved_paths = gate_module.paths_from_git_untracked(temporary_git_repository)

    resolved_names = {each_path.name for each_path in resolved_paths}
    assert "untracked.py" in resolved_names
    assert "tracked.py" not in resolved_names


def _gate_import_names_in_source(module_source: str) -> set[str]:
    """Collect the names a source file imports from ``code_rules_gate``.

    Args:
        module_source: Python source text to scan for the gate import block.

    Returns:
        The imported-name set from the ``from code_rules_gate import (...)``
        statement in the source, empty when no such block exists.
    """
    _, _, after_open = module_source.partition("from code_rules_gate import (")
    import_block, _, _ = after_open.partition(")")
    return {
        each_line.strip().rstrip(",")
        for each_line in import_block.splitlines()
        if each_line.strip() and not each_line.strip().startswith("#")
    }


def test_entry_exposes_every_symbol_the_preflight_hook_imports() -> None:
    """The gate entry re-exports the whole surface the spawn-preflight hook uses.

    The code-verifier spawn-preflight hook imports gate helpers by name at
    runtime; a name the entry drops breaks that hook's import and silently
    turns its deny paths into allows.
    """
    hook_path = (
        Path(__file__).resolve().parents[4]
        / "hooks"
        / "blocking"
        / "code_verifier_spawn_preflight_gate.py"
    )
    hook_imported_names = _gate_import_names_in_source(
        hook_path.read_text(encoding="utf-8")
    )

    assert hook_imported_names, "hook no longer imports from code_rules_gate"
    missing_names = sorted(
        each_name
        for each_name in hook_imported_names
        if not hasattr(gate_module, each_name)
    )
    assert not missing_names, f"gate entry drops hook imports: {missing_names}"
