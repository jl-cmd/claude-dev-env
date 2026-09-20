"""Fixed inputs a case row is evaluated with, and the git fixture argument lists."""

from __future__ import annotations

from hook_audit_parts.config.hook_harness_constants import Outcome

MALFORMED_STDIN = "{not json"
ALL_STOPPING_OUTCOMES: frozenset[Outcome] = frozenset({"block", "ask", "rewrite"})
ALL_GIT_IDENTITY_ARGUMENTS = (
    "-c",
    "user.name=audit",
    "-c",
    "user.email=audit@example.invalid",
)
ALL_GIT_INIT_BARE_ARGUMENTS = ("init", "--bare", "--initial-branch=main", ".")
ALL_GIT_ADD_FIRST_ARGUMENTS = ("add", "first.txt")
ALL_GIT_ADD_SECOND_ARGUMENTS = ("add", "second.txt")
ALL_GIT_COMMIT_FIRST_ARGUMENTS = ("commit", "-m", "first")
ALL_GIT_COMMIT_SECOND_ARGUMENTS = ("commit", "-m", "second")
ALL_GIT_PUSH_MAIN_ARGUMENTS = ("push", "origin", "HEAD:main")
ALL_ORIGIN_HEAD_ARGUMENTS = ("rev-parse", "refs/heads/main")
ALL_CACHED_ORIGIN_HEAD_ARGUMENTS = ("rev-parse", "refs/remotes/origin/main")
FIRST_FILE_NAME = "first.txt"
SECOND_FILE_NAME = "second.txt"
FIRST_FILE_TEXT = "first\n"
SECOND_FILE_TEXT = "second\n"
ORIGIN_DIRECTORY_NAME = "origin.git"
SEED_DIRECTORY_NAME = "seed"
CLONE_DIRECTORY_NAME = "clone"
STALE_CLONE_FIXTURE_NAME = "stale_clone"
UTF8_ENCODING = "utf-8"
