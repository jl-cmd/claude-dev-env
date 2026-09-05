#!/usr/bin/env python3
"""Run staged policy lint, then preserve the existing staged CODE_RULES gate.

Git invokes this module through the installed native pre-commit shim. Policy
lint reads the Git index, including GIT_INDEX_FILE when Git supplies an alternate
index. It runs locally for every repository using the managed native hook;
GitHub Actions are not required. The existing gate remains for checks whose
replacement coverage has not been established.

A missing linter, launch failure, or timeout is an infrastructure failure rather
than a clean result. Linter diagnostics and failed-rule statuses reach Git.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gate_utils import is_safe_regular_file, resolve_gate_script_path
from git_hooks_constants import (
    GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    GATE_SCRIPT_NOT_FOUND_MESSAGE,
    IMMEDIATE_SCOPE_ARGUMENT,
    INVOKE_GATE_FAILURE_MESSAGE,
)
from git_hooks_constants.staged_policy_lint import (
    POLICY_LINT_FAILED_MESSAGE,
    POLICY_LINT_INFRASTRUCTURE_EXIT_CODE,
    POLICY_LINT_PACKAGE_PARENT_INDEX,
    POLICY_LINT_SCRIPT_RELATIVE_PATH,
    POLICY_LINT_STAGED_ARGUMENT,
    POLICY_LINT_TIMEOUT_SECONDS,
    POLICY_LINT_UNAVAILABLE_MESSAGE,
)


def resolve_policy_lint_script_path() -> Path:
    """Resolve the linter shipped beside this source or installed hooks tree.

    Returns:
        The policy-linter entry point in the same package or managed home.
    """
    package_root = Path(__file__).resolve().parents[POLICY_LINT_PACKAGE_PARENT_INDEX]
    return package_root / POLICY_LINT_SCRIPT_RELATIVE_PATH


def run_staged_policy_lint() -> int:
    """Run the actual staged linter with Git's environment and working directory.

    Returns:
        The linter status, or the infrastructure status when it cannot run.
    """
    try:
        script_path = resolve_policy_lint_script_path()
        if not script_path.is_file():
            print(POLICY_LINT_UNAVAILABLE_MESSAGE, file=sys.stderr)
            return POLICY_LINT_INFRASTRUCTURE_EXIT_CODE
        completion = subprocess.run(
            [sys.executable, str(script_path.resolve(strict=True)), POLICY_LINT_STAGED_ARGUMENT],
            check=False,
            timeout=POLICY_LINT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as launch_error:
        print(POLICY_LINT_FAILED_MESSAGE.format(error=launch_error), file=sys.stderr)
        return POLICY_LINT_INFRASTRUCTURE_EXIT_CODE
    return completion.returncode


def invoke_gate(gate_script_path: Path) -> int:
    """Invoke the shared staged gate and return its exit code."""
    immediate_scope_argument = IMMEDIATE_SCOPE_ARGUMENT
    invoke_gate_failure_message = INVOKE_GATE_FAILURE_MESSAGE
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    try:
        resolved_gate_path = gate_script_path.resolve(strict=True)
        completion = subprocess.run(
            [sys.executable, str(resolved_gate_path), immediate_scope_argument],
            check=False,
        )
    except OSError as launch_error:
        print(
            invoke_gate_failure_message.format(error=launch_error),
            file=sys.stderr,
        )
        return gate_infrastructure_failure_exit_code
    return completion.returncode


def main() -> int:
    """Run local staged policy lint before the retained native commit checks.

    Returns:
        The first failing check's status, or zero when the checks pass.
    """
    lint_exit_code = run_staged_policy_lint()
    if lint_exit_code != 0:
        return lint_exit_code
    gate_script_not_found_message = GATE_SCRIPT_NOT_FOUND_MESSAGE
    gate_script_path, exact_allowed_path = resolve_gate_script_path()
    if not is_safe_regular_file(gate_script_path, exact_allowed_path):
        print(
            gate_script_not_found_message.format(path=gate_script_path),
            file=sys.stderr,
        )
        return 0
    return invoke_gate(gate_script_path)


if __name__ == "__main__":
    sys.exit(main())
