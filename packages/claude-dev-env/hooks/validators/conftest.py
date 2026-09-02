"""Pytest fixture module ensuring validators directory is importable regardless of invocation cwd."""

import sys
from pathlib import Path


VALIDATORS_DIRECTORY = Path(__file__).resolve().parent
HOOKS_DIRECTORY = VALIDATORS_DIRECTORY.parent
VALIDATORS_DIRECTORY_STRING = str(VALIDATORS_DIRECTORY)
HOOKS_DIRECTORY_STRING = str(HOOKS_DIRECTORY)

for each_directory_string in (VALIDATORS_DIRECTORY_STRING, HOOKS_DIRECTORY_STRING):
    if each_directory_string in sys.path:
        sys.path.remove(each_directory_string)
    sys.path.insert(0, each_directory_string)

for each_module_name in list(sys.modules):
    if each_module_name != "hooks_constants" and not each_module_name.startswith(
        "hooks_constants."
    ):
        continue
    loaded_file = getattr(sys.modules[each_module_name], "__file__", None)
    if loaded_file is None:
        sys.modules.pop(each_module_name, None)
        continue
    try:
        is_from_this_tree = Path(loaded_file).resolve().is_relative_to(HOOKS_DIRECTORY)
    except (OSError, ValueError):
        is_from_this_tree = False
    if not is_from_this_tree:
        sys.modules.pop(each_module_name, None)
