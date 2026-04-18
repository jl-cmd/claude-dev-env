"""Tests for git and GitHub validation checks."""

import json
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from .git_checks import (
    Violation,
    check_single_commit_when_pr_exists,
    check_draft_pr_state,
    main,
)


class TestSingleCommitWhenPrExists:
    """Test that PR branches have exactly 1 commit ahead of base."""

    @patch("git_checks.subprocess.run")
    def test_no_pr_returns_empty(self, mock_run: MagicMock) -> None:
        """When no PR exists, check should return empty list."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_single_commit_ahead_passes(self, mock_run: MagicMock) -> None:
        """Exactly 1 commit ahead should pass."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="1", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_zero_commits_ahead_fails(self, mock_run: MagicMock) -> None:
        """Zero commits ahead should fail."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="0", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert len(violations) == 1
        assert violations[0].file == ""
        assert violations[0].line == 0
        assert "exactly 1 commit" in violations[0].message
        assert "0 commits" in violations[0].message

    @patch("git_checks.subprocess.run")
    def test_multiple_commits_ahead_fails(self, mock_run: MagicMock) -> None:
        """More than 1 commit ahead should fail."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="3", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert len(violations) == 1
        assert "exactly 1 commit" in violations[0].message
        assert "3 commits" in violations[0].message

    @patch("git_checks.subprocess.run")
    def test_gh_cli_not_available_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI not available, should return empty (warning, not failure)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            FileNotFoundError("gh not found"),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_git_not_available_returns_empty(self, mock_run: MagicMock) -> None:
        """When git not available, should return empty."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            FileNotFoundError("git not found"),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_extracts_base_branch_from_pr_info(self, mock_run: MagicMock) -> None:
        """Should extract base branch name from gh pr list JSON output, falling back to main when absent."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "develop", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="2", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert len(violations) == 1
        mock_run.assert_any_call(
            ["git", "rev-list", "--count", "develop..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        mock_run.reset_mock()
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="2", stderr=""),
        ]

        fallback_violations = check_single_commit_when_pr_exists()

        assert len(fallback_violations) == 1
        assert "main" in fallback_violations[0].message
        mock_run.assert_any_call(
            ["git", "rev-list", "--count", "main..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

    @patch("git_checks.subprocess.run")
    def test_non_numeric_commit_count_returns_empty(self, mock_run: MagicMock) -> None:
        """When git rev-list returns non-numeric output, should return empty."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="not a number\n", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_gh_timeout_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI times out, should return empty (warning, not failure)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            subprocess.TimeoutExpired(cmd=["gh", "pr", "list"], timeout=30),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_git_timeout_returns_empty(self, mock_run: MagicMock) -> None:
        """When git times out, should return empty (warning, not failure)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            subprocess.TimeoutExpired(cmd=["git", "rev-list"], timeout=30),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_passes_resolved_branch_name_to_gh(self, mock_run: MagicMock) -> None:
        """gh pr list must receive the resolved branch name, never the literal 'HEAD'."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/my-branch\n", stderr=""),
            MagicMock(returncode=0, stdout='[{"baseRefName": "main", "number": 123}]', stderr=""),
            MagicMock(returncode=0, stdout="1", stderr=""),
        ]

        check_single_commit_when_pr_exists()

        mock_run.assert_any_call(
            ["gh", "pr", "list", "--head", "feature/my-branch", "--json", "baseRefName,number"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

    @patch("git_checks.subprocess.run")
    def test_unresolved_branch_returns_empty(self, mock_run: MagicMock) -> None:
        """When current branch cannot be resolved, should return empty."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="\n", stderr=""),
        ]

        violations = check_single_commit_when_pr_exists()

        assert violations == []
        mock_run.assert_called_once()


class TestDraftPrState:
    """Test that PR is in draft state when pushing review fixes."""

    @patch("git_checks.subprocess.run")
    def test_no_pr_returns_empty(self, mock_run: MagicMock) -> None:
        """When no PR exists, check should return empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")

        violations = check_draft_pr_state()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_draft_pr_passes(self, mock_run: MagicMock) -> None:
        """Draft PR should pass."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"number": 123, "isDraft": true}]',
            stderr=""
        )

        violations = check_draft_pr_state()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_non_draft_pr_fails(self, mock_run: MagicMock) -> None:
        """Non-draft PR should fail."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"number": 123, "isDraft": false}]',
            stderr=""
        )

        violations = check_draft_pr_state()

        assert len(violations) == 1
        assert violations[0].file == ""
        assert violations[0].line == 0
        assert "draft" in violations[0].message.lower()
        assert "gh pr ready --undo" in violations[0].message

    @patch("git_checks.subprocess.run")
    def test_gh_cli_not_available_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI not available, should return empty (warning, not failure)."""
        mock_run.side_effect = FileNotFoundError("gh not found")

        violations = check_draft_pr_state()

        assert violations == []

    @patch("git_checks.subprocess.run")
    def test_gh_timeout_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI times out, should return empty (warning, not failure)."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh", "pr", "list"], timeout=30)

        violations = check_draft_pr_state()

        assert violations == []


class TestMain:
    """Test main function integration."""

    @patch("validators.git_checks.check_single_commit_when_pr_exists")
    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_no_violations_exits_zero(
        self,
        mock_draft: MagicMock,
        mock_commit: MagicMock,
        capsys,
    ) -> None:
        """main() should exit 0 when no violations found."""
        mock_commit.return_value = []
        mock_draft.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    @patch("validators.git_checks.check_single_commit_when_pr_exists")
    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_with_violations_exits_one(
        self,
        mock_draft: MagicMock,
        mock_commit: MagicMock,
        capsys,
    ) -> None:
        """main() should exit 1 and print violations when found."""
        mock_commit.return_value = [
            Violation(file="", line=0, message="Branch has 3 commits ahead")
        ]
        mock_draft.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Branch has 3 commits ahead" in captured.out

    @patch("validators.git_checks.check_single_commit_when_pr_exists")
    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_prints_violations_without_file_line(
        self,
        mock_draft: MagicMock,
        mock_commit: MagicMock,
        capsys,
    ) -> None:
        """main() should print git violations without file:line: prefix."""
        mock_commit.return_value = []
        mock_draft.return_value = [
            Violation(file="", line=0, message="PR must be in draft state")
        ]

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == "PR must be in draft state\n"
        assert ":0:" not in captured.out

    @patch("validators.git_checks.check_single_commit_when_pr_exists")
    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_prints_all_violations(
        self,
        mock_draft: MagicMock,
        mock_commit: MagicMock,
        capsys,
    ) -> None:
        """main() should print all violations."""
        mock_commit.return_value = [
            Violation(file="", line=0, message="Branch has 2 commits")
        ]
        mock_draft.return_value = [
            Violation(file="", line=0, message="PR not in draft")
        ]

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Branch has 2 commits" in captured.out
        assert "PR not in draft" in captured.out
