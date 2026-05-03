"""Tests for open_followup_copilot_pr.

Covers:
- branch name follows COPILOT_FOLLOWUP_BRANCH_TEMPLATE with the short SHA
- subprocess sequence: gh pr view (base ref) -> git fetch -> git switch -c -> git push -> gh pr create
- gh pr create uses --draft, --base, --head, --title, --body-file (per gh-body-file rule)
- the returned PR URL is the trimmed stdout from gh pr create
- subprocess errors propagate
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "open_followup_copilot_pr.py"
    spec = importlib.util.spec_from_file_location(
        "open_followup_copilot_pr", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


open_followup_copilot_pr_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def _scripted_subprocess_runs(
    *,
    base_ref_payload: str,
    new_pr_url: str,
) -> list[subprocess.CompletedProcess]:
    return [
        _completed(base_ref_payload),
        _completed(""),
        _completed(""),
        _completed(""),
        _completed(new_pr_url),
    ]


def test_should_build_branch_name_from_parent_number_and_short_sha(
    tmp_path: Path,
) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Item 1\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="https://github.com/acme/widget/pull/313\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeefcafe",
            findings_file=findings_file,
        )
    git_switch_argv = mock_run.call_args_list[2][0][0]
    expected_branch = "chore/copilot-followup-312-abc12345"
    assert expected_branch in git_switch_argv


def test_should_invoke_subprocess_call_sequence_in_documented_order(
    tmp_path: Path,
) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Item\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="https://github.com/acme/widget/pull/313\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeefcafe",
            findings_file=findings_file,
        )
    invoked_command_sequence = [
        each_call[0][0] for each_call in mock_run.call_args_list
    ]
    assert invoked_command_sequence[0][0:3] == ["gh", "pr", "view"]
    assert invoked_command_sequence[1][0:2] == ["git", "fetch"]
    assert invoked_command_sequence[2][0:3] == ["git", "switch", "-c"]
    assert invoked_command_sequence[3][0:2] == ["git", "push"]
    assert invoked_command_sequence[4][0:3] == ["gh", "pr", "create"]


def test_should_invoke_gh_pr_create_with_draft_and_body_file_flags(
    tmp_path: Path,
) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding A\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "develop"}),
        new_pr_url="https://github.com/acme/widget/pull/444\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeef",
            findings_file=findings_file,
        )
    pr_create_argv = mock_run.call_args_list[4][0][0]
    assert pr_create_argv[0:3] == ["gh", "pr", "create"]
    assert "--draft" in pr_create_argv
    assert "--base" in pr_create_argv
    assert "develop" in pr_create_argv
    assert "--head" in pr_create_argv
    assert "--title" in pr_create_argv
    assert "--body-file" in pr_create_argv
    body_file_argv = pr_create_argv[pr_create_argv.index("--body-file") + 1]
    assert body_file_argv == str(findings_file)


def test_should_render_pr_title_via_named_template_constant(tmp_path: Path) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="https://github.com/acme/widget/pull/513\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeef",
            findings_file=findings_file,
        )
    pr_create_argv = mock_run.call_args_list[4][0][0]
    title_index = pr_create_argv.index("--title")
    title_value = pr_create_argv[title_index + 1]
    assert title_value == "chore: address Copilot findings from PR #312"


def test_should_return_trimmed_pr_url(tmp_path: Path) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="  https://github.com/acme/widget/pull/313  \n",
    )
    with patch("subprocess.run", side_effect=payload_sequence):
        new_pr_url = open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeef",
            findings_file=findings_file,
        )
    assert new_pr_url == "https://github.com/acme/widget/pull/313"


def test_should_pass_repo_arg_to_gh_pr_view_for_base_ref(tmp_path: Path) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="https://github.com/acme/widget/pull/313\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeef",
            findings_file=findings_file,
        )
    pr_view_argv = mock_run.call_args_list[0][0][0]
    assert pr_view_argv[0:3] == ["gh", "pr", "view"]
    assert "--repo" in pr_view_argv
    repo_arg_value = pr_view_argv[pr_view_argv.index("--repo") + 1]
    assert repo_arg_value == "acme/widget"


def test_should_pass_repo_arg_to_gh_pr_create_for_followup_pr(
    tmp_path: Path,
) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding\n", encoding="utf-8")
    payload_sequence = _scripted_subprocess_runs(
        base_ref_payload=json.dumps({"baseRefName": "main"}),
        new_pr_url="https://github.com/acme/widget/pull/313\n",
    )
    with patch("subprocess.run", side_effect=payload_sequence) as mock_run:
        open_followup_copilot_pr_module.open_followup_copilot_pr(
            owner="acme",
            repo="widget",
            parent_number=312,
            head="abc12345deadbeef",
            findings_file=findings_file,
        )
    pr_create_argv = mock_run.call_args_list[4][0][0]
    assert pr_create_argv[0:3] == ["gh", "pr", "create"]
    assert "--repo" in pr_create_argv
    repo_arg_value = pr_create_argv[pr_create_argv.index("--repo") + 1]
    assert repo_arg_value == "acme/widget"


def test_should_raise_when_subprocess_fails(tmp_path: Path) -> None:
    findings_file = tmp_path / "findings.md"
    findings_file.write_text("- Finding\n", encoding="utf-8")
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            open_followup_copilot_pr_module.open_followup_copilot_pr(
                owner="acme",
                repo="widget",
                parent_number=312,
                head="abc12345",
                findings_file=findings_file,
            )
