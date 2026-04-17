"""Specifications for the AI rules sync listener script."""

import subprocess
from pathlib import Path
from typing import Generator
from unittest.mock import patch

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
