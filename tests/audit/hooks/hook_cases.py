"""Evaluate a case file row against one registered hook and reach a first verdict."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from hook_audit_parts.config.hook_cases_constants import (
    ALL_CACHED_ORIGIN_HEAD_ARGUMENTS,
    ALL_GIT_ADD_FIRST_ARGUMENTS,
    ALL_GIT_ADD_SECOND_ARGUMENTS,
    ALL_GIT_COMMIT_FIRST_ARGUMENTS,
    ALL_GIT_COMMIT_SECOND_ARGUMENTS,
    ALL_GIT_IDENTITY_ARGUMENTS,
    ALL_GIT_INIT_BARE_ARGUMENTS,
    ALL_GIT_PUSH_MAIN_ARGUMENTS,
    ALL_ORIGIN_HEAD_ARGUMENTS,
    ALL_STOPPING_OUTCOMES,
    CLONE_DIRECTORY_NAME,
    FIRST_FILE_NAME,
    FIRST_FILE_TEXT,
    MALFORMED_STDIN,
    ORIGIN_DIRECTORY_NAME,
    SECOND_FILE_NAME,
    SECOND_FILE_TEXT,
    SEED_DIRECTORY_NAME,
    STALE_CLONE_FIXTURE_NAME,
    UTF8_ENCODING,
)
from hook_harness import (
    HookRegistration,
    HookRun,
    Outcome,
    Sandbox,
    age_path,
    build_payload,
    is_matcher_hit,
    run_event_chain,
    run_hook,
)

CaseKind = Literal["prohibited", "near_neighbor", "malformed", "non_matching"]
MechanismVerdict = Literal["works", "inactive/broken"]


@dataclass(frozen=True)
class CaseRun:
    hook_id: str
    kind: CaseKind
    expected_outcome: Outcome
    run: HookRun
    is_matcher_hit: bool
    all_effect_failures: tuple[str, ...]
    claim_chain_expected: Outcome | None = None
    claim_chain_observed: Outcome | None = None

    @property
    def is_pass(self) -> bool:
        if self.run.outcome == "harness_failure":
            return False
        if self.kind == "malformed":
            return not self.all_effect_failures
        if self.kind == "non_matching":
            return self.run.outcome not in ALL_STOPPING_OUTCOMES
        return (
            self.run.outcome == self.expected_outcome and not self.all_effect_failures
        )


def _run_git(working_directory: Path, all_arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *ALL_GIT_IDENTITY_ARGUMENTS, *all_arguments],
        cwd=str(working_directory),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def build_stale_clone(sandbox: Sandbox) -> None:
    """Create an origin, a clone, and one origin commit the clone has not fetched.

    Args:
        sandbox: The sandbox the origin and both clones are created inside.
    """
    origin_directory = sandbox.root / ORIGIN_DIRECTORY_NAME
    seed_directory = sandbox.root / SEED_DIRECTORY_NAME
    origin_directory.mkdir()
    _run_git(origin_directory, ALL_GIT_INIT_BARE_ARGUMENTS)
    _run_git(sandbox.root, ["clone", str(origin_directory), SEED_DIRECTORY_NAME])
    (seed_directory / FIRST_FILE_NAME).write_text(FIRST_FILE_TEXT, encoding=UTF8_ENCODING)
    _run_git(seed_directory, ALL_GIT_ADD_FIRST_ARGUMENTS)
    _run_git(seed_directory, ALL_GIT_COMMIT_FIRST_ARGUMENTS)
    _run_git(seed_directory, ALL_GIT_PUSH_MAIN_ARGUMENTS)
    _run_git(sandbox.root, ["clone", str(origin_directory), CLONE_DIRECTORY_NAME])
    (seed_directory / SECOND_FILE_NAME).write_text(
        SECOND_FILE_TEXT, encoding=UTF8_ENCODING
    )
    _run_git(seed_directory, ALL_GIT_ADD_SECOND_ARGUMENTS)
    _run_git(seed_directory, ALL_GIT_COMMIT_SECOND_ARGUMENTS)
    _run_git(seed_directory, ALL_GIT_PUSH_MAIN_ARGUMENTS)


def is_origin_ref_current(sandbox: Sandbox) -> bool:
    """Report whether the clone's cached origin ref matches the origin branch.

    Args:
        sandbox: The sandbox holding the origin and the clone.

    Returns:
        True when the clone has fetched the newest origin commit.
    """
    origin_head = _run_git(
        sandbox.root / ORIGIN_DIRECTORY_NAME, ALL_ORIGIN_HEAD_ARGUMENTS
    )
    cached_head = _run_git(
        sandbox.root / CLONE_DIRECTORY_NAME, ALL_CACHED_ORIGIN_HEAD_ARGUMENTS
    )
    return origin_head == cached_head


def apply_setup(sandbox: Sandbox, all_setup_fields: dict[str, object]) -> None:
    """Create the directories, files, and git fixture a case row asks for.

    Args:
        sandbox: The sandbox everything is created inside.
        all_setup_fields: The setup block of the case row.
    """
    for each_directory in _as_list(all_setup_fields.get("dirs")):
        _create_directory(sandbox, each_directory)
    for each_file in _as_list(all_setup_fields.get("files")):
        _create_file(sandbox, each_file)
    if all_setup_fields.get("git_fixture") == STALE_CLONE_FIXTURE_NAME:
        build_stale_clone(sandbox)


def _create_directory(sandbox: Sandbox, all_directory_fields: dict[str, object]) -> None:
    directory_path = Path(sandbox.expand(str(all_directory_fields["path"])))
    directory_path.mkdir(parents=True, exist_ok=True)
    if "age_days" in all_directory_fields:
        age_path(directory_path, float(str(all_directory_fields["age_days"])))


def _create_file(sandbox: Sandbox, all_file_fields: dict[str, object]) -> None:
    file_path = Path(sandbox.expand(str(all_file_fields["path"])))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        sandbox.expand(str(all_file_fields.get("content", ""))), encoding=UTF8_ENCODING
    )
    if "age_days" in all_file_fields:
        age_path(file_path, float(str(all_file_fields["age_days"])))


def _as_list(candidate: object) -> list[dict[str, object]]:
    return candidate if isinstance(candidate, list) else []


def _stdout_failures(run: HookRun, all_expectation_fields: dict[str, object]) -> list[str]:
    all_failures: list[str] = []
    for each_text in _as_list(all_expectation_fields.get("stdout_contains")):
        if str(each_text) not in run.stdout:
            all_failures.append(f"stdout lacks {each_text!r}")
    updated_input = _updated_input(run)
    for each_text in _as_list(all_expectation_fields.get("updated_input_contains")):
        if str(each_text) not in json.dumps(updated_input):
            all_failures.append(f"updatedInput lacks {each_text!r}")
    return all_failures


def _updated_input(run: HookRun) -> object:
    hook_specific = (run.parsed_stdout or {}).get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return {}
    return hook_specific.get("updatedInput", {})


def _path_failures(
    sandbox: Sandbox, all_expectation_fields: dict[str, object]
) -> list[str]:
    all_failures: list[str] = []
    for each_path in _as_list(all_expectation_fields.get("paths_absent")):
        if Path(sandbox.expand(str(each_path))).exists():
            all_failures.append(f"path still present: {each_path}")
    for each_path in _as_list(all_expectation_fields.get("paths_present")):
        if not Path(sandbox.expand(str(each_path))).exists():
            all_failures.append(f"path missing: {each_path}")
    return all_failures


def _file_text_failures(
    sandbox: Sandbox, all_expectation_fields: dict[str, object]
) -> list[str]:
    all_failures: list[str] = []
    for each_check in _as_list(all_expectation_fields.get("file_contains")):
        checked_path = Path(sandbox.expand(str(each_check["path"])))
        checked_text = (
            checked_path.read_text(encoding=UTF8_ENCODING)
            if checked_path.is_file()
            else ""
        )
        if sandbox.expand(str(each_check["text"])) not in checked_text:
            all_failures.append(f"{each_check['path']} lacks {each_check['text']!r}")
    return all_failures


def collect_effect_failures(
    sandbox: Sandbox, run: HookRun, all_expectation_fields: dict[str, object]
) -> list[str]:
    """List every effect a case row expects that the run did not leave behind.

    Args:
        sandbox: The sandbox the run wrote into.
        run: The finished hook run.
        all_expectation_fields: The expect block of the case row.

    Returns:
        One sentence per expectation the run did not meet.
    """
    all_failures = [
        *_stdout_failures(run, all_expectation_fields),
        *_path_failures(sandbox, all_expectation_fields),
        *_file_text_failures(sandbox, all_expectation_fields),
    ]
    if "origin_ref_current" in all_expectation_fields:
        expected_currency = bool(all_expectation_fields["origin_ref_current"])
        if is_origin_ref_current(sandbox) != expected_currency:
            all_failures.append(f"origin ref current is not {expected_currency}")
    return all_failures


def _claim_chain_outcomes(
    all_case_fields: dict[str, object],
    registration: HookRegistration,
    sandbox: Sandbox,
    plugin_root: Path,
    all_registrations: list[HookRegistration] | None,
) -> tuple[Outcome | None, Outcome | None]:
    claim_chain = all_case_fields.get("claim_chain")
    if not isinstance(claim_chain, dict):
        return None, None
    chain_payload = build_payload(
        str(claim_chain["event"]), sandbox, dict(claim_chain["payload"])
    )
    chain_observed = run_event_chain(
        all_registrations or [registration], chain_payload, plugin_root, sandbox
    )
    return claim_chain["expect_outcome"], chain_observed


def run_case(
    registration: HookRegistration,
    all_case_fields: dict[str, object],
    plugin_root: Path,
    sandbox_root: Path,
    all_registrations: list[HookRegistration] | None = None,
) -> CaseRun:
    """Run one case row against one registered hook in a fresh sandbox.

    Args:
        registration: The hook the case row is evaluated against.
        all_case_fields: The case row, with its setup, payload, and expect.
        plugin_root: The checkout the plugin-root placeholder resolves to.
        sandbox_root: The directory the sandbox is built under.
        all_registrations: Every registered hook, for the claim chain.

    Returns:
        What the hook did, and whether it met what the case row expects.
    """
    kind: CaseKind = all_case_fields["kind"]
    sandbox = Sandbox(sandbox_root)
    all_setup_fields = all_case_fields.get("setup", {})
    assert isinstance(all_setup_fields, dict)
    apply_setup(sandbox, all_setup_fields)
    event = str(all_case_fields.get("event", registration.event))
    all_event_fields = all_case_fields.get("payload", {})
    assert isinstance(all_event_fields, dict)
    payload = build_payload(event, sandbox, all_event_fields)
    stdin_text = MALFORMED_STDIN if kind == "malformed" else json.dumps(payload)
    all_extra_environment = {
        str(each_name): str(each_setting)
        for each_name, each_setting in dict(all_case_fields.get("env", {})).items()
    }
    run = run_hook(
        registration, stdin_text, plugin_root, sandbox, all_extra_environment
    )
    all_expectation_fields = all_case_fields.get("expect", {})
    assert isinstance(all_expectation_fields, dict)
    claim_chain_expected, claim_chain_observed = _claim_chain_outcomes(
        all_case_fields, registration, sandbox, plugin_root, all_registrations
    )
    return CaseRun(
        hook_id=registration.hook_id,
        kind=kind,
        expected_outcome=all_expectation_fields.get("outcome", "silent"),
        run=run,
        is_matcher_hit=is_matcher_hit(registration, payload),
        all_effect_failures=tuple(
            collect_effect_failures(sandbox, run, all_expectation_fields)
        ),
        claim_chain_expected=claim_chain_expected,
        claim_chain_observed=claim_chain_observed,
    )


def _case_run_reasons(each_case_run: CaseRun) -> list[str]:
    all_reasons: list[str] = []
    if each_case_run.run.outcome == "harness_failure":
        all_reasons.append(
            f"{each_case_run.kind}: harness-visible failure exit={each_case_run.run.exit_code}"
        )
    elif not each_case_run.is_pass:
        all_reasons.append(
            f"{each_case_run.kind}: expected {each_case_run.expected_outcome}, "
            f"observed {each_case_run.run.outcome} {list(each_case_run.all_effect_failures)}"
        )
    if each_case_run.claim_chain_expected != each_case_run.claim_chain_observed:
        all_reasons.append(
            f"claim: the protected outcome expected {each_case_run.claim_chain_expected}, "
            f"observed {each_case_run.claim_chain_observed} across every registered hook"
        )
    if each_case_run.kind == "prohibited" and not each_case_run.is_matcher_hit:
        all_reasons.append(
            "prohibited: registered matcher never selects the claimed input"
        )
    return all_reasons


def first_verdict(
    all_case_runs: list[CaseRun],
) -> tuple[MechanismVerdict, list[str]]:
    """Flag a hook that crashes, misses its claimed input, or stops a valid neighbor.

    Args:
        all_case_runs: Every case row already run against one hook.

    Returns:
        The verdict, and one sentence per reason behind it.
    """
    all_reasons: list[str] = []
    for each_case_run in all_case_runs:
        all_reasons.extend(_case_run_reasons(each_case_run))
    return ("inactive/broken" if all_reasons else "works"), all_reasons
