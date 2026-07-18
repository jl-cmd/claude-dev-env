"""Named constants for the host-aware `/code-review` invoker.

::

    ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
        ok: ("low", "medium", "high", "xhigh", "max")
        flag: "ultra"  (rejected; needs an interactive terminal)
    RECORD_STAMP_FLAG
        ok: "--record-stamp"

Effort tokens re-export the hooks enforcement constants (single source).
Scalar flags, JSON keys, and mint-loop messages live here for the invoker.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_enforcement_constants_module() -> ModuleType:
    """Load the hooks enforcement constants by explicit file path.

    Binds a private module name so a foreign ``config`` package on
    ``sys.path`` cannot win the import and drift the effort token set.
    """
    package_root_directory = Path(__file__).resolve().parent.parent.parent
    constants_file_path = (
        package_root_directory
        / "hooks"
        / "blocking"
        / "config"
        / "code_review_enforcement_constants.py"
    )
    module_name = "_code_review_enforcement_constants_for_scripts"
    cached_module = sys.modules.get(module_name)
    if cached_module is not None:
        return cached_module
    module_spec = importlib.util.spec_from_file_location(
        module_name,
        constants_file_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError(
            f"could not load code-review enforcement constants from {constants_file_path}"
        )
    constants_module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = constants_module
    module_spec.loader.exec_module(constants_module)
    return constants_module


_ENFORCEMENT_CONSTANTS = _load_enforcement_constants_module()

ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER: tuple[str, ...] = (
    _ENFORCEMENT_CONSTANTS.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
)
"""Effort tokens ordered low to max; single source from enforcement constants."""

RECORD_STAMP_FLAG: str = _ENFORCEMENT_CONSTANTS.SANCTIONED_STAMP_MINTER_FLAG
"""CLI flag that forces chain mode and mints a clean stamp on a stable pass."""

DEFAULT_CODE_REVIEW_EFFORT: str = "high"
"""Default effort when the caller omits the positional effort token."""

CODE_REVIEW_SLASH_COMMAND: str = "/code-review"
"""Built-in Claude Code slash command that runs the repository review."""

CODE_REVIEW_FIX_FLAG: str = "--fix"
"""Slash-command flag that applies automatic fixes for review findings."""

CODE_REVIEW_MODEL_ALIAS: str = "opus"
"""CLI `--model` short alias the review always pins to."""

PERMISSION_MODE_FLAG: str = "--permission-mode"
"""CLI flag that selects how the headless claude process handles tool permission prompts."""

PERMISSION_MODE_BYPASS: str = "bypassPermissions"
"""Permission-mode value that auto-approves tools for unattended chain runs."""

MODE_IN_SESSION: str = "in_session"
"""Result mode when the host is Claude and the session already runs opus."""

MODE_CHAIN: str = "chain"
"""Result mode when the helper spawns a headless claude chain for the review."""

RESULT_KEY_MODE: str = "mode"
"""JSON result key naming the review mode (`in_session` or `chain`)."""

RESULT_KEY_SERVED_COMMAND: str = "served_command"
"""JSON result key naming the chain binary that served the call, or null."""

RESULT_KEY_RETURNCODE: str = "returncode"
"""JSON result key holding the process return code from the chain run."""

RESULT_KEY_DIRTY_TREE: str = "dirty_tree"
"""JSON result key holding whether the working tree is dirty after the review."""

CLI_SESSION_MODEL_FLAG: str = "--session-model"
"""CLI flag naming the caller's current session model short alias."""

GIT_BINARY: str = "git"
"""Executable name resolved on PATH for working-tree dirty checks."""

GIT_STATUS_SUBCOMMAND: str = "status"
"""Git subcommand used to detect an uncommitted dirty working tree."""

GIT_PORCELAIN_FLAG: str = "--porcelain"
"""Git status flag that prints machine-readable dirty-path lines."""

IN_SESSION_RETURNCODE: int = 0
"""Return code reported when the helper hands the review back to the in-session skill."""

HOST_PROFILE_ERROR_RETURNCODE: int = 1
"""Return code when host-profile detection raises ValueError at the CLI boundary."""

SUCCESSFUL_REVIEW_RETURNCODE: int = 0
"""Return code required before a clean stamp may advance past CODE_REVIEW."""

RESULT_KEY_STAMP_MINTED: str = "stamp_minted"
"""JSON result key holding whether a clean stamp was written this run."""

RESULT_KEY_PASS_COUNT: str = "pass_count"
"""JSON result key holding how many review passes the mint loop ran."""

RESULT_KEY_BOUND_HASH: str = "bound_hash"
"""JSON result key holding the surface hash bound into a minted stamp, or null."""

CLI_EFFORT_METAVAR: str = "effort"
"""Argparse metavar for the positional effort token."""

CLI_EFFORT_HELP: str = (
    "Review effort token: low, medium, high, xhigh, or max "
    "(ultra is rejected; default high)."
)
"""Help text for the positional effort argument."""

CLI_RECORD_STAMP_HELP: str = (
    "Force chain mode, loop a capped number of review passes, and mint a "
    "clean stamp only when a pass exits 0 with a stable surface hash."
)
"""Help text for the --record-stamp flag."""

INVALID_EFFORT_RETURNCODE: int = 2
"""Return code when the caller passes an unknown or unsupported effort token."""

STAMP_DID_NOT_CONVERGE_RETURNCODE: int = 1
"""Return code when the mint loop hits its pass cap without a stable clean pass."""

MAXIMUM_STAMP_MINT_PASSES: int = 3
"""Cap on review passes under --record-stamp before the invoker gives up."""

EFFORT_TOKEN_LIST_SEPARATOR: str = ", "
"""Separator used when listing allowed effort tokens in error messages."""

INVALID_EFFORT_MESSAGE: str = (
    "invalid effort {effort!r}: must be one of {allowed}; "
    "'ultra' is rejected because it requires an interactive terminal"
)
"""Stderr template when the caller supplies an unknown or ultra effort token."""

STAMP_DID_NOT_CONVERGE_MESSAGE: str = (
    "code-review stamp minting did not converge after {pass_count} passes "
    "(surface kept changing or review return codes stayed non-zero); no stamp written"
)
"""Stderr template when the mint loop hits the pass cap without minting."""

STAMP_STORE_IMPORT_FAILURE_MESSAGE: str = (
    "code-review stamp store could not be imported for --record-stamp: {error}"
)
"""Stderr template when --record-stamp cannot load the stamp store module."""

STAMP_STORE_MODULE_FILE_NAME: str = "code_review_stamp_store.py"
"""File name of the stamp store module under hooks/blocking."""

STAMP_STORE_MODULE_NAME: str = "code_review_stamp_store"
"""Import name of the stamp store module."""

STAMP_STORE_LIVE_SURFACE_HASH_NAME: str = "live_surface_hash"
"""Attribute name of the live surface-hash helper on the stamp store module."""

STAMP_STORE_RECORD_CLEAN_STAMP_NAME: str = "record_clean_stamp"
"""Attribute name of the stamp-mint helper on the stamp store module."""

STAMP_STORE_RESOLVE_REPO_ROOT_NAME: str = "resolve_repo_root"
"""Attribute name of the repo-root resolver on the stamp store module."""
