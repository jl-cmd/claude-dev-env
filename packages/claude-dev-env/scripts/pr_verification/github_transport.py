from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPResponse as OpenedHttpReply

import jwt

from .config.constants import (
    UTF8_ENCODING,
)
from .config.timing import HTTP_TIMEOUT_SECONDS
from .github_parsing import GitHubError


@dataclass(frozen=True)
class HttpReply:
    status_code: int
    headers: dict[str, str]
    body: bytes


HttpRequester = Callable[[str, str, dict[str, str], bytes | None], HttpReply]
JwtEncoder = Callable[[dict[str, int | str], str, str], str]


def _read_http_error(error: urllib.error.HTTPError) -> HttpReply:
    return HttpReply(
        status_code=error.code,
        headers=dict(error.headers.items()),
        body=error.read(),
    )


def request_http(
    method: str,
    url: str,
    all_headers: dict[str, str],
    body: bytes | None,
) -> HttpReply:
    """Send one GitHub HTTP request.

    Args:
        method: HTTP method.
        url: Absolute request URL.
        all_headers: Request headers.
        body: Encoded request body, or None.

    Returns:
        The HTTP reply, including error replies with a status code.

    Raises:
        GitHubError: If the request fails before a status code exists.
    """
    request = urllib.request.Request(
        url=url, data=body, headers=all_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as reply:
            return _read_http_reply(reply)
    except urllib.error.HTTPError as error:
        return _read_http_error(error)
    except (urllib.error.URLError, OSError) as error:
        raise GitHubError(str(error)) from error


def _read_http_reply(reply: OpenedHttpReply) -> HttpReply:
    return HttpReply(
        status_code=reply.status,
        headers=dict(reply.headers.items()),
        body=reply.read(),
    )


def encode_app_jwt(
    all_claims: dict[str, int | str], private_key: str, algorithm: str
) -> str:
    """Encode an app JWT.

    Args:
        all_claims: JWT claims.

    Returns:
        Encoded token.
    """
    encoded_token = jwt.encode(all_claims, private_key, algorithm=algorithm)
    if isinstance(encoded_token, bytes):
        return encoded_token.decode(UTF8_ENCODING)
    return encoded_token
