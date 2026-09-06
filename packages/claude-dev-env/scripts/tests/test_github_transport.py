from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from email.message import Message
from pathlib import Path
from unittest.mock import Mock

import jwt
import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from pr_verification.config.timing import HTTP_TIMEOUT_SECONDS
from pr_verification.github_parsing import GitHubError
from pr_verification.github_transport import HttpReply, encode_app_jwt, request_http


@contextmanager
def reply_context(http_reply_mock: Mock) -> Iterator[Mock]:
    yield http_reply_mock


def make_http_reply_mock(
    status_code: int, headers: dict[str, str], body: bytes
) -> Mock:
    http_reply_mock = Mock()
    http_reply_mock.status = status_code
    http_reply_mock.headers.items.return_value = list(headers.items())
    http_reply_mock.read.return_value = body
    return http_reply_mock


def test_request_http_returns_success_reply_and_request_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_reply_mock = make_http_reply_mock(
        200, {"Content-Type": "application/json"}, b'{"ok":true}'
    )
    all_requests: list[tuple[urllib.request.Request, float]] = []

    def open_url(
        request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[Mock]:
        all_requests.append((request, timeout))
        return reply_context(http_reply_mock)

    monkeypatch.setattr(urllib.request, "urlopen", open_url)

    reply = request_http(
        "GET",
        "https://github.test/resource",
        {"Accept": "application/json"},
        None,
    )

    assert reply == HttpReply(200, {"Content-Type": "application/json"}, b'{"ok":true}')
    assert all_requests[0][0].full_url == "https://github.test/resource"
    assert all_requests[0][0].get_method() == "GET"
    assert all_requests[0][1] == HTTP_TIMEOUT_SECONDS


def test_request_http_returns_http_error_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    http_headers = Message()
    http_headers["X-Request-Id"] = "request-id"
    http_error = urllib.error.HTTPError(
        "https://github.test/resource",
        404,
        "missing",
        http_headers,
        io.BytesIO(b"not found"),
    )

    def open_url(request: urllib.request.Request, timeout: float) -> Mock:
        raise http_error

    monkeypatch.setattr(urllib.request, "urlopen", open_url)

    reply = request_http("GET", "https://github.test/resource", {}, None)

    assert reply == HttpReply(404, {"X-Request-Id": "request-id"}, b"not found")


def test_request_http_propagates_url_error_as_github_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def open_url(request: urllib.request.Request, timeout: float) -> Mock:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", open_url)

    with pytest.raises(GitHubError, match="offline"):
        request_http("GET", "https://github.test/resource", {}, None)


def test_encode_app_jwt_preserves_arguments_and_normalizes_bytes_and_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_calls: list[tuple[dict[str, int | str], str, str]] = []
    encoded_tokens = iter((b"encoded-bytes", "encoded-string"))

    def encode_jwt(
        claims: dict[str, int | str], private_key: str, algorithm: str
    ) -> bytes | str:
        all_calls.append((claims, private_key, algorithm))
        return next(encoded_tokens)

    monkeypatch.setattr(jwt, "encode", encode_jwt)
    claims: dict[str, int | str] = {"iss": "42", "iat": 940, "exp": 1540}

    bytes_token = encode_app_jwt(claims, "private-key", "RS256")
    string_token = encode_app_jwt(claims, "private-key", "RS256")

    assert bytes_token == "encoded-bytes"
    assert string_token == "encoded-string"
    assert all_calls == [
        (claims, "private-key", "RS256"),
        (claims, "private-key", "RS256"),
    ]
