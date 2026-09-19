"""Evaluate a case file row against one registered hook and reach a first verdict."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
MALFORMED_STDIN = "{not json"
ALL_STOPPING_OUTCOMES: frozenset[Outcome] = frozenset({"block", "ask", "rewrite"})
GIT_IDENTITY_ARGUMENTS = [
    "-c",
    "user.name=audit",
    "-c",
    "user.email=audit@example.invalid",
]


@dataclass(frozen=True)
class CaseResult:
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


def _run_git(working_directory: Path, all_arguments: list[str]) -> str:
    completed = subprocess.run(
        ["git", *GIT_IDENTITY_ARGUMENTS, *all_arguments],
        cwd=str(working_directory),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def build_stale_clone(sandbox: Sandbox) -> None:
    """Create an origin, a clone, and one origin commit the clone has not fetched."""
    origin_directory = sandbox.root / "origin.git"
    seed_directory = sandbox.root / "seed"
    origin_directory.mkdir()
    _run_git(origin_directory, ["init", "--bare", "--initial-branch=main", "."])
    _run_git(sandbox.root, ["clone", str(origin_directory), "seed"])
    (seed_directory / "first.txt").write_text("first\n", encoding="utf-8")
    _run_git(seed_directory, ["add", "first.txt"])
    _run_git(seed_directory, ["commit", "-m", "first"])
    _run_git(seed_directory, ["push", "origin", "HEAD:main"])
    _run_git(sandbox.root, ["clone", str(origin_directory), "clone"])
    (seed_directory / "second.txt").write_text("second\n", encoding="utf-8")
    _run_git(seed_directory, ["add", "second.txt"])
    _run_git(seed_directory, ["commit", "-m", "second"])
    _run_git(seed_directory, ["push", "origin", "HEAD:main"])


def is_origin_ref_current(sandbox: Sandbox) -> bool:
    origin_head = _run_git(
        sandbox.root / "origin.git", ["rev-parse", "refs/heads/main"]
    )
    cached_head = _run_git(
        sandbox.root / "clone", ["rev-parse", "refs/remotes/origin/main"]
    )
    return origin_head == cached_head


def apply_setup(sandbox: Sandbox, setup: dict[str, object]) -> None:
    for each_directory in _as_list(setup.get("dirs")):
        directory_path = Path(sandbox.expand(str(each_directory["path"])))
        directory_path.mkdir(parents=True, exist_ok=True)
        if "age_days" in each_directory:
            age_path(directory_path, float(each_directory["age_days"]))
    for each_file in _as_list(setup.get("files")):
        file_path = Path(sandbox.expand(str(each_file["path"])))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(sandbox.expand(str(each_file.get("content", ""))), encoding="utf-8")
        if "age_days" in each_file:
            age_path(file_path, float(each_file["age_days"]))
    if setup.get("git_fixture") == "stale_clone":
        build_stale_clone(sandbox)


def _as_list(candidate: object) -> list[dict[str, object]]:
    return candidate if isinstance(candidate, list) else []


def collect_effect_failures(
    sandbox: Sandbox, run: HookRun, expectation: dict[str, object]
) -> list[str]:
    all_failures: list[str] = []
    for each_text in expectation.get("stdout_contains", []):
        if str(each_text) not in run.stdout:
            all_failures.append(f"stdout lacks {each_text!r}")
    for each_text in expectation.get("updated_input_contains", []):
        hook_specific = (run.parsed_output or {}).get("hookSpecificOutput", {})
        updated_input = (
            hook_specific.get("updatedInput", {})
            if isinstance(hook_specific, dict)
            else {}
        )
        if str(each_text) not in json.dumps(updated_input):
            all_failures.append(f"updatedInput lacks {each_text!r}")
    for each_path in expectation.get("paths_absent", []):
        if Path(sandbox.expand(str(each_path))).exists():
            all_failures.append(f"path still present: {each_path}")
    for each_path in expectation.get("paths_present", []):
        if not Path(sandbox.expand(str(each_path))).exists():
            all_failures.append(f"path missing: {each_path}")
    for each_check in expectation.get("file_contains", []):
        checked_path = Path(sandbox.expand(str(each_check["path"])))
        checked_text = (
            checked_path.read_text(encoding="utf-8") if checked_path.is_file() else ""
        )
        if sandbox.expand(str(each_check["text"])) not in checked_text:
            all_failures.append(f"{each_check['path']} lacks {each_check['text']!r}")
    if "origin_ref_current" in expectation:
        if is_origin_ref_current(sandbox) != bool(expectation["origin_ref_current"]):
            all_failures.append(
                f"origin ref current is not {expectation['origin_ref_current']}"
            )
    return all_failures


def run_case(
    registration: HookRegistration,
    case: dict[str, object],
    plugin_root: Path,
    sandbox_root: Path,
    all_registrations: list[HookRegistration] | None = None,
) -> CaseResult:
    kind: CaseKind = case["kind"]
    sandbox = Sandbox(sandbox_root)
    setup = case.get("setup", {})
    assert isinstance(setup, dict)
    apply_setup(sandbox, setup)
    event = str(case.get("event", registration.event))
    event_fields = case.get("payload", {})
    assert isinstance(event_fields, dict)
    payload = build_payload(event, sandbox, event_fields)
    stdin_text = MALFORMED_STDIN if kind == "malformed" else json.dumps(payload)
    extra_environment = {
        str(each_name): str(each_value)
        for each_name, each_value in dict(case.get("env", {})).items()
    }
    run = run_hook(registration, stdin_text, plugin_root, sandbox, extra_environment)
    expectation = case.get("expect", {})
    assert isinstance(expectation, dict)
    claim_chain = case.get("claim_chain")
    claim_chain_expected: Outcome | None = None
    claim_chain_observed: Outcome | None = None
    if isinstance(claim_chain, dict):
        chain_payload = build_payload(
            str(claim_chain["event"]), sandbox, dict(claim_chain["payload"])
        )
        claim_chain_expected = claim_chain["expect_outcome"]
        claim_chain_observed = run_event_chain(
            all_registrations or [registration], chain_payload, plugin_root, sandbox
        )
    return CaseResult(
        hook_id=registration.hook_id,
        kind=kind,
        expected_outcome=expectation.get("outcome", "silent"),
        run=run,
        is_matcher_hit=is_matcher_hit(registration, payload),
        all_effect_failures=tuple(collect_effect_failures(sandbox, run, expectation)),
        claim_chain_expected=claim_chain_expected,
        claim_chain_observed=claim_chain_observed,
    )


def first_verdict(
    all_case_results: list[CaseResult],
) -> tuple[MechanismVerdict, list[str]]:
    """Flag a hook that crashes, misses its claimed input, or stops a valid neighbor."""
    all_reasons: list[str] = []
    for each_result in all_case_results:
        if each_result.run.outcome == "harness_failure":
            all_reasons.append(
                f"{each_result.kind}: harness-visible failure exit={each_result.run.exit_code}"
            )
        elif not each_result.is_pass:
            all_reasons.append(
                f"{each_result.kind}: expected {each_result.expected_outcome}, "
                f"observed {each_result.run.outcome} {list(each_result.all_effect_failures)}"
            )
        if each_result.claim_chain_expected != each_result.claim_chain_observed:
            all_reasons.append(
                f"claim: the protected outcome expected {each_result.claim_chain_expected}, "
                f"observed {each_result.claim_chain_observed} across every registered hook"
            )
        if each_result.kind == "prohibited" and not each_result.is_matcher_hit:
            all_reasons.append(
                "prohibited: registered matcher never selects the claimed input"
            )
    return ("inactive/broken" if all_reasons else "works"), all_reasons
