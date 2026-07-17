"""Deterministic loader for the verified-commit constants modules.

The blocking hooks import their shared constants as
``from config.verified_commit_constants import ...`` and
``from config.verified_commit_context_constants import ...``. In the installed
hook tree a second, unrelated ``config`` package can sit ahead of this package
on ``sys.path`` and win those dotted names by path order, so the import binds
to the wrong file and raises ImportError on any constant the stale copy lacks.
This module binds each dotted name to its sibling ``config/`` file by explicit
location, so resolution never depends on ``sys.path`` order.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def register_verified_commit_constants() -> None:
    """Bind both verified-commit constants dotted names to their config files.

    ::

        sys.path = ["<installed hooks>", "<blocking>"]  # foreign config first
        register_verified_commit_constants()
        from config.verified_commit_constants import DETACHED_HEAD_LABEL
        ok: bound to <blocking>/config/verified_commit_constants.py

    A ``from config.verified_commit_constants import`` that follows this call
    reads the entry straight from ``sys.modules``, so it resolves to this file
    whatever else owns the ``config`` name. An entry already cached is left in
    place, so the call is idempotent and never displaces a module a caller
    loaded on purpose.

    Returns:
        None. The effect is the ``sys.modules`` registration.
    """
    all_constants_module_stems = (
        "verified_commit_constants",
        "verified_commit_context_constants",
        "verified_commit_gate_output_constants",
    )
    for each_module_stem in all_constants_module_stems:
        _register_config_module(each_module_stem)


def _register_config_module(module_stem: str) -> None:
    """Bind one ``config.<module_stem>`` dotted name to its sibling file."""
    config_module_dotted_name = f"config.{module_stem}"
    if config_module_dotted_name in sys.modules:
        return
    constants_file_path = (
        Path(__file__).resolve().parent / "config" / f"{module_stem}.py"
    )
    module_spec = importlib.util.spec_from_file_location(
        config_module_dotted_name, constants_file_path
    )
    if module_spec is None or module_spec.loader is None:
        return
    constants_module = importlib.util.module_from_spec(module_spec)
    sys.modules[config_module_dotted_name] = constants_module
    module_spec.loader.exec_module(constants_module)
