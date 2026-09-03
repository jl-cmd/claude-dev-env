"""Tests for git and GitHub validation checks."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from .git_checks import (
    Violation,
    check_draft_pr_state,
    main,
)


class TestDraftPrState:
    """Test that PR is in draft state when pushing review fixes."""

    @patch("validators.git_checks.subprocess.run")
    def test_no_pr_returns_empty(self, mock_run: MagicMock) -> None:
        """When no PR exists, check should return empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")

        violations = check_draft_pr_state()

        assert violations == []

    @patch("validators.git_checks.subprocess.run")
    def test_draft_pr_passes(self, mock_run: MagicMock) -> None:
        """Draft PR should pass."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"number": 123, "isDraft": true}]',
            stderr=""
        )

        violations = check_draft_pr_state()

        assert violations == []

    @patch("validators.git_checks.subprocess.run")
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

    @patch("validators.git_checks.subprocess.run")
    def test_gh_cli_not_available_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI not available, should return empty (warning, not failure)."""
        mock_run.side_effect = FileNotFoundError("gh not found")

        violations = check_draft_pr_state()

        assert violations == []

    @patch("validators.git_checks.subprocess.run")
    def test_gh_timeout_returns_empty(self, mock_run: MagicMock) -> None:
        """When gh CLI times out, should return empty (warning, not failure)."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh", "pr", "list"], timeout=30)

        violations = check_draft_pr_state()

        assert violations == []


class TestMain:
    """Test main function integration."""

    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_no_violations_exits_zero(
        self,
        mock_draft: MagicMock,
        capsys,
    ) -> None:
        """main() should exit 0 when no violations found."""
        mock_draft.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    @patch("validators.git_checks.check_draft_pr_state")
    def test_main_prints_violations_without_file_line(
        self,
        mock_draft: MagicMock,
        capsys,
    ) -> None:
        """main() should print git violations without file:line: prefix."""
        mock_draft.return_value = [
            Violation(file="", line=0, message="PR must be in draft state")
        ]

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == "PR must be in draft state\n"
        assert ":0:" not in captured.out
