"""Tests for the NAS local-identity loader used by the ssh enforcer hook."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks_constants import local_identity  # noqa: E402

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
