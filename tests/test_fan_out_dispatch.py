"""Specifications for the fan-out dispatch script's pure filtering and formatting logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import fan_out_dispatch


def make_repo_fixture(
    full_name: str = "JonEcho/some-repo",
    archived: bool = False,
    has_push: bool = True,
    is_fork: bool = False,
) -> dict:
    owner_login = full_name.split("/")[0]
    return {
        "full_name": full_name,
        "name": full_name.split("/")[1],
        "owner": {"login": owner_login},
        "archived": archived,
        "fork": is_fork,
        "permissions": {"push": has_push, "pull": True},
    }


class TestIsTargetRepo:
    def should_include_jonecho_repos_with_push(self) -> None:
        repo = make_repo_fixture("JonEcho/my-project")

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_include_jlcmd_repos_with_push(self) -> None:
        repo = make_repo_fixture("jl-cmd/some-tool")

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_exclude_archived_repos(self) -> None:
        repo = make_repo_fixture("JonEcho/old-project", archived=True)

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_repos_without_push_permission(self) -> None:
        repo = make_repo_fixture("JonEcho/read-only", has_push=False)

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_the_source_repo_itself(self) -> None:
        repo = make_repo_fixture("jl-cmd/claude-code-config")

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_repos_owned_by_other_accounts(self) -> None:
        repo = make_repo_fixture("some-other-org/their-project")

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_include_forks_when_owner_is_jonecho(self) -> None:
        repo = make_repo_fixture("JonEcho/forked-repo", is_fork=True)

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_include_forks_when_owner_is_jlcmd(self) -> None:
        repo = make_repo_fixture("jl-cmd/forked-repo", is_fork=True)

        assert fan_out_dispatch.is_target_repo(repo) is True


class TestBuildSummaryTable:
    def should_include_header_row(self) -> None:
        table = fan_out_dispatch.build_summary_table({}, {}, {})

        assert "| Repo |" in table
        assert "| Dispatch Status |" in table
        assert "| Listener Conclusion |" in table

    def should_list_each_repo_in_its_own_row(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": "sent",
            "JonEcho/beta": "opted-out",
        }

        table = fan_out_dispatch.build_summary_table(dispatch_status_by_repo, {}, {})

        assert "JonEcho/alpha" in table
        assert "JonEcho/beta" in table

    def should_show_listener_conclusion_alongside_dispatch_status(self) -> None:
        dispatch_status_by_repo = {"JonEcho/alpha": "sent"}
        conclusion_by_repo = {"JonEcho/alpha": "success"}

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, conclusion_by_repo, {}
        )

        assert "success" in table

    def should_show_notes_when_provided(self) -> None:
        dispatch_status_by_repo = {"JonEcho/alpha": "sent"}
        notes_by_repo = {"JonEcho/alpha": "drift or sync error"}

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, {}, notes_by_repo
        )

        assert "drift or sync error" in table


class TestBuildStaleSection:
    def should_return_empty_string_when_no_stale_repos(self) -> None:
        assert fan_out_dispatch.build_stale_section([]) == ""

    def should_list_each_stale_repo(self) -> None:
        stale_repos = ["JonEcho/old-project", "jl-cmd/abandoned"]

        section = fan_out_dispatch.build_stale_section(stale_repos)

        assert "JonEcho/old-project" in section
        assert "jl-cmd/abandoned" in section

    def should_include_stale_section_heading(self) -> None:
        section = fan_out_dispatch.build_stale_section(["JonEcho/some-repo"])

        assert "Stale listeners" in section
