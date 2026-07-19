"""Configuration constants for the ``enter_worktree_origin_prefetch`` hook.

The hook keeps a freshly created worktree from starting on a stale cached
``refs/remotes/origin/<default-branch>`` value: it fetches that ref right
before ``EnterWorktree`` resolves its base.
"""

from __future__ import annotations

ENTER_WORKTREE_TOOL_NAME: str = "EnterWorktree"
ENTER_WORKTREE_PATH_INPUT_KEY: str = "path"

ORIGIN_REMOTE_NAME: str = "origin"
ORIGIN_HEAD_SYMBOLIC_REF: str = "refs/remotes/origin/HEAD"
ORIGIN_REMOTE_REF_PREFIX: str = "refs/remotes/origin/"

GIT_SYMBOLIC_REF_TIMEOUT_SECONDS: int = 5
GIT_FETCH_TIMEOUT_SECONDS: int = 15
