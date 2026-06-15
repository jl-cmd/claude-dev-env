"""Entry-point tests proving the zero-payload-alias check guards hook-infrastructure files.

A pass-through alias inside a hook module is the motivating case for the
zero-payload-alias check, so the deny must fire on the same PreToolUse path a
live Write into ``packages/claude-dev-env/hooks/blocking`` would take — not only
through ``validate_content``, which hook files never reach at PreToolUse. These
tests drive the real ``main()`` stdin entry point and the pre-check CLI with a
hook-infrastructure target.

Each test builds a temporary tree whose tail mirrors a production hook directory
(``packages/claude-dev-env/hooks/blocking``) so ``is_hook_infrastructure`` matches
the target path the same way it would for the real directory.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

_HOOK_DIRECTORY = pathlib.Path(__file__).resolve().parent
_HOOKS_PARENT = _HOOK_DIRECTORY.parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))
if str(_HOOKS_PARENT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_PARENT))

from code_rules_enforcer import main  # noqa: E402

code_rules_enforcer = SimpleNamespace(main=main, sys=sys)

_ENFORCER_SCRIPT_PATH = _HOOK_DIRECTORY / "code_rules_enforcer.py"

PASS_THROUGH_ALIAS_SOURCE = (
    "def find_bare_path_segments(content: str) -> set[str]:\n"
    "    return {part for part in content.split() if part}\n"
    "\n"
    "def find_bare_index_segments(content: str) -> set[str]:\n"
    "    return find_bare_path_segments(content)\n"
)

_HOOK_INFRASTRUCTURE_TAIL = pathlib.Path("packages") / "claude-dev-env" / "hooks" / "blocking"


@pytest.fixture
def hook_blocking_dir() -> Iterator[pathlib.Path]:
    base_directory = pathlib.Path(tempfile.mkdtemp())
    blocking_directory = base_directory / _HOOK_INFRASTRUCTURE_TAIL
    blocking_directory.mkdir(parents=True)
    try:
        yield blocking_directory
    finally:
        shutil.rmtree(base_directory, ignore_errors=False)


def _run_main_with_write_payload(
    file_path: str,
    content: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Drive ``main()`` through its stdin entry point for a Write and return stdout.

    Args:
        file_path: The on-disk path the Write targets.
        content: The whole-file body the Write would create.
        monkeypatch: The fixture used to redirect ``sys.stdin``.
        capsys: The fixture used to capture the deny payload on stdout.

    Returns:
        The captured stdout, which holds the deny payload when violations fire.
    """
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )
    monkeypatch.setattr(code_rules_enforcer.sys, "stdin", io.StringIO(write_payload))
    with contextlib.suppress(SystemExit):
        code_rules_enforcer.main([])
    return capsys.readouterr().out


def test_write_of_pass_through_alias_into_hook_directory_denies(
    hook_blocking_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Write that introduces a pass-through alias into a hook file is denied.

    The target lives under a hook-infrastructure path the full code-rules suite
    exempts, so this proves the zero-payload-alias check still fires on the exact
    directory its docstring names as the motivating case — at the PreToolUse Write
    point, not only through ``validate_content``."""
    new_file = hook_blocking_dir / "new_blocker.py"
    stdout = _run_main_with_write_payload(
        str(new_file), PASS_THROUGH_ALIAS_SOURCE, monkeypatch, capsys
    )
    assert stdout != "", (
        "A pass-through alias written into a hook-infrastructure file must produce "
        "a deny payload, got empty stdout"
    )
    deny_payload = json.loads(stdout)
    decision = deny_payload["hookSpecificOutput"]["permissionDecision"]
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert decision == "deny", f"expected deny, got: {decision!r}"
    assert "find_bare_index_segments" in reason, (
        f"the deny reason must name the pass-through alias, got: {reason!r}"
    )


def test_precheck_of_pass_through_alias_at_hook_target_exits_nonzero(
    hook_blocking_dir: pathlib.Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The pre-check CLI flags a pass-through alias judged at a hook-infrastructure target.

    Driving the real ``--check`` argv path proves the gate's pre-check mode also
    routes a hook ``.py`` target through the zero-payload-alias check rather than
    exiting clean on the blanket hook-infrastructure exemption."""
    staging_directory = tmp_path_factory.mktemp("staging")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(PASS_THROUGH_ALIAS_SOURCE, encoding="utf-8")
    target_path = str(hook_blocking_dir / "new_blocker.py")
    completed = subprocess.run(
        [
            sys.executable,
            str(_ENFORCER_SCRIPT_PATH),
            "--check",
            str(candidate_file),
            "--as",
            target_path,
        ],
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, (
        "a pass-through alias at a hook target must exit nonzero, got: "
        f"{completed.returncode}, stdout: {completed.stdout!r}, "
        f"stderr: {completed.stderr!r}"
    )
    assert "find_bare_index_segments" in completed.stdout, (
        f"the pre-check must name the pass-through alias, got: {completed.stdout!r}"
    )
