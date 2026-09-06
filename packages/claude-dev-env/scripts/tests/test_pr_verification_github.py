from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from pr_verification.github import (
    GitHubApi,
    GitHubAppAuthenticator,
    GitHubError,
    HttpReply,
)
from pr_verification.model import RepositorySettings, StatusState


class RecordingRequester:
    def __init__(self, all_replies: list[HttpReply]) -> None:
        self.all_replies = all_replies
        self.all_requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> HttpReply:
        self.all_requests.append((method, url, headers, body))
        return self.all_replies.pop(0)


def repository_settings() -> RepositorySettings:
    return RepositorySettings(
        slug="owner/repository",
        clone_url="https://github.test/owner/repository.git",
    )


def pull_payload(
    head_sha: str = "head",
    base_ref: str = "main",
) -> dict[str, object]:
    return {
        "number": 7,
        "draft": True,
        "merge_commit_sha": "merge",
        "base": {"ref": base_ref, "sha": "base"},
        "head": {"sha": head_sha},
    }


def branch_payload(branch_sha: str = "current-base") -> dict[str, object]:
    return {
        "ref": "refs/heads/main",
        "object": {"sha": branch_sha, "type": "commit"},
    }


def _issue_repository_api(
    tmp_path: Path,
    requester: RecordingRequester,
    all_claims: list[dict[str, int | str]],
) -> GitHubApi:
    private_key_path = tmp_path / "app.pem"
    private_key_path.write_text("private-key", encoding="utf-8")

    def encode_jwt(
        claims: dict[str, int | str], private_key: str, algorithm: str
    ) -> str:
        all_claims.append(claims)
        assert private_key == "private-key"
        assert algorithm == "RS256"
        return "app-jwt"

    authenticator = GitHubAppAuthenticator(
        "https://api.github.test",
        42,
        84,
        private_key_path,
        requester=requester,
        jwt_encoder=encode_jwt,
        clock=lambda: 1000.0,
    )
    return authenticator.issue_repository_api(repository_settings())


def test_lists_draft_pull_requests() -> None:
    requester = RecordingRequester(
        [HttpReply(200, {}, json.dumps([pull_payload()]).encode("utf-8"))]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    all_candidates = github.list_open_candidates(repository_settings())

    assert len(all_candidates) == 1
    assert all_candidates[0].is_draft is True
    assert "state=open" in requester.all_requests[0][1]


def test_reads_merge_commit_parents_in_order() -> None:
    requester = RecordingRequester(
        [
            HttpReply(
                200,
                {},
                json.dumps(
                    {"sha": "merge", "parents": [{"sha": "base"}, {"sha": "head"}]}
                ).encode("utf-8"),
            )
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    all_parent_shas = github.get_commit_parents(repository_settings(), "merge")

    assert all_parent_shas == ("base", "head")


def test_posts_status_to_recognized_merge_sha() -> None:
    requester = RecordingRequester([HttpReply(201, {}, b"{}")])
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    github.post_status(
        repository_settings(),
        "merge",
        StatusState.SUCCESS,
        "local/verify",
        "All required checks passed",
    )

    method, url, headers, body = requester.all_requests[0]
    assert method == "POST"
    assert url.endswith("/repos/owner/repository/statuses/merge")
    assert headers["Authorization"] == "Bearer installation-token"
    assert json.loads(body or b"{}")["context"] == "local/verify"


def test_adds_and_removes_one_label_without_replacing_other_labels() -> None:
    requester = RecordingRequester(
        [
            HttpReply(200, {}, b"[]"),
            HttpReply(200, {}, json.dumps([{"name": "local-checks:passed"}]).encode()),
            HttpReply(204, {}, b""),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    github.add_label(repository_settings(), 7, "local-checks:passed")
    github.remove_label(repository_settings(), 7, "local-checks:passed")

    add_method, add_url, _, add_body = requester.all_requests[0]
    read_method, read_url, _, read_body = requester.all_requests[1]
    remove_method, remove_url, _, remove_body = requester.all_requests[2]
    assert add_method == "POST"
    assert add_url.endswith("/repos/owner/repository/issues/7/labels")
    assert json.loads(add_body or b"{}") == {"labels": ["local-checks:passed"]}
    assert read_method == "GET"
    assert read_url.endswith("/repos/owner/repository/issues/7/labels")
    assert read_body is None
    assert remove_method == "DELETE"
    assert remove_url.endswith(
        "/repos/owner/repository/issues/7/labels/local-checks%3Apassed"
    )
    assert remove_body is None


def test_removes_label_when_github_returns_ok() -> None:
    requester = RecordingRequester(
        [
            HttpReply(200, {}, json.dumps([{"name": "local-checks:passed"}]).encode()),
            HttpReply(200, {}, b"{}"),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    github.remove_label(repository_settings(), 7, "local-checks:passed")

    assert requester.all_requests[1][0] == "DELETE"


def test_ignores_label_that_is_already_absent() -> None:
    requester = RecordingRequester([HttpReply(200, {}, b"[]")])
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    github.remove_label(repository_settings(), 7, "local-checks:passed")

    assert len(requester.all_requests) == 1


def test_raises_when_label_delete_is_forbidden() -> None:
    requester = RecordingRequester(
        [
            HttpReply(200, {}, json.dumps([{"name": "local-checks:passed"}]).encode()),
            HttpReply(403, {}, b"{}"),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    try:
        github.remove_label(repository_settings(), 7, "local-checks:passed")
    except GitHubError as error:
        assert "403" in str(error)
    else:
        raise AssertionError("Expected forbidden label deletion to fail")


def test_app_token_is_scoped_to_one_repository_and_required_permissions(
    tmp_path: Path,
) -> None:
    requester = RecordingRequester(
        [
            HttpReply(
                201, {}, json.dumps({"token": "installation-token"}).encode("utf-8")
            )
        ]
    )
    all_claims: list[dict[str, int | str]] = []
    github = _issue_repository_api(tmp_path, requester, all_claims)

    request_body = json.loads(requester.all_requests[0][3] or b"{}")
    assert github.installation_token == "installation-token"
    assert request_body == {
        "repositories": ["repository"],
        "permissions": {
            "contents": "read",
            "pull_requests": "read",
            "statuses": "write",
        },
    }
    assert all_claims == [{"iss": "42", "iat": 940, "exp": 1540}]


def test_app_token_opt_in_adds_issue_write_permission(tmp_path: Path) -> None:
    private_key_path = tmp_path / "app.pem"
    private_key_path.write_text("private-key", encoding="utf-8")
    requester = RecordingRequester(
        [HttpReply(201, {}, json.dumps({"token": "token"}).encode("utf-8"))]
    )
    authenticator = GitHubAppAuthenticator(
        "https://api.github.test",
        42,
        84,
        private_key_path,
        requester=requester,
        jwt_encoder=lambda claims, private_key, algorithm: "app-jwt",
    )

    authenticator.issue_repository_api(
        repository_settings(), should_write_issue_labels=True
    )

    request_body = json.loads(requester.all_requests[0][3] or b"{}")
    assert request_body == {
        "repositories": ["repository"],
        "permissions": {
            "contents": "read",
            "pull_requests": "write",
            "statuses": "write",
            "issues": "write",
        },
    }


def test_ignores_pull_until_github_recognizes_merge_sha() -> None:
    unrecognized_pull = pull_payload()
    unrecognized_pull["merge_commit_sha"] = None
    requester = RecordingRequester(
        [HttpReply(200, {}, json.dumps([unrecognized_pull]).encode("utf-8"))]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    all_candidates = github.list_open_candidates(repository_settings())

    assert all_candidates == ()


def test_lists_pull_without_merge_sha_for_advisory_reads() -> None:
    unrecognized_pull = pull_payload()
    unrecognized_pull["merge_commit_sha"] = None
    requester = RecordingRequester(
        [
            HttpReply(200, {}, json.dumps([unrecognized_pull]).encode("utf-8")),
            HttpReply(200, {}, json.dumps(branch_payload()).encode("utf-8")),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    all_candidates = github.list_open_candidates(
        repository_settings(), should_require_merge_commit=False
    )

    assert len(all_candidates) == 1
    assert all_candidates[0].merge_sha == ""
    assert all_candidates[0].base_sha == "current-base"


def test_get_candidate_uses_current_branch_sha_for_advisory_reads() -> None:
    requester = RecordingRequester(
        [
            HttpReply(
                200,
                {},
                json.dumps(pull_payload(base_ref="release/#7")).encode("utf-8"),
            ),
            HttpReply(
                200,
                {},
                json.dumps(branch_payload("new-base")).encode("utf-8"),
            ),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    candidate = github.get_candidate(
        repository_settings(),
        7,
        should_require_merge_commit=False,
    )

    assert candidate.base_sha == "new-base"
    assert requester.all_requests[1][1].endswith(
        "/repos/owner/repository/git/ref/heads/release/%237"
    )


def test_list_resolves_each_unique_base_ref_once() -> None:
    second_pull = pull_payload("second-head")
    second_pull["number"] = 8
    requester = RecordingRequester(
        [
            HttpReply(
                200,
                {},
                json.dumps([pull_payload(), second_pull]).encode("utf-8"),
            ),
            HttpReply(200, {}, json.dumps(branch_payload()).encode("utf-8")),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    all_candidates = github.list_open_candidates(
        repository_settings(),
        should_require_merge_commit=False,
    )
    all_branch_requests = [
        each_request
        for each_request in requester.all_requests
        if "/git/ref/heads/" in each_request[1]
    ]

    assert [each_candidate.base_sha for each_candidate in all_candidates] == [
        "current-base",
        "current-base",
    ]
    assert len(all_branch_requests) == 1


def test_advisory_candidate_propagates_branch_read_failure() -> None:
    requester = RecordingRequester(
        [
            HttpReply(200, {}, json.dumps(pull_payload()).encode("utf-8")),
            HttpReply(500, {}, b"{}"),
        ]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    with pytest.raises(GitHubError, match="500"):
        github.get_candidate(
            repository_settings(),
            7,
            should_require_merge_commit=False,
        )


def test_strict_candidate_keeps_pull_base_without_branch_read() -> None:
    requester = RecordingRequester(
        [HttpReply(200, {}, json.dumps(pull_payload()).encode("utf-8"))]
    )
    github = GitHubApi("https://api.github.test", "installation-token", requester)

    candidate = github.get_candidate(repository_settings(), 7)

    assert candidate.base_sha == "base"
    assert len(requester.all_requests) == 1
