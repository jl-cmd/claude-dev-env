#!/usr/bin/env node

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, copyFileSync, unlinkSync, rmSync, realpathSync } from 'node:fs';
import { join, dirname, resolve, relative } from 'node:path';
import { homedir } from 'node:os';
import { execSync, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { installAllGitHooks } from './git_hooks_installer.mjs';
import { installMypyIniForClaudeHooks } from './install_mypy_ini.mjs';

const CLAUDE_HOME = join(homedir(), '.claude');
const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MANIFEST_FILE = join(CLAUDE_HOME, '.claude-dev-env-manifest.json');
const PACKAGE_NAME = 'claude-dev-env';
const PACKAGE_VERSION = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
const packageRequire = createRequire(import.meta.url);

export const CONTENT_DIRECTORIES = ['rules', 'docs', 'commands', 'agents', 'system-prompts', 'scripts', '_shared', 'audit-rubrics'];

export function collectPackageSourceConflicts(packageDirectory) {
    const gitConflictStatusCodes = new Set(['DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU']);
    const porcelainStatusLineMinLength = 4;
    const porcelainStatusCodeLength = 2;
    const porcelainPathOffset = 3;
    const gitNotARepoExitStatus = 128;
    const gitNotARepoStderrMarker = 'not a git repository';
    const gitBinaryMissingErrorCode = 'ENOENT';
    let porcelainOutput;
    try {
        porcelainOutput = execFileSync(
            'git',
            ['status', '--porcelain', '-z', '--', '.'],
            {
                cwd: packageDirectory,
                encoding: 'utf8',
                stdio: ['ignore', 'pipe', 'pipe'],
            },
        );
    } catch (gitInvocationError) {
        const isGitBinaryMissing = gitInvocationError.code === gitBinaryMissingErrorCode;
        if (isGitBinaryMissing) {
            console.error(
                '  Note: source-state guard skipped — git binary not available on PATH.',
            );
            return [];
        }
        const stderrText = gitInvocationError.stderr ? gitInvocationError.stderr.toString() : '';
        const isNotARepoFailure = gitInvocationError.status === gitNotARepoExitStatus
            && stderrText.includes(gitNotARepoStderrMarker);
        if (isNotARepoFailure) {
            return [];
        }
        throw gitInvocationError;
    }
    const allConflicts = [];
    for (const rawRecord of porcelainOutput.split('\0')) {
        if (rawRecord.length < porcelainStatusLineMinLength) continue;
        const statusCode = rawRecord.slice(0, porcelainStatusCodeLength);
        if (!gitConflictStatusCodes.has(statusCode)) continue;
        const conflictPath = rawRecord.slice(porcelainPathOffset);
        allConflicts.push({ statusCode, path: conflictPath });
    }
    return allConflicts;
}

function abortWhenPackageSourceHasConflicts(packageDirectory) {
    const conflicts = collectPackageSourceConflicts(packageDirectory);
    if (conflicts.length === 0) return;
    console.error(
        `\nERROR: ${PACKAGE_NAME} source has unmerged conflicts under ${packageDirectory}:\n`,
    );
    for (const conflict of conflicts) {
        console.error(`  ${conflict.statusCode} ${conflict.path}`);
    }
    console.error(
        '\nResolve the conflicts in the package source before running the installer.',
    );
    console.error(
        'Installing from a conflicted source can copy stale or broken files into ~/.claude/.\n',
    );
    process.exit(1);
}

function resolveDependencyPackageRoot(dependencyPackageName) {
    const dependencyPackageJsonPath = packageRequire.resolve(
        `${dependencyPackageName}/package.json`
    );
    return dirname(dependencyPackageJsonPath);
}

function discoverDependencyGroups() {
    const ownPackageJsonPath = join(PACKAGE_ROOT, 'package.json');
    const ownPackageJson = JSON.parse(readFileSync(ownPackageJsonPath, 'utf8'));
    const dependencies = ownPackageJson.dependencies || {};
    const discoveredGroups = {};
    for (const dependencyName of Object.keys(dependencies)) {
        let dependencyRoot;
        try {
            dependencyRoot = resolveDependencyPackageRoot(dependencyName);
        } catch {
            console.error(`  WARNING: Could not resolve dependency ${dependencyName}, skipping`);
            continue;
        }
        const dependencyPackageJson = JSON.parse(
            readFileSync(join(dependencyRoot, 'package.json'), 'utf8')
        );
        const groupName = dependencyPackageJson.claudeDevEnv?.groupName
            || dependencyName.replace(/^@[^/]+\//, '');
        const group = {
            description: dependencyPackageJson.description || dependencyName,
            packageRoot: dependencyRoot,
        };
        const skillsDirectory = join(dependencyRoot, 'skills');
        if (existsSync(skillsDirectory)) {
            group.skills = readdirSync(skillsDirectory, { withFileTypes: true })
                .filter(entry => entry.isDirectory())
                .map(entry => entry.name);
        }
        const hooksDirectory = join(dependencyRoot, 'hooks');
        if (existsSync(hooksDirectory)) {
            const hookFiles = collectFiles(hooksDirectory)
                .filter(file => !file.endsWith('hooks.json'))
                .filter(file => {
                    const baseName = file.replace(/\\/g, '/').split('/').pop();
                    return !baseName.startsWith('test_');
                })
                .map(file => relative(hooksDirectory, file).replace(/\\/g, '/'));
            if (hookFiles.length > 0) {
                group.includeHookFiles = hookFiles;
            }
        }
        const rulesDirectory = join(dependencyRoot, 'rules');
        if (existsSync(rulesDirectory)) {
            const ruleFiles = readdirSync(rulesDirectory)
                .filter(file => file.endsWith('.md'));
            if (ruleFiles.length > 0) {
                group.includeRules = ruleFiles;
            }
        }
        discoveredGroups[groupName] = group;
    }
    return discoveredGroups;
}

const INSTALL_GROUPS = {
    core: {
        description: 'Development standards, hooks, agents, commands',
        skills: [
            'anthropic-plan', 'everything-search',
            'pr-review-responder',
            'recall', 'remember', 'task-build', 'verified-build'
        ],
        includeDirectories: ['rules', 'docs', 'commands', 'agents', 'audit-rubrics'],
        includeAllHooks: true,
    },
    journal: {
        description: 'Session logging and memory',
        skills: ['session-log', 'session-tidy'],
    },
    research: {
        description: 'Deep research and citation tools',
        skills: ['deep-research', 'research-mode'],
    },
    ...discoverDependencyGroups(),
};

/**
 * Returns the ordered python interpreter candidates to probe for the given
 * platform. On win32 the `py -3` launcher is probed first because it resolves
 * through the Windows registry and is immune to the Microsoft Store
 * `python.exe` App Execution Alias that otherwise gets baked into settings.json.
 *
 * @param {string} platform A value from `process.platform` (e.g. 'win32', 'linux').
 * @returns {{command: string, versionFlag: string}[]} Candidates in probe order.
 */
export function pythonCandidatesForPlatform(platform) {
    const windowsOrder = [
        { command: 'py -3', versionFlag: '--version' },
        { command: 'python3', versionFlag: '--version' },
        { command: 'python', versionFlag: '--version' },
    ];
    const defaultOrder = [
        { command: 'python3', versionFlag: '--version' },
        { command: 'python', versionFlag: '--version' },
        { command: 'py -3', versionFlag: '--version' },
    ];
    return platform === 'win32' ? windowsOrder : defaultOrder;
}

/**
 * Reports whether a resolved interpreter path belongs to the Microsoft Store
 * Python, whose `python.exe` App Execution Alias reparse stub cannot be spawned
 * as a hook subprocess. Both the alias under `Microsoft\WindowsApps` and the
 * package executable under `Program Files\WindowsApps` sit beneath a
 * `WindowsApps` directory, so the installer skips any candidate resolving there.
 *
 * @param {string} executablePath Absolute interpreter path from sys.executable.
 * @returns {boolean} True when the path lives under a WindowsApps directory.
 */
export function isWindowsStorePythonStub(executablePath) {
    return /[\\/]windowsapps[\\/]/i.test(executablePath);
}

/**
 * Formats an absolute interpreter path as a settings.json hook command prefix:
 * forward-slash separators, double-quoted when the path contains a space so the
 * harness parses the interpreter as a single argument.
 *
 * @param {string} executablePath Absolute interpreter path from sys.executable.
 * @returns {string} The command-prefix form of the interpreter path.
 */
export function interpreterCommandFromPath(executablePath) {
    const forwardSlashedPath = executablePath.replace(/\\/g, '/');
    return forwardSlashedPath.includes(' ') ? `"${forwardSlashedPath}"` : forwardSlashedPath;
}

/**
 * Picks the interpreter command baked into every managed hook in settings.json.
 * On win32 the first working candidate is resolved to its absolute
 * sys.executable and that path is baked in, so a later PATH change or Microsoft
 * Store update that re-points the `py`/`python` launcher cannot silently break
 * the hooks; candidates resolving to the non-spawnable WindowsApps stub are
 * skipped. Other platforms keep the bare command (e.g. `python3`).
 *
 * @returns {string|null} The interpreter command, or null when none is usable.
 */
function detectPython() {
    const candidates = pythonCandidatesForPlatform(process.platform);
    for (const { command, versionFlag } of candidates) {
        try {
            const version = execSync(`${command} ${versionFlag}`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
            if (!version.includes('Python 3.')) continue;
            if (process.platform !== 'win32') return command;
            const executablePath = execSync(`${command} -c "import sys; print(sys.executable)"`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
            if (!executablePath || isWindowsStorePythonStub(executablePath)) continue;
            return interpreterCommandFromPath(executablePath);
        } catch { /* try next */ }
    }
    return null;
}

function collectFiles(directory) {
    const collected = [];
    if (!existsSync(directory)) return collected;
    const entries = readdirSync(directory, { withFileTypes: true });
    for (const entry of entries) {
        const entryPath = join(directory, entry.name);
        if (entry.isDirectory()) {
            collected.push(...collectFiles(entryPath));
        } else {
            collected.push(entryPath);
        }
    }
    return collected;
}

function copyTree(sourceBase, destBase) {
    const files = collectFiles(sourceBase);
    const stats = { created: 0, updated: 0, paths: [] };
    for (const sourceFile of files) {
        const relativePath = relative(sourceBase, sourceFile);
        const destFile = join(destBase, relativePath);
        mkdirSync(dirname(destFile), { recursive: true });
        const existed = existsSync(destFile);
        copyFileSync(sourceFile, destFile);
        stats.paths.push(destFile);
        if (existed) {
            stats.updated++;
            console.log(`  \u21bb ${join(relative(CLAUDE_HOME, destBase), relativePath)} (updated)`);
        } else {
            stats.created++;
            console.log(`  \u2713 ${join(relative(CLAUDE_HOME, destBase), relativePath)} (new)`);
        }
    }
    return stats;
}

/**
 * If destPath exists and differs from incomingPath, copy the existing file to
 * ~/.claude/backups/CLAUDE.md.<timestamp>.bak before the installer overwrites it.
 */
function backupClaudeHubBeforeOverwrite(destPath, incomingPath) {
    if (!existsSync(destPath)) return null;
    const existingBytes = readFileSync(destPath);
    const incomingBytes = readFileSync(incomingPath);
    if (existingBytes.equals(incomingBytes)) return null;
    const backupsDir = join(CLAUDE_HOME, 'backups');
    mkdirSync(backupsDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupPath = join(backupsDir, `CLAUDE.md.${stamp}.bak`);
    copyFileSync(destPath, backupPath);
    return backupPath;
}

/**
 * Hook script paths that were folded into the PreToolUse dispatcher in Stage 1.
 * These entries no longer appear in hooks.json but must still be recognized as
 * managed so a reinstall from an older settings shape prunes them and they do
 * not double-run alongside the dispatcher.
 */
export const FOLDED_HOOK_RELATIVE_PATHS = new Set([
    'blocking/write_existing_file_blocker.py',
    'blocking/sensitive_file_protector.py',
    'validation/hook_format_validator.py',
    'blocking/code_rules_enforcer.py',
    'blocking/tdd_enforcer.py',
    'blocking/windows_rmtree_blocker.py',
    'blocking/state_description_blocker.py',
    'blocking/subprocess_budget_completeness.py',
    'blocking/hook_prose_detector_consistency.py',
    'blocking/verified_commit_message_accuracy_blocker.py',
    'blocking/workflow_substitution_slot_blocker.py',
    'blocking/claude_md_orphan_file_blocker.py',
    'blocking/open_questions_in_plans_blocker.py',
    'blocking/plain_language_blocker.py',
]);

/**
 * Hook script paths that were folded into the PostToolUse dispatcher. These
 * after-write hooks no longer appear in hooks.json but must still be recognized
 * as managed so a reinstall from an older settings shape prunes them and they do
 * not double-run alongside the PostToolUse dispatcher.
 */
export const POST_FOLDED_HOOK_RELATIVE_PATHS = new Set([
    'validation/mypy_validator.py',
    'workflow/auto_formatter.py',
    'workflow/doc_gist_auto_publish.py',
]);

/**
 * Builds the set of hook script paths this installer manages, each relative to
 * the hooks directory (e.g. 'blocking/code_rules_enforcer.py'), parsed from the
 * `${CLAUDE_PLUGIN_ROOT}/hooks/<path>` references in hooks.json. Inline
 * `python3 -c` commands reference the hooks directory without a script tail and
 * contribute nothing. Also includes every path from FOLDED_HOOK_RELATIVE_PATHS
 * and POST_FOLDED_HOOK_RELATIVE_PATHS so a reinstall from an older settings shape
 * prunes both the PreToolUse and the PostToolUse folded entries.
 *
 * @param {{hooks: object}} hooksConfig Parsed hooks.json.
 * @returns {Set<string>} Forward-slash relative script paths under hooks/.
 */
export function managedHookScriptRelativePaths(hooksConfig) {
    const relativePaths = new Set([
        ...FOLDED_HOOK_RELATIVE_PATHS,
        ...POST_FOLDED_HOOK_RELATIVE_PATHS,
    ]);
    const scriptReferencePattern = /\$\{CLAUDE_PLUGIN_ROOT\}\/hooks\/(\S+?\.py)/g;
    for (const matcherGroups of Object.values(hooksConfig.hooks)) {
        for (const sourceGroup of matcherGroups) {
            for (const hook of sourceGroup.hooks) {
                for (const scriptMatch of hook.command.matchAll(scriptReferencePattern)) {
                    relativePaths.add(scriptMatch[1]);
                }
            }
        }
    }
    return relativePaths;
}

/**
 * Builds the union of managed hook script paths across the given package source
 * roots by parsing each root's hooks/hooks.json. The installer copies hook
 * scripts into ~/.claude/hooks/ but never copies hooks.json itself, so the
 * uninstall and update-refresh purge must read the managed-hook set from the
 * package source the same way the merge does, never from ~/.claude/hooks/.
 * Roots without a hooks.json contribute nothing.
 *
 * @param {string[]} sourceRoots Package roots that hold a hooks/hooks.json.
 * @returns {Set<string>} Forward-slash relative script paths under hooks/.
 */
export function managedHookScriptRelativePathsFromSourceRoots(sourceRoots) {
    const relativePaths = new Set();
    for (const sourceRoot of sourceRoots) {
        const hooksJsonPath = join(sourceRoot, 'hooks', 'hooks.json');
        if (!existsSync(hooksJsonPath)) continue;
        const hooksConfig = JSON.parse(readFileSync(hooksJsonPath, 'utf8'));
        for (const relativePath of managedHookScriptRelativePaths(hooksConfig)) {
            relativePaths.add(relativePath);
        }
    }
    return relativePaths;
}

/**
 * Resolves every package source root the installer can copy hooks from: this
 * package plus each resolvable dependency package that ships hooks. The purge
 * reads hooks.json from these roots so it prunes managed entries no matter which
 * package contributed them.
 *
 * @returns {string[]} Distinct package roots, this package first.
 */
function managedPackageSourceRoots() {
    const dependencyRoots = Object.values(INSTALL_GROUPS)
        .filter(group => group.packageRoot)
        .map(group => group.packageRoot);
    return [...new Set([PACKAGE_ROOT, ...dependencyRoots])];
}

/**
 * Reports whether a settings.json hook command points at one of this installer's
 * managed scripts, no matter how the home directory was written ($HOME, ~,
 * ${HOME}, or an absolute path) or which path separator was used. Matching on
 * the `/.claude/hooks/<relative>` tail lets a reinstall prune stale entries from
 * earlier installs that used a different interpreter prefix, while leaving
 * user-authored hooks outside the managed set untouched.
 *
 * @param {string} commandString The hook command from settings.json.
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {boolean} True when the command references a managed script.
 */
export function commandReferencesManagedHook(commandString, managedHookRelativePaths) {
    const normalizedCommand = commandString.replace(/\\/g, '/');
    if (commandIsInlineManagedValidatorRunner(normalizedCommand)) {
        return true;
    }
    for (const relativePath of managedHookRelativePaths) {
        if (commandTailEndsAtManagedHook(normalizedCommand, relativePath)) {
            return true;
        }
    }
    return false;
}

/**
 * Reports whether a command contains the `/.claude/hooks/<relative>` tail ending
 * at a path boundary: end of string, or an argument separator (whitespace, quote,
 * or semicolon). Anchoring the tail keeps a user hook whose path is the managed
 * tail plus a suffix (`code_rules_enforcer.py.bak`, `a.py/extra/thing.py`) outside
 * the managed set, so it is never pruned.
 *
 * @param {string} normalizedCommand Forward-slash-normalized hook command.
 * @param {string} relativePath Managed script path under hooks/.
 * @returns {boolean} True when the managed tail ends at a path boundary.
 */
function commandTailEndsAtManagedHook(normalizedCommand, relativePath) {
    const commandArgumentBoundary = /[\s'";]/;
    const managedTail = `/.claude/hooks/${relativePath}`;
    let searchStart = normalizedCommand.indexOf(managedTail);
    while (searchStart !== -1) {
        const characterAfterTail = normalizedCommand[searchStart + managedTail.length];
        if (characterAfterTail === undefined || commandArgumentBoundary.test(characterAfterTail)) {
            return true;
        }
        searchStart = normalizedCommand.indexOf(managedTail, searchStart + 1);
    }
    return false;
}

/**
 * Reports whether a settings.json hook command is the inline validators-runner
 * the installer writes in place of a standalone script. That hook inserts the
 * managed hooks directory onto sys.path and imports run_all_validators, so it
 * carries no `<script>.py` tail for managedHookScriptRelativePaths to record.
 * Matching its shape lets a reinstall prune the prior copy before appending the
 * freshly rewritten one, keeping the merge idempotent.
 *
 * @param {string} normalizedCommand Forward-slash-normalized hook command.
 * @returns {boolean} True when the command is the inline validators runner.
 */
export function commandIsInlineManagedValidatorRunner(normalizedCommand) {
    const inlineValidatorRunnerMarker = /sys\.path\.insert\([^)]*\.claude\/hooks[^)]*\)[\s\S]*run_all_validators/;
    return (
        normalizedCommand.includes('/.claude/hooks') &&
        inlineValidatorRunnerMarker.test(normalizedCommand)
    );
}

/**
 * Strips every managed hook (standalone script or inline validators runner) from
 * all existing matcher groups of one event in a settings object, dropping any
 * group left empty. Run before the per-group merge so a managed hook that an
 * upgrade moves to a different matcher group is pruned from its old group rather
 * than left to double-run. User-authored hooks outside the managed set stay.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {string} eventType The lifecycle event whose groups are pruned.
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {void}
 */
function pruneManagedHooksFromEvent(settings, eventType, managedHookRelativePaths) {
    const existingGroups = settings.hooks[eventType];
    if (!existingGroups) return;
    settings.hooks[eventType] = existingGroups
        .map(group => ({
            ...group,
            hooks: group.hooks.filter(
                hook => !commandReferencesManagedHook(hook.command, managedHookRelativePaths)
            ),
        }))
        .filter(group => group.hooks.length > 0);
}

/**
 * Merges the installer's managed hook groups into a settings object in memory,
 * pruning every prior managed hook (standalone script or inline validators
 * runner) from each event's existing matcher groups before appending the freshly
 * rewritten copies so repeated merges stay idempotent and a managed hook moved to
 * a new matcher group does not double-run. User-authored hooks are preserved
 * untouched.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {{hooks: object}} hooksConfig Parsed hooks.json.
 * @param {string} pluginRootDir Directory ${CLAUDE_PLUGIN_ROOT} resolves to.
 * @param {string} pythonCommand Interpreter command that replaces python3.
 * @returns {number} Count of matcher groups merged.
 */
export function mergeHooksIntoSettings(settings, hooksConfig, pluginRootDir, pythonCommand) {
    const managedHookRelativePaths = managedHookScriptRelativePaths(hooksConfig);
    if (!settings.hooks) settings.hooks = {};
    let groupCount = 0;
    for (const [eventType, matcherGroups] of Object.entries(hooksConfig.hooks)) {
        if (!settings.hooks[eventType]) settings.hooks[eventType] = [];
        pruneManagedHooksFromEvent(settings, eventType, managedHookRelativePaths);
        for (const sourceGroup of matcherGroups) {
            const rewrittenHooks = sourceGroup.hooks.map(hook => {
                let command = hook.command;
                command = command.replace(/\$\{CLAUDE_PLUGIN_ROOT\}/g, pluginRootDir.replace(/\\/g, '/'));
                command = command.replace(/^python3\b/, pythonCommand);
                return { ...hook, command };
            });
            const existingIndex = settings.hooks[eventType].findIndex(
                group => group.matcher === sourceGroup.matcher
            );
            if (existingIndex >= 0) {
                const existing = settings.hooks[eventType][existingIndex];
                const userHooks = existing.hooks.filter(
                    hook => !commandReferencesManagedHook(hook.command, managedHookRelativePaths)
                );
                settings.hooks[eventType][existingIndex] = {
                    ...existing,
                    hooks: [...userHooks, ...rewrittenHooks],
                };
            } else {
                settings.hooks[eventType].push({ matcher: sourceGroup.matcher, hooks: rewrittenHooks });
            }
            groupCount++;
        }
    }
    return groupCount;
}

/**
 * Removes every managed hook (standalone script or inline validators runner)
 * from a settings object in memory, matching each command through
 * commandReferencesManagedHook so entries written with any home-path style
 * ($HOME, ~, ${HOME}, or absolute) and any path separator are pruned. Matcher
 * groups left empty are dropped, and an empty hooks map is removed entirely.
 * User-authored hooks outside the managed set are preserved untouched.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {void}
 */
export function pruneManagedHooksFromSettings(settings, managedHookRelativePaths) {
    if (!settings.hooks) return;
    for (const [eventType, matcherGroups] of Object.entries(settings.hooks)) {
        settings.hooks[eventType] = matcherGroups
            .map(group => ({
                ...group,
                hooks: group.hooks.filter(
                    hook => !commandReferencesManagedHook(hook.command, managedHookRelativePaths)
                ),
            }))
            .filter(group => group.hooks.length > 0);
        if (settings.hooks[eventType].length === 0) delete settings.hooks[eventType];
    }
    if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
}

function mergeHooks(hooksSourceRoot, pythonCommand) {
    const hooksJsonPath = join(hooksSourceRoot, 'hooks', 'hooks.json');
    if (!existsSync(hooksJsonPath)) return 0;
    const hooksConfig = JSON.parse(readFileSync(hooksJsonPath, 'utf8'));
    const settingsPath = join(CLAUDE_HOME, 'settings.json');
    let settings = {};
    if (existsSync(settingsPath)) {
        const raw = readFileSync(settingsPath, 'utf8').trim();
        if (raw) {
            try { settings = JSON.parse(raw); }
            catch { console.error('  ERROR: settings.json is malformed JSON. Fix it and rerun.'); process.exit(1); }
        }
    }
    const groupCount = mergeHooksIntoSettings(settings, hooksConfig, CLAUDE_HOME, pythonCommand);
    writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
    return groupCount;
}

function writeManifest(installedFiles) {
    const manifest = { package: PACKAGE_NAME, version: PACKAGE_VERSION, installedAt: new Date().toISOString(), files: installedFiles };
    writeFileSync(MANIFEST_FILE, JSON.stringify(manifest, null, 2) + '\n');
}

function install(selectedGroups, options = {}) {
    const isUpdateRefresh = Boolean(options.isUpdateRefresh);
    if (isUpdateRefresh && !selectedGroups && existsSync(MANIFEST_FILE)) {
        console.log(
            `${PACKAGE_NAME}: --update — removing prior managed files under ${CLAUDE_HOME}, then reinstalling from the package.\n`,
        );
        purgeManagedInstallation({ requireManifest: false });
    } else if (isUpdateRefresh) {
        const installScope = selectedGroups ? `groups: ${selectedGroups.join(', ')}` : 'full';
        console.log(`${PACKAGE_NAME}: --update — re-running ${installScope} install into ${CLAUDE_HOME}\n`);
    }
    const groupLabel = selectedGroups ? `groups: ${selectedGroups.join(', ')}` : 'all';
    console.log(`\nInstalling ${PACKAGE_NAME} (${groupLabel})...\n`);
    abortWhenPackageSourceHasConflicts(PACKAGE_ROOT);
    const pythonCommand = detectPython();
    if (!pythonCommand) {
        console.error('ERROR: No usable Python 3 found. Install Python 3.8+ from python.org and ensure py, python3, or python is on PATH. On Windows the Microsoft Store python.exe alias is rejected because it cannot run hooks.');
        process.exit(1);
    }
    console.log(`  Python: ${pythonCommand}`);
    mkdirSync(CLAUDE_HOME, { recursive: true });

    const activeGroups = selectedGroups
        ? selectedGroups.map(groupName => ({ groupName, ...INSTALL_GROUPS[groupName] }))
        : Object.entries(INSTALL_GROUPS).map(([groupName, group]) => ({ groupName, ...group }));

    const allowedSkills = selectedGroups
        ? new Set(activeGroups.flatMap(group => group.skills || []))
        : null;
    const allowedDirectories = selectedGroups
        ? new Set(activeGroups.flatMap(group => group.includeDirectories || []))
        : null;
    const shouldInstallAllHooks = selectedGroups
        ? activeGroups.some(group => group.includeAllHooks)
        : true;
    const allowedHookFiles = selectedGroups
        ? new Set(activeGroups.flatMap(group => group.includeHookFiles || []))
        : null;
    const allowedRules = selectedGroups
        ? new Set(activeGroups.flatMap(group => group.includeRules || []))
        : null;

    const dependencyRoots = [...new Set(
        activeGroups.filter(group => group.packageRoot).map(group => group.packageRoot)
    )];
    const builtinGroupsActive = activeGroups.some(group => !group.packageRoot);
    const allSourceRoots = [
        ...(builtinGroupsActive ? [PACKAGE_ROOT] : []),
        ...dependencyRoots,
    ];

    const allInstalledFiles = [];
    const summary = {};
    for (const directory of CONTENT_DIRECTORIES) {
        const hasFullAccess = !allowedDirectories || allowedDirectories.has(directory);
        const hasPartialRules = directory === 'rules' && allowedRules && allowedRules.size > 0;
        if (!hasFullAccess && !hasPartialRules) continue;
        for (const sourceRoot of allSourceRoots) {
            const sourceDir = join(sourceRoot, directory);
            if (!existsSync(sourceDir)) continue;
            const destDir = join(CLAUDE_HOME, directory);
            if (hasFullAccess) {
                const stats = copyTree(sourceDir, destDir);
                if (!summary[directory]) {
                    summary[directory] = stats;
                } else {
                    summary[directory].created += stats.created;
                    summary[directory].updated += stats.updated;
                    summary[directory].paths.push(...stats.paths);
                }
                allInstalledFiles.push(...stats.paths);
            } else if (hasPartialRules) {
                let rulesCreated = 0;
                let rulesUpdated = 0;
                for (const ruleFile of allowedRules) {
                    const sourcePath = join(sourceDir, ruleFile);
                    if (!existsSync(sourcePath)) continue;
                    const destPath = join(destDir, ruleFile);
                    mkdirSync(dirname(destPath), { recursive: true });
                    const existed = existsSync(destPath);
                    copyFileSync(sourcePath, destPath);
                    allInstalledFiles.push(destPath);
                    if (existed) { rulesUpdated++; } else { rulesCreated++; }
                    console.log(`  ${existed ? '\u21bb' : '\u2713'} ${join(directory, ruleFile)} (${existed ? 'updated' : 'new'})`);
                }
                if (!summary[directory]) {
                    summary[directory] = { created: rulesCreated, updated: rulesUpdated, paths: [] };
                } else {
                    summary[directory].created += rulesCreated;
                    summary[directory].updated += rulesUpdated;
                }
            }
        }
    }
    let skillsCreated = 0;
    let skillsUpdated = 0;
    const skillPaths = [];
    for (const sourceRoot of allSourceRoots) {
        const skillsSource = join(sourceRoot, 'skills');
        if (!existsSync(skillsSource)) continue;
        const skillDirs = readdirSync(skillsSource, { withFileTypes: true }).filter(entry => entry.isDirectory());
        for (const skillDir of skillDirs) {
            if (allowedSkills && !allowedSkills.has(skillDir.name)) continue;
            const stats = copyTree(join(skillsSource, skillDir.name), join(CLAUDE_HOME, 'skills', skillDir.name));
            skillsCreated += stats.created;
            skillsUpdated += stats.updated;
            skillPaths.push(...stats.paths);
        }
    }
    summary.skills = { created: skillsCreated, updated: skillsUpdated, paths: skillPaths };
    allInstalledFiles.push(...skillPaths);
    const shouldInstallAnyHooks = shouldInstallAllHooks || (allowedHookFiles && allowedHookFiles.size > 0);
    if (shouldInstallAnyHooks) {
        let totalHooksCreated = 0;
        let totalHooksUpdated = 0;
        let totalHookGroups = 0;
        for (const sourceRoot of allSourceRoots) {
            const hooksSource = join(sourceRoot, 'hooks');
            if (!existsSync(hooksSource)) continue;
            const hooksDestination = join(CLAUDE_HOME, 'hooks');
            const filesToCopy = collectFiles(hooksSource)
                .filter(file => !file.endsWith('hooks.json'))
                .filter(file => {
                    if (shouldInstallAllHooks) return true;
                    const relativePath = relative(hooksSource, file).replace(/\\/g, '/');
                    return allowedHookFiles.has(relativePath);
                });
            for (const sourceFile of filesToCopy) {
                const relativePath = relative(hooksSource, sourceFile);
                const destFile = join(hooksDestination, relativePath);
                mkdirSync(dirname(destFile), { recursive: true });
                const existed = existsSync(destFile);
                copyFileSync(sourceFile, destFile);
                allInstalledFiles.push(destFile);
                if (existed) { totalHooksUpdated++; } else { totalHooksCreated++; }
            }
            const groupCount = mergeHooks(sourceRoot, pythonCommand);
            totalHookGroups += groupCount;
        }
        summary.hookFiles = { created: totalHooksCreated, updated: totalHooksUpdated };
        console.log(`  Hook files: ${totalHooksCreated} new, ${totalHooksUpdated} updated`);
        summary.hookGroups = totalHookGroups;
        console.log(`  Hook groups: ${totalHookGroups} merged into settings.json`);

        console.warn(
            '  Warning: git hook installation sets core.hooksPath globally — '
            + 'the hook will run in every git repo on this machine.',
        );
        const gitHookInstallationResult = installAllGitHooks({ claudeHomeDirectory: CLAUDE_HOME });
        summary.gitHooks = {
            shimPaths: gitHookInstallationResult.createdShimPaths,
            hooksPathConfiguration: gitHookInstallationResult.hooksPathConfigurationResult,
        };
        const hooksPathConfigurationAction = gitHookInstallationResult.hooksPathConfigurationResult.action;
        if (hooksPathConfigurationAction === 'set') {
            allInstalledFiles.push(...gitHookInstallationResult.createdShimPaths);
            console.log(`  Git hooks: configured core.hooksPath -> ${gitHookInstallationResult.gitHooksDirectory}`);
        } else if (hooksPathConfigurationAction === 'already-set') {
            allInstalledFiles.push(...gitHookInstallationResult.createdShimPaths);
            console.log('  Git hooks: core.hooksPath already points to claude-dev-env, no change');
        } else {
            console.warn(`  Git hooks: ${gitHookInstallationResult.hooksPathConfigurationResult.reason}`);
        }
        console.log(`  Git hook shims: ${gitHookInstallationResult.createdShimPaths.length} files (pre-commit, pre-push, post-commit)`);

        const mypyIniInstallResult = installMypyIniForClaudeHooks({
            homeDirectory: homedir(),
            claudeHooksDirectory: join(CLAUDE_HOME, 'hooks'),
        });
        if (mypyIniInstallResult.action === 'created') {
            allInstalledFiles.push(mypyIniInstallResult.path);
            console.log(`  ✓ ${relative(homedir(), mypyIniInstallResult.path)} (new — enables mypy to resolve config.messages imports)`);
        } else if (mypyIniInstallResult.action === 'already-configured') {
            console.log(`  .mypy.ini: already configured for Claude hooks`);
        } else {
            console.warn(`  WARNING: .mypy.ini exists at ${mypyIniInstallResult.path} without the expected mypy_path.`);
            console.warn(`    To enable mypy for Claude hooks, add this line under [mypy]:`);
            console.warn(`      ${mypyIniInstallResult.expectedLine}`);
        }
    }
    const claudeHubSource = join(PACKAGE_ROOT, 'CLAUDE.md');
    if (existsSync(claudeHubSource)) {
        const claudeHubDest = join(CLAUDE_HOME, 'CLAUDE.md');
        const backupPath = backupClaudeHubBeforeOverwrite(claudeHubDest, claudeHubSource);
        if (backupPath) {
            console.log(
                `  \u21bb ${relative(CLAUDE_HOME, backupPath)} (previous CLAUDE.md hub preserved)`
            );
        }
        copyFileSync(claudeHubSource, claudeHubDest);
        allInstalledFiles.push(claudeHubDest);
        console.log(`  \u2713 ${relative(CLAUDE_HOME, claudeHubDest)} (hub)`);
    }
    writeManifest(allInstalledFiles);
    console.log(`\nInstalled ${PACKAGE_NAME}:`);
    for (const directory of CONTENT_DIRECTORIES) {
        if (summary[directory]) {
            const { created, updated } = summary[directory];
            console.log(`  ${directory}: ${created + updated} files (${created} new, ${updated} updated)`);
        }
    }
    if (summary.skills) {
        const { created, updated } = summary.skills;
        console.log(`  skills: ${created + updated} files (${created} new, ${updated} updated)`);
    }
    if (summary.hookFiles) {
        console.log(`  hooks: ${summary.hookFiles.created + summary.hookFiles.updated} files, ${summary.hookGroups} groups in settings.json`);
    }
    console.log(`  python: ${pythonCommand}\n`);
}

function normalizePathForComparison(rawPath) {
    return rawPath.trim().replaceAll('\\', '/');
}


function pathsAreEquivalent(storedPath, installedPath) {
    const normalizedStored = normalizePathForComparison(storedPath);
    const normalizedInstalled = normalizePathForComparison(installedPath);
    if (normalizedStored === normalizedInstalled) {
        return true;
    }
    const isMaybeCaseInsensitive = process.platform === 'win32' || process.platform === 'darwin';
    return isMaybeCaseInsensitive && normalizedStored.toLowerCase() === normalizedInstalled.toLowerCase();
}


function unsetGlobalGitHooksPathIfOurs() {
    const installedGitHooksDirectory = join(CLAUDE_HOME, 'hooks', 'git-hooks');
    let currentHooksPath = '';
    try {
        currentHooksPath = execFileSync('git', ['config', '--global', '--get', 'core.hooksPath'], {
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'pipe'],
        }).trim();
    } catch (gitReadError) {
        if (gitReadError.status === 1) {
            return;
        }
        const stderrDetail = gitReadError.stderr ? ` stderr: ${gitReadError.stderr.trim()}` : '';
        console.warn(`  Git hooks: could not read core.hooksPath during uninstall (${gitReadError.message}${stderrDetail}) — hooks path may need manual cleanup`);
        return;
    }
    if (!pathsAreEquivalent(currentHooksPath, installedGitHooksDirectory)) {
        return;
    }
    try {
        execFileSync('git', ['config', '--global', '--unset', 'core.hooksPath'], { stdio: 'ignore' });
        console.log('  Git hooks: unset global core.hooksPath');
    } catch (gitUnsetError) {
        console.warn(`  Git hooks: could not unset core.hooksPath (${gitUnsetError.message})`);
    }
}


function purgeManagedInstallation({ requireManifest }) {
    if (!existsSync(MANIFEST_FILE)) {
        if (requireManifest) {
            console.error('No installation manifest found. Nothing to uninstall.');
            process.exit(1);
        }
        return 0;
    }
    const manifest = JSON.parse(readFileSync(MANIFEST_FILE, 'utf8'));
    let removed = 0;
    for (const filePath of manifest.files) {
        if (existsSync(filePath)) {
            unlinkSync(filePath);
            console.log(`  \u2717 ${relative(CLAUDE_HOME, filePath)} (removed)`);
            removed++;
        }
    }
    const settingsPath = join(CLAUDE_HOME, 'settings.json');
    if (existsSync(settingsPath)) {
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        if (settings.hooks) {
            const managedHookRelativePaths = managedHookScriptRelativePathsFromSourceRoots(
                managedPackageSourceRoots()
            );
            pruneManagedHooksFromSettings(settings, managedHookRelativePaths);
            writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
            console.log('  Hook entries removed from settings.json');
        }
    }
    unsetGlobalGitHooksPathIfOurs();
    unlinkSync(MANIFEST_FILE);
    for (const directory of [...CONTENT_DIRECTORIES, 'skills', 'hooks']) {
        const dirPath = join(CLAUDE_HOME, directory);
        try {
            if (existsSync(dirPath) && readdirSync(dirPath).length === 0) {
                rmSync(dirPath, { recursive: true });
            }
        } catch { /* leave non-empty dirs */ }
    }
    console.log(`\nRemoved ${removed} files.\n`);
}

function uninstall() {
    console.log(`\nUninstalling ${PACKAGE_NAME}...\n`);
    purgeManagedInstallation({ requireManifest: true });
}

function printHelp() {
    console.log(`
${PACKAGE_NAME} - Claude Code development standards installer

Usage:
  npx ${PACKAGE_NAME}              Install everything
  npx ${PACKAGE_NAME} --update     Full install: remove prior manifest-tracked files first, then reinstall
  npx ${PACKAGE_NAME} --only X     Install specific groups
  npx ${PACKAGE_NAME} --uninstall  Remove installed files
  npx ${PACKAGE_NAME} --help       Show this help

Groups:
  core              Development standards, hooks, agents, commands
  prompt-generator  Prompt engineering tools
  journal           Session logging and memory
  research          Deep research and citation tools

Examples:
  npx ${PACKAGE_NAME} --only prompt-generator
  npx ${PACKAGE_NAME} --only prompt-generator,research

Install location: ~/.claude/

If ~/.claude/CLAUDE.md already exists and differs from the package copy, the installer
writes the previous contents to ~/.claude/backups/CLAUDE.md.<timestamp>.bak first.
`);
}

/**
 * Reports whether this module is the process entry point (run as
 * `node install.mjs`, or through a bin symlink such as the npm-installed
 * `claude-dev-env` launcher) rather than imported by another module such as the
 * test suite. The install/uninstall dispatch runs only when true, so importing
 * the module carries no side effects.
 *
 * Both sides resolve to their real on-disk paths before comparison, so a
 * symlinked launcher whose target is this module still counts as the entry
 * point even though `process.argv[1]` keeps the symlink path while
 * `import.meta.url` reports the resolved target. When either path cannot be
 * resolved on disk (for example a synthetic path in a unit test), the raw
 * paths are compared instead.
 *
 * @param {string} moduleUrl The module's import.meta.url.
 * @param {string|undefined} entryScriptPath The invoked script path (process.argv[1]).
 * @returns {boolean} True when the module is the process entry point.
 */
export function invokedAsEntryPoint(moduleUrl, entryScriptPath) {
    if (!entryScriptPath) return false;
    const modulePath = fileURLToPath(moduleUrl);
    return realPathOrSelf(modulePath) === realPathOrSelf(entryScriptPath);
}

function realPathOrSelf(filesystemPath) {
    try {
        return realpathSync(filesystemPath);
    } catch {
        return filesystemPath;
    }
}

if (invokedAsEntryPoint(import.meta.url, process.argv[1])) {
    const rawArgs = process.argv.slice(2);
    const args = rawArgs.filter((flag) => flag !== '--update');
    const isUpdateRefresh = rawArgs.includes('--update');
    if (args.includes('--help') || args.includes('-h')) {
        printHelp();
    } else if (args.includes('--uninstall')) {
        uninstall();
    } else {
        const onlyIndex = args.indexOf('--only');
        let selectedGroups = null;
        if (onlyIndex !== -1) {
            const onlyValue = args[onlyIndex + 1];
            if (!onlyValue || onlyValue.startsWith('--')) {
                console.error(`ERROR: --only requires a comma-separated list of groups.\nAvailable groups: ${Object.keys(INSTALL_GROUPS).join(', ')}`);
                process.exit(1);
            }
            selectedGroups = onlyValue.split(',').map(name => name.trim());
            const invalidGroups = selectedGroups.filter(name => !INSTALL_GROUPS[name]);
            if (invalidGroups.length > 0) {
                console.error(`ERROR: Unknown group(s): ${invalidGroups.join(', ')}\nAvailable groups: ${Object.keys(INSTALL_GROUPS).join(', ')}`);
                process.exit(1);
            }
        }
        install(selectedGroups, { isUpdateRefresh });
    }
}
