"""Specifications for the AI rules sync listener script."""

import os
import subprocess
import urllib.error
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

import sync_ai_rules


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sync-ai-rules"
CANONICAL_BODY = (FIXTURE_DIR / "source_body.md").read_text(encoding="utf-8")
FAKE_SOURCE_COMMIT = "abc123def456"
FAKE_GITHUB_TOKEN = "ghp_fake_token_for_tests"
FAKE_GITHUB_REPOSITORY = "test-owner/test-repo"


@pytest.fixture
def git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Yields a fully initialized git work repo with a bare remote and cwd set to it."""
    bare_remote = tmp_path / "remote.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    subprocess.run(
        ["git", "init", "--bare", str(bare_remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "init", str(work_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(work_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(work_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=str(work_dir),
        check=True,
        capture_output=True,
    )
    readme = work_dir / "README.md"
    readme.write_text("Test repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."], cwd=str(work_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(work_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "--set-upstream", "origin", "HEAD:main"],
        cwd=str(work_dir),
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(str(work_dir))

    yield work_dir


@pytest.fixture
def sync_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sets environment variables required by sync_ai_rules.main()."""
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORY", FAKE_GITHUB_REPOSITORY)
    monkeypatch.setenv("SOURCE_COMMIT", FAKE_SOURCE_COMMIT)
    monkeypatch.setenv("RAW_URL", "https://example.com/fake-canonical")
    monkeypatch.setenv("FORCE_INITIAL_OVERWRITE", "false")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def count_commits(work_dir: Path) -> int:
    completed = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return int(completed.stdout.strip())


def run_sync_with_canonical_body(canonical_body: str = CANONICAL_BODY) -> int:
    with patch("sync_ai_rules.fetch_canonical_body", return_value=canonical_body):
        with patch("sync_ai_rules.open_github_issue"):
            with patch(
                "sync_ai_rules.find_existing_drift_issue", return_value=None
            ):
                with patch("sync_ai_rules.add_issue_comment"):
                    return sync_ai_rules.main()


class TestBuildSyncHeader:
    def should_include_start_and_end_markers(self) -> None:
        header = sync_ai_rules.build_sync_header(
            "deadbeef", "2024-01-01T00:00:00+00:00"
        )

        assert sync_ai_rules.SYNC_HEADER_START_MARKER in header
        assert sync_ai_rules.SYNC_HEADER_END_MARKER in header

    def should_embed_source_commit_in_header(self) -> None:
        header = sync_ai_rules.build_sync_header("abc123", "2024-01-01T00:00:00+00:00")

        assert "abc123" in header

    def should_embed_synced_at_timestamp_in_header(self) -> None:
        timestamp = "2024-06-15T12:30:00+00:00"

        header = sync_ai_rules.build_sync_header("abc123", timestamp)

        assert timestamp in header

    def should_embed_source_repo_and_file_path(self) -> None:
        header = sync_ai_rules.build_sync_header("abc123", "2024-01-01T00:00:00+00:00")

        assert sync_ai_rules.SOURCE_REPO in header
        assert sync_ai_rules.SOURCE_FILE_PATH in header


class TestStripSyncHeader:
    def should_return_none_when_start_marker_is_absent(self) -> None:
        content = "plain content without any sync markers\n"

        assert sync_ai_rules.strip_sync_header(content) is None

    def should_return_none_when_end_marker_is_absent(self) -> None:
        content = f"{sync_ai_rules.SYNC_HEADER_START_MARKER}\nno end marker\n"

        assert sync_ai_rules.strip_sync_header(content) is None

    def should_return_body_after_header_separator(self) -> None:
        body = "# Rules\n\nSome content here.\n"
        full_content = sync_ai_rules.build_destination_content(
            body, "abc123", "2024-01-01T00:00:00+00:00"
        )

        stripped = sync_ai_rules.strip_sync_header(full_content)

        assert stripped == body

    def should_roundtrip_with_build_destination_content(self) -> None:
        original_body = CANONICAL_BODY

        full_content = sync_ai_rules.build_destination_content(
            original_body, "sha1", "2024-01-01T00:00:00+00:00"
        )
        recovered_body = sync_ai_rules.strip_sync_header(full_content)

        assert recovered_body == original_body


class TestComputeSha256:
    def should_produce_consistent_hash_for_same_input(self) -> None:
        content = "deterministic input\n"

        first_hash = sync_ai_rules.compute_sha256(content)
        second_hash = sync_ai_rules.compute_sha256(content)

        assert first_hash == second_hash

    def should_produce_different_hashes_for_different_inputs(self) -> None:
        assert sync_ai_rules.compute_sha256("a\n") != sync_ai_rules.compute_sha256(
            "b\n"
        )

    def should_return_64_character_hex_string(self) -> None:
        sha = sync_ai_rules.compute_sha256("any content")

        assert len(sha) == 64
        assert all(character in "0123456789abcdef" for character in sha)


class TestSyncNoDestinationScenario:
    """Scenario: neither destination file exists — sync should create both."""

    def should_exit_zero_when_no_destinations_exist(
        self, git_repo: Path, sync_env: None
    ) -> None:
        exit_code = run_sync_with_canonical_body()

        assert exit_code == 0

    def should_create_copilot_instructions_file(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        copilot_path = git_repo / ".github" / "copilot-instructions.md"
        assert copilot_path.exists()

    def should_create_bugbot_file(self, git_repo: Path, sync_env: None) -> None:
        run_sync_with_canonical_body()

        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        assert bugbot_path.exists()

    def should_embed_canonical_body_in_each_destination(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        copilot_path = git_repo / ".github" / "copilot-instructions.md"
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"

        for destination in (copilot_path, bugbot_path):
            content = destination.read_text(encoding="utf-8")
            stripped_body = sync_ai_rules.strip_sync_header(content)
            assert stripped_body == CANONICAL_BODY

    def should_include_source_commit_in_destination_header(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        copilot_path = git_repo / ".github" / "copilot-instructions.md"
        assert FAKE_SOURCE_COMMIT in copilot_path.read_text(encoding="utf-8")

    def should_create_exactly_one_bot_commit(
        self, git_repo: Path, sync_env: None
    ) -> None:
        commits_before = count_commits(git_repo)
        run_sync_with_canonical_body()
        commits_after = count_commits(git_repo)

        assert commits_after == commits_before + 1

    def should_include_body_sha256_trailer_in_commit_message(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        completed = subprocess.run(
            ["git", "show", "--format=%B", "--no-patch", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        expected_sha = sync_ai_rules.compute_sha256(CANONICAL_BODY)
        assert (
            f"{sync_ai_rules.SYNC_BODY_SHA256_TRAILER_KEY}: {expected_sha}"
            in completed.stdout
        )


class TestSyncMatchingDestinationScenario:
    """Scenario: destinations already match canonical body — sync should be a no-op."""

    def should_exit_zero_when_destinations_are_current(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        exit_code = run_sync_with_canonical_body()

        assert exit_code == 0

    def should_create_no_new_commits_when_body_is_unchanged(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()
        commits_after_first_sync = count_commits(git_repo)

        run_sync_with_canonical_body()
        commits_after_second_sync = count_commits(git_repo)

        assert commits_after_second_sync == commits_after_first_sync


class TestSyncDriftScenario:
    """Scenario: a destination was manually edited after the last bot sync — sync should fail."""

    def should_exit_nonzero_when_drift_is_detected(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.write_text("Manually edited content.\n", encoding="utf-8")
        subprocess.run(
            ["git", "config", "user.name", "Human"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "human@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", str(bugbot_path)], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Manual edit"],
            check=True,
            capture_output=True,
        )

        exit_code = run_sync_with_canonical_body()

        assert exit_code != 0

    def should_not_modify_destinations_when_drift_is_detected(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        drifted_content = "Manually edited content.\n"
        bugbot_path.write_text(drifted_content, encoding="utf-8")
        subprocess.run(
            ["git", "config", "user.name", "Human"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "human@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", str(bugbot_path)], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Manual edit"],
            check=True,
            capture_output=True,
        )
        commits_before_drift_run = count_commits(git_repo)

        run_sync_with_canonical_body()

        assert bugbot_path.read_text(encoding="utf-8") == drifted_content
        assert count_commits(git_repo) == commits_before_drift_run

    def should_open_github_issue_when_drift_is_detected(
        self, git_repo: Path, sync_env: None
    ) -> None:
        run_sync_with_canonical_body()

        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.write_text("Manually edited content.\n", encoding="utf-8")
        subprocess.run(
            ["git", "config", "user.name", "Human"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "human@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", str(bugbot_path)], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Manual edit"],
            check=True,
            capture_output=True,
        )

        with patch("sync_ai_rules.fetch_canonical_body", return_value=CANONICAL_BODY):
            with patch("sync_ai_rules.open_github_issue") as mock_open_issue:
                with patch(
                    "sync_ai_rules.find_existing_drift_issue", return_value=None
                ):
                    with patch("sync_ai_rules.add_issue_comment"):
                        sync_ai_rules.main()

        mock_open_issue.assert_called_once()
        call_args = mock_open_issue.call_args
        assert ".cursor/BUGBOT.md" in call_args.args[2]


class TestOptOutSentinel:
    def should_exit_zero_without_syncing_when_sentinel_exists(
        self, git_repo: Path, sync_env: None
    ) -> None:
        sentinel_path = git_repo / ".github" / "sync-ai-rules.optout"
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.write_text("This repo is opted out.\n", encoding="utf-8")

        with patch("sync_ai_rules.fetch_canonical_body") as mock_fetch:
            exit_code = sync_ai_rules.main()

        assert exit_code == 0
        mock_fetch.assert_not_called()


class TestFirstSyncPolicyWithExistingContent:
    def should_fail_when_destination_has_human_content_and_no_force_flag(
        self, git_repo: Path, sync_env: None
    ) -> None:
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.parent.mkdir(parents=True, exist_ok=True)
        bugbot_path.write_text("Existing human content.\n", encoding="utf-8")

        exit_code = run_sync_with_canonical_body()

        assert exit_code != 0

    def should_succeed_when_force_initial_overwrite_is_true(
        self, git_repo: Path, sync_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.parent.mkdir(parents=True, exist_ok=True)
        bugbot_path.write_text("Existing human content.\n", encoding="utf-8")
        monkeypatch.setenv("FORCE_INITIAL_OVERWRITE", "true")

        exit_code = run_sync_with_canonical_body()

        assert exit_code == 0


class TestEmptyEnvVarFallback:
    """workflow_dispatch sets env vars to empty strings when client_payload is absent."""

    def should_use_default_raw_url_when_env_var_is_empty(
        self, git_repo: Path, sync_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAW_URL", "")
        monkeypatch.setenv("SOURCE_COMMIT", "")

        with patch(
            "sync_ai_rules.fetch_canonical_body", return_value=CANONICAL_BODY
        ) as mock_fetch:
            with patch("sync_ai_rules.open_github_issue"):
                with patch(
                    "sync_ai_rules.find_existing_drift_issue", return_value=None
                ):
                    with patch("sync_ai_rules.add_issue_comment"):
                        exit_code = sync_ai_rules.main()

        assert exit_code == 0
        mock_fetch.assert_called_once_with(sync_ai_rules.DEFAULT_RAW_URL)

    def should_use_unknown_placeholder_when_source_commit_is_empty(
        self, git_repo: Path, sync_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOURCE_COMMIT", "")

        run_sync_with_canonical_body()

        copilot_path = git_repo / ".github" / "copilot-instructions.md"
        header_content = copilot_path.read_text(encoding="utf-8")
        assert sync_ai_rules.UNKNOWN_COMMIT_PLACEHOLDER in header_content

    def should_treat_empty_force_initial_overwrite_as_false(
        self, git_repo: Path, sync_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.parent.mkdir(parents=True, exist_ok=True)
        bugbot_path.write_text("Existing human content.\n", encoding="utf-8")
        monkeypatch.setenv("FORCE_INITIAL_OVERWRITE", "")

        exit_code = run_sync_with_canonical_body()

        assert exit_code != 0


class TestGitignoreWildcard:
    """Some target repos have a bare '*' pattern in .gitignore that would swallow new files."""

    def should_succeed_when_gitignore_excludes_everything(
        self, git_repo: Path, sync_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gitignore_path = git_repo / ".gitignore"
        gitignore_path.write_text("*\n!.gitignore\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=str(git_repo),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add permissive gitignore"],
            cwd=str(git_repo),
            check=True,
            capture_output=True,
        )
        monkeypatch.setenv("FORCE_INITIAL_OVERWRITE", "true")

        exit_code = run_sync_with_canonical_body()

        assert exit_code == 0
        copilot_path = git_repo / ".github" / "copilot-instructions.md"
        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        assert copilot_path.exists()
        assert bugbot_path.exists()


class TestStripSyncHeaderMarkerOrder:
    """When the end marker appears before the start marker, strip should return None."""

    def should_return_none_when_end_marker_precedes_start_marker(self) -> None:
        content = (
            f"{sync_ai_rules.SYNC_HEADER_END_MARKER}\n"
            f"body in between\n"
            f"{sync_ai_rules.SYNC_HEADER_START_MARKER}\n"
        )

        assert sync_ai_rules.strip_sync_header(content) is None


class TestFindLastBotCommitUsesCommitterEmail:
    """Drift detection uses the committer email, not the author email."""

    def should_detect_bot_commit_when_author_is_human_and_committer_is_bot(
        self, git_repo: Path
    ) -> None:
        destination_path = ".github/copilot-instructions.md"
        full_path = git_repo / destination_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text("body content\n", encoding="utf-8")

        env_with_committer_override = {
            **os.environ,
            "GIT_COMMITTER_NAME": sync_ai_rules.BOT_AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": sync_ai_rules.BOT_AUTHOR_EMAIL,
            "GIT_AUTHOR_NAME": "Human Contributor",
            "GIT_AUTHOR_EMAIL": "human@example.com",
        }
        subprocess.run(
            ["git", "add", destination_path],
            cwd=str(git_repo),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "sync commit with bot committer"],
            cwd=str(git_repo),
            check=True,
            capture_output=True,
            env=env_with_committer_override,
        )

        bot_commit_hash = sync_ai_rules.find_last_bot_commit_hash(destination_path)

        assert bot_commit_hash is not None


class TestCrlfLineEndingsRoundTrip:
    """CRLF line endings in existing content must not break SHA comparison or header strip."""

    def should_strip_sync_header_when_content_has_crlf_endings(self) -> None:
        lf_content = sync_ai_rules.build_destination_content(
            "# Body\n\nLine one.\n", "abc", "2024-01-01T00:00:00+00:00"
        )
        crlf_content = lf_content.replace("\n", "\r\n")

        stripped = sync_ai_rules.strip_sync_header(crlf_content)

        assert stripped == "# Body\n\nLine one.\n"
        assert "\r" not in stripped

    def should_produce_same_sha_for_lf_and_crlf_versions(self) -> None:
        lf_body = "# Body\n\nLine one.\n"
        crlf_body = lf_body.replace("\n", "\r\n")

        assert sync_ai_rules.compute_sha256(lf_body) == sync_ai_rules.compute_sha256(
            crlf_body
        )


class TestWhitespaceOnlyDestinationWarning:
    """Whitespace-only file with prior bot commit should warn and continue."""

    def should_log_warning_when_destination_is_whitespace_only_after_bot_history(
        self,
        git_repo: Path,
        sync_env: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run_sync_with_canonical_body()

        bugbot_path = git_repo / ".cursor" / "BUGBOT.md"
        bugbot_path.write_text("   \n\n", encoding="utf-8")
        capsys.readouterr()

        run_sync_with_canonical_body()

        captured = capsys.readouterr()
        assert "lost its sync header" in captured.err
        assert ".cursor/BUGBOT.md" in captured.err


def make_urlopen_context_manager(
    status: int = 201, body_bytes: bytes = b"{}"
) -> MagicMock:
    fake_response = MagicMock()
    fake_response.status = status
    fake_response.read.return_value = body_bytes
    context_manager = MagicMock()
    context_manager.__enter__.return_value = fake_response
    context_manager.__exit__.return_value = False
    return context_manager


class TestDriftReportCombinesDestinationsIntoSingleIssue:
    """When two destinations drift in one run, only one issue should be opened."""

    def should_open_exactly_one_issue_when_both_destinations_drift(self) -> None:
        all_errors: list[sync_ai_rules.DriftError] = [
            sync_ai_rules.DriftError(
                destination_path=".github/copilot-instructions.md",
                message="Drift in copilot file",
            ),
            sync_ai_rules.DriftError(
                destination_path=".cursor/BUGBOT.md",
                message="Drift in bugbot file",
            ),
        ]

        with patch.object(
            sync_ai_rules, "find_existing_drift_issue", return_value=None
        ) as mock_find:
            with patch.object(sync_ai_rules, "open_github_issue") as mock_open_issue:
                with patch.object(
                    sync_ai_rules, "add_issue_comment"
                ) as mock_add_comment:
                    sync_ai_rules.report_drift_errors(
                        all_errors, FAKE_GITHUB_TOKEN, FAKE_GITHUB_REPOSITORY
                    )

        assert mock_find.call_count == 1
        assert mock_open_issue.call_count == 1
        assert mock_add_comment.call_count == 0

    def should_add_exactly_one_comment_when_existing_issue_exists(self) -> None:
        all_errors: list[sync_ai_rules.DriftError] = [
            sync_ai_rules.DriftError(
                destination_path=".github/copilot-instructions.md",
                message="Drift in copilot file",
            ),
            sync_ai_rules.DriftError(
                destination_path=".cursor/BUGBOT.md",
                message="Drift in bugbot file",
            ),
        ]

        with patch.object(
            sync_ai_rules, "find_existing_drift_issue", return_value=42
        ):
            with patch.object(sync_ai_rules, "open_github_issue") as mock_open_issue:
                with patch.object(
                    sync_ai_rules, "add_issue_comment"
                ) as mock_add_comment:
                    sync_ai_rules.report_drift_errors(
                        all_errors, FAKE_GITHUB_TOKEN, FAKE_GITHUB_REPOSITORY
                    )

        assert mock_open_issue.call_count == 0
        assert mock_add_comment.call_count == 1


class TestCommitAndPushSyncAbortsRebaseOnConflict:
    """When push fails and retries, rebase --abort must run before the next attempt."""

    def should_invoke_rebase_abort_between_push_attempts(self) -> None:
        recorded_commands: list[list[str]] = []

        def fake_run(
            command_args: list[str],
            *runner_args: object,
            **runner_kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            recorded_commands.append(command_args)
            if command_args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return subprocess.CompletedProcess(
                    command_args, 0, stdout="main\n", stderr=""
                )
            is_push_command = command_args[:2] == ["git", "push"]
            push_attempt_index = sum(
                1 for recorded in recorded_commands[:-1] if recorded[:2] == ["git", "push"]
            )
            if is_push_command and push_attempt_index == 0:
                raise subprocess.CalledProcessError(1, command_args)
            return subprocess.CompletedProcess(
                command_args, 0, stdout="", stderr=""
            )

        with patch("sync_ai_rules.subprocess.run", side_effect=fake_run):
            with patch("sync_ai_rules.time.sleep"):
                sync_ai_rules.commit_and_push_sync(
                    [".github/copilot-instructions.md"], "abc", "sha"
                )

        rebase_abort_positions = [
            each_index
            for each_index, command in enumerate(recorded_commands)
            if command[:3] == ["git", "rebase", "--abort"]
        ]
        push_positions = [
            each_index
            for each_index, command in enumerate(recorded_commands)
            if command[:2] == ["git", "push"]
        ]
        assert len(push_positions) >= 2
        assert rebase_abort_positions, "expected at least one git rebase --abort call between push attempts"
        assert len(rebase_abort_positions) >= len(push_positions) - 1
        for each_index in range(len(push_positions) - 1):
            assert any(
                push_positions[each_index] < abort_position < push_positions[each_index + 1]
                for abort_position in rebase_abort_positions
            )


class TestOpenGithubIssueRaisesOnNonCreatedStatus:
    """Issue creation must raise RuntimeError when status is anything other than 201."""

    def should_raise_runtime_error_when_status_is_ok_instead_of_created(self) -> None:
        fake_context = make_urlopen_context_manager(status=sync_ai_rules.HTTP_STATUS_OK)

        with patch("urllib.request.urlopen", return_value=fake_context):
            with pytest.raises(RuntimeError):
                sync_ai_rules.open_github_issue(
                    FAKE_GITHUB_TOKEN,
                    FAKE_GITHUB_REPOSITORY,
                    "title",
                    "body",
                )


class TestCanonicalBodyMinimumLengthFloor:
    """Short canonical bodies must cause main() to exit with a nonzero code."""

    def should_exit_nonzero_when_canonical_body_is_too_short(
        self, git_repo: Path, sync_env: None
    ) -> None:
        with patch("sync_ai_rules.fetch_canonical_body", return_value="short\n"):
            with patch("sync_ai_rules.find_existing_drift_issue", return_value=None):
                with patch("sync_ai_rules.add_issue_comment"):
                    with patch("sync_ai_rules.open_github_issue"):
                        exit_code = sync_ai_rules.main()

        assert exit_code == 1


class TestFetchCanonicalBodyRetry:
    """The fetch retry loop handles transient failures with bounded attempts."""

    def should_return_body_when_first_attempt_succeeds(self) -> None:
        fake_context = make_urlopen_context_manager(
            status=sync_ai_rules.HTTP_STATUS_OK, body_bytes=b"full canonical body"
        )
        with patch("urllib.request.urlopen", return_value=fake_context) as mock_urlopen:
            body_text = sync_ai_rules.fetch_canonical_body("https://example.com/raw")

        assert body_text == "full canonical body"
        assert mock_urlopen.call_count == 1

    def should_retry_then_succeed_when_first_attempt_fails(self) -> None:
        fake_ok_context = make_urlopen_context_manager(
            status=sync_ai_rules.HTTP_STATUS_OK, body_bytes=b"full canonical body"
        )
        with patch(
            "urllib.request.urlopen",
            side_effect=[urllib.error.URLError("first"), fake_ok_context],
        ) as mock_urlopen:
            with patch("sync_ai_rules.time.sleep"):
                body_text = sync_ai_rules.fetch_canonical_body(
                    "https://example.com/raw"
                )

        assert body_text == "full canonical body"
        assert mock_urlopen.call_count == 2

    def should_raise_after_max_attempts(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=[urllib.error.URLError("x")]
            * sync_ai_rules.FETCH_CANONICAL_MAX_ATTEMPTS,
        ) as mock_urlopen:
            with patch("sync_ai_rules.time.sleep"):
                with pytest.raises(urllib.error.URLError):
                    sync_ai_rules.fetch_canonical_body("https://example.com/raw")

        assert mock_urlopen.call_count == sync_ai_rules.FETCH_CANONICAL_MAX_ATTEMPTS
