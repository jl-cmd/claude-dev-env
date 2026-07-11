"""Behavior tests for the code_rules_enforcer pre-check mode and full-file forecast."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import (  # noqa: E402
    main,
    validate_content,
)

code_rules_enforcer = SimpleNamespace(
    main=main,
    sys=sys,
    validate_content=validate_content,
)

_ENFORCER_SCRIPT_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"

_VIOLATING_PRODUCTION_SOURCE = "def process_data(payload: str) -> None:\n    print(payload)\n"

_CLEAN_CLI_SOURCE = (
    "def announce_payload(payload: str) -> None:\n"
    '    """Log the payload.\n'
    "\n"
    "    Args:\n"
    "        payload: The text to record.\n"
    '    """\n'
    "    print(payload)\n"
)

_UNTOUCHED_PRINT_VIOLATION_SOURCE = "def emit_audit_line() -> None:\n    print(99)\n"

_CLEAN_FRAGMENT_BEFORE = "def short_helper() -> int:\n    return 1\n"


def _run_enforcer_cli(
    all_cli_arguments: list[str],
) -> subprocess.CompletedProcess[str]:
    """Drive the enforcer script through its real argv entry point.

    Args:
        all_cli_arguments: The argument vector appended after the script path.

    Returns:
        The completed process carrying stdout, stderr, and the exit code.
    """
    return subprocess.run(
        [sys.executable, str(_ENFORCER_SCRIPT_PATH), *all_cli_arguments],
        input="",
        capture_output=True,
        text=True,
        check=False,
    )


def _run_precheck(
    candidate_path: str,
    target_path: str,
) -> subprocess.CompletedProcess[str]:
    """Drive the enforcer script in pre-check mode through its real argv entry point.

    Args:
        candidate_path: The path of the complete candidate file to validate.
        target_path: The destination path used for all classification, passed
            through ``--as``.

    Returns:
        The completed process carrying the pre-check stdout, stderr, and exit code.
    """
    return _run_enforcer_cli(["--check", candidate_path, "--as", target_path])


def _run_main_with_edit_payload(
    file_path: str,
    old_string: str,
    new_string: str,
    monkeypatch: object,
    capsys: object,
) -> str:
    """Drive ``main()`` through its stdin entry point for an Edit and return stdout.

    Args:
        file_path: The on-disk path the Edit targets.
        old_string: The Edit's ``old_string`` fragment.
        new_string: The Edit's ``new_string`` fragment.
        monkeypatch: The pytest fixture used to redirect ``sys.stdin``.
        capsys: The pytest fixture used to capture the deny payload on stdout.

    Returns:
        The captured stdout, which holds the deny payload when violations fire.
    """
    edit_payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )
    getattr(monkeypatch, "setattr")(code_rules_enforcer.sys, "stdin", io.StringIO(edit_payload))
    try:
        code_rules_enforcer.main([])
    except SystemExit:
        pass
    captured = getattr(capsys, "readouterr")()
    return captured.out


def test_precheck_stream_parameter_carries_no_banned_noun() -> None:
    """The pre-check helper's stream parameter must not carry a banned noun.

    A parameter such as ``output_stream`` carries the banned noun ``output``;
    the hook-infrastructure exemption hides it on a direct edit, but the pull
    request gate and a reviewer judge this source at a production path, where the
    banned-noun check fires. Scanning the enforcer source at a production path
    proves the introduced stream parameter is free of that violation."""
    enforcer_source = _ENFORCER_SCRIPT_PATH.read_text(encoding="utf-8")
    issues = code_rules_enforcer.validate_content(
        enforcer_source, "/project/src/code_rules_enforcer.py"
    )
    banned_noun_issues = [
        each_issue
        for each_issue in issues
        if "banned noun" in each_issue.lower() and "stream" in each_issue
    ]
    assert banned_noun_issues == [], (
        f"the stream parameter must carry no banned noun, got: {banned_noun_issues!r}"
    )


def test_precheck_reports_violations_and_exits_nonzero_for_production_candidate(
    tmp_path_factory: object,
) -> None:
    """A violating candidate judged at a production target prints each violation to
    stdout and exits 1."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    target_path = str(production_directory / "production_module.py")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 1, (
        f"violating candidate must exit nonzero, got: {completed.returncode}, "
        f"stdout: {completed.stdout!r}, stderr: {completed.stderr!r}"
    )
    assert "process_data" in completed.stdout, (
        f"banned-prefix violation must appear on stdout, got: {completed.stdout!r}"
    )
    assert "print" in completed.stdout, (
        f"library-print violation must appear on stdout, got: {completed.stdout!r}"
    )


def test_precheck_emits_no_output_and_exits_zero_for_clean_candidate(
    tmp_path_factory: object,
) -> None:
    """A clean candidate produces no stdout and exits 0."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("scripts")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(_CLEAN_CLI_SOURCE, encoding="utf-8")
    target_path = str(production_directory / "announce_cli.py")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 0, (
        f"clean candidate must exit 0, got: {completed.returncode}, "
        f"stdout: {completed.stdout!r}, stderr: {completed.stderr!r}"
    )
    assert completed.stdout == "", f"clean candidate must emit no stdout, got: {completed.stdout!r}"


def test_precheck_target_path_drives_test_file_exemptions(
    tmp_path_factory: object,
) -> None:
    """Production-shaped content judged against a ``test_*.py`` target passes
    because test-file exemptions apply through the target path."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    target_path = str(production_directory / "test_orders.py")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 0, (
        "test-file exemptions must apply through the target path, "
        f"got exit: {completed.returncode}, stdout: {completed.stdout!r}"
    )


def test_precheck_noncode_target_exits_zero_with_no_output(
    tmp_path_factory: object,
) -> None:
    """A non-code target extension is exempt: the pre-check exits 0 with no output."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    target_path = str(production_directory / "notes.txt")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 0, f"non-code target must exit 0, got: {completed.returncode}"
    assert completed.stdout == "", f"non-code target must emit no stdout, got: {completed.stdout!r}"


def test_precheck_missing_candidate_errors_on_stderr_without_traceback(
    tmp_path_factory: object,
) -> None:
    """A nonexistent candidate path prints a one-line stderr error and exits
    nonzero without a Python traceback."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    missing_candidate = str(production_directory / "nonexistent_candidate.py")
    target_path = str(production_directory / "production_module.py")
    completed = _run_precheck(missing_candidate, target_path)
    assert completed.returncode != 0, (
        f"missing candidate must exit nonzero, got: {completed.returncode}"
    )
    assert "Traceback" not in completed.stderr, (
        f"missing candidate must not raise a traceback, got: {completed.stderr!r}"
    )
    assert completed.stderr.strip() != "", "missing candidate must produce a stderr error message"


def test_edit_deny_reason_includes_forecast_and_precheck_hint(
    tmp_path_factory: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """An Edit whose new_string introduces a violation on a file that already
    contains a separate violation elsewhere blocks on the fragment violation and
    appends a full-file forecast naming the untouched violation plus the
    pre-check hint."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    untouched_print_violation = _UNTOUCHED_PRINT_VIOLATION_SOURCE
    clean_before = _CLEAN_FRAGMENT_BEFORE
    introduces_banned_noun_after = (
        "def short_helper() -> int:\n    output = 0\n    return output\n"
    )
    on_disk_before = untouched_print_violation + "\n" + clean_before
    source_file = production_directory / "production_module.py"
    source_file.write_text(on_disk_before, encoding="utf-8")
    stdout = _run_main_with_edit_payload(
        str(source_file),
        clean_before,
        introduces_banned_noun_after,
        monkeypatch,
        capsys,
    )
    deny_payload = json.loads(stdout)
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    blocking_section, _, forecast_section = reason.partition("FULL-FILE FORECAST")
    assert "output" in blocking_section, (
        f"fragment-introduced banned-noun must block, got reason: {reason!r}"
    )
    assert forecast_section != "", (
        f"forecast section must be present, got reason: {reason!r}"
    )
    assert "Library print()" in forecast_section, (
        f"forecast must name the untouched print violation, got reason: {reason!r}"
    )
    assert "--check" in reason, f"pre-check hint must be present, got reason: {reason!r}"


def test_edit_clean_fragment_on_dirty_file_produces_no_deny_payload(
    tmp_path_factory: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """A clean Edit fragment on a file that is dirty elsewhere must not block —
    the forecast never converts a clean-fragment edit into a deny."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    untouched_print_violation = _UNTOUCHED_PRINT_VIOLATION_SOURCE
    clean_before = _CLEAN_FRAGMENT_BEFORE
    clean_after = "def short_helper() -> int:\n    return 0\n"
    on_disk_before = untouched_print_violation + "\n" + clean_before
    source_file = production_directory / "production_module.py"
    source_file.write_text(on_disk_before, encoding="utf-8")
    stdout = _run_main_with_edit_payload(
        str(source_file),
        clean_before,
        clean_after,
        monkeypatch,
        capsys,
    )
    assert stdout == "", (
        f"a clean fragment on a dirty file must not produce a deny payload, got stdout: {stdout!r}"
    )


def test_every_deny_reason_carries_the_precheck_hint(
    tmp_path_factory: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """A deny with no forecast still appends the pre-check hint to the reason."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    clean_before = _CLEAN_FRAGMENT_BEFORE
    introduces_violation_after = "def short_helper() -> int:\n    print(1)\n    return 1\n"
    source_file = production_directory / "production_module.py"
    source_file.write_text(clean_before, encoding="utf-8")
    stdout = _run_main_with_edit_payload(
        str(source_file),
        clean_before,
        introduces_violation_after,
        monkeypatch,
        capsys,
    )
    deny_payload = json.loads(stdout)
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "--check" in reason, (
        f"every deny reason must carry the pre-check hint, got reason: {reason!r}"
    )
    quoted_script_path = f'"{_ENFORCER_SCRIPT_PATH.resolve()}"'
    assert quoted_script_path in reason, (
        f"hint must quote the script path for space-safe copy-paste, got reason: {reason!r}"
    )
    quoted_interpreter_path = f'"{sys.executable}"'
    assert quoted_interpreter_path in reason, (
        f"hint must name the running interpreter, quoted, got reason: {reason!r}"
    )


def test_forecast_skipped_when_edit_prior_is_unreconstructable(
    tmp_path_factory: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """An Edit whose old_string is absent from the file has no reliable prior to
    diff against, so the full-file forecast must not run: a pre-existing inline
    comment must never surface as an 'inline comment added' forecast entry that
    falsely claims an untouched comment will block future edits."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    commented_on_disk = "tally = 1  # pre-existing inline note\n"
    source_file = production_directory / "production_module.py"
    source_file.write_text(commented_on_disk, encoding="utf-8")
    absent_old = "def absent_function() -> int:\n    return 0\n"
    introduces_print_new = "def absent_function() -> int:\n    print(1)\n    return 2\n"
    stdout = _run_main_with_edit_payload(
        str(source_file),
        absent_old,
        introduces_print_new,
        monkeypatch,
        capsys,
    )
    deny_payload = json.loads(stdout)
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "pre-existing inline note" not in reason, (
        "an unreconstructable-prior Edit must not forecast a pre-existing comment "
        f"as a future blocker, got reason: {reason!r}"
    )


def test_forecast_omits_the_fragment_introduced_violation(
    tmp_path_factory: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """An Edit that introduces the file's only print() blocks on it without the
    forecast re-listing that same violation under its full-file line number."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    padding_helper = "def first_helper() -> int:\n    return 1\n"
    introduces_print_after = "def short_helper() -> int:\n    print(1)\n    return 1\n"
    on_disk_before = padding_helper + "\n" + _CLEAN_FRAGMENT_BEFORE
    source_file = production_directory / "production_module.py"
    source_file.write_text(on_disk_before, encoding="utf-8")
    stdout = _run_main_with_edit_payload(
        str(source_file),
        _CLEAN_FRAGMENT_BEFORE,
        introduces_print_after,
        monkeypatch,
        capsys,
    )
    deny_payload = json.loads(stdout)
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    blocking_section, _, forecast_section = reason.partition("FULL-FILE FORECAST")
    assert "Library print()" in blocking_section, (
        f"the fragment-introduced print must block, got reason: {reason!r}"
    )
    assert "Library print()" not in forecast_section, (
        f"the forecast must not re-list the fragment's own violation, got reason: {reason!r}"
    )


def test_precheck_missing_candidate_value_exits_two_with_usage() -> None:
    """A ``--check`` flag with no candidate path is a usage error: exit 2 with a
    usage line on stderr, never a silent clean verdict."""
    completed = _run_enforcer_cli(["--check"])
    assert completed.returncode == 2, (
        f"missing candidate value must exit 2, got: {completed.returncode}, "
        f"stdout: {completed.stdout!r}, stderr: {completed.stderr!r}"
    )
    assert "usage:" in completed.stderr, (
        f"missing candidate value must print usage on stderr, got: {completed.stderr!r}"
    )


def test_precheck_flag_shaped_candidate_value_exits_two_with_usage(
    tmp_path_factory: object,
) -> None:
    """``--check`` immediately followed by ``--as`` is a usage error rather than
    an attempt to read a file literally named ``--as``."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    target_path = str(production_directory / "production_module.py")
    completed = _run_enforcer_cli(["--check", "--as", target_path])
    assert completed.returncode == 2, (
        f"flag-shaped candidate value must exit 2, got: {completed.returncode}, "
        f"stdout: {completed.stdout!r}, stderr: {completed.stderr!r}"
    )
    assert "usage:" in completed.stderr, (
        f"flag-shaped candidate value must print usage on stderr, got: {completed.stderr!r}"
    )


def test_precheck_rejects_unrecognized_trailing_token_with_usage(
    tmp_path_factory: object,
) -> None:
    """A pre-check vector carrying a token beyond the supported
    ``--check <candidate> [--as <target>]`` shape is a usage error: an extra
    trailing token never silently passes as a clean verdict on the candidate."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("scripts")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(_CLEAN_CLI_SOURCE, encoding="utf-8")
    target_path = str(production_directory / "announce_cli.py")
    completed = _run_enforcer_cli(
        ["--check", str(candidate_file), "--as", target_path, "--unexpected"]
    )
    assert completed.returncode == 2, (
        f"a trailing unrecognized token must exit 2, got: {completed.returncode}, "
        f"stdout: {completed.stdout!r}, stderr: {completed.stderr!r}"
    )
    assert "usage:" in completed.stderr, (
        f"a trailing unrecognized token must print usage on stderr, got: {completed.stderr!r}"
    )


def test_precheck_strips_candidate_byte_order_mark_before_validation(
    tmp_path_factory: object,
) -> None:
    """A UTF-8 byte-order mark on the candidate must not hide AST-based
    violations: the candidate is judged exactly as its decoded content would
    arrive in a live tool payload."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(
        "\ufeff" + _VIOLATING_PRODUCTION_SOURCE, encoding="utf-8"
    )
    target_path = str(production_directory / "production_module.py")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 1, (
        f"a BOM candidate must fail exactly like its no-BOM twin, got: "
        f"{completed.returncode}, stdout: {completed.stdout!r}, "
        f"stderr: {completed.stderr!r}"
    )
    assert "process_data" in completed.stdout, (
        f"banned-prefix violation must appear on stdout, got: {completed.stdout!r}"
    )


def test_precheck_strips_every_leading_byte_order_mark_before_validation(
    tmp_path_factory: object,
) -> None:
    """Stacked byte-order marks must not hide AST-based violations: every
    leading mark is stripped, so a double-BOM candidate fails exactly like its
    clean-prefixed twin rather than silently skipping AST parsing."""
    staging_directory = getattr(tmp_path_factory, "mktemp")("staging")
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(
        "\ufeff\ufeff" + _VIOLATING_PRODUCTION_SOURCE, encoding="utf-8"
    )
    target_path = str(production_directory / "production_module.py")
    completed = _run_precheck(str(candidate_file), target_path)
    assert completed.returncode == 1, (
        f"a double-BOM candidate must fail exactly like its no-BOM twin, got: "
        f"{completed.returncode}, stdout: {completed.stdout!r}, "
        f"stderr: {completed.stderr!r}"
    )
    assert "process_data" in completed.stdout, (
        f"banned-prefix violation must appear on stdout, got: {completed.stdout!r}"
    )


def test_precheck_duplicate_flags_exit_two_with_usage() -> None:
    """A repeated ``--check`` or ``--as`` flag is an ambiguous vector: the
    pre-check rejects it with the usage exit code before reading any file,
    never silently judging only the first occurrence."""
    duplicate_check = _run_enforcer_cli(
        ["--check", "first_candidate.py", "--check", "second_candidate.py"]
    )
    assert duplicate_check.returncode == 2, (
        f"duplicate --check must exit 2, got: {duplicate_check.returncode}, "
        f"stdout: {duplicate_check.stdout!r}, stderr: {duplicate_check.stderr!r}"
    )
    assert "usage:" in duplicate_check.stderr, (
        f"duplicate --check must print usage on stderr, got: {duplicate_check.stderr!r}"
    )
    duplicate_as = _run_enforcer_cli(
        ["--check", "candidate.py", "--as", "first_target.py", "--as", "second_target.py"]
    )
    assert duplicate_as.returncode == 2, (
        f"duplicate --as must exit 2, got: {duplicate_as.returncode}, "
        f"stdout: {duplicate_as.stdout!r}, stderr: {duplicate_as.stderr!r}"
    )
    assert "usage:" in duplicate_as.stderr, (
        f"duplicate --as must print usage on stderr, got: {duplicate_as.stderr!r}"
    )
