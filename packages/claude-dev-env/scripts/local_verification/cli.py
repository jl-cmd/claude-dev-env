from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never, TextIO

scripts_directory = Path(__file__).resolve().parents[1]
if str(scripts_directory) not in sys.path:
    sys.path.insert(0, str(scripts_directory))

from local_verification.config import (
    CLI_AGGREGATE_MESSAGE_TEMPLATE,
    CLI_ELIGIBILITY_MESSAGE_TEMPLATE,
    CLI_FAILURE_MESSAGE_TEMPLATE,
    CLI_REPORT_MESSAGE_TEMPLATE,
    CLI_REVISION_MESSAGE_TEMPLATE,
    CLI_START_MESSAGE_TEMPLATE,
    INCOMPLETE_EXIT_CODE,
    INVALID_INPUT_EXIT_CODE,
    PASSED_STATUS,
    REPORT_NEWLINE,
    UNRESOLVED_REVISION,
)
from local_verification.manifest import ManifestRunFatal, load_manifest
from local_verification.model import VerificationManifest, VerificationReport
from local_verification.runner import run_verification


class _VerificationArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ManifestRunFatal(message)


def main(
    all_arguments: Sequence[str],
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run the local verification manifest.
    Args:
        all_arguments: Command arguments.
    Returns:
        The verifier exit code.
    """
    parser = _build_parser()
    try:
        parsed_arguments = parser.parse_args(all_arguments)
    except ManifestRunFatal as error:
        stderr.write(f"{error}{REPORT_NEWLINE}")
        return INVALID_INPUT_EXIT_CODE
    report_path = Path(parsed_arguments.output)
    if not _clear_previous_report(report_path, stderr):
        return INCOMPLETE_EXIT_CODE
    _write_progress(stdout, CLI_START_MESSAGE_TEMPLATE.format(report_path=report_path))
    manifest = _load_manifest_for_cli(parsed_arguments.manifest, stderr)
    if manifest is None:
        return INVALID_INPUT_EXIT_CODE
    report = _run_manifest_verification(manifest, parsed_arguments, stdout, stderr)
    if report is None:
        return INCOMPLETE_EXIT_CODE
    _write_report_summary(report, report_path, stdout, stderr)
    return report.exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = _VerificationArgumentParser(prog="cde verify", add_help=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repo", dest="repository", required=True)
    parser.add_argument("--base", dest="base_revision", required=True)
    parser.add_argument("--output", required=True)
    return parser


def _run_manifest_verification(
    manifest: VerificationManifest,
    parsed_arguments: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
) -> VerificationReport | None:
    try:
        return run_verification(
            manifest,
            Path(parsed_arguments.repository),
            parsed_arguments.base_revision,
            Path(parsed_arguments.output),
            progress_callback=lambda progress_message: _write_progress(
                stdout, progress_message
            ),
        )
    except (OSError, ValueError) as error:
        stderr.write(f"{error}{REPORT_NEWLINE}")
        return None


def _clear_previous_report(report_path: Path, stderr: TextIO) -> bool:
    try:
        report_path.unlink(missing_ok=True)
    except OSError as error:
        stderr.write(f"{error}{REPORT_NEWLINE}")
        return False
    return True


def _write_progress(progress_stream: TextIO, progress_message: str) -> None:
    progress_stream.write(f"{progress_message}{REPORT_NEWLINE}")
    progress_stream.flush()


def _write_report_summary(
    report: VerificationReport,
    report_path: Path,
    stdout: TextIO,
    stderr: TextIO,
) -> None:
    _write_progress(
        stdout, CLI_AGGREGATE_MESSAGE_TEMPLATE.format(status=report.aggregate_status)
    )
    _write_progress(
        stdout,
        CLI_REVISION_MESSAGE_TEMPLATE.format(
            head=_format_revision(report.head_revision),
            base=_format_revision(report.base_revision),
        ),
    )
    _write_progress(
        stdout,
        CLI_ELIGIBILITY_MESSAGE_TEMPLATE.format(
            worktree_clean=str(report.worktree_clean).lower(),
            inputs_unchanged=str(report.inputs_unchanged).lower(),
            publishable=str(report.publishable).lower(),
        ),
    )
    _write_progress(stdout, CLI_REPORT_MESSAGE_TEMPLATE.format(report_path=report_path))
    if report.aggregate_status != PASSED_STATUS:
        stderr.write(
            f"{CLI_FAILURE_MESSAGE_TEMPLATE.format(status=report.aggregate_status)}{REPORT_NEWLINE}"
        )


def _format_revision(revision: str | None) -> str:
    return revision or UNRESOLVED_REVISION


def _load_manifest_for_cli(
    manifest_name: str, stderr: TextIO
) -> VerificationManifest | None:
    try:
        return load_manifest(Path(manifest_name))
    except (ManifestRunFatal, OSError) as error:
        stderr.write(f"{error}{REPORT_NEWLINE}")
        return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
