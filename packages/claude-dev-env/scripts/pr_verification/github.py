from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

from . import github_api, github_transport
from .config.constants import (
    APP_EXPIRATION_CLAIM,
    APP_ISSUED_AT_CLAIM,
    APP_ISSUER_CLAIM,
    APP_JWT_ALGORITHM,
    CONTENTS_PERMISSION_KEY,
    HTTP_CREATED,
    INSTALLATION_TOKEN_ENDPOINT_TEMPLATE,
    ISSUES_PERMISSION_KEY,
    PERMISSIONS_KEY,
    PULL_REQUESTS_PERMISSION_KEY,
    READ_PERMISSION,
    REPOSITORIES_KEY,
    STATUSES_PERMISSION_KEY,
    TOKEN_KEY,
    TOKEN_RESOURCE_NAME,
    UTF8_ENCODING,
    WRITE_PERMISSION,
)
from .config.timing import (
    APP_JWT_CLOCK_SKEW_SECONDS,
    APP_JWT_LIFETIME_SECONDS,
)
from .github_api import authorized_headers, request_json
from .github_parsing import require_mapping, require_text
from .github_transport import (
    HttpRequester,
    JwtEncoder,
    encode_app_jwt,
    request_http,
)
from .model import RepositorySettings

GitHubApi = github_api.GitHubApi
GitHubError = github_api.GitHubError
HttpReply = github_transport.HttpReply


def _build_installation_token_body(
    repository: RepositorySettings, should_write_issue_labels: bool
) -> bytes:
    all_permissions = {
        CONTENTS_PERMISSION_KEY: READ_PERMISSION,
        PULL_REQUESTS_PERMISSION_KEY: READ_PERMISSION,
        STATUSES_PERMISSION_KEY: WRITE_PERMISSION,
    }
    if should_write_issue_labels:
        all_permissions[ISSUES_PERMISSION_KEY] = WRITE_PERMISSION
        all_permissions[PULL_REQUESTS_PERMISSION_KEY] = WRITE_PERMISSION
    token_request = {
        REPOSITORIES_KEY: [repository.name],
        PERMISSIONS_KEY: all_permissions,
    }
    return json.dumps(token_request).encode(UTF8_ENCODING)


class GitHubAppAuthenticator:
    def __init__(
        self,
        api_url: str,
        app_id: int,
        installation_id: int,
        private_key_path: Path,
        requester: HttpRequester = request_http,
        jwt_encoder: JwtEncoder = encode_app_jwt,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.api_url = api_url
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key_path = private_key_path
        self.requester = requester
        self.jwt_encoder = jwt_encoder
        self.clock = clock

    def issue_repository_api(
        self,
        repository: RepositorySettings,
        *,
        should_write_issue_labels: bool = False,
    ) -> GitHubApi:
        """Create a repository-scoped API client.

        Args:
            repository: Repository to scope.

        Returns:
            Authenticated API client.
        """
        installation_token = self._request_repository_token(
            repository, should_write_issue_labels
        )
        return GitHubApi(self.api_url, installation_token, self.requester)

    def _request_repository_token(
        self, repository: RepositorySettings, should_write_issue_labels: bool
    ) -> str:
        app_token = self.create_app_token()
        endpoint = INSTALLATION_TOKEN_ENDPOINT_TEMPLATE.format(
            installation_id=self.installation_id
        )
        request_body = _build_installation_token_body(
            repository, should_write_issue_labels
        )
        token_payload = request_json(
            self.requester,
            "POST",
            self.api_url + endpoint,
            authorized_headers(app_token),
            request_body,
            HTTP_CREATED,
        )
        token_mapping = require_mapping(token_payload, TOKEN_RESOURCE_NAME)
        return require_text(token_mapping, TOKEN_KEY, TOKEN_RESOURCE_NAME)

    def create_app_token(self) -> str:
        """Create an app JWT for token exchange.

        Returns:
            The encoded app token.
        """
        current_time = int(self.clock())
        all_claims: dict[str, int | str] = {
            APP_ISSUER_CLAIM: str(self.app_id),
            APP_ISSUED_AT_CLAIM: current_time - APP_JWT_CLOCK_SKEW_SECONDS,
            APP_EXPIRATION_CLAIM: current_time + APP_JWT_LIFETIME_SECONDS,
        }
        private_key = self.private_key_path.read_text(encoding=UTF8_ENCODING)
        return self.jwt_encoder(all_claims, private_key, APP_JWT_ALGORITHM)
