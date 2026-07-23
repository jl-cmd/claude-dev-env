/**
 * The top-level skill directory names this package has ever shipped.
 *
 * The installer subtracts the skills the current package installs from this set
 * to learn which shipped skills have retired, so a full reinstall can remove a
 * retired skill left behind under ~/.claude/skills. Because the current set is
 * subtracted at runtime, restoring a retired skill to the package protects it
 * automatically — it re-enters the installed set and drops out of the retired
 * set on the next install.
 *
 * The list is a committed literal rather than a git query, because a user
 * installs from the npm tarball, which carries no source-repo history. Refresh
 * it by running, from the repository root:
 *
 *   git log --all --pretty=format: --name-only -- 'packages/claude-dev-env/skills/*\/SKILL.md' | sort -u
 *
 * and pasting each distinct top-level skill directory name below.
 */
export const EVER_SHIPPED_SKILL_NAMES = new Set([
    'anthropic-plan',
    'auditing-claude-config',
    'autoconverge',
    'bdd-protocol',
    'bg-agent',
    'bugteam',
    'caveman',
    'closeout',
    'code',
    'codex-review',
    'copilot-finding-triage',
    'copilot-review',
    'deep-research',
    'everything-search',
    'findbugs',
    'fixbugs',
    'fresh-branch',
    'gh-paginate',
    'gotcha',
    'grok-spawn',
    'grokify',
    'implement',
    'issue-tracker',
    'log-audit',
    'logifix',
    'monitor-open-prs',
    'orchestrator',
    'orchestrator-refresh',
    'post-audit-findings',
    'pr-consistency-audit',
    'pr-converge',
    'pr-fix-protocol',
    'pr-loop-cloud-transport',
    'pr-loop-lifecycle',
    'pr-review-responder',
    'pr-scope-resolve',
    'pre-compact',
    'privacy-hygiene',
    'qbug',
    'rebase',
    'recall',
    'refine',
    'remember',
    'research-mode',
    'reviewer-gates',
    'session-log',
    'session-tidy',
    'skill-builder',
    'structure-prompt',
    'task-build',
    'team-advisor',
    'update',
    'usage-pause',
    'verified-build',
]);
