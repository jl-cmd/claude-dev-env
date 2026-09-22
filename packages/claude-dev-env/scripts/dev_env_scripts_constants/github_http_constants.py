"""GitHub REST request constants shared by independent request-building modules.

``agent_merge_check_constants.py``, ``merge_gate_check_constants.py``, and
``pr_verification/config/constants.py`` each built their own copy of these
literals. This module holds the one copy; it carries no third-party import so
that ``agent_merge_check.py`` and ``merge_gate_checks.py`` can read it without
pulling in the PyJWT dependency that ``pr_verification`` scopes to itself.
"""

from __future__ import annotations

GITHUB_API_ROOT: str = "https://api.github.com"
ACCEPT_HEADER: str = "Accept"
GITHUB_ACCEPT_TYPE: str = "application/vnd.github+json"
AUTHORIZATION_HEADER: str = "Authorization"
BEARER_PREFIX: str = "Bearer "
UTF8_ENCODING: str = "utf-8"
