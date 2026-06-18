"""Directory-name allowlist consumed by ``code_rules_path_utils.is_config_file``.

``code_rules_enforcer.py`` and ``validators/exempt_paths.py`` use the
classifier to decide whether a file is a config file. The classifier
walks every parent directory segment and returns True when any segment
matches a name in this set. Keeping the set in ``hooks_constants`` makes
the classifier importable without a self-exempting hook in the consumer
module.
"""

from __future__ import annotations


ALL_CONFIG_DIRECTORY_NAMES = frozenset(
    {
        "anthropic_plan_scripts_constants",
        "config",
        "hooks_constants",
        "git_hooks_constants",
        "pr_loop_shared_constants",
        "skills_pr_loop_constants",
        "pr_converge_skill_constants",
        "pr_converge_scripts_constants",
        "bugteam_scripts_constants",
        "doc_gist_scripts_constants",
        "implement_scripts_constants",
        "dev_env_scripts_constants",
    }
)
