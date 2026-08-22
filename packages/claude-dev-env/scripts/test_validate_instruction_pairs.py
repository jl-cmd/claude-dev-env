import subprocess
from pathlib import Path

from validate_instruction_pairs import validate_repository


def read_workflow(workflow_filename: str) -> str:
    workflow_path = (
        Path(__file__).resolve().parents[3]
        / ".github"
        / "workflows"
        / workflow_filename
    )
    return workflow_path.read_text(encoding="utf-8")


def initialize_repository(repository_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=repository_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Instruction tests"],
        cwd=repository_root,
        check=True,
    )


def stage_instruction_files(repository_root: Path) -> None:
    subprocess.run(["git", "add", "AGENTS.md", "CLAUDE.md"], cwd=repository_root, check=True)


def test_exact_import_passes(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    stage_instruction_files(tmp_path)

    assert validate_repository(tmp_path) == []


def test_claude_context_fails_exact_import_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n\nExtra context\n")
    stage_instruction_files(tmp_path)

    all_errors = validate_repository(tmp_path)

    assert any("exactly import" in each_error for each_error in all_errors)


def test_nearest_ancestor_import_passes(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    nested_directory = tmp_path / ".claude"
    nested_directory.mkdir()
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (nested_directory / "CLAUDE.md").write_bytes(b"@../AGENTS.md\n")
    subprocess.run(["git", "add", "AGENTS.md", ".claude/CLAUDE.md"], cwd=tmp_path, check=True)

    assert validate_repository(tmp_path) == []


def test_crlf_import_fails_line_ending_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\r\n")
    stage_instruction_files(tmp_path)

    all_errors = validate_repository(tmp_path)

    assert any("exactly import" in each_error for each_error in all_errors)


def test_executable_import_fails_git_mode_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    stage_instruction_files(tmp_path)
    subprocess.run(
        ["git", "update-index", "--chmod=+x", "CLAUDE.md"],
        cwd=tmp_path,
        check=True,
    )

    all_errors = validate_repository(tmp_path)

    assert any("Git mode 100644" in each_error for each_error in all_errors)


def test_untracked_import_fails_tracking_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")

    all_errors = validate_repository(tmp_path)

    assert any("Git mode 100644" in each_error for each_error in all_errors)


def test_pull_request_target_trigger_is_unconditional() -> None:
    workflow_text = read_workflow("validate-instruction-pairs.yml")

    assert "  pull_request:\n  pull_request_target:\n  push:\n" in workflow_text


def test_instruction_pairs_status_context_stays_exact() -> None:
    workflow_text = read_workflow("validate-instruction-pairs.yml")
    reusable_workflow_text = read_workflow("instruction-pairs-reusable.yml")
    caller_job_body = workflow_text.split("  instruction-pairs:\n", 1)[1]
    caller_job_before_uses = caller_job_body.split("uses:", 1)[0]

    assert (
        "  instruction-pairs:\n"
        "    uses: ./.github/workflows/instruction-pairs-reusable.yml\n"
        "    with:\n"
        in workflow_text
    )
    assert "      validator-ref: ${{ github.sha }}\n" in workflow_text
    assert (
        "      checkout-ref: ${{ github.event.pull_request.head.sha || github.sha }}\n"
        in workflow_text
    )
    assert "if:" not in caller_job_before_uses
    assert "  instruction-pairs:\n    name: instruction-pairs\n" in reusable_workflow_text


def test_release_please_short_circuit_exists_in_workflow() -> None:
    workflow_text = read_workflow("validate-instruction-pairs.yml")
    reusable_workflow_text = read_workflow("instruction-pairs-reusable.yml")

    assert "skip-validation:" in reusable_workflow_text
    assert "type: boolean" in reusable_workflow_text
    assert "default: false" in reusable_workflow_text
    assert "if: ${{ inputs.skip-validation }}" in reusable_workflow_text
    assert "if: ${{ !inputs.skip-validation }}" in reusable_workflow_text
    assert (
        "Skipping instruction-pairs tree validation for a release-please pull request."
        in reusable_workflow_text
    )
    assert "ref: ${{ inputs.checkout-ref }}" in reusable_workflow_text
    assert "release-please--" in workflow_text
    assert "chore(.*): release " in workflow_text
    assert "autorelease: pending" in workflow_text
    assert "skip-validation:" in workflow_text
