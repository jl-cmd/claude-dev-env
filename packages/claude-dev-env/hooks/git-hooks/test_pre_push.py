from __future__ import annotations

import importlib
import io
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
_git_hooks_directory_string = str(SCRIPT_DIRECTORY)
while _git_hooks_directory_string in sys.path:
    sys.path.remove(_git_hooks_directory_string)
sys.path.insert(0, _git_hooks_directory_string)
for each_module_name in list(sys.modules):
    if each_module_name == "config" or each_module_name.startswith("config."):
        del sys.modules[each_module_name]
importlib.invalidate_caches()

import pre_push
import git_hooks_constants


ALL_ZEROS_OBJECT_NAME: str = "0" * 40
NON_ZERO_LOCAL_SHA: str = "a" * 40
NON_ZERO_REMOTE_SHA_ONE: str = "1" * 40
NON_ZERO_REMOTE_SHA_TWO: str = "2" * 40


def _isolate_code_review_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CODE_REVIEW_PUSH_GATE_PATH", str(tmp_path / "no_code_review_gate.py")
    )


def test_resolve_base_reference_uses_remote_object_when_non_zero() -> None:
    stdin_text = (
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == NON_ZERO_REMOTE_SHA_ONE


def test_resolve_base_reference_falls_back_when_remote_is_all_zeros() -> None:
    stdin_text = f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_falls_back_when_stdin_empty() -> None:
    base_reference = pre_push.resolve_base_reference_from_stdin("")

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_prefers_first_non_zero_remote_object_among_many() -> (
    None
):
    stdin_text = (
        f"refs/heads/new_branch {ALL_ZEROS_OBJECT_NAME} refs/heads/new_branch {ALL_ZEROS_OBJECT_NAME}\n"
        f"refs/heads/existing {NON_ZERO_LOCAL_SHA} refs/heads/existing {NON_ZERO_REMOTE_SHA_TWO}\n"
    )

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == NON_ZERO_REMOTE_SHA_TWO


def test_main_exits_zero_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_invokes_gate_with_resolved_base_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_arguments_path = tmp_path / "recorded_arguments.txt"
    recording_gate_script_path = tmp_path / "recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    remote_sha = "9" * 40
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {remote_sha}\n"),
    )

    exit_code = pre_push.main()

    assert exit_code == 0
    assert recorded_arguments_path.exists(), (
        f"recording gate did not write to {recorded_arguments_path}"
    )
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--base", remote_sha]


def test_main_propagates_blocking_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocking_gate_script_path = tmp_path / "blocking_gate.py"
    blocking_gate_script_path.write_text(
        "import sys\nsys.exit(1)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(blocking_gate_script_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 1


def test_main_propagates_infrastructure_failure_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    infrastructure_failure_gate_path = tmp_path / "infrastructure_failure_gate.py"
    infrastructure_failure_gate_path.write_text(
        "import sys\nsys.exit(2)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(infrastructure_failure_gate_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 2


def test_main_exits_two_when_stdin_raises_ioerror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))

    class RaisingStdin:
        def read(self) -> str:
            raise IOError("broken pipe")

    monkeypatch.setattr(sys, "stdin", RaisingStdin())

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_main_exits_two_when_invoke_gate_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_resolve_base_reference_emits_warning_for_malformed_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_stdin_text = "only_one_field\n"

    pre_push.resolve_base_reference_from_stdin(malformed_stdin_text)

    captured = capsys.readouterr()
    assert "malformed" in captured.err


def test_resolve_base_reference_returns_none_when_local_sha_is_all_zeros() -> None:
    stdin_text = f"refs/heads/feature {ALL_ZEROS_OBJECT_NAME} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference is None


def test_main_exits_zero_immediately_when_push_is_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))
    deletion_stdin = f"refs/heads/feature {ALL_ZEROS_OBJECT_NAME} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(deletion_stdin))

    exit_code = pre_push.main()

    assert exit_code == 0


def test_resolve_base_reference_returns_sentinel_when_only_malformed_lines_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_only_stdin = "one_field_only\nalso_malformed\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(malformed_only_stdin)

    assert base_reference == git_hooks_constants.NO_PARSEABLE_STDIN_LINES_SENTINEL


def test_main_prints_stderr_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    pre_push.main()

    captured = capsys.readouterr()
    assert captured.err != ""


def test_resolve_base_reference_exits_two_when_only_malformed_lines_and_no_valid_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_only_stdin = "one_field_only\nalso_malformed\n"

    result = pre_push.resolve_base_reference_from_stdin(malformed_only_stdin)

    assert result == git_hooks_constants.NO_PARSEABLE_STDIN_LINES_SENTINEL


def test_main_exits_two_when_all_stdin_lines_are_malformed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO("one_field_only\nalso_malformed\n"))

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    captured = capsys.readouterr()
    assert "no parseable stdin lines" in captured.err


def test_invoke_gate_returns_infrastructure_failure_when_strict_resolve_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    original_resolve = Path.resolve

    def raising_resolve(self: Path, strict: bool = False) -> Path:
        if strict and self == gate_path.resolve():
            raise FileNotFoundError("not found")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", raising_resolve)

    exit_code = pre_push.invoke_gate(gate_path, "origin/main")

    assert exit_code == 2


def test_invoke_gate_uses_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_gate_dir = tmp_path / "real"
    real_gate_dir.mkdir()
    real_gate_path = real_gate_dir / "gate.py"
    recorded_path_file = tmp_path / "recorded_path.txt"
    real_gate_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_path_file}").write_text(sys.argv[0], encoding="utf-8")\n'
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    symlink_gate_path = tmp_path / "link_gate.py"
    symlink_gate_path.symlink_to(real_gate_path)
    resolved_path = symlink_gate_path.resolve()
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(symlink_gate_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
    ))

    exit_code = pre_push.main()

    assert exit_code == 0
    executed_path = recorded_path_file.read_text(encoding="utf-8")
    assert executed_path == str(resolved_path)


def test_find_protected_branch_push_violation_flags_feature_branch_to_main() -> None:
    stdin_text = (
        f"refs/heads/feat/example {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    violation = pre_push.find_protected_branch_push_violation(stdin_text)

    assert violation == ("feat/example", "main")


def test_find_protected_branch_push_violation_flags_feature_branch_to_master() -> None:
    stdin_text = (
        f"refs/heads/topic {NON_ZERO_LOCAL_SHA} refs/heads/master {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    violation = pre_push.find_protected_branch_push_violation(stdin_text)

    assert violation == ("topic", "master")


def test_find_protected_branch_push_violation_allows_main_onto_main() -> None:
    stdin_text = (
        f"refs/heads/main {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    violation = pre_push.find_protected_branch_push_violation(stdin_text)

    assert violation is None


def test_find_protected_branch_push_violation_allows_feature_onto_own_ref() -> None:
    stdin_text = (
        f"refs/heads/feat/example {NON_ZERO_LOCAL_SHA} refs/heads/feat/example {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    violation = pre_push.find_protected_branch_push_violation(stdin_text)

    assert violation is None


def test_find_protected_branch_push_violation_ignores_deletion_of_main() -> None:
    stdin_text = (
        f"(delete) {ALL_ZEROS_OBJECT_NAME} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    violation = pre_push.find_protected_branch_push_violation(stdin_text)

    assert violation is None


def test_main_blocks_feature_branch_push_onto_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    passing_gate_path = tmp_path / "gate.py"
    passing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(passing_gate_path))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/feat/example {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE
    captured = capsys.readouterr()
    assert "feat/example" in captured.err
    assert "main" in captured.err


def test_main_blocks_protected_push_even_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/feat/example {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE
    captured = capsys.readouterr()
    assert "feat/example" in captured.err


def test_main_allows_main_onto_main_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passing_gate_path = tmp_path / "gate.py"
    passing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(passing_gate_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/main {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


CODE_REVIEW_STUB_BLOCK_REASON: str = "CODE_REVIEW_STUB_BLOCK_REASON"


def _write_passing_code_rules_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    passing_gate_path = tmp_path / "code_rules_gate.py"
    passing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(passing_gate_path))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )


def _write_code_review_gate_stub(tmp_path: Path, returned_reason_literal: str) -> Path:
    stub_gate_path = tmp_path / "code_review_push_gate.py"
    stub_gate_path.write_text(
        "def deny_reason_for_directory(target_directory):\n"
        f"    return {returned_reason_literal}\n",
        encoding="utf-8",
    )
    return stub_gate_path


def test_main_blocks_when_code_review_gate_returns_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_passing_code_rules_gate(tmp_path, monkeypatch)
    stub_gate_path = _write_code_review_gate_stub(
        tmp_path, repr(CODE_REVIEW_STUB_BLOCK_REASON)
    )
    monkeypatch.setenv("CODE_REVIEW_PUSH_GATE_PATH", str(stub_gate_path))

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.CODE_REVIEW_STAMP_BLOCK_EXIT_CODE
    captured = capsys.readouterr()
    assert CODE_REVIEW_STUB_BLOCK_REASON in captured.err


def test_main_allows_when_code_review_gate_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_passing_code_rules_gate(tmp_path, monkeypatch)
    stub_gate_path = _write_code_review_gate_stub(tmp_path, "None")
    monkeypatch.setenv("CODE_REVIEW_PUSH_GATE_PATH", str(stub_gate_path))

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_code_review_check_fails_open_when_gate_module_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_passing_code_rules_gate(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "CODE_REVIEW_PUSH_GATE_PATH", str(tmp_path / "does_not_exist.py")
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_allows_deletion_push_even_when_code_review_gate_would_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passing_gate_path = tmp_path / "code_rules_gate.py"
    passing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(passing_gate_path))
    stub_gate_path = _write_code_review_gate_stub(
        tmp_path, repr(CODE_REVIEW_STUB_BLOCK_REASON)
    )
    monkeypatch.setenv("CODE_REVIEW_PUSH_GATE_PATH", str(stub_gate_path))
    deletion_stdin = (
        f"refs/heads/feature {ALL_ZEROS_OBJECT_NAME} "
        f"refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(deletion_stdin))

    exit_code = pre_push.main()

    assert exit_code == 0


DEFAULT_BRANCH_NAME: str = "main"
FEATURE_BRANCH_NAME: str = "feature/example"
UNPROTECTED_DEFAULT_BRANCH_NAME: str = "develop"
ORIGIN_DEFAULT_BRANCH_REFERENCE: str = (
    git_hooks_constants.ORIGIN_REMOTE_TRACKING_REFERENCE_PREFIX + DEFAULT_BRANCH_NAME
)
ORIGIN_UNPROTECTED_DEFAULT_BRANCH_REFERENCE: str = (
    git_hooks_constants.ORIGIN_REMOTE_TRACKING_REFERENCE_PREFIX
    + UNPROTECTED_DEFAULT_BRANCH_NAME
)
ORIGIN_HEAD_REFERENCE: str = git_hooks_constants.ORIGIN_HEAD_SYMBOLIC_REFERENCE
LOCAL_ALIAS_BRANCH_NAME: str = "release-candidate"
TOPIC_REMOTE_BRANCH_NAME: str = "topic-x"
BASE_FILE_NAME: str = "README.md"
FLAGGED_FILE_NAME: str = "flagged_module.py"
BRANCH_FILE_NAME: str = "branch_module.py"
DEFAULT_BRANCH_FILE_NAME: str = "default_branch_module.py"
ALL_FIXTURE_GIT_FLAGS: tuple[str, ...] = (
    "-c",
    "user.name=hooks-test",
    "-c",
    "user.email=hooks-test@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=absent_fixture_hooks",
)
FIXTURE_GIT_TIMEOUT_SECONDS: int = 60


def _run_fixture_git(repository: Path, *all_arguments: str) -> str:
    """Run one git command inside a fixture repository, isolated from user hooks."""
    completion = subprocess.run(
        ["git", *ALL_FIXTURE_GIT_FLAGS, *all_arguments],
        cwd=str(repository),
        capture_output=True,
        text=True,
        check=True,
        timeout=FIXTURE_GIT_TIMEOUT_SECONDS,
    )
    return completion.stdout.strip()


def _commit_file(repository: Path, file_name: str) -> str:
    """Write and commit one file, returning the resulting commit object name."""
    (repository / file_name).write_text(f"body of {file_name}\n", encoding="utf-8")
    _run_fixture_git(repository, "add", file_name)
    _run_fixture_git(repository, "commit", "-m", f"add {file_name}")
    return _run_fixture_git(repository, "rev-parse", "HEAD")


def _set_origin_default_branch_tip(
    repository: Path, default_branch_reference: str, default_branch_tip: str
) -> None:
    """Point an origin default-branch remote-tracking ref at a commit."""
    _run_fixture_git(
        repository, "update-ref", default_branch_reference, default_branch_tip
    )


def _set_origin_head(repository: Path, default_branch_reference: str) -> None:
    """Point the origin HEAD symbolic ref at an origin default-branch ref."""
    _run_fixture_git(
        repository, "symbolic-ref", ORIGIN_HEAD_REFERENCE, default_branch_reference
    )


def _push_stdin_line(
    local_branch_name: str,
    pushed_object_name: str,
    remote_branch_name: str,
    remote_object_name: str,
) -> str:
    """Build the pre-push stdin line git writes for one branch update."""
    return (
        f"refs/heads/{local_branch_name} {pushed_object_name} "
        f"refs/heads/{remote_branch_name} {remote_object_name}\n"
    )


def _build_rebased_branch_repository(
    tmp_path: Path, default_branch_file_name: str, branch_file_name: str
) -> tuple[Path, str, str]:
    """Build a repository whose feature branch sits rebased onto an advanced main.

    Args:
        tmp_path: The pytest temporary directory the repository is built in.
        default_branch_file_name: File the default branch gains after the branch forks.
        branch_file_name: File the feature branch adds.

    Returns:
        The repository path, the rebased branch tip, and the pre-rebase tip the
        remote still holds. The origin HEAD symbolic ref stays unset.
    """
    repository = tmp_path / "rebased_branch_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    _commit_file(repository, BASE_FILE_NAME)
    _run_fixture_git(repository, "checkout", "-b", FEATURE_BRANCH_NAME)
    pre_rebase_tip = _commit_file(repository, branch_file_name)
    _run_fixture_git(repository, "checkout", DEFAULT_BRANCH_NAME)
    _set_origin_default_branch_tip(
        repository,
        ORIGIN_DEFAULT_BRANCH_REFERENCE,
        _commit_file(repository, default_branch_file_name),
    )
    _run_fixture_git(repository, "checkout", FEATURE_BRANCH_NAME)
    _run_fixture_git(repository, "rebase", DEFAULT_BRANCH_NAME)
    return repository, _run_fixture_git(repository, "rev-parse", "HEAD"), pre_rebase_tip


def _write_diff_scoped_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a gate that flags the marker file when it sits in the base..HEAD diff."""
    gate_script_path = tmp_path / "diff_scoped_gate.py"
    gate_script_path.write_text(
        "import subprocess\n"
        "import sys\n"
        "base_reference = sys.argv[2]\n"
        "merge_base = subprocess.run(\n"
        "    ['git', 'merge-base', 'HEAD', base_reference],\n"
        "    capture_output=True, text=True, check=True,\n"
        ").stdout.strip()\n"
        "all_changed_names = subprocess.run(\n"
        "    ['git', 'diff', '--name-only', merge_base, 'HEAD'],\n"
        "    capture_output=True, text=True, check=True,\n"
        ").stdout.split()\n"
        f"sys.exit(1 if {FLAGGED_FILE_NAME!r} in all_changed_names else 0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_script_path))


def _build_default_branch_repository(tmp_path: Path) -> tuple[Path, str, str]:
    """Build a repository with an origin default branch and a topic branch off it.

    Args:
        tmp_path: The pytest temporary directory the repository is built in.

    Returns:
        The repository path, the default branch tip, and the topic branch tip.
    """
    repository = tmp_path / "default_branch_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    _commit_file(repository, BASE_FILE_NAME)
    default_branch_tip = _commit_file(repository, DEFAULT_BRANCH_FILE_NAME)
    _run_fixture_git(repository, "checkout", "-b", FEATURE_BRANCH_NAME)
    topic_branch_tip = _commit_file(repository, BRANCH_FILE_NAME)
    _set_origin_default_branch_tip(
        repository, ORIGIN_DEFAULT_BRANCH_REFERENCE, default_branch_tip
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    return repository, default_branch_tip, topic_branch_tip


def _same_branch_push_line(
    local_object_name: str, remote_object_name: str
) -> pre_push.PushLine:
    """Build a PushLine whose local and remote refs name the same branch."""
    return pre_push.PushLine(
        local_branch_name=FEATURE_BRANCH_NAME,
        local_object_name=local_object_name,
        remote_branch_name=FEATURE_BRANCH_NAME,
        remote_object_name=remote_object_name,
    )


def test_parse_push_line_reads_both_branch_names_and_both_object_names() -> None:
    parsed_line = pre_push.parse_push_line(
        f"refs/heads/{FEATURE_BRANCH_NAME} {NON_ZERO_LOCAL_SHA} "
        f"refs/heads/{DEFAULT_BRANCH_NAME} {NON_ZERO_REMOTE_SHA_ONE}"
    )

    assert parsed_line == pre_push.PushLine(
        local_branch_name=FEATURE_BRANCH_NAME,
        local_object_name=NON_ZERO_LOCAL_SHA,
        remote_branch_name=DEFAULT_BRANCH_NAME,
        remote_object_name=NON_ZERO_REMOTE_SHA_ONE,
    )


def test_parse_push_line_returns_none_for_a_line_missing_fields() -> None:
    assert pre_push.parse_push_line("refs/heads/feature one_more_field") is None


def test_is_branch_update_separates_updates_from_deletions_and_new_branches() -> None:
    assert pre_push.is_branch_update(
        _same_branch_push_line(NON_ZERO_LOCAL_SHA, NON_ZERO_REMOTE_SHA_ONE)
    )
    assert not pre_push.is_branch_update(
        _same_branch_push_line(ALL_ZEROS_OBJECT_NAME, NON_ZERO_REMOTE_SHA_ONE)
    )
    assert not pre_push.is_branch_update(
        _same_branch_push_line(NON_ZERO_LOCAL_SHA, ALL_ZEROS_OBJECT_NAME)
    )


def test_run_git_reference_query_returns_stdout_for_a_resolvable_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, default_branch_tip, _topic_branch_tip = _build_default_branch_repository(
        tmp_path
    )
    monkeypatch.chdir(repository)

    resolved_object_name = pre_push.run_git_reference_query(
        ("git", "rev-parse", ORIGIN_DEFAULT_BRANCH_REFERENCE)
    )

    assert resolved_object_name == default_branch_tip


def test_run_git_reference_query_returns_none_for_an_absent_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _default_branch_tip, _topic_branch_tip = (
        _build_default_branch_repository(tmp_path)
    )
    monkeypatch.chdir(repository)

    resolved_object_name = pre_push.run_git_reference_query(
        ("git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/absent")
    )

    assert resolved_object_name is None


def test_resolve_default_branch_reference_reads_the_origin_head_symbolic_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _default_branch_tip, _topic_branch_tip = (
        _build_default_branch_repository(tmp_path)
    )
    monkeypatch.chdir(repository)

    assert pre_push.resolve_default_branch_reference() == ORIGIN_DEFAULT_BRANCH_REFERENCE


def test_resolve_default_branch_reference_returns_none_without_remote_tracking_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository_without_remote_tracking_refs"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    _commit_file(repository, BASE_FILE_NAME)
    monkeypatch.chdir(repository)

    assert pre_push.resolve_default_branch_reference() is None


def test_find_branch_update_push_returns_the_update_that_follows_a_deletion_line() -> (
    None
):
    stdin_text = (
        f"(delete) {ALL_ZEROS_OBJECT_NAME} refs/heads/retired {NON_ZERO_REMOTE_SHA_ONE}\n"
        + _push_stdin_line(
            FEATURE_BRANCH_NAME,
            NON_ZERO_LOCAL_SHA,
            DEFAULT_BRANCH_NAME,
            NON_ZERO_REMOTE_SHA_TWO,
        )
    )

    branch_update = pre_push.find_branch_update_push(stdin_text)

    assert branch_update == pre_push.PushLine(
        local_branch_name=FEATURE_BRANCH_NAME,
        local_object_name=NON_ZERO_LOCAL_SHA,
        remote_branch_name=DEFAULT_BRANCH_NAME,
        remote_object_name=NON_ZERO_REMOTE_SHA_TWO,
    )


def test_find_branch_update_push_returns_none_when_every_line_is_a_deletion() -> None:
    deletion_only_stdin = _push_stdin_line(
        FEATURE_BRANCH_NAME,
        ALL_ZEROS_OBJECT_NAME,
        FEATURE_BRANCH_NAME,
        NON_ZERO_REMOTE_SHA_ONE,
    )

    assert pre_push.find_branch_update_push(deletion_only_stdin) is None


def test_resolve_default_branch_merge_base_returns_the_fork_point(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, default_branch_tip, topic_branch_tip = _build_default_branch_repository(
        tmp_path
    )
    monkeypatch.chdir(repository)

    merge_base_object_name = pre_push.resolve_default_branch_merge_base(
        FEATURE_BRANCH_NAME, topic_branch_tip
    )

    assert merge_base_object_name == default_branch_tip


def test_resolve_default_branch_merge_base_returns_none_for_a_default_branch_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _default_branch_tip, topic_branch_tip = (
        _build_default_branch_repository(tmp_path)
    )
    monkeypatch.chdir(repository)

    merge_base_object_name = pre_push.resolve_default_branch_merge_base(
        DEFAULT_BRANCH_NAME, topic_branch_tip
    )

    assert merge_base_object_name is None


def test_resolve_gate_base_reference_returns_the_default_branch_merge_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, default_branch_tip, topic_branch_tip = _build_default_branch_repository(
        tmp_path
    )
    monkeypatch.chdir(repository)
    stdin_text = _push_stdin_line(
        FEATURE_BRANCH_NAME,
        topic_branch_tip,
        FEATURE_BRANCH_NAME,
        NON_ZERO_REMOTE_SHA_ONE,
    )

    assert pre_push.resolve_gate_base_reference(stdin_text) == default_branch_tip


def test_resolve_gate_base_reference_returns_none_for_a_deletion_only_push() -> None:
    deletion_only_stdin = _push_stdin_line(
        FEATURE_BRANCH_NAME,
        ALL_ZEROS_OBJECT_NAME,
        FEATURE_BRANCH_NAME,
        ALL_ZEROS_OBJECT_NAME,
    )

    assert pre_push.resolve_gate_base_reference(deletion_only_stdin) is None


def test_main_allows_default_branch_file_the_rebase_replayed_onto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, rebased_tip, pre_rebase_tip = _build_rebased_branch_repository(
        tmp_path,
        default_branch_file_name=FLAGGED_FILE_NAME,
        branch_file_name=BRANCH_FILE_NAME,
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                FEATURE_BRANCH_NAME, rebased_tip, FEATURE_BRANCH_NAME, pre_rebase_tip
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_blocks_violation_the_branch_itself_adds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, rebased_tip, pre_rebase_tip = _build_rebased_branch_repository(
        tmp_path,
        default_branch_file_name=DEFAULT_BRANCH_FILE_NAME,
        branch_file_name=FLAGGED_FILE_NAME,
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                FEATURE_BRANCH_NAME, rebased_tip, FEATURE_BRANCH_NAME, pre_rebase_tip
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 1


def test_main_uses_remote_object_when_no_default_branch_reference_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository_without_remote"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    remote_object_name = _commit_file(repository, BASE_FILE_NAME)
    _run_fixture_git(repository, "checkout", "-b", FEATURE_BRANCH_NAME)
    pushed_object_name = _commit_file(repository, BRANCH_FILE_NAME)
    recorded_arguments_path = tmp_path / "recorded_arguments.txt"
    recording_gate_script_path = tmp_path / "recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                FEATURE_BRANCH_NAME,
                pushed_object_name,
                FEATURE_BRANCH_NAME,
                remote_object_name,
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--base", remote_object_name]


def test_main_uses_remote_object_when_the_default_branch_is_pushed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "stale_tracking_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    stale_tracking_tip = _commit_file(repository, BASE_FILE_NAME)
    remote_object_name = _commit_file(repository, FLAGGED_FILE_NAME)
    pushed_object_name = _commit_file(repository, DEFAULT_BRANCH_FILE_NAME)
    _set_origin_default_branch_tip(
        repository, ORIGIN_DEFAULT_BRANCH_REFERENCE, stale_tracking_tip
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                DEFAULT_BRANCH_NAME,
                pushed_object_name,
                DEFAULT_BRANCH_NAME,
                remote_object_name,
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_uses_merge_base_when_a_default_named_local_branch_updates_a_topic_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "default_named_local_branch_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", UNPROTECTED_DEFAULT_BRANCH_NAME)
    remote_object_name = _commit_file(repository, BASE_FILE_NAME)
    default_branch_tip = _commit_file(repository, FLAGGED_FILE_NAME)
    pushed_object_name = _commit_file(repository, BRANCH_FILE_NAME)
    _set_origin_default_branch_tip(
        repository, ORIGIN_UNPROTECTED_DEFAULT_BRANCH_REFERENCE, default_branch_tip
    )
    _set_origin_head(repository, ORIGIN_UNPROTECTED_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                UNPROTECTED_DEFAULT_BRANCH_NAME,
                pushed_object_name,
                TOPIC_REMOTE_BRANCH_NAME,
                remote_object_name,
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_uses_remote_object_when_a_renamed_local_branch_updates_the_default_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "renamed_local_branch_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", UNPROTECTED_DEFAULT_BRANCH_NAME)
    stale_tracking_tip = _commit_file(repository, BASE_FILE_NAME)
    remote_object_name = _commit_file(repository, FLAGGED_FILE_NAME)
    pushed_object_name = _commit_file(repository, DEFAULT_BRANCH_FILE_NAME)
    _run_fixture_git(repository, "checkout", "-b", LOCAL_ALIAS_BRANCH_NAME)
    _set_origin_default_branch_tip(
        repository, ORIGIN_UNPROTECTED_DEFAULT_BRANCH_REFERENCE, stale_tracking_tip
    )
    _set_origin_head(repository, ORIGIN_UNPROTECTED_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                LOCAL_ALIAS_BRANCH_NAME,
                pushed_object_name,
                UNPROTECTED_DEFAULT_BRANCH_NAME,
                remote_object_name,
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_reads_default_branch_tracking_reference_when_origin_head_is_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, rebased_tip, pre_rebase_tip = _build_rebased_branch_repository(
        tmp_path,
        default_branch_file_name=FLAGGED_FILE_NAME,
        branch_file_name=BRANCH_FILE_NAME,
    )
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                FEATURE_BRANCH_NAME, rebased_tip, FEATURE_BRANCH_NAME, pre_rebase_tip
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_skips_a_deletion_line_to_reach_the_branch_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, rebased_tip, pre_rebase_tip = _build_rebased_branch_repository(
        tmp_path,
        default_branch_file_name=FLAGGED_FILE_NAME,
        branch_file_name=BRANCH_FILE_NAME,
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    _write_diff_scoped_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.chdir(repository)
    deletion_line = (
        f"(delete) {ALL_ZEROS_OBJECT_NAME} refs/heads/retired {NON_ZERO_REMOTE_SHA_ONE}\n"
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            deletion_line
            + _push_stdin_line(
                FEATURE_BRANCH_NAME, rebased_tip, FEATURE_BRANCH_NAME, pre_rebase_tip
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_allows_when_code_review_enforcement_flag_is_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native pre-push honors the real gate with enforcement off.

    Points at the production push gate (not a reason stub). With the shipped
    default `CODE_REVIEW_ENFORCEMENT_ENABLED = False`, the gate returns no
    deny reason and the backstop allows the push — one path covering flag,
    real gate load, and pre-push exit together.
    """
    _write_passing_code_rules_gate(tmp_path, monkeypatch)
    real_gate_path = (
        Path(__file__).resolve().parent.parent
        / "blocking"
        / "code_review_push_gate.py"
    )
    assert real_gate_path.is_file()
    monkeypatch.setenv("CODE_REVIEW_PUSH_GATE_PATH", str(real_gate_path))

    exit_code = pre_push.main()

    assert exit_code == 0
