"""Load the code-rules enforcer's ``validate_content`` for in-process use.

The gate runs the same ``validate_content`` the PreToolUse enforcer runs, so it
locates the ``hooks/blocking/code_rules_enforcer.py`` module from disk, executes
it with the hooks directory on ``sys.path``, and hands back its callable.
"""

import importlib.machinery
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from pr_loop_shared_constants.code_rules_gate_constants import GATE_ERROR_EXIT_CODE

ValidateContentCallable = Callable[..., list[str]]

_ENFORCER_RELATIVE_PATH = Path("hooks") / "blocking" / "code_rules_enforcer.py"


def _first_ancestor_with_enforcer(starting_form: Path) -> Path | None:
    """Return the first ancestor of *starting_form* that holds the enforcer.

    Args:
        starting_form: A resolved or absolute path to climb from.

    Returns:
        The ancestor directory containing the enforcer file, or None.
    """
    for each_candidate in [starting_form, *starting_form.parents]:
        if (each_candidate / _ENFORCER_RELATIVE_PATH).is_file():
            return each_candidate
    return None


def resolve_claude_dev_env_root(starting_path: Path) -> Path:
    """Walk up from *starting_path* to the claude-dev-env package root.

    Args:
        starting_path: A path inside the worktree; the function climbs to the
            ancestor holding ``hooks/blocking/code_rules_enforcer.py``.

    Returns:
        The resolved package root that contains the enforcer file.

    Raises:
        SystemExit: When no ancestor contains the enforcer.
    """
    starting = Path(starting_path).resolve()
    found_root = _first_ancestor_with_enforcer(starting)
    if found_root is not None:
        return found_root
    sys.stderr.write(
        f"code_rules_gate: could not locate {_ENFORCER_RELATIVE_PATH} above {starting}\n"
    )
    raise SystemExit(GATE_ERROR_EXIT_CODE)


def _resolve_package_root_absolute(starting_path: Path) -> Path:
    """Return the enforcer-bearing root from an absolute or resolved form.

    Args:
        starting_path: The path to climb from, tried both absolute and resolved.

    Returns:
        The ancestor directory containing the enforcer file.

    Raises:
        SystemExit: When neither form finds the enforcer.
    """
    for each_starting_form in (
        Path(starting_path).absolute(),
        Path(starting_path).resolve(),
    ):
        found_root = _first_ancestor_with_enforcer(each_starting_form)
        if found_root is not None:
            return found_root
    raise SystemExit(GATE_ERROR_EXIT_CODE)


def _hooks_constants_module_names() -> list[str]:
    """Return the loaded module names that belong to the hooks constants package."""
    return [
        each_key
        for each_key in list(sys.modules)
        if each_key == "hooks_constants" or each_key.startswith("hooks_constants.")
    ]


def _load_enforcer_specification(
    enforcer_path: Path,
) -> importlib.machinery.ModuleSpec:
    """Return an import spec for the enforcer module at *enforcer_path*.

    Args:
        enforcer_path: The on-disk path of ``code_rules_enforcer.py``.

    Returns:
        A loadable module specification for the enforcer.

    Raises:
        SystemExit: When the file is missing or a spec cannot be built.
    """
    if not enforcer_path.is_file():
        sys.stderr.write(f"code_rules_gate: missing enforcer at {enforcer_path}\n")
        raise SystemExit(GATE_ERROR_EXIT_CODE)
    specification = importlib.util.spec_from_file_location("code_rules_enforcer", enforcer_path)
    if specification is None or specification.loader is None:
        sys.stderr.write("code_rules_gate: could not load code_rules_enforcer.\n")
        raise SystemExit(GATE_ERROR_EXIT_CODE)
    return specification


def _exec_enforcer_with_hooks_on_path(
    specification: importlib.machinery.ModuleSpec, module: ModuleType
) -> None:
    """Execute *module* with the hooks directory temporarily on ``sys.path``.

    Args:
        specification: The loadable spec whose loader executes the module.
        module: The freshly created enforcer module object to populate.
    """
    loader = specification.loader
    assert loader is not None
    package_root_for_imports = _resolve_package_root_absolute(Path(__file__).absolute())
    hooks_root_path = str(package_root_for_imports / "hooks")
    while hooks_root_path in sys.path:
        sys.path.remove(hooks_root_path)
    if hooks_root_path not in sys.path:
        sys.path.insert(0, hooks_root_path)
    all_saved_modules: dict[str, ModuleType] = {
        each_name: sys.modules.pop(each_name) for each_name in _hooks_constants_module_names()
    }
    try:
        loader.exec_module(module)
    finally:
        _restore_hooks_constants_modules(all_saved_modules, hooks_root_path)


def load_validate_content() -> ValidateContentCallable:
    """Load ``code_rules_enforcer.validate_content`` for in-process use.

    Returns:
        The ``validate_content`` callable from the enforcer module.

    Raises:
        SystemExit: When the package root or the enforcer module cannot load.
    """
    package_root = resolve_claude_dev_env_root(Path(__file__).resolve())
    specification = _load_enforcer_specification(
        package_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    )
    module = importlib.util.module_from_spec(specification)
    _exec_enforcer_with_hooks_on_path(specification, module)
    return module.validate_content


def _restore_hooks_constants_modules(
    all_saved_modules: dict[str, ModuleType], hooks_root_path: str
) -> None:
    """Restore the sys.path and hooks-constants state after loading the enforcer.

    Args:
        all_saved_modules: The hooks-constants modules captured before loading.
        hooks_root_path: The hooks directory added to sys.path for the load.
    """
    while hooks_root_path in sys.path:
        sys.path.remove(hooks_root_path)
    for each_name in _hooks_constants_module_names():
        sys.modules.pop(each_name, None)
    sys.modules.update(all_saved_modules)
