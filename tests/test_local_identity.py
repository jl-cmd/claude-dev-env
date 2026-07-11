"""Specifications for config/local_identity.py owner-scope and token-name resolution."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import local_identity

FANOUT_OWNER_SCOPES_ENV_VAR = "FANOUT_OWNER_SCOPES"


class TestFanoutOwnerScopesFromEnvironment:
    def should_split_comma_separated_scopes_and_strip_whitespace(self) -> None:
        with patch.dict(
            os.environ, {FANOUT_OWNER_SCOPES_ENV_VAR: "acme, acme-labs"}, clear=False
        ):
            assert local_identity.fanout_owner_scopes() == ["acme", "acme-labs"]

    def should_prefer_the_environment_over_the_local_file(self, tmp_path: Path) -> None:
        config_directory = tmp_path / "config"
        config_directory.mkdir()
        (config_directory / "local-identity.json").write_text(
            json.dumps({"github_owner_scopes": ["filescope"]}), encoding="utf-8"
        )
        with patch.dict(
            os.environ, {FANOUT_OWNER_SCOPES_ENV_VAR: "envscope"}, clear=False
        ):
            with patch.object(local_identity, "_repository_root", return_value=tmp_path):
                assert local_identity.fanout_owner_scopes() == ["envscope"]


class TestFanoutOwnerScopesFromLocalFile:
    def should_read_scopes_from_the_local_identity_file(self, tmp_path: Path) -> None:
        config_directory = tmp_path / "config"
        config_directory.mkdir()
        (config_directory / "local-identity.json").write_text(
            json.dumps({"github_owner_scopes": ["filescope-a", "filescope-b"]}),
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(FANOUT_OWNER_SCOPES_ENV_VAR, None)
            with patch.object(local_identity, "_repository_root", return_value=tmp_path):
                assert local_identity.fanout_owner_scopes() == [
                    "filescope-a",
                    "filescope-b",
                ]


class TestFanoutOwnerScopesPlaceholderDefault:
    def should_return_the_placeholder_when_no_env_and_no_file(
        self, tmp_path: Path
    ) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(FANOUT_OWNER_SCOPES_ENV_VAR, None)
            with patch.object(local_identity, "_repository_root", return_value=tmp_path):
                assert local_identity.fanout_owner_scopes() == ["example-owner"]


class TestTokenEnvVarName:
    def should_upper_case_drop_hyphens_and_append_the_token_suffix(self) -> None:
        assert local_identity.token_env_var_name("acme-labs") == "ACMELABS_TOKEN"

    def should_append_the_token_suffix_to_a_single_word_scope(self) -> None:
        assert local_identity.token_env_var_name("acme") == "ACME_TOKEN"
