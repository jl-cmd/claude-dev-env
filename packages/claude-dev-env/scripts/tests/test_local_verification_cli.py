from __future__ import annotations

import io
import json
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from local_verification.cli import main


def _write_failure_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "fails",
                        "argv": [sys.executable, "-c", "raise SystemExit(4)"],
                        "cwd": ".",
                        "timeout_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _run_failure_cli(tmp_path: Path) -> tuple[int, str, str, Path]:
    manifest_path = _write_failure_manifest(tmp_path)
    output_path = tmp_path / "verification.json"
    standard_output = io.StringIO()
    standard_error = io.StringIO()
    exit_code = main(
        [
            "--manifest",
            str(manifest_path),
            "--repo",
            str(tmp_path),
            "--base",
            "base-sha",
            "--output",
            str(output_path),
        ],
        stdout=standard_output,
        stderr=standard_error,
    )
    return exit_code, standard_output.getvalue(), standard_error.getvalue(), output_path


def test_cli_writes_json_and_returns_failure_code(tmp_path: Path) -> None:
    exit_code, standard_output, standard_error, output_path = _run_failure_cli(tmp_path)

    assert exit_code == 1
    assert "check start: fails" in standard_output
    assert "aggregate: failed" in standard_output
    assert "revision: head=unresolved base=unresolved" in standard_output
    assert (
        "eligibility: clean=false unchanged=false publishable=false" in standard_output
    )
    assert f"report: {output_path}" in standard_output
    assert "verification failed" in standard_error
    assert (
        json.loads(output_path.read_text(encoding="utf-8"))["aggregate"]["status"]
        == "failed"
    )


def test_cli_rejects_zero_checks_without_writing_success(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"version": 1, "checks": []}), encoding="utf-8")
    output_path = tmp_path / "verification.json"
    output_path.write_text(json.dumps({"publishable": True}), encoding="utf-8")

    exit_code = main(
        [
            "--manifest",
            str(manifest_path),
            "--repo",
            str(tmp_path),
            "--base",
            "base-sha",
            "--output",
            str(output_path),
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert exit_code == 2
    assert not output_path.exists()
