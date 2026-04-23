"""Tests for groq_bugteam_dotenv local .env loading."""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

_SCRIPTS_DIRECTORY = pathlib.Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from groq_bugteam_dotenv import (  # noqa: E402
    claude_dev_env_dotenv_path,
    load_claude_dev_env_dotenv_file,
)


class TestLoadClaudeDevEnvDotenvFile:
    def test_sets_groq_key_from_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("GROQ_API_KEY=from_file_value\n", encoding="utf-8")
        load_claude_dev_env_dotenv_file(env_file)
        assert os.environ["GROQ_API_KEY"] == "from_file_value"

    def test_does_not_override_existing_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GROQ_API_KEY", "preset_value")
        env_file = tmp_path / ".env"
        env_file.write_text("GROQ_API_KEY=from_file_value\n", encoding="utf-8")
        load_claude_dev_env_dotenv_file(env_file)
        assert os.environ["GROQ_API_KEY"] == "preset_value"

    def test_skips_comments_and_blank_lines(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("\n# comment\nGROQ_API_KEY=x\n", encoding="utf-8")
        load_claude_dev_env_dotenv_file(env_file)
        assert os.environ["GROQ_API_KEY"] == "x"

    def test_strips_export_prefix(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("export GROQ_API_KEY=exported\n", encoding="utf-8")
        load_claude_dev_env_dotenv_file(env_file)
        assert os.environ["GROQ_API_KEY"] == "exported"

    def test_strips_double_quotes(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text('GROQ_API_KEY="quoted"\n', encoding="utf-8")
        load_claude_dev_env_dotenv_file(env_file)
        assert os.environ["GROQ_API_KEY"] == "quoted"

    def test_missing_file_is_no_op(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        missing_file = tmp_path / "does_not_exist.env"
        load_claude_dev_env_dotenv_file(missing_file)
        assert "GROQ_API_KEY" not in os.environ


def test_claude_dev_env_dotenv_path_ends_with_env_filename():
    resolved = claude_dev_env_dotenv_path()
    assert resolved.name == ".env"
    assert resolved.parent.name == "claude-dev-env"
