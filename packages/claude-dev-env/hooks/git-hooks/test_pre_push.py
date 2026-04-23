from __future__ import annotations

import importlib
import io
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
import config


ALL_ZEROS_OBJECT_NAME: str = "0" * 40
NON_ZERO_LOCAL_SHA: str = "a" * 40
NON_ZERO_REMOTE_SHA_ONE: str = "1" * 40
NON_ZERO_REMOTE_SHA_TWO: str = "2" * 40


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

    assert exit_code == config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


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

    assert exit_code == config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


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

    assert base_reference == config.NO_PARSEABLE_STDIN_LINES_SENTINEL


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

    assert result == config.NO_PARSEABLE_STDIN_LINES_SENTINEL


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

    assert exit_code == config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
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
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        f"refs/heads/feature {NON_ZERO_LOCAL_SHA} refs/heads/feature {NON_ZERO_REMOTE_SHA_ONE}\n"
    ))

    exit_code = pre_push.main()

    assert exit_code == 0
    executed_path = recorded_path_file.read_text(encoding="utf-8")
    assert executed_path == str(resolved_path)
