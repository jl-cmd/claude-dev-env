"""Load plan-to-pr skill constants without colliding with repo-root config.

Repo pytest sets ``pythonpath = .``, so a bare ``from config.constants import …``
can bind the monorepo root ``config`` package instead of this skill's
``scripts/config/constants.py``. Load the skill file under a unique module name
and re-export its public names for script imports.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_skill_constants_module() -> ModuleType:
    """Return the skill-local constants module, loading it once per process."""
    skill_constants_module_name = "plan_to_pr_scripts_config_constants"
    skill_constants_path = Path(__file__).resolve().parent / "config" / "constants.py"
    existing_module = sys.modules.get(skill_constants_module_name)
    if existing_module is not None:
        return existing_module
    module_spec = importlib.util.spec_from_file_location(
        skill_constants_module_name, skill_constants_path
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError(
            f"unable to load plan-to-pr skill constants from {skill_constants_path}"
        )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules[skill_constants_module_name] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_skill_constants = _load_skill_constants_module()
for each_constant_name, each_constant_binding in _skill_constants.__dict__.items():
    if each_constant_name.startswith("_"):
        continue
    globals()[each_constant_name] = each_constant_binding
