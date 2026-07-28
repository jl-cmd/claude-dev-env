from __future__ import annotations

import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import git_hooks_constants
import pre_push


SCRIPT_DIRECTORY = Path(__file__).resolve().parent

REAL_RUN_GIT_TEXT_COMMAND = pre_push.run_git_text_command


CODE_REVIEW_ENFORCEMENT_ENV_VAR: str = "CLAUDE_CODE_REVIEW_ENFORCEMENT"
ENFORCEMENT_CONSTANTS_MODULE_NAME: str = "config.code_review_enforcement_constants"
ALL_ZEROS_OBJECT_NAME: str = "0" * 40
NON_ZERO_LOCAL_SHA: str = "a" * 40
NON_ZERO_REMOTE_SHA_ONE: str = "1" * 40
NON_ZERO_REMOTE_SHA_TWO: str = "2" * 40


GIT_RESOLVED_EXIT_CODE: int = 0
RESOLVED_COMMIT_OBJECT_NAME: str = "c" * 40
HOOK_INVOCATION_NAME: str = "pre-push"
PUSHED_REMOTE_NAME: str = "upstream"
PUSHED_REMOTE_URL: str = "https://example.invalid/owner/repository.git"


LOCALE_INVALID_REFERENCE_LISTING_BYTES: bytes = b"origin/caf\xe9\norigin/main\n"
EMPTY_COMMAND_STREAM_BYTES: bytes = b""
STRICT_DECODER_NAME: str = "utf-8"
UNDECODABLE_BYTE_START_INDEX: int = 10
UNDECODABLE_BYTE_END_INDEX: int = 11
UNDECODABLE_BYTE_REASON: str = "invalid continuation byte"
TEXT_DECODING_KEYWORD: str = "text"
GIT_MISSING_REFERENCE_EXIT_CODE: int = 1
GIT_LAUNCH_FAILURE_DETAIL: str = "git executable not found"
RESOLVED_REMOTE_MAIN_REFERENCE: str = "origin/main"
UNRESOLVABLE_BASE_REPORT_MARKER: str = "no usable gate base"
GIT_UNAVAILABLE_REPORT_MARKER: str = "could not run git"
NEW_BRANCH_PUSH_STDIN: str = (
    f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"
)


def _refuse_locale_decoding() -> UnicodeDecodeError:
    """Build the error a text-mode subprocess raises on undecodable output."""
    return UnicodeDecodeError(
        STRICT_DECODER_NAME,
        LOCALE_INVALID_REFERENCE_LISTING_BYTES,
        UNDECODABLE_BYTE_START_INDEX,
        UNDECODABLE_BYTE_END_INDEX,
        UNDECODABLE_BYTE_REASON,
    )


def _completed_git_process(
    all_command_arguments: list[str], exit_code: int, standard_output_bytes: bytes
) -> subprocess.CompletedProcess[bytes]:
    """Build a completed git process carrying raw bytes on standard output."""
    return subprocess.CompletedProcess(
        all_command_arguments,
        exit_code,
        standard_output_bytes,
        EMPTY_COMMAND_STREAM_BYTES,
    )


def _answer_git_with_locale_invalid_bytes(
    all_command_arguments: list[str],
    **all_keyword_arguments: object,
) -> subprocess.CompletedProcess[bytes]:
    """Stand in for a git whose output the process locale cannot decode.

    ::

        text=True -> UnicodeDecodeError   bytes mode -> the raw listing

    Args:
        all_command_arguments: The full git command the seam assembled.
        all_keyword_arguments: The keyword arguments the seam passed.

    Returns:
        A completed process carrying the raw listing bytes.
    """
    if all_keyword_arguments.get(TEXT_DECODING_KEYWORD):
        raise _refuse_locale_decoding()
    if git_hooks_constants.GIT_FOR_EACH_REF_SUBCOMMAND in all_command_arguments:
        return _completed_git_process(
            all_command_arguments,
            GIT_RESOLVED_EXIT_CODE,
            LOCALE_INVALID_REFERENCE_LISTING_BYTES,
        )
    return _completed_git_process(
        all_command_arguments,
        GIT_MISSING_REFERENCE_EXIT_CODE,
        EMPTY_COMMAND_STREAM_BYTES,
    )


def _write_gate_that_allows_every_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point both gates at stubs that allow, with a new-branch push on stdin."""
    passing_gate_path = tmp_path / "code_rules_gate.py"
    passing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(passing_gate_path))
    _isolate_code_review_gate(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(NEW_BRANCH_PUSH_STDIN))


def test_reference_listing_with_locale_invalid_bytes_resolves_a_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _answer_git_with_locale_invalid_bytes)

    resolved_reference = pre_push.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        REAL_RUN_GIT_TEXT_COMMAND,
    )

    assert resolved_reference == RESOLVED_REMOTE_MAIN_REFERENCE


def test_run_git_text_command_raises_when_git_cannot_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising_subprocess_run(
        all_command_arguments: list[str], **all_keyword_arguments: object
    ) -> subprocess.CompletedProcess[bytes]:
        raise OSError(GIT_LAUNCH_FAILURE_DETAIL)

    monkeypatch.setattr(subprocess, "run", raising_subprocess_run)

    with pytest.raises(pre_push.GitCommandUnavailable):
        REAL_RUN_GIT_TEXT_COMMAND([git_hooks_constants.GIT_FOR_EACH_REF_SUBCOMMAND])


def test_main_reports_infrastructure_failure_when_git_cannot_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_gate_that_allows_every_push(tmp_path, monkeypatch)

    def unavailable_run_git_text_command(
        all_command_arguments: list[str],
    ) -> tuple[int, str]:
        raise pre_push.GitCommandUnavailable(GIT_LAUNCH_FAILURE_DETAIL)

    monkeypatch.setattr(
        pre_push, "run_git_text_command", unavailable_run_git_text_command
    )

    exit_code = pre_push.main()

    captured_streams = capsys.readouterr()
    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    assert GIT_UNAVAILABLE_REPORT_MARKER in captured_streams.err
    assert GIT_LAUNCH_FAILURE_DETAIL in captured_streams.err
    assert UNRESOLVABLE_BASE_REPORT_MARKER not in captured_streams.err


def test_main_reports_a_missing_default_branch_as_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_gate_that_allows_every_push(tmp_path, monkeypatch)

    def empty_run_git_text_command(
        all_command_arguments: list[str],
    ) -> tuple[int, str]:
        return GIT_MISSING_REFERENCE_EXIT_CODE, ""

    monkeypatch.setattr(pre_push, "run_git_text_command", empty_run_git_text_command)

    exit_code = pre_push.main()

    captured_streams = capsys.readouterr()
    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    assert UNRESOLVABLE_BASE_REPORT_MARKER in captured_streams.err
    assert GIT_UNAVAILABLE_REPORT_MARKER not in captured_streams.err


@pytest.fixture(autouse=True)
def resolve_remote_head_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every reference resolve, so these tests ignore the clone's remote state.

    ``main`` resolves the gate base through git before it invokes the gate. A
    clone with no ``origin/HEAD`` would send these tests down the unresolvable
    path and change what ``main`` returns. Stubbing the seam keeps each test
    about the flow it names. Base resolution itself is covered by
    ``test_pre_push_base_reference.py``.
    """

    def fake_run_git_text_command(all_command_arguments: list[str]) -> tuple[int, str]:
        return GIT_RESOLVED_EXIT_CODE, RESOLVED_COMMIT_OBJECT_NAME

    monkeypatch.setattr(pre_push, "run_git_text_command", fake_run_git_text_command)


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


def test_resolve_base_reference_from_stdin_falls_back_when_remote_is_all_zeros() -> None:
    stdin_text = f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_from_stdin_falls_back_when_stdin_is_empty() -> None:
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


def test_main_passes_the_pushed_remote_name_to_base_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_passing_code_rules_gate(tmp_path, monkeypatch)
    _isolate_code_review_gate(tmp_path, monkeypatch)
    all_recorded_remote_names: list[str] = []

    def recording_resolve_usable_base_reference(
        base_reference: str,
        remote_name: str,
        ask_git: Callable[[list[str]], tuple[int, str]],
    ) -> str:
        all_recorded_remote_names.append(remote_name)
        return base_reference

    monkeypatch.setattr(
        pre_push,
        "resolve_usable_base_reference",
        recording_resolve_usable_base_reference,
    )
    monkeypatch.setattr(
        sys, "argv", [HOOK_INVOCATION_NAME, PUSHED_REMOTE_NAME, PUSHED_REMOTE_URL]
    )

    exit_code = pre_push.main()

    assert exit_code == 0
    assert all_recorded_remote_names == [PUSHED_REMOTE_NAME]


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


def test_resolve_base_reference_from_stdin_emits_warning_for_malformed_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_stdin_text = "only_one_field\n"

    pre_push.resolve_base_reference_from_stdin(malformed_stdin_text)

    captured = capsys.readouterr()
    assert "malformed" in captured.err


def test_resolve_base_reference_from_stdin_returns_none_when_local_sha_is_all_zeros() -> None:
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


def test_resolve_base_reference_from_stdin_reports_sentinel_with_no_valid_lines() -> None:
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


def test_main_allows_when_code_review_enforcement_flag_is_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native pre-push honors the real gate with enforcement off.

    Points at the production push gate (not a reason stub). The gate resolves
    its flag when its config module first executes, so this test clears the
    environment variable and evicts that one module if a sibling suite cached
    it earlier in the same session. The gate then returns no deny reason and
    the backstop allows the push.
    """
    monkeypatch.delenv(CODE_REVIEW_ENFORCEMENT_ENV_VAR, raising=False)
    monkeypatch.delitem(sys.modules, ENFORCEMENT_CONSTANTS_MODULE_NAME, raising=False)
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
