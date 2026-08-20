"""Put the pr-converge script directories on sys.path for standalone runs.

Importing this module makes the skill's constants package and the shared
``reviews_disabled`` module resolvable when a script in this directory runs
as ``__main__``. Each directory is added once, guarded against duplicates.

The skill tree lives under ``.agents/skills``. Shared PR-loop scripts live
under the package ``_shared`` tree, or under ``~/.claude/_shared`` when this
file is loaded from an installed agents home.
"""

import sys
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_skill_directory = _scripts_directory.parent
_skills_directory = _skill_directory.parent
_skills_home_directory = _skills_directory.parent
_package_or_user_home = (
    _skills_home_directory.parent
    if _skills_home_directory.name == ".agents"
    else _skills_home_directory
)
_shared_under_package = _package_or_user_home / "_shared" / "pr-loop" / "scripts"
_shared_under_claude = (
    _package_or_user_home / ".claude" / "_shared" / "pr-loop" / "scripts"
)
_shared_pr_loop_scripts_directory = (
    _shared_under_package
    if _shared_under_package.is_dir()
    else _shared_under_claude
)
_codex_review_scripts_directory = _skills_directory / "codex-review" / "scripts"

if str(_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_scripts_directory))
if str(_skill_directory) not in sys.path:
    sys.path.insert(0, str(_skill_directory))
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))
if str(_codex_review_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_codex_review_scripts_directory))
