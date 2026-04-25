"""Existence and coherence check for SPEC_IMPLEMENTER_SYSTEM_PROMPT."""

from __future__ import annotations

import importlib.util
import pathlib
import sys


def _load_config_module():
    module_path = pathlib.Path(__file__).parent / "groq_bugteam_config.py"
    module_spec = importlib.util.spec_from_file_location(
        "groq_bugteam_config_spec", module_path
    )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam_config_spec"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam_config = _load_config_module()


def test_spec_implementer_prompt_is_non_empty_string():
    prompt_text = groq_bugteam_config.SPEC_IMPLEMENTER_SYSTEM_PROMPT
    assert isinstance(prompt_text, str)
    assert len(prompt_text.strip()) > 0


def test_spec_implementer_prompt_declares_mechanical_only_discipline():
    prompt_text = groq_bugteam_config.SPEC_IMPLEMENTER_SYSTEM_PROMPT
    assert "mechanical edits only" in prompt_text
