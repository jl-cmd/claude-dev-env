"""Tests for groq_bugteam.py pure logic.

Network calls (Groq HTTP) and filesystem/git side effects are out of scope for
unit tests; they are exercised in the live end-to-end run.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import urllib.error

import groq_bugteam_dotenv
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
for _cached in list(sys.modules):
    if _cached == "config" or _cached.startswith("config."):
        del sys.modules[_cached]

from config import groq_bugteam_config  # noqa: E402


def _load_groq_bugteam_module():
    scripts_directory = pathlib.Path(__file__).parent
    sys.path.insert(0, str(scripts_directory))
    for cached_module_name in list(sys.modules):
        if cached_module_name == "config" or cached_module_name.startswith("config."):
            del sys.modules[cached_module_name]
    module_path = scripts_directory / "groq_bugteam.py"
    module_spec = importlib.util.spec_from_file_location("groq_bugteam", module_path)
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam = _load_groq_bugteam_module()


class TestConstantsSourcedFromConfig:
    def test_endpoint_is_imported_from_config(self):
        assert groq_bugteam.GROQ_API_ENDPOINT == groq_bugteam_config.GROQ_API_ENDPOINT

    def test_primary_model_is_imported_from_config(self):
        assert groq_bugteam.GROQ_PRIMARY_MODEL == groq_bugteam_config.GROQ_PRIMARY_MODEL


class TestClampText:
    def test_returns_text_unchanged_when_under_limit(self):
        assert groq_bugteam.clamp_text("hello world", 100) == "hello world"

    def test_truncates_long_text_with_marker(self):
        long_text = "a" * 1000
        clamped = groq_bugteam.clamp_text(long_text, 200)
        assert "truncated" in clamped
        assert len(clamped) < len(long_text)
        assert clamped.startswith("a")
        assert clamped.endswith("a")

    def test_preserves_head_and_tail(self):
        text = "HEAD" + ("x" * 1000) + "TAIL"
        clamped = groq_bugteam.clamp_text(text, 100)
        assert clamped.startswith("HEAD")
        assert clamped.endswith("TAIL")

    @pytest.mark.parametrize("max_characters", [50, 100, 200, 500, 1000])
    def test_output_never_exceeds_max_characters(self, max_characters):
        long_text = "a" * 5000
        clamped = groq_bugteam.clamp_text(long_text, max_characters)
        assert len(clamped) <= max_characters

    def test_returns_plain_head_when_marker_does_not_fit(self):
        long_text = "a" * 1000
        tiny_budget = 10
        clamped = groq_bugteam.clamp_text(long_text, tiny_budget)
        assert len(clamped) <= tiny_budget
        assert clamped == long_text[:tiny_budget]
        assert "truncated" not in clamped

    def test_truncation_marker_count_matches_characters_actually_dropped(self):
        long_text = "a" * 1000
        max_characters = 200
        clamped = groq_bugteam.clamp_text(long_text, max_characters)
        marker_match = re.search(r"truncated (\d+) chars", clamped)
        assert marker_match is not None
        reported_truncated_count = int(marker_match.group(1))
        full_marker = f"\n\n... [truncated {reported_truncated_count} chars] ...\n\n"
        preserved_original_length = len(clamped) - len(full_marker)
        actually_truncated_count = len(long_text) - preserved_original_length
        assert reported_truncated_count == actually_truncated_count


class TestParseJsonObject:
    def test_parses_clean_json(self):
        parsed = groq_bugteam.parse_json_object('{"findings": []}')
        assert parsed == {"findings": []}

    def test_extracts_json_from_surrounding_prose(self):
        noisy_response = 'Sure, here is the result:\n\n{"findings": [{"severity": "P1"}]}\n\nLet me know if you need more.'
        parsed = groq_bugteam.parse_json_object(noisy_response)
        assert parsed == {"findings": [{"severity": "P1"}]}

    def test_raises_when_no_json_present(self):
        with pytest.raises(ValueError):
            groq_bugteam.parse_json_object("no braces here")


class TestNormalizeFindings:
    def test_drops_findings_with_unknown_files(self):
        raw_findings = [
            {
                "severity": "P0",
                "category": "H",
                "file": "known.py",
                "line": 10,
                "title": "t",
                "description": "d",
            },
            {
                "severity": "P1",
                "category": "A",
                "file": "unknown.py",
                "line": 5,
                "title": "t2",
                "description": "d2",
            },
        ]
        normalized = groq_bugteam.normalize_findings(raw_findings, {"known.py": ""})
        assert len(normalized) == 1
        assert normalized[0]["file"] == "known.py"

    def test_coerces_non_string_line_to_int(self):
        raw_findings = [
            {
                "severity": "P0",
                "category": "H",
                "file": "a.py",
                "line": "42",
                "title": "t",
                "description": "d",
            },
        ]
        normalized = groq_bugteam.normalize_findings(raw_findings, {"a.py": ""})
        assert normalized[0]["line"] == 42

    def test_defaults_to_zero_line_on_bad_value(self):
        raw_findings = [
            {
                "severity": "P1",
                "category": "H",
                "file": "a.py",
                "line": "not-a-number",
                "title": "t",
                "description": "d",
            },
        ]
        normalized = groq_bugteam.normalize_findings(raw_findings, {"a.py": ""})
        assert normalized[0]["line"] == 0

    def test_clamps_invalid_severity_to_p2(self):
        raw_findings = [
            {
                "severity": "CRITICAL",
                "category": "H",
                "file": "a.py",
                "line": 1,
                "title": "t",
                "description": "d",
            },
        ]
        normalized = groq_bugteam.normalize_findings(raw_findings, {"a.py": ""})
        assert normalized[0]["severity"] == "P2"

    def test_keeps_single_letter_category(self):
        raw_findings = [
            {
                "severity": "P0",
                "category": "HIJ",
                "file": "a.py",
                "line": 1,
                "title": "t",
                "description": "d",
            },
        ]
        normalized = groq_bugteam.normalize_findings(raw_findings, {"a.py": ""})
        assert normalized[0]["category"] == "H"

    def test_handles_empty_input(self):
        assert groq_bugteam.normalize_findings([], {"a.py": ""}) == []


class TestGroupFindingsByFile:
    def test_groups_findings_and_preserves_global_indexes(self):
        findings = [
            {
                "file": "a.py",
                "severity": "P0",
                "category": "H",
                "line": 1,
                "title": "t1",
                "description": "d1",
            },
            {
                "file": "b.py",
                "severity": "P1",
                "category": "A",
                "line": 2,
                "title": "t2",
                "description": "d2",
            },
            {
                "file": "a.py",
                "severity": "P2",
                "category": "E",
                "line": 3,
                "title": "t3",
                "description": "d3",
            },
        ]
        grouped = groq_bugteam.group_findings_by_file(findings)
        assert set(grouped.keys()) == {"a.py", "b.py"}
        assert [index for index, _ in grouped["a.py"]] == [0, 2]
        assert [index for index, _ in grouped["b.py"]] == [1]


class TestBuildReviewBody:
    def test_returns_clean_body_when_no_findings(self):
        body = groq_bugteam.build_review_body([], "llama-3.3-70b-versatile", "", [])
        assert "clean" in body
        assert "llama-3.3-70b-versatile" in body

    def test_counts_severities_and_lists_findings(self):
        findings = [
            {
                "severity": "P0",
                "category": "H",
                "file": "a.py",
                "line": 10,
                "title": "SQL injection",
                "description": "trace",
            },
            {
                "severity": "P1",
                "category": "F",
                "file": "b.py",
                "line": 5,
                "title": "silent except",
                "description": "trace2",
            },
        ]
        fix_outcomes = [
            {"finding_index": 0, "status": "fixed"},
            {"finding_index": 1, "status": "skipped", "reason": "too complex"},
        ]
        body = groq_bugteam.build_review_body(
            findings, "llama-3.3-70b-versatile", "abc1234", fix_outcomes
        )
        assert "1 P0 / 1 P1 / 0 P2" in body
        assert "abc1234" in body
        assert "SQL injection" in body
        assert "silent except" in body
        assert "fixed" in body
        assert "skipped: too complex" in body

    def test_marks_findings_without_outcome_as_not_attempted(self):
        findings = [
            {
                "severity": "P2",
                "category": "E",
                "file": "a.py",
                "line": 1,
                "title": "dead code",
                "description": "d",
            },
        ]
        body = groq_bugteam.build_review_body(
            findings, "llama-3.3-70b-versatile", "", []
        )
        assert "not attempted" in body


class TestIsRecoverableHttpError:
    def _make_error(self, status_code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url="x", code=status_code, msg="", hdrs=None, fp=None
        )

    @pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
    def test_recoverable_statuses(self, status):
        assert groq_bugteam.is_recoverable_http_error(self._make_error(status)) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_non_recoverable_statuses(self, status):
        assert groq_bugteam.is_recoverable_http_error(self._make_error(status)) is False

    def test_413_triggers_skip_to_next_model(self):
        assert groq_bugteam.should_skip_to_next_model(self._make_error(413)) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
    def test_other_statuses_do_not_trigger_model_skip(self, status):
        assert groq_bugteam.should_skip_to_next_model(self._make_error(status)) is False


class TestCallGroqWithFallback:
    def _install_fake_transport(self, monkeypatch, fake_post_to_groq):
        monkeypatch.setattr(groq_bugteam, "post_to_groq", fake_post_to_groq)
        monkeypatch.setattr(groq_bugteam.time, "sleep", lambda _seconds: None)

    def test_non_recoverable_http_error_does_not_attempt_fallback_model(self, monkeypatch):
        attempted_models: list[str] = []

        def fake_post_to_groq(api_key, model, messages, temperature, max_completion_tokens):
            attempted_models.append(model)
            raise urllib.error.HTTPError(
                url="x", code=401, msg="unauthorized", hdrs=None, fp=None
            )

        self._install_fake_transport(monkeypatch, fake_post_to_groq)
        with pytest.raises(RuntimeError):
            groq_bugteam.call_groq_with_fallback("k", [], 0.0, 100)
        assert attempted_models == [groq_bugteam.GROQ_PRIMARY_MODEL]

    def test_413_falls_back_to_secondary_model(self, monkeypatch):
        attempted_models: list[str] = []

        def fake_post_to_groq(api_key, model, messages, temperature, max_completion_tokens):
            attempted_models.append(model)
            if model == groq_bugteam.GROQ_PRIMARY_MODEL:
                raise urllib.error.HTTPError(
                    url="x", code=413, msg="payload too large", hdrs=None, fp=None
                )
            return "ok-content"

        self._install_fake_transport(monkeypatch, fake_post_to_groq)
        result = groq_bugteam.call_groq_with_fallback("k", [], 0.0, 100)
        assert result.model == groq_bugteam.GROQ_FALLBACK_MODEL
        assert attempted_models[0] == groq_bugteam.GROQ_PRIMARY_MODEL
        assert groq_bugteam.GROQ_FALLBACK_MODEL in attempted_models

    def test_recoverable_error_retries_same_model_then_falls_back(self, monkeypatch):
        call_log: list[str] = []

        def fake_post_to_groq(api_key, model, messages, temperature, max_completion_tokens):
            call_log.append(model)
            raise urllib.error.HTTPError(
                url="x", code=503, msg="service unavailable", hdrs=None, fp=None
            )

        self._install_fake_transport(monkeypatch, fake_post_to_groq)
        with pytest.raises(RuntimeError):
            groq_bugteam.call_groq_with_fallback("k", [], 0.0, 100)
        assert call_log.count(groq_bugteam.GROQ_PRIMARY_MODEL) > 1
        assert groq_bugteam.GROQ_FALLBACK_MODEL in call_log


class TestCoerceIndexesToIntSet:
    def test_coerces_string_indexes_to_ints(self):
        assert groq_bugteam.coerce_indexes_to_int_set(["0", "2"]) == {0, 2}

    def test_drops_non_numeric_entries(self):
        assert groq_bugteam.coerce_indexes_to_int_set(["0", "abc", None, 1]) == {0, 1}

    def test_handles_none_input(self):
        assert groq_bugteam.coerce_indexes_to_int_set(None) == set()

    def test_handles_empty_list(self):
        assert groq_bugteam.coerce_indexes_to_int_set([]) == set()

    def test_accepts_already_int_values(self):
        assert groq_bugteam.coerce_indexes_to_int_set([0, 1, 2]) == {0, 1, 2}


class TestCoerceSkippedEntries:
    def test_coerces_string_finding_index_to_int(self):
        assert groq_bugteam.coerce_skipped_entries(
            [{"finding_index": "3", "reason": "x"}]
        ) == {3: "x"}

    def test_drops_entries_without_parseable_index(self):
        assert groq_bugteam.coerce_skipped_entries(
            [{"finding_index": "not-a-number", "reason": "x"}]
        ) == {}

    def test_drops_entries_missing_finding_index(self):
        assert groq_bugteam.coerce_skipped_entries([{"reason": "orphan"}]) == {}

    def test_defaults_reason_to_empty_string(self):
        assert groq_bugteam.coerce_skipped_entries([{"finding_index": 1}]) == {1: ""}

    def test_handles_none_input(self):
        assert groq_bugteam.coerce_skipped_entries(None) == {}

    def test_treats_none_reason_as_empty_string(self):
        assert groq_bugteam.coerce_skipped_entries(
            [{"finding_index": 1, "reason": None}]
        ) == {1: ""}

    def test_stringifies_non_string_reasons(self):
        assert groq_bugteam.coerce_skipped_entries(
            [{"finding_index": 1, "reason": 42}]
        ) == {1: "42"}


class TestBuildFixUserMessage:
    def test_embeds_file_content_byte_for_byte_with_trailing_newline(self):
        original_content = "line1\nline2\n"
        message = groq_bugteam.build_fix_user_message("some.py", original_content, findings_block="[]")
        assert original_content in message
        assert "line2\n</current_file_contents>" in message

    def test_embeds_file_content_byte_for_byte_without_trailing_newline(self):
        original_content = "line1\nline2"
        message = groq_bugteam.build_fix_user_message("some.py", original_content, findings_block="[]")
        assert f"{original_content}\n</current_file_contents>" in message
        assert "line2\n\n</current_file_contents>" not in message


class TestShouldWriteFixedFile:
    def test_does_not_write_when_no_finding_applied(self):
        assert groq_bugteam.should_write_fixed_file(
            applied_indexes=set(),
            updated_content="new",
            current_content="old",
        ) is False

    def test_does_not_write_when_content_unchanged(self):
        assert groq_bugteam.should_write_fixed_file(
            applied_indexes={0},
            updated_content="same",
            current_content="same",
        ) is False

    def test_writes_when_finding_applied_and_content_changed(self):
        assert groq_bugteam.should_write_fixed_file(
            applied_indexes={0},
            updated_content="new",
            current_content="old",
        ) is True


class TestPreserveTrailingNewline:
    def test_adds_trailing_newline_when_original_had_one(self):
        preserved = groq_bugteam.preserve_trailing_newline(
            original="line1\nline2\n", updated="line1\nfixed2"
        )
        assert preserved == "line1\nfixed2\n"

    def test_strips_trailing_newline_when_original_lacked_one(self):
        preserved = groq_bugteam.preserve_trailing_newline(
            original="no newline", updated="fixed content\n"
        )
        assert preserved == "fixed content"

    def test_keeps_matching_form_unchanged(self):
        assert (
            groq_bugteam.preserve_trailing_newline(original="x\n", updated="y\n")
            == "y\n"
        )
        assert (
            groq_bugteam.preserve_trailing_newline(original="x", updated="y") == "y"
        )


class TestIsSafeRelativePath:
    def test_rejects_absolute_posix_path(self):
        assert groq_bugteam.is_safe_relative_path("/etc/passwd") is False

    def test_rejects_parent_directory_escape(self):
        assert groq_bugteam.is_safe_relative_path("../../etc/passwd") is False

    def test_rejects_embedded_parent_reference(self):
        assert groq_bugteam.is_safe_relative_path("src/../../etc/passwd") is False

    def test_accepts_simple_relative_path(self):
        assert groq_bugteam.is_safe_relative_path("src/foo.py") is True

    def test_accepts_nested_relative_path(self):
        assert groq_bugteam.is_safe_relative_path("packages/mod/scripts/foo.py") is True


class TestDecodeSubprocessStderr:
    def test_decodes_bytes_input(self):
        decoded = groq_bugteam.decode_subprocess_stderr(b"fatal: broken")
        assert decoded == "fatal: broken"

    def test_returns_str_input_unchanged(self):
        assert groq_bugteam.decode_subprocess_stderr("fatal: broken") == "fatal: broken"

    def test_handles_none_input(self):
        assert groq_bugteam.decode_subprocess_stderr(None) == ""

    def test_replaces_undecodable_bytes(self):
        decoded = groq_bugteam.decode_subprocess_stderr(b"\xff\xfe broken")
        assert "broken" in decoded


class TestRunPipelineRefusals:
    def test_rejects_missing_api_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(
            groq_bugteam_dotenv,
            "claude_dev_env_dotenv_path",
            lambda: tmp_path / "missing.env",
        )
        result = groq_bugteam.run_pipeline({"diff": "anything"})
        assert "error" in result
        assert "GROQ_API_KEY" in result["error"]

    def test_rejects_empty_diff(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_placeholder_value")
        result = groq_bugteam.run_pipeline({"diff": "   ", "files_content": {}})
        assert "error" in result
        assert "diff is empty" in result["error"]

    def test_rejects_fixes_without_worktree(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_placeholder_value")
        result = groq_bugteam.run_pipeline(
            {"diff": "some diff", "files_content": {"a.py": ""}, "apply_fixes": True}
        )
        assert "error" in result
        assert "worktree_path" in result["error"]
