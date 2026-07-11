"""Unit tests for pr-description-enforcer readability scoring and state."""

import importlib.util
import io
import json
import pathlib
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from blocking import pr_description_readability as readability_module

hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
validate_pr_body = hook_module.validate_pr_body


@pytest.fixture(autouse=True)
def _isolate_readability_state(tmp_path_factory, monkeypatch):
    """Redirect the three readability state files to per-test temp paths for every test.

    The enabled file is written with enabled=False, which isolates every test from
    the live state directory by setting a readability-off baseline. Tests that
    exercise readability scoring re-enable it via the `readability_state_paths_enabled`
    fixture, which re-points READABILITY_ENABLED_STATE_FILE at a fresh path whose
    missing enabled file defaults to enabled.
    """
    per_test_state_dir = tmp_path_factory.mktemp("readability_state")
    strike_path = per_test_state_dir / "strikes.json"
    override_path = per_test_state_dir / "overrides.json"
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)


@pytest.fixture
def readability_state_paths_enabled(tmp_path, monkeypatch):
    """Redirect the three readability state files to per-test temp paths while keeping
    readability enabled. The autouse `_isolate_readability_state` fixture disables
    readability by default for unrelated tests; tests exercising strike-counter or
    dispatch behavior need it ON, so this fixture re-points the three state paths
    WITHOUT stubbing _is_readability_enabled.

    Returns:
        Tuple of (strike_path, override_path, enabled_path).
    """
    strike_path = tmp_path / "strikes.json"
    override_path = tmp_path / "overrides.json"
    enabled_path = tmp_path / "enabled.json"
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)
    return strike_path, override_path, enabled_path


def _readability_failing_body() -> str:
    """A Heavy-classified body whose intro sentence dramatically exceeds the
    max-sentence-words threshold. Wraps the long sentence in `## Problem` and
    `## Test plan` headers so the Heavy required-header check is satisfied
    and only the readability violation fires; otherwise the missing-header
    violations would inflate the result list and mask readability regressions
    behind broad `any()` substring matches."""
    return (
        "## Problem\n\n"
        "Adds a multi-step coordination protocol that traverses the entire "
        "request lifecycle through every middleware layer in the system, ensuring that "
        "downstream consumers observe a perfectly consistent ordering guarantee across "
        "all participating subsystems including the queueing component and the storage "
        "subsystem and the notification dispatch path that fans out to subscribers "
        "across every channel registered against the tenant scope including email and "
        "push and webhook delivery surfaces simultaneously in one transactional unit.\n\n"
        "## Test plan\n\n"
        "- `pytest packages/claude-dev-env/hooks/blocking/test_pr_description_enforcer.py`\n"
    )


def test_readability_strike_one_emits_metric_violation(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    violations = validate_pr_body(body)
    assert any(
        "readability" in each_violation.lower() or "sentence" in each_violation.lower()
        for each_violation in violations
    )
    assert not any("--readability-loosen" in each_violation for each_violation in violations)
    assert readability_module._read_strike_count() == 1


def test_readability_strike_two_still_metric_violation(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    validate_pr_body(body)
    violations = validate_pr_body(body)
    assert readability_module._read_strike_count() == 2
    assert not any("--readability-loosen" in each_violation for each_violation in violations)


def test_readability_strike_three_fires_escape_hatch(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    validate_pr_body(body)
    validate_pr_body(body)
    violations = validate_pr_body(body)
    assert readability_module._read_strike_count() == 3
    assert any("--readability-loosen" in each_violation for each_violation in violations)
    assert any("--readability-disable" in each_violation for each_violation in violations)
    assert any("--readability-reset" in each_violation for each_violation in violations)


def test_loosen_cap_errors_on_fourth_invocation(readability_state_paths_enabled) -> None:
    assert readability_module._apply_readability_loosen() == "ok"
    assert readability_module._apply_readability_loosen() == "ok"
    assert readability_module._apply_readability_loosen() == "ok"
    fourth_outcome = readability_module._apply_readability_loosen()
    assert fourth_outcome == "cap_reached"


def test_loosen_flesch_floor_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    floor_value = readability_module.READABILITY_MIN_FLESCH_FLOOR
    payload = {
        "flesch_min": floor_value,
        "max_sentence_words": 30,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert readability_module._apply_readability_loosen() == "floor_reached"


def test_loosen_max_sentence_ceiling_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    ceiling_value = readability_module.READABILITY_MAX_SENTENCE_WORDS_CEILING
    payload = {
        "flesch_min": 50,
        "max_sentence_words": ceiling_value,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert readability_module._apply_readability_loosen() == "ceiling_reached"


def test_loosen_avg_sentence_ceiling_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    ceiling_value = readability_module.READABILITY_AVG_SENTENCE_WORDS_CEILING
    payload = {
        "flesch_min": 50,
        "max_sentence_words": 30,
        "avg_sentence_words": ceiling_value,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert readability_module._apply_readability_loosen() == "ceiling_reached"


def test_threshold_override_file_widens_max_sentence_words(readability_state_paths_enabled) -> None:
    """When max_sentence_words override is 50, the loaded thresholds reflect that value."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    payload = {
        "flesch_min": 30,
        "max_sentence_words": 50,
        "avg_sentence_words": 40,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    thresholds = readability_module._load_readability_thresholds()
    assert thresholds.max_sentence_words == 50
    assert thresholds.flesch_min == 30
    assert thresholds.avg_sentence_words == 40


def test_loosen_writes_expected_scaled_thresholds(readability_state_paths_enabled) -> None:
    """First loosen invocation scales flesch by 0.9 and sentence widths by 10/9."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    assert readability_module._apply_readability_loosen() == "ok"
    written_payload = json.loads(override_path.read_text())
    assert written_payload["flesch_min"] == 45
    assert written_payload["max_sentence_words"] == 32
    assert written_payload["avg_sentence_words"] == 20
    assert written_payload["loosens_used"] == 1


def test_dispatch_loosen_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The loosen handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability thresholds loosened 10%\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_loosen_cap_writes_to_error_stream(readability_state_paths_enabled) -> None:
    """When the loosen cap is hit, the handler writes the corrective message to error stream."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps({"loosens_used": readability_module.READABILITY_LOOSEN_CAP})
    )
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 1
    assert "loosen cap reached" in error_stream.getvalue()
    assert output_stream.getvalue() == ""


def test_dispatch_loosen_floor_writes_to_error_stream(readability_state_paths_enabled) -> None:
    """When the floor is reached, the handler writes the corrective message to error stream."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    floor_payload = {
        "flesch_min": readability_module.READABILITY_MIN_FLESCH_FLOOR,
        "max_sentence_words": 30,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(floor_payload))
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 1
    assert "floor/ceiling" in error_stream.getvalue()
    assert output_stream.getvalue() == ""


def test_dispatch_reset_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The reset handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-reset",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability strike counter and override thresholds reset\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_disable_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The disable handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-disable",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability check disabled\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_enable_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The enable handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        readability_module._dispatch_cli_flag(
            "--readability-enable",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability check enabled\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_read_strike_count_clamps_negative_to_zero(readability_state_paths_enabled) -> None:
    """A corrupted strike-count JSON state with a negative integer must not
    silently bypass escalation. Reads clamp to >= 0 so subsequent increments
    walk the strike threshold from a sane baseline."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.parent.mkdir(parents=True, exist_ok=True)
    strike_path.write_text(json.dumps({"strikes": -5}))
    assert readability_module._read_strike_count() == 0, "negative strikes must clamp to 0"


def test_increment_strike_count_clamps_negative_starting_value(
    readability_state_paths_enabled,
) -> None:
    """`_increment_strike_count` must not propagate a corrupted negative
    starting value. The new count after one increment from a negative
    baseline is exactly 1, not (negative + 1)."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.parent.mkdir(parents=True, exist_ok=True)
    strike_path.write_text(json.dumps({"strikes": -3}))
    new_count_after_increment = readability_module._increment_strike_count()
    assert new_count_after_increment == 1, (
        f"increment from negative starting value must clamp first; got {new_count_after_increment}"
    )


def test_read_loosens_used_clamps_negative_to_zero(readability_state_paths_enabled) -> None:
    """A corrupted `loosens_used` JSON state with a negative integer must
    not silently bypass the loosen cap. Reads clamp to >= 0 so the cap
    check enforces the documented ceiling."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps({"loosens_used": -2}))
    assert readability_module._read_loosens_used() == 0, "negative loosens_used must clamp to 0"


def test_strike_count_rejects_boolean_value_as_strikes(readability_state_paths_enabled) -> None:
    """A corrupted strikes.json with `{"strikes": true}` must not be silently
    accepted as the integer 1. Python's `bool` is a subclass of `int`, so a bare
    `isinstance(value, int)` guard lets a malformed payload disable strike
    behavior without warning. The reader must explicitly exclude bool values."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.write_text('{"strikes": true}')
    assert readability_module._read_strike_count() == 0


def test_loosens_used_rejects_boolean_value(readability_state_paths_enabled) -> None:
    """`{"loosens_used": true}` must read as the default 0, not coerce the bool
    to 1 via the `isinstance(x, int)` quirk that accepts bool."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.write_text('{"loosens_used": true}')
    assert readability_module._read_loosens_used() == 0


def test_readability_thresholds_reject_boolean_values(readability_state_paths_enabled) -> None:
    """A threshold field set to a boolean must fall back to the default integer,
    not silently coerce True to 1 or False to 0 via Python's bool-is-int quirk."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.write_text(
        '{"flesch_min": true, "max_sentence_words": false, "avg_sentence_words": true}'
    )
    thresholds = readability_module._load_readability_thresholds()
    assert thresholds.flesch_min == readability_module.DEFAULT_READABILITY_THRESHOLDS.flesch_min
    assert (
        thresholds.max_sentence_words
        == readability_module.DEFAULT_READABILITY_THRESHOLDS.max_sentence_words
    )
    assert (
        thresholds.avg_sentence_words
        == readability_module.DEFAULT_READABILITY_THRESHOLDS.avg_sentence_words
    )


def test_readability_violation_strings_match_agent_doc_format() -> None:
    """The agent SKILL example shows the canonical readability message format
    (`Readability: longest sentence is N words (maximum 28); split or rewrite
    the longest sentence`). The hook's `_evaluate_readability_metrics` must
    emit the same `maximum N` / `split or rewrite` wording so users see the
    exact form documented in the agent file."""
    text_with_long_sentence = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi omicron pi rho sigma tau upsilon phi chi psi omega aleph "
        "beth gimel daleth he waw zayin heth teth yodh kaph lamedh mem nun."
    )
    messages_via_eval = readability_module._evaluate_readability_metrics(
        text_with_long_sentence, readability_module.DEFAULT_READABILITY_THRESHOLDS
    )
    joined_messages = "\n".join(messages_via_eval)
    assert "(maximum" in joined_messages, (
        f"Readability messages must use `maximum N` wording (matching agent doc); "
        f"got: {joined_messages!r}"
    )
    assert "split or rewrite the longest sentence" in joined_messages, (
        f"Longest-sentence message must end with `split or rewrite the longest sentence`; "
        f"got: {joined_messages!r}"
    )


def test_compute_flesch_reading_ease_uses_named_constants() -> None:
    """`_compute_flesch_reading_ease` must reference the named Flesch constants
    rather than embed the magic literals 206.835 / 1.015 / 84.6 / 100.0 inline.
    Smoke-test the empty-input path returns the perfect-score default."""
    perfect_score = readability_module._compute_flesch_reading_ease("")
    assert perfect_score == readability_module.FLESCH_PERFECT_SCORE
    perfect_score_no_words = readability_module._compute_flesch_reading_ease("   ")
    assert perfect_score_no_words == readability_module.FLESCH_PERFECT_SCORE


def test_extract_readability_target_text_strips_fences_before_finding_header() -> None:
    """`_extract_readability_target_text` must strip fenced code blocks before
    searching for the first structural header. Otherwise a fenced example like
    ```\\n## Problem\\n``` is matched as the first header and the intro / section
    boundaries collapse to bogus values."""
    body = (
        "Intro paragraph that should be the intro for readability analysis.\n\n"
        "```\n## Problem\n```\n\n"
        "## RealHeader\n\n"
        "Real first-section prose for readability measurement.\n"
    )
    target_text = readability_module._extract_readability_target_text(body)
    assert "Intro paragraph" in target_text, f"Intro paragraph must survive; got {target_text!r}"
    assert "Real first-section prose" in target_text, (
        f"First real section prose must follow; got {target_text!r}"
    )


def test_single_use_helper_constants_are_inlined() -> None:
    """`_vowel_set`, `_sentence_split_pattern`, and `_all_cli_flag_tokens` each
    had exactly one consumer in production. The file-global-constants rule
    requires either a second caller or a move out of module scope; inlining
    into the single consumer is the chosen resolution. Pin that the three
    names are no longer module attributes so they cannot drift back."""
    for each_name in ("_vowel_set", "_sentence_split_pattern", "_all_cli_flag_tokens"):
        assert not hasattr(readability_module, each_name), (
            f"{each_name} must be inlined into its single consumer, not "
            "carried as a file-global constant."
        )
        assert not hasattr(hook_module, each_name), (
            f"{each_name} must be inlined into its single consumer, not "
            "carried as a file-global constant."
        )
