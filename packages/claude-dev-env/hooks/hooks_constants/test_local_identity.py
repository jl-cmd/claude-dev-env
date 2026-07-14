"""Tests for the NAS local-identity loader used by the ssh enforcer hook."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

try:
    from hooks_constants import local_identity
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hooks_constants import local_identity

ALL_NAS_ENV_VARS = ("CLAUDE_NAS_HOST", "CLAUDE_NAS_SSH_USER", "CLAUDE_NAS_SSH_PORT")


def _clear_nas_env() -> None:
    for each_env_var in ALL_NAS_ENV_VARS:
        os.environ.pop(each_env_var, None)


class TestNasValuesFromEnvironment:
    def should_read_host_user_and_port_from_the_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CLAUDE_NAS_HOST": "10.0.0.5",
                "CLAUDE_NAS_SSH_USER": "tester",
                "CLAUDE_NAS_SSH_PORT": "2200",
            },
            clear=False,
        ):
            assert local_identity.nas_host() == "10.0.0.5"
            assert local_identity.nas_ssh_user() == "tester"
            assert local_identity.nas_ssh_port() == 2200


class TestNasValuesFromLocalFile:
    def should_read_host_user_and_port_from_the_local_identity_file(
        self, tmp_path: Path
    ) -> None:
        claude_home = tmp_path / ".claude"
        claude_home.mkdir()
        (claude_home / "local-identity.json").write_text(
            json.dumps(
                {"nas": {"host": "10.1.1.9", "ssh_user": "fileuser", "ssh_port": 2222}}
            ),
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=False):
            _clear_nas_env()
            with patch.object(Path, "home", return_value=tmp_path):
                assert local_identity.nas_host() == "10.1.1.9"
                assert local_identity.nas_ssh_user() == "fileuser"
                assert local_identity.nas_ssh_port() == 2222


class TestNasValuesPlaceholderDefault:
    def should_return_placeholders_when_no_env_and_no_file(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {}, clear=False):
            _clear_nas_env()
            with patch.object(Path, "home", return_value=tmp_path):
                assert local_identity.nas_host() == "nas.example.local"
                assert local_identity.nas_ssh_user() == "operator"
                assert local_identity.nas_ssh_port() == 22


class TestPiiExemptRepositorySlugs:
    def should_read_slugs_from_the_environment_lowercased(self) -> None:
        with patch.dict(
            os.environ,
            {"CLAUDE_PII_EXEMPT_REPOS": "ExemptOwner/exempt-repo, Other/Repo"},
            clear=False,
        ):
            slugs = local_identity.pii_exempt_repository_slugs()
            assert slugs == frozenset({"exemptowner/exempt-repo", "other/repo"})

    def should_read_slugs_from_the_local_identity_file(self, tmp_path: Path) -> None:
        claude_home = tmp_path / ".claude"
        claude_home.mkdir()
        (claude_home / "local-identity.json").write_text(
            json.dumps({"pii_exempt_repositories": ["FileOwner/file-repo"]}),
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PII_EXEMPT_REPOS", None)
            with patch.object(Path, "home", return_value=tmp_path):
                slugs = local_identity.pii_exempt_repository_slugs()
                assert slugs == frozenset({"fileowner/file-repo"})

    def should_return_an_empty_set_when_no_env_and_no_file(
        self, tmp_path: Path
    ) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PII_EXEMPT_REPOS", None)
            with patch.object(Path, "home", return_value=tmp_path):
                assert local_identity.pii_exempt_repository_slugs() == frozenset()

    def should_prefer_environment_slugs_over_local_identity_file(
        self, tmp_path: Path
    ) -> None:
        claude_home = tmp_path / ".claude"
        claude_home.mkdir()
        (claude_home / "local-identity.json").write_text(
            json.dumps({"pii_exempt_repositories": ["FileOwner/file-repo"]}),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_PII_EXEMPT_REPOS": "EnvOwner/env-repo"},
            clear=False,
        ):
            with patch.object(Path, "home", return_value=tmp_path):
                slugs = local_identity.pii_exempt_repository_slugs()
                assert slugs == frozenset({"envowner/env-repo"})

    def should_fall_through_to_json_when_environment_is_whitespace_only(
        self, tmp_path: Path
    ) -> None:
        claude_home = tmp_path / ".claude"
        claude_home.mkdir()
        (claude_home / "local-identity.json").write_text(
            json.dumps({"pii_exempt_repositories": ["FileOwner/file-repo"]}),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_PII_EXEMPT_REPOS": " , , "},
            clear=False,
        ):
            with patch.object(Path, "home", return_value=tmp_path):
                slugs = local_identity.pii_exempt_repository_slugs()
                assert slugs == frozenset({"fileowner/file-repo"})


class TestPiiAllowlistedValuesByRepository:
    def test_reads_the_mapping_lowercasing_slugs_and_keeping_values_exact(
        self, tmp_path: Path
    ) -> None:
        allowed_value = "owner.fixture" + "@" + "acme-corp" + ".example" + ".io"
        identity_path = tmp_path / "local-identity.json"
        identity_path.write_text(
            json.dumps(
                {"pii_allowlisted_values": {"Owner/Private-Repo": [allowed_value]}}
            ),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(identity_path)},
            clear=False,
        ):
            values_by_slug = local_identity.pii_allowlisted_values_by_repository()
            assert values_by_slug == {"owner/private-repo": frozenset({allowed_value})}

    def test_returns_empty_mapping_when_the_file_is_missing(
        self, tmp_path: Path
    ) -> None:
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(tmp_path / "absent.json")},
            clear=False,
        ):
            assert local_identity.pii_allowlisted_values_by_repository() == {}

    def test_returns_empty_mapping_when_the_json_is_corrupt(
        self, tmp_path: Path
    ) -> None:
        identity_path = tmp_path / "local-identity.json"
        identity_path.write_text("{ not valid json", encoding="utf-8")
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(identity_path)},
            clear=False,
        ):
            assert local_identity.pii_allowlisted_values_by_repository() == {}

    def test_returns_empty_mapping_when_the_key_is_absent(
        self, tmp_path: Path
    ) -> None:
        identity_path = tmp_path / "local-identity.json"
        identity_path.write_text(
            json.dumps({"nas": {"host": "10.0.0.5"}}), encoding="utf-8"
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(identity_path)},
            clear=False,
        ):
            assert local_identity.pii_allowlisted_values_by_repository() == {}

    def test_drops_blank_slugs_and_non_list_value_entries(
        self, tmp_path: Path
    ) -> None:
        allowed_value = "keep.fixture" + "@" + "acme-corp" + ".example" + ".io"
        identity_path = tmp_path / "local-identity.json"
        identity_path.write_text(
            json.dumps(
                {
                    "pii_allowlisted_values": {
                        "  ": [allowed_value],
                        "Owner/Repo": allowed_value,
                        "Owner/Kept": [allowed_value, 7],
                    }
                }
            ),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(identity_path)},
            clear=False,
        ):
            values_by_slug = local_identity.pii_allowlisted_values_by_repository()
            assert values_by_slug == {"owner/kept": frozenset({allowed_value})}


class TestLocalIdentityPathOverride:
    def test_prefers_the_env_path_over_the_home_directory_file(
        self, tmp_path: Path
    ) -> None:
        override_path = tmp_path / "override" / "local-identity.json"
        override_path.parent.mkdir()
        override_path.write_text(
            json.dumps({"nas": {"host": "10.9.9.9"}}), encoding="utf-8"
        )
        with patch.dict(
            os.environ,
            {"CLAUDE_LOCAL_IDENTITY_PATH": str(override_path)},
            clear=False,
        ), patch.object(Path, "home", return_value=tmp_path):
            _clear_nas_env()
            assert local_identity.nas_host() == "10.9.9.9"


class TestDenyMessagesQuoteTheResolvedHost:
    def should_include_the_resolved_host_and_port_in_the_bare_binary_message(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {"CLAUDE_NAS_HOST": "10.0.0.5", "CLAUDE_NAS_SSH_PORT": "2200"},
            clear=False,
        ):
            os.environ.pop("CLAUDE_NAS_SSH_USER", None)
            message = local_identity.bare_ssh_binary_deny_message()
            assert "10.0.0.5" in message
            assert "-p 2200" in message
            assert "BatchMode=yes" in message

    def should_include_the_resolved_host_in_the_missing_batch_mode_message(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_NAS_HOST": "10.0.0.5"}, clear=False):
            message = local_identity.missing_batch_mode_deny_message()
            assert "10.0.0.5" in message
            assert "BatchMode=yes" in message
