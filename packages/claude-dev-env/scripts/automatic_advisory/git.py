from __future__ import annotations

import os
import subprocess

from pr_verification.model import PullRequestCandidate

from .config.constants import (
    GIT_BASE_REFSPEC_TEMPLATE,
    GIT_EXECUTABLE,
    GIT_FETCH_ARGUMENT,
    GIT_FORCE_FLAG,
    GIT_NO_TAGS_FLAG,
    GIT_PROMPT_DISABLED_VALUE,
    GIT_REMOTE_BASE_REFSPEC_TEMPLATE,
    GIT_TERMINAL_PROMPT_ENVIRONMENT_KEY,
)
from .config.timing import GIT_FETCH_TIMEOUT_SECONDS
from .model import AdvisoryRegistration


def _fetch_base(
    registration: AdvisoryRegistration,
    candidate: PullRequestCandidate,
) -> bool:
    all_fetch_refspecs = _base_fetch_refspecs(registration, candidate)
    try:
        completed_process = subprocess.run(
            (
                GIT_EXECUTABLE,
                GIT_FETCH_ARGUMENT,
                GIT_FORCE_FLAG,
                GIT_NO_TAGS_FLAG,
                registration.remote_name,
                *all_fetch_refspecs,
            ),
            cwd=registration.checkout_path,
            capture_output=True,
            check=False,
            env=_build_git_environment(),
            timeout=GIT_FETCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed_process.returncode == 0


def _base_fetch_refspecs(
    registration: AdvisoryRegistration,
    candidate: PullRequestCandidate,
) -> tuple[str, str]:
    return (
        GIT_BASE_REFSPEC_TEMPLATE.format(
            base_ref=candidate.base_ref,
            pull_request=registration.pull_request_number,
        ),
        GIT_REMOTE_BASE_REFSPEC_TEMPLATE.format(
            base_ref=candidate.base_ref,
            remote_name=registration.remote_name,
        ),
    )


def _build_git_environment() -> dict[str, str]:
    git_environment = os.environ.copy()
    git_environment[GIT_TERMINAL_PROMPT_ENVIRONMENT_KEY] = GIT_PROMPT_DISABLED_VALUE
    return git_environment
