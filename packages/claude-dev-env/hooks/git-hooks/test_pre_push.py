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


def test_run_git_reference_query_returns_replaced_text_on_locale_invalid_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """text=True would raise; bytes mode returns the replacing-policy decode."""
    locale_invalid_reference_bytes = b"refs/remotes/origin/caf\xe9"
    expected_replaced_reference = locale_invalid_reference_bytes.decode(
        git_hooks_constants.GIT_OUTPUT_ENCODING_NAME,
        errors=git_hooks_constants.GIT_OUTPUT_DECODE_ERRORS_POLICY,
    )

    def answer_with_locale_invalid_reference(
        all_command_arguments: list[str], **all_keyword_arguments: object
    ) -> subprocess.CompletedProcess[bytes]:
        if all_keyword_arguments.get(TEXT_DECODING_KEYWORD):
            raise _refuse_locale_decoding()
        return _completed_git_process(
            all_command_arguments,
            GIT_RESOLVED_EXIT_CODE,
            locale_invalid_reference_bytes,
        )

    monkeypatch.setattr(subprocess, "run", answer_with_locale_invalid_reference)

    resolved_output = pre_push.run_git_reference_query(
        ("git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/HEAD")
    )

    assert resolved_output == expected_replaced_reference


def test_unresolvable_merge_base_message_describes_pending_validation() -> None:
    skip_message = git_hooks_constants.UNRESOLVABLE_MERGE_BASE_MESSAGE
    assert "CODE_RULES validation is pending" in skip_message
    assert "Restore shared history" in skip_message


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
    _isolate_from_default_branch_refs(tmp_path, monkeypatch)
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
    # No default-branch ref so the gate base is the stdin remote object, not a
    # merge-base skip; usable-base resolution then sees the pushed remote name.
    _isolate_repository_and_write_passing_code_rules_gate(tmp_path, monkeypatch)
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
    _isolate_from_default_branch_refs(tmp_path, monkeypatch)
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
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            f"refs/heads/main {NON_ZERO_LOCAL_SHA} refs/heads/main {NON_ZERO_REMOTE_SHA_ONE}\n"
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == 0



def _write_passing_code_rules_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Install a passing CODE_RULES gate and a one-line feature push on stdin."""
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


def _isolate_repository_and_write_passing_code_rules_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Move into a repository without origin refs, then install a passing gate."""
    _isolate_from_default_branch_refs(tmp_path, monkeypatch)
    _write_passing_code_rules_gate(tmp_path, monkeypatch)


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


def _isolate_from_default_branch_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Move the test into a fresh repository that holds no origin default branch.

    Tests that feed synthetic object names need a working directory where no
    default-branch ref resolves, so the hook takes its stdin remote-object
    fallback rather than reading the ambient repository's origin refs.
    """
    isolated_repository = tmp_path / "repository_without_origin_refs"
    isolated_repository.mkdir()
    _run_fixture_git(isolated_repository, "init", "-b", DEFAULT_BRANCH_NAME)
    monkeypatch.chdir(isolated_repository)


def _build_unrelated_history_repository(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository whose feature branch shares no history with the default.

    The origin default-branch ref and the origin HEAD symbolic ref both resolve,
    so ``git merge-base`` runs and reports no merge base rather than the hook
    failing to find a default branch at all.

    Args:
        tmp_path: The pytest temporary directory the repository is built in.

    Returns:
        The repository path and the orphan feature branch tip.
    """
    repository = tmp_path / "unrelated_history_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    _commit_file(repository, BASE_FILE_NAME)
    default_branch_tip = _commit_file(repository, DEFAULT_BRANCH_FILE_NAME)
    _run_fixture_git(repository, "checkout", "--orphan", FEATURE_BRANCH_NAME)
    _run_fixture_git(repository, "reset")
    orphan_branch_tip = _commit_file(repository, BRANCH_FILE_NAME)
    _set_origin_default_branch_tip(
        repository, ORIGIN_DEFAULT_BRANCH_REFERENCE, default_branch_tip
    )
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    return repository, orphan_branch_tip


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


def test_resolve_gate_base_reference_flags_an_unresolvable_merge_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, orphan_branch_tip = _build_unrelated_history_repository(tmp_path)
    monkeypatch.chdir(repository)
    assert (
        pre_push.run_git_reference_query(
            ("git", "merge-base", orphan_branch_tip, ORIGIN_DEFAULT_BRANCH_REFERENCE)
        )
        is None
    ), "fixture branch shares history with the default branch"
    stdin_text = _push_stdin_line(
        FEATURE_BRANCH_NAME,
        orphan_branch_tip,
        FEATURE_BRANCH_NAME,
        NON_ZERO_REMOTE_SHA_ONE,
    )

    base_reference = pre_push.resolve_gate_base_reference(stdin_text)

    assert base_reference == git_hooks_constants.UNRESOLVABLE_MERGE_BASE_SENTINEL


def test_resolve_gate_base_reference_treats_a_dangling_origin_head_as_no_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symbolic origin/HEAD whose target is missing falls through to no default branch ref.

    The gate base then uses the stdin remote object, the same path as when no
    default-branch ref resolves at all.
    """
    repository = tmp_path / "dangling_origin_head_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    pushed_object_name = _commit_file(repository, BASE_FILE_NAME)
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    monkeypatch.chdir(repository)
    stdin_text = _push_stdin_line(
        FEATURE_BRANCH_NAME,
        pushed_object_name,
        FEATURE_BRANCH_NAME,
        NON_ZERO_REMOTE_SHA_ONE,
    )

    base_reference = pre_push.resolve_gate_base_reference(stdin_text)

    assert base_reference == NON_ZERO_REMOTE_SHA_ONE


def test_main_allows_the_push_when_origin_head_names_an_absent_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dangling origin/HEAD does not skip the gate; it uses the remote object base."""
    repository = tmp_path / "dangling_origin_head_push_repository"
    repository.mkdir()
    _run_fixture_git(repository, "init", "-b", DEFAULT_BRANCH_NAME)
    remote_object_name = _commit_file(repository, BASE_FILE_NAME)
    _run_fixture_git(repository, "checkout", "-b", FEATURE_BRANCH_NAME)
    pushed_object_name = _commit_file(repository, BRANCH_FILE_NAME)
    _set_origin_head(repository, ORIGIN_DEFAULT_BRANCH_REFERENCE)
    recorded_arguments_path = tmp_path / "recorded_arguments_dangling.txt"
    recording_gate_script_path = tmp_path / "recording_gate_dangling.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))
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


def test_main_keeps_the_gate_pending_when_no_merge_base_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository, orphan_branch_tip = _build_unrelated_history_repository(tmp_path)
    recorded_arguments_path = tmp_path / "unreached_gate_arguments.txt"
    recording_gate_script_path = tmp_path / "unreached_recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))
    monkeypatch.chdir(repository)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            _push_stdin_line(
                FEATURE_BRANCH_NAME,
                orphan_branch_tip,
                FEATURE_BRANCH_NAME,
                NON_ZERO_REMOTE_SHA_ONE,
            )
        ),
    )

    exit_code = pre_push.main()

    assert exit_code == git_hooks_constants.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    assert not recorded_arguments_path.exists(), (
        "the gate remains pending until the hook verifies a usable base"
    )
    assert git_hooks_constants.UNRESOLVABLE_MERGE_BASE_MESSAGE in capsys.readouterr().err


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
