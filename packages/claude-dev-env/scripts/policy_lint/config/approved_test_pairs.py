from __future__ import annotations

from pathlib import PurePosixPath

APPROVED_TEST_PATHS_BY_PRODUCTION_PATH: dict[
    PurePosixPath, frozenset[PurePosixPath]
] = {
    PurePosixPath(
        "packages/claude-dev-env/hooks/git-hooks/verification_notice_context.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_verification_notice.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/hooks/git-hooks/verification_notice_state.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_verification_notice.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/hooks/hooks_constants/post_tool_use_dispatcher_constants.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/hooks/validation/test_post_tool_use_dispatcher.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/checkout.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/cli.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_recovery.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_repairs.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/configuration.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_recovery.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/execution.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_recovery.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_repairs.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/git.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_repairs.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/model.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_closed_pr_label.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/process_host.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_repairs.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/publisher.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_repairs.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/runner.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_recovery.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_closed_pr_label.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/state.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_closed_pr_label.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/automatic_advisory/windows_job.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_automatic_advisory_job_cleanup.py"
            ),
        }
    ),
    PurePosixPath("packages/claude-dev-env/scripts/local_report_cli.py"): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_report_publisher_cli.py"
            ),
        }
    ),
    PurePosixPath("packages/claude-dev-env/scripts/local_report_core.py"): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_report_publisher.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_report_validation.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_report_publisher.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/check_runner.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/check_support.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/cli.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification_cli.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/command_runner.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/git_state.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/manifest.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/model.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/local_verification/runner.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification.py"
            ),
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_local_verification_cli.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/pr_verification/branch_refs.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_github.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/pr_verification/github_api.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_github.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/pr_verification/github_parsing.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_github.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/pr_verification/github.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_github.py"
            ),
        }
    ),
    PurePosixPath("packages/claude-dev-env/scripts/pr_verification/lock.py"): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_lock.py"
            ),
        }
    ),
    PurePosixPath(
        "packages/claude-dev-env/scripts/pr_verification/model.py"
    ): frozenset(
        {
            PurePosixPath(
                "packages/claude-dev-env/scripts/tests/test_pr_verification_github.py"
            ),
        }
    ),
}
