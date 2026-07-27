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

pre_push = importlib.import_module("pre_push")
git_hooks_constants = importlib.import_module("git_hooks_constants")


ALL_ZEROS_OBJECT_NAME: str = "0" * 40
NON_ZERO_LOCAL_SHA: str = "a" * 40
NON_ZERO_REMOTE_SHA_ONE: str = "1" * 40
NON_ZERO_REMOTE_SHA_TWO: str = "2" * 40


def _isolate_code_review_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CODE_REVIEW_PUSH_GATE_PATH", str(tmp_path / "no_code_review_gate.py")
    )


def test_resolve_base_reference_from_stdin_uses_remote_object_when_non_zero() -> None:
    stdin_text = (
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
    )

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == NON_ZERO_REMOTE_SHA_ONE


def test_resolve_base_reference_from_stdin_defaults_when_remote_is_all_zeros() -> None:
    stdin_text = f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_from_stdin_defaults_when_stdin_empty() -> None:
    base_reference = pre_push.resolve_base_reference_from_stdin("")

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_from_stdin_prefers_first_non_zero_remote_object() -> (
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
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_resolve_base_reference_from_stdin_warns_on_malformed_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_stdin_text = "only_one_field\n"

    pre_push.resolve_base_reference_from_stdin(malformed_stdin_text)

    captured = capsys.readouterr()
    assert "malformed" in captured.err


def test_resolve_base_reference_from_stdin_returns_none_for_deletion_push() -> None:
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


def test_resolve_base_reference_from_stdin_returns_sentinel_for_malformed_lines() -> None:
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
        "def git_hook_deny_reason(target_directory):\n"
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


GIT_TEST_COMMAND_TIMEOUT_SECONDS: int = 30
TRACKED_FILE_NAME: str = "app.py"
TRACKED_FILE_TEXT: str = "def add(left: int, right: int) -> int:\n    return left + right\n"
ORIGIN_MAIN_REMOTE_TRACKING_REFERENCE: str = "origin/main"
ORIGIN_HEAD_SYMBOLIC_TARGET: str = "refs/remotes/origin/main"
UNRESOLVED_BASE_STDERR_FRAGMENT: str = "no remote base reference"
EMPTY_HOOKS_DIRECTORY_NAME: str = "empty_git_hooks"
NON_DEFAULT_REMOTE_BRANCH_NAME: str = "topic"
NON_DEFAULT_REMOTE_TRACKING_REFERENCE: str = "refs/remotes/origin/topic"


def _run_git_command(working_directory: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(working_directory), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TEST_COMMAND_TIMEOUT_SECONDS,
    )


def _detach_installed_git_hooks(work_directory: Path) -> None:
    """Point the fixture repo at an empty hooks directory of its own."""
    empty_hooks_directory = work_directory / EMPTY_HOOKS_DIRECTORY_NAME
    empty_hooks_directory.mkdir()
    _run_git_command(work_directory, "config", "core.hooksPath", str(empty_hooks_directory))


def _initialize_committed_work_tree(work_directory: Path, branch_name: str) -> None:
    """Init *work_directory* on *branch_name* with one commit and no hooks."""
    _run_git_command(work_directory, "init", f"--initial-branch={branch_name}")
    _run_git_command(work_directory, "config", "user.email", "tests@example.com")
    _run_git_command(work_directory, "config", "user.name", "Reviewer")
    _detach_installed_git_hooks(work_directory)
    (work_directory / TRACKED_FILE_NAME).write_text(TRACKED_FILE_TEXT, encoding="utf-8")
    _run_git_command(work_directory, "add", "-A")
    _run_git_command(work_directory, "commit", "-m", "base")


def _initialize_bare_origin(origin_directory: Path, branch_name: str) -> None:
    """Init a bare origin repository at *origin_directory* on *branch_name*."""
    subprocess.run(
        ["git", "init", "--bare", f"--initial-branch={branch_name}", str(origin_directory)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TEST_COMMAND_TIMEOUT_SECONDS,
    )


def _make_repo_without_origin_head(tmp_path: Path) -> Path:
    """Build a work tree whose origin carries main but no ``origin/HEAD`` ref.

    This is the fresh-container clone shape: the remote-tracking branch exists,
    while ``refs/remotes/origin/HEAD`` was never written.
    """
    origin_directory = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_directory)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TEST_COMMAND_TIMEOUT_SECONDS,
    )
    work_directory = tmp_path / "work"
    work_directory.mkdir()
    _run_git_command(work_directory, "init", "--initial-branch=main")
    _run_git_command(work_directory, "config", "user.email", "tests@example.com")
    _run_git_command(work_directory, "config", "user.name", "Reviewer")
    _detach_installed_git_hooks(work_directory)
    (work_directory / TRACKED_FILE_NAME).write_text(TRACKED_FILE_TEXT, encoding="utf-8")
    _run_git_command(work_directory, "add", "-A")
    _run_git_command(work_directory, "commit", "-m", "base")
    _run_git_command(work_directory, "remote", "add", "origin", str(origin_directory))
    _run_git_command(work_directory, "push", "-u", "origin", "main")
    return work_directory


def _make_repo_without_remote(tmp_path: Path) -> Path:
    work_directory = tmp_path / "solo"
    work_directory.mkdir()
    _run_git_command(work_directory, "init", "--initial-branch=main")
    _run_git_command(work_directory, "config", "user.email", "tests@example.com")
    _run_git_command(work_directory, "config", "user.name", "Reviewer")
    _detach_installed_git_hooks(work_directory)
    (work_directory / TRACKED_FILE_NAME).write_text(TRACKED_FILE_TEXT, encoding="utf-8")
    _run_git_command(work_directory, "add", "-A")
    _run_git_command(work_directory, "commit", "-m", "base")
    return work_directory


def _make_repo_with_only_non_default_remote_branch(tmp_path: Path) -> Path:
    """Build a work tree whose sole remote-tracking ref names a topic branch.

    ::

        refs/remotes/origin/topic  present   the branch the checkout fetched
        refs/remotes/origin/HEAD   absent
        origin/main, origin/master absent

    This is the pull-request CI checkout shape: the fetch wrote one
    remote-tracking ref, and no remote default branch name resolves. The ref
    that is present is a usable gate base.
    """
    origin_directory = tmp_path / "topic_origin.git"
    _initialize_bare_origin(origin_directory, NON_DEFAULT_REMOTE_BRANCH_NAME)
    work_directory = tmp_path / "topic_work"
    work_directory.mkdir()
    _initialize_committed_work_tree(work_directory, NON_DEFAULT_REMOTE_BRANCH_NAME)
    _run_git_command(work_directory, "remote", "add", "origin", str(origin_directory))
    _run_git_command(
        work_directory, "push", "-u", "origin", NON_DEFAULT_REMOTE_BRANCH_NAME
    )
    return work_directory


def _write_exiting_gate_script(gate_script_path: Path, gate_exit_code: int) -> None:
    """Write a stub gate script that exits with *gate_exit_code*."""
    gate_script_path.write_text(
        f"import sys\nsys.exit({gate_exit_code})\n", encoding="utf-8"
    )


def test_main_propagates_blocking_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocking gate blocks the push where no remote branch name resolves."""
    work_directory = _make_repo_with_only_non_default_remote_branch(tmp_path)
    blocking_gate_script_path = tmp_path / "blocking_gate.py"
    _write_exiting_gate_script(
        blocking_gate_script_path, git_hooks_constants.CODE_REVIEW_STAMP_BLOCK_EXIT_CODE
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(blocking_gate_script_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.CODE_REVIEW_STAMP_BLOCK_EXIT_CODE


def test_main_propagates_infrastructure_failure_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing gate fails the push where no remote branch name resolves."""
    work_directory = _make_repo_with_only_non_default_remote_branch(tmp_path)
    infrastructure_failure_gate_path = tmp_path / "infrastructure_failure_gate.py"
    _write_exiting_gate_script(
        infrastructure_failure_gate_path,
        git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(infrastructure_failure_gate_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_main_propagates_blocking_exit_code_from_stdin_remote_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The remote object on stdin is a base of its own with no remote refs."""
    work_directory = _make_repo_without_remote(tmp_path)
    blocking_gate_script_path = tmp_path / "blocking_gate.py"
    _write_exiting_gate_script(
        blocking_gate_script_path, git_hooks_constants.CODE_REVIEW_STAMP_BLOCK_EXIT_CODE
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(blocking_gate_script_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/feature {NON_ZERO_LOCAL_SHA} "
            f"refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.CODE_REVIEW_STAMP_BLOCK_EXIT_CODE


def test_resolve_remote_default_base_reference_uses_newest_remote_tracking_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_with_only_non_default_remote_branch(tmp_path)
    monkeypatch.chdir(work_directory)

    base_reference = pre_push.resolve_remote_default_base_reference()

    assert base_reference == NON_DEFAULT_REMOTE_TRACKING_REFERENCE


def test_main_passes_newest_remote_tracking_reference_to_gate_for_new_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_with_only_non_default_remote_branch(tmp_path)
    recorded_arguments_path = tmp_path / "recorded_newest_base.txt"
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
    new_branch_stdin = (
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} "
        f"refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(new_branch_stdin))
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == 0
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--base", NON_DEFAULT_REMOTE_TRACKING_REFERENCE]


def test_resolve_remote_default_base_reference_uses_origin_head_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_without_origin_head(tmp_path)
    _run_git_command(work_directory, "remote", "set-head", "origin", "main")
    monkeypatch.chdir(work_directory)

    base_reference = pre_push.resolve_remote_default_base_reference()

    assert base_reference == ORIGIN_HEAD_SYMBOLIC_TARGET


def test_resolve_remote_default_base_reference_falls_back_without_origin_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_without_origin_head(tmp_path)
    monkeypatch.chdir(work_directory)

    base_reference = pre_push.resolve_remote_default_base_reference()

    assert base_reference == ORIGIN_MAIN_REMOTE_TRACKING_REFERENCE


def test_resolve_remote_default_base_reference_is_none_without_usable_remote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_without_remote(tmp_path)
    monkeypatch.chdir(work_directory)

    base_reference = pre_push.resolve_remote_default_base_reference()

    assert base_reference is None


def test_main_passes_resolved_default_base_to_gate_without_origin_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_directory = _make_repo_without_origin_head(tmp_path)
    recorded_arguments_path = tmp_path / "recorded_default_base.txt"
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
    new_branch_stdin = (
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(new_branch_stdin))
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == 0
    recorded_arguments = recorded_arguments_path.read_text(encoding="utf-8").splitlines()
    assert recorded_arguments == ["--base", ORIGIN_MAIN_REMOTE_TRACKING_REFERENCE]


def test_main_skips_code_rules_gate_when_no_remote_base_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_directory = _make_repo_without_remote(tmp_path)
    blocking_gate_script_path = tmp_path / "blocking_gate.py"
    blocking_gate_script_path.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(blocking_gate_script_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    new_branch_stdin = (
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(new_branch_stdin))
    monkeypatch.chdir(work_directory)

    exit_code = pre_push.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert UNRESOLVED_BASE_STDERR_FRAGMENT in captured.err
