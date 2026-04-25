"""Coherence tests for groq_bugteam_spec module import surface.

The behavioral contract for apply_fix_from_spec lives in
test_groq_bugteam_apply_fix_from_spec.py; those tests pass whether the
function is defined in groq_bugteam.py directly or re-exported from the
spec module. This file exists solely so the spec module has a
same-named test companion for filename-based test pairing.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
import types

import pytest


def _load_spec_module():
    scripts_directory = pathlib.Path(__file__).parent
    sys.path.insert(0, str(scripts_directory))
    sys.modules.pop("groq_bugteam_spec", None)
    module_path = scripts_directory / "groq_bugteam_spec.py"
    module_spec = importlib.util.spec_from_file_location(
        "groq_bugteam_spec", module_path
    )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam_spec"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam_spec = _load_spec_module()


def test_is_spec_mode_invocation_detects_flag_value_pair():
    assert groq_bugteam_spec.is_spec_mode_invocation(["--mode", "spec"]) is True
    assert groq_bugteam_spec.is_spec_mode_invocation(["--mode", "pipeline"]) is False
    assert groq_bugteam_spec.is_spec_mode_invocation([]) is False


def _attach_required_groq_attributes(target_module: types.ModuleType) -> None:
    target_module.call_groq_with_fallback = lambda *args, **kwargs: None
    target_module.parse_json_object = lambda text: {}
    target_module.preserve_trailing_newline = lambda original, updated: updated


def test_resolver_prefers_registered_groq_bugteam_over_main(monkeypatch):
    fake_groq_bugteam = types.ModuleType("groq_bugteam")
    _attach_required_groq_attributes(fake_groq_bugteam)
    monkeypatch.setitem(sys.modules, "groq_bugteam", fake_groq_bugteam)

    resolved_module = groq_bugteam_spec.resolve_groq_bugteam_module()

    assert resolved_module is fake_groq_bugteam


def test_resolver_falls_back_to_main_when_groq_bugteam_absent(monkeypatch):
    monkeypatch.delitem(sys.modules, "groq_bugteam", raising=False)
    fake_main = types.ModuleType("__main__")
    _attach_required_groq_attributes(fake_main)
    monkeypatch.setitem(sys.modules, "__main__", fake_main)

    resolved_module = groq_bugteam_spec.resolve_groq_bugteam_module()

    assert resolved_module is fake_main


def test_resolver_falls_back_to_main_when_registered_module_is_stub(monkeypatch):
    stub_groq_bugteam = types.ModuleType("groq_bugteam")
    stub_groq_bugteam.call_groq_with_fallback = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "groq_bugteam", stub_groq_bugteam)
    complete_main = types.ModuleType("__main__")
    _attach_required_groq_attributes(complete_main)
    monkeypatch.setitem(sys.modules, "__main__", complete_main)

    resolved_module = groq_bugteam_spec.resolve_groq_bugteam_module()

    assert resolved_module is complete_main


def test_resolver_raises_when_registered_module_missing_required_attributes(
    monkeypatch,
):
    stub_groq_bugteam = types.ModuleType("groq_bugteam")
    stub_groq_bugteam.call_groq_with_fallback = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "groq_bugteam", stub_groq_bugteam)
    monkeypatch.delitem(sys.modules, "__main__", raising=False)

    try:
        groq_bugteam_spec.resolve_groq_bugteam_module()
    except RuntimeError as resolver_error:
        resolver_error_text = str(resolver_error)
        assert "parse_json_object" in resolver_error_text
        assert "preserve_trailing_newline" in resolver_error_text
    else:
        raise AssertionError("resolver should have raised RuntimeError")


def test_resolver_raises_when_neither_module_available(monkeypatch):
    monkeypatch.delitem(sys.modules, "groq_bugteam", raising=False)
    placeholder_main = types.ModuleType("__main__")
    monkeypatch.setitem(sys.modules, "__main__", placeholder_main)

    try:
        groq_bugteam_spec.resolve_groq_bugteam_module()
    except RuntimeError as resolver_error:
        resolver_error_text = str(resolver_error)
        assert "groq_bugteam" in resolver_error_text
    else:
        raise AssertionError("resolver should have raised RuntimeError")


FAKE_API_KEY = "gsk_test_placeholder_value"


def _install_fake_groq_bugteam_module(monkeypatch, response_object):
    """Register a minimal fake groq_bugteam module for resolver lookup."""

    fake_module = types.ModuleType("groq_bugteam")

    def fake_call(api_key, messages, temperature, max_completion_tokens):
        return types.SimpleNamespace(
            content=json.dumps(response_object),
            model="fake-model",
        )

    def fake_parse_json_object(text):
        return json.loads(text)

    def fake_preserve_trailing_newline(original, updated):
        if original.endswith("\n") and not updated.endswith("\n"):
            return updated + "\n"
        if not original.endswith("\n") and updated.endswith("\n"):
            return updated[:-1]
        return updated

    fake_module.call_groq_with_fallback = fake_call
    fake_module.parse_json_object = fake_parse_json_object
    fake_module.preserve_trailing_newline = fake_preserve_trailing_newline
    monkeypatch.setitem(sys.modules, "groq_bugteam", fake_module)
    monkeypatch.setenv("GROQ_API_KEY", FAKE_API_KEY)


def test_skipped_entry_missing_finding_index_does_not_crash(monkeypatch):
    original_file = "alpha\nbeta\n"
    spec_list = [
        {
            "finding_index": 4,
            "severity": "P1",
            "category": "J",
            "file": "sample.py",
            "target_line_start": 1,
            "target_line_end": 1,
            "intended_change": "rename alpha",
            "replacement_code": "alpha_fixed",
            "acceptance_criteria": ["alpha_fixed appears on line 1"],
        }
    ]
    patched_file = "alpha_fixed\nbeta\n"
    fake_response = {
        "updated_content": patched_file,
        "applied_finding_indexes": [4],
        "skipped": [{"reason": "malformed entry without finding_index"}],
        "acceptance_checks": [
            {
                "finding_index": 4,
                "criterion": "alpha_fixed appears on line 1",
                "met": True,
            }
        ],
    }
    _install_fake_groq_bugteam_module(monkeypatch, fake_response)

    outcome = groq_bugteam_spec.apply_fix_from_spec(spec_list, original_file)

    assert outcome["updated_content"] == patched_file
    assert outcome["applied_finding_indexes"] == [4]


def test_null_updated_content_falls_back_to_current_content(monkeypatch):
    original_file = "alpha\nbeta\n"
    spec_list = [
        {
            "finding_index": 0,
            "severity": "P2",
            "category": "E",
            "file": "sample.py",
            "target_line_start": 1,
            "target_line_end": 1,
            "intended_change": "no-op fallback",
            "replacement_code": "alpha",
            "acceptance_criteria": ["alpha remains on line 1"],
        }
    ]
    fake_response = {
        "updated_content": None,
        "applied_finding_indexes": [],
        "skipped": [
            {
                "finding_index": 0,
                "reason": "Groq returned null updated_content",
            }
        ],
        "acceptance_checks": [],
    }
    _install_fake_groq_bugteam_module(monkeypatch, fake_response)

    outcome = groq_bugteam_spec.apply_fix_from_spec(spec_list, original_file)

    assert outcome["updated_content"] == original_file


def test_null_collection_fields_coerce_to_empty_lists(monkeypatch):
    original_file = "alpha\n"
    spec_list = [
        {
            "finding_index": 1,
            "severity": "P2",
            "category": "E",
            "file": "sample.py",
            "target_line_start": 1,
            "target_line_end": 1,
            "intended_change": "no-op",
            "replacement_code": "alpha",
            "acceptance_criteria": ["alpha remains"],
        }
    ]
    fake_response = {
        "updated_content": original_file,
        "applied_finding_indexes": None,
        "skipped": None,
        "acceptance_checks": None,
    }
    _install_fake_groq_bugteam_module(monkeypatch, fake_response)

    outcome = groq_bugteam_spec.apply_fix_from_spec(spec_list, original_file)

    assert outcome["applied_finding_indexes"] == []
    assert outcome["skipped"] == []
    assert outcome["acceptance_checks"] == []


def test_dict_collection_fields_coerce_to_empty_lists(monkeypatch):
    original_file = "alpha\n"
    spec_list = [
        {
            "finding_index": 2,
            "severity": "P2",
            "category": "E",
            "file": "sample.py",
            "target_line_start": 1,
            "target_line_end": 1,
            "intended_change": "no-op",
            "replacement_code": "alpha",
            "acceptance_criteria": ["alpha remains"],
        }
    ]
    fake_response = {
        "updated_content": original_file,
        "applied_finding_indexes": {"not": "a list"},
        "skipped": {"0": "not a list either"},
        "acceptance_checks": {"also": "a dict"},
    }
    _install_fake_groq_bugteam_module(monkeypatch, fake_response)

    outcome = groq_bugteam_spec.apply_fix_from_spec(spec_list, original_file)

    assert outcome["applied_finding_indexes"] == []
    assert outcome["skipped"] == []
    assert outcome["acceptance_checks"] == []


def test_non_string_updated_content_falls_back_to_current_content(monkeypatch):
    original_file = "alpha\nbeta\n"
    spec_list = [
        {
            "finding_index": 0,
            "severity": "P2",
            "category": "E",
            "file": "sample.py",
            "target_line_start": 1,
            "target_line_end": 1,
            "intended_change": "no-op fallback",
            "replacement_code": "alpha",
            "acceptance_criteria": ["alpha remains on line 1"],
        }
    ]
    fake_response = {
        "updated_content": {"unexpected": "dict instead of str"},
        "applied_finding_indexes": [],
        "skipped": [],
        "acceptance_checks": [],
    }
    _install_fake_groq_bugteam_module(monkeypatch, fake_response)

    outcome = groq_bugteam_spec.apply_fix_from_spec(spec_list, original_file)

    assert outcome["updated_content"] == original_file


def test_run_spec_mode_main_emits_error_json_on_missing_api_key(
    monkeypatch, capsys
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        "groq_bugteam_dotenv.load_claude_dev_env_dotenv_file",
        lambda: None,
    )
    spec_payload = {
        "spec": [
            {
                "finding_index": 0,
                "severity": "P1",
                "category": "J",
                "file": "sample.py",
                "target_line_start": 1,
                "target_line_end": 1,
                "intended_change": "noop",
                "replacement_code": "noop",
                "acceptance_criteria": ["noop"],
            }
        ],
        "current_content": "noop\n",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(spec_payload)))

    with pytest.raises(SystemExit) as exit_info:
        groq_bugteam_spec.run_spec_mode_main()

    captured = capsys.readouterr()
    emitted_outcome = json.loads(captured.out)
    assert "error" in emitted_outcome
    assert "GROQ_API_KEY" in emitted_outcome["error"]
    assert exit_info.value.code != 0
