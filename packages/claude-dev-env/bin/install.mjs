#!/usr/bin/env node

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, copyFileSync, unlinkSync, rmSync, rmdirSync, renameSync, realpathSync, lstatSync } from 'node:fs';
import { join, dirname, resolve, relative, basename, isAbsolute, extname } from 'node:path';
import { homedir } from 'node:os';
import { execSync, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { installAllGitHooks } from './git_hooks_installer.mjs';
import { installMypyIniForClaudeHooks } from './install_mypy_ini.mjs';
import { expandHomeDirectoryTokensInSettings } from './expand_home_directory_tokens.mjs';
import { EVER_SHIPPED_SKILL_NAMES } from './ever-shipped-skills.mjs';
import {
    SKIPPED_SOURCE_ENTRY_NAMES,
    SKIPPED_SOURCE_FILE_EXTENSIONS,
    RUN_BACKUP_DIRECTORY_NAME_PATTERN,
    MANAGED_SKILLS_DIRECTORY_NAME,
    MANAGED_HOOKS_DIRECTORY_NAME,
    SETTINGS_FILE_NAME,
    MYPY_INI_FILE_NAME,
} from './install-constants.mjs';

const CLAUDE_HOME = join(homedir(), '.claude');
const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MANIFEST_FILE = join(CLAUDE_HOME, '.claude-dev-env-manifest.json');
const MYPY_INI_INSTALL_PATH = join(homedir(), MYPY_INI_FILE_NAME);
const PACKAGE_NAME = 'claude-dev-env';
const PACKAGE_VERSION = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
const packageRequire = createRequire(import.meta.url);

export const CONTENT_DIRECTORIES = ['rules', 'docs', 'commands', 'agents', 'system-prompts', 'scripts', '_shared', 'audit-rubrics'];

/**
 * Every top-level directory under ~/.claude the installer writes into: the
 * content directories plus the two it fills through their own copy loops. The
 * uninstall purge walks this list to find the root a recorded file belongs to and
 * to drop a managed directory the purge empties, and the full-install stale-file
 * prune walks it to give each root its own diff.
 */
export const MANAGED_TOP_LEVEL_DIRECTORY_NAMES = [
    ...CONTENT_DIRECTORIES,
    MANAGED_SKILLS_DIRECTORY_NAME,
    MANAGED_HOOKS_DIRECTORY_NAME,
];

const SKILL_MANIFEST_FILENAME = 'SKILL.md';
const NEVER_PRUNED_SKILL_DIRECTORIES = new Set(['_shared']);
const PRUNED_SKILLS_BACKUP_DIRECTORY_NAME = '.claude-dev-env-pruned';
const RETIRED_SKILL_REASON_LABEL = 'retired';
const STALE_FILE_REASON_LABEL = 'stale';
const MANIFEST_FILES_KEY = 'files';
const MANIFEST_SKILLS_KEY = 'skills';

export const CORE_INCLUDE_DIRECTORIES = [
    'rules', 'docs', 'commands', 'agents', 'audit-rubrics', '_shared', 'scripts',
];

export const CORE_SKILLS = [
    'orchestrator', 'orchestrator-refresh', 'team-advisor', 'grokify',
    'grok-spawn',
    'anthropic-plan', 'everything-search',
    'privacy-hygiene',
    'issue-tracker',
    'recall', 'remember', 'task-build',
];

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

/**
 * Discovers the install groups contributed by resolvable dependency packages and
 * the names of the declared dependencies that failed to resolve.
 *
 * A dependency that cannot be resolved contributes no group, so its skills never
 * enter the installed set. The retired-skill prune subtracts the installed set
 * from the ever-shipped set, so an unresolved dependency whose skills migrated
 * out of the main package would leave those live skills looking retired. The
 * returned unresolved-name list lets the caller skip the prune in that degraded
 * mode rather than delete a live skill.
 *
 * @returns {{groups: object, unresolvedDependencyNames: string[]}} The resolvable
 *   dependency groups keyed by group name, and the names that failed to resolve.
 */
function discoverDependencyGroups() {
    const ownPackageJsonPath = join(PACKAGE_ROOT, 'package.json');
    const ownPackageJson = JSON.parse(readFileSync(ownPackageJsonPath, 'utf8'));
    const dependencies = ownPackageJson.dependencies || {};
    const discoveredGroups = {};
    const unresolvedDependencyNames = [];
    for (const dependencyName of Object.keys(dependencies)) {
        let dependencyRoot;
        try {
            dependencyRoot = resolveDependencyPackageRoot(dependencyName);
        } catch {
            console.error(`  WARNING: Could not resolve dependency ${dependencyName}, skipping`);
            unresolvedDependencyNames.push(dependencyName);
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
        const skillsDirectory = join(dependencyRoot, MANAGED_SKILLS_DIRECTORY_NAME);
        if (existsSync(skillsDirectory)) {
            group.skills = readdirSync(skillsDirectory, { withFileTypes: true })
                .filter(entry => entry.isDirectory())
                .map(entry => entry.name);
        }
        const hooksDirectory = join(dependencyRoot, MANAGED_HOOKS_DIRECTORY_NAME);
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
    return { groups: discoveredGroups, unresolvedDependencyNames };
}

const dependencyDiscovery = discoverDependencyGroups();
const UNRESOLVED_DEPENDENCY_NAMES = dependencyDiscovery.unresolvedDependencyNames;

export const INSTALL_GROUPS = {
    core: {
        description: 'Development standards, hooks, agents, commands',
        skills: CORE_SKILLS,
        includeDirectories: CORE_INCLUDE_DIRECTORIES,
        includeAllHooks: true,
    },
    journal: {
        description: 'Session logging and memory',
        skills: ['session-log', 'session-tidy'],
    },
    ...dependencyDiscovery.groups,
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

/**
 * Report whether a source entry belongs to a build artifact the installer leaves
 * in the package source.
 *
 * @param {string} entryName One directory entry's name.
 * @returns {boolean} True when the walk skips the entry and everything under it.
 */
function isSkippedSourceEntry(entryName) {
    if (SKIPPED_SOURCE_ENTRY_NAMES.has(entryName)) return true;
    return SKIPPED_SOURCE_FILE_EXTENSIONS.has(extname(entryName).toLowerCase());
}

/**
 * List every file under a source directory, skipping the build artifacts a
 * contributor's local tooling writes beside the source.
 *
 * Running the Python suites fills the package source with `__pycache__` trees and
 * tool caches. The `files` negations in `package.json` keep them out of the
 * published tarball, with `.npmignore` carrying the same patterns for tooling
 * that reads it, so an `npx` install never sees them; a local
 * `node bin/install.mjs` reads the working tree directly, so the walk itself
 * skips them. `SKIPPED_SOURCE_ENTRY_NAMES` and
 * `SKIPPED_SOURCE_FILE_EXTENSIONS` name what drops out.
 *
 * The skip and the cleanup of artifacts an earlier install already copied are one
 * code path. A `.pyc` a prior manifest records under any managed root sits
 * outside the set this walk returns, so the next full install reads it as stale,
 * moves it into that run's backup root, and drops it from the manifest the run
 * writes.
 *
 * @param {string} directory The absolute source directory to walk.
 * @returns {string[]} Absolute paths of the files the installer copies.
 */
export function collectFiles(directory) {
    const collected = [];
    if (!existsSync(directory)) return collected;
    const entries = readdirSync(directory, { withFileTypes: true });
    for (const entry of entries) {
        if (isSkippedSourceEntry(entry.name)) continue;
        const entryPath = join(directory, entry.name);
        if (entry.isDirectory()) {
            collected.push(...collectFiles(entryPath));
        } else {
            collected.push(entryPath);
        }
    }
    return collected;
}

let cachedRunBackupRoot = null;

/**
 * Return the one backup directory this install run moves pruned content into.
 *
 * Retired skill directories and the stale files of every managed root share a
 * single timestamped root, so one run leaves one recovery point rather than
 * several.
 *
 * @returns {string} Absolute path to the run's backup root.
 */
function currentRunBackupRoot() {
    if (cachedRunBackupRoot === null) {
        const runTimestamp = new Date().toISOString().replace(/[:.]/g, '-');
        cachedRunBackupRoot = join(CLAUDE_HOME, PRUNED_SKILLS_BACKUP_DIRECTORY_NAME, runTimestamp);
    }
    return cachedRunBackupRoot;
}

/**
 * Remove every run backup directory under ~/.claude/.claude-dev-env-pruned
 * except the one this run wrote.
 *
 * A pruning install leaves one timestamped recovery point, and a recovery point
 * is worth keeping only while it describes content close to what sits on disk.
 * Keeping the newest run holds the recovery the user reaches for and bounds a
 * directory that otherwise grows with every install.
 *
 * Only a direct child whose name carries this installer's timestamp shape is
 * removed, so anything else under the backup directory stays. The pruned-backup
 * directory itself stays too, since it holds the current run. A removal that
 * fails logs a warning and the sweep continues, so retention never ends an
 * install.
 *
 * @param {string} keptRunBackupRoot Absolute path to this run's backup directory.
 * @returns {number} How many superseded run backup directories were removed.
 */
function removeSupersededRunBackups(keptRunBackupRoot) {
    const prunedBackupDirectory = join(CLAUDE_HOME, PRUNED_SKILLS_BACKUP_DIRECTORY_NAME);
    const keptComparisonKey = comparisonKeyForPath(keptRunBackupRoot);
    let allEntries;
    try {
        allEntries = readdirSync(prunedBackupDirectory, { withFileTypes: true });
    } catch (readError) {
        console.warn(`  Warning: could not read ${PRUNED_SKILLS_BACKUP_DIRECTORY_NAME} to retire older backups (${readError.message})`);
        return 0;
    }
    let removedCount = 0;
    for (const entry of allEntries) {
        if (!entry.isDirectory()) continue;
        if (!RUN_BACKUP_DIRECTORY_NAME_PATTERN.test(entry.name)) continue;
        const runBackupPath = join(prunedBackupDirectory, entry.name);
        if (comparisonKeyForPath(runBackupPath) === keptComparisonKey) continue;
        try {
            rmSync(runBackupPath, { recursive: true });
            removedCount++;
        } catch (removalError) {
            console.warn(`  Warning: could not remove older prune backup ${relative(CLAUDE_HOME, runBackupPath)} (${removalError.message})`);
        }
    }
    return removedCount;
}

/**
 * Retire older run backups once this run has written its own.
 *
 * A run that moved nothing created no backup root, so its `~/.claude` holds only
 * the recovery points earlier runs left; that run sweeps nothing and the user
 * keeps every one of them.
 *
 * The log line names the run backup and the window it lasts, so a user reading the
 * install output knows where to recover moved content and how long it stays.
 *
 * @returns {void}
 */
function retainNewestRunBackupOnly() {
    const runBackupRoot = currentRunBackupRoot();
    if (!existsSync(runBackupRoot)) return;
    const removedCount = removeSupersededRunBackups(runBackupRoot);
    if (removedCount > 0) {
        console.log(`  Prune backups: ${removedCount} older run backup(s) removed — recover moved content from ${PRUNED_SKILLS_BACKUP_DIRECTORY_NAME}/${basename(runBackupRoot)}, which stays until the next pruning install`);
    }
}

/**
 * Move one managed path into the run's backup root, leaving it in place when the
 * move fails.
 *
 * A retired skill directory and a stale file share this mover, so both land under
 * the same timestamped recovery point and both report through the same wording.
 * Content is moved rather than deleted, so a user-authored file that happens to
 * sit inside a managed directory stays recoverable, and a failed move costs at
 * most a cosmetic leftover.
 *
 * A path resolving outside the managed home is left alone with a warning, so a
 * malformed record is caught here rather than inside a rename.
 *
 * @param {string} sourcePath Absolute path under the managed home to move.
 * @param {string} backupRoot The run's timestamped backup directory.
 * @param {string} backupRelativePath Path to mirror the content at inside the backup root.
 * @param {string} reasonLabel Why the path is being moved (`retired` or `stale`).
 * @param {string} managedHomeDirectory The managed home the source must sit under.
 * @returns {boolean} True when the move succeeded.
 */
function moveIntoRunBackup(
    sourcePath, backupRoot, backupRelativePath, reasonLabel, managedHomeDirectory,
) {
    if (!isManagedPath(sourcePath, managedHomeDirectory)) {
        console.warn(`  Warning: leaving ${sourcePath} in place — the ${reasonLabel} path resolves outside ${managedHomeDirectory}`);
        return false;
    }
    const backupPath = join(backupRoot, backupRelativePath);
    const displayPath = relative(managedHomeDirectory, sourcePath);
    const backupDisplayPath = relative(managedHomeDirectory, backupPath);
    try {
        mkdirSync(dirname(backupPath), { recursive: true });
        renameSync(sourcePath, backupPath);
        console.log(`  ✗ ${displayPath} (${reasonLabel} — moved to ${backupDisplayPath})`);
        return true;
    } catch (moveError) {
        console.warn(`  Warning: could not move ${reasonLabel} ${displayPath} to backup, leaving in place (${moveError.message})`);
        return false;
    }
}

/**
 * Report whether a filesystem comparison on this platform ignores letter case.
 *
 * @returns {boolean} True on the platforms whose default filesystem is case-insensitive.
 */
function isCaseInsensitiveFilesystem() {
    return process.platform === 'win32' || process.platform === 'darwin';
}

/**
 * Build the lookup key two absolute paths are compared through: resolved,
 * forward-slashed, and lowercased wherever the filesystem ignores letter case.
 *
 * Case folding is what keeps a case-only rename safe. A skill whose readme ships
 * as `README.md` over an installed `Readme.md` writes its bytes through the
 * existing on-disk name, so a case-sensitive key would read the installed name as
 * a file this run never wrote and move the freshly written content aside.
 *
 * The `isCaseInsensitive` option carries that decision as a value, so a test names
 * the branch it drives and both branches stay covered on a host of either kind.
 *
 * @param {string} filesystemPath A path to build a comparison key for.
 * @param {{isCaseInsensitive?: boolean}} options Whether keys fold letter case; defaults to this host's filesystem.
 * @returns {string} The comparison key.
 */
export function comparisonKeyForPath(filesystemPath, options = {}) {
    const { isCaseInsensitive = isCaseInsensitiveFilesystem() } = options;
    const normalizedPath = normalizePathForComparison(resolve(filesystemPath));
    return isCaseInsensitive ? normalizedPath.toLowerCase() : normalizedPath;
}

/**
 * Report whether a path sits strictly inside a directory.
 *
 * @param {string} candidatePath The absolute path to test.
 * @param {string} directoryPath The absolute directory to test against.
 * @returns {boolean} True when the candidate is a descendant of the directory.
 */
function isInsideDirectory(candidatePath, directoryPath) {
    const relativePath = relative(directoryPath, candidatePath);
    return relativePath !== '' && !relativePath.startsWith('..') && !isAbsolute(relativePath);
}

/**
 * Report whether an absolute path a record names resolves inside ~/.claude.
 *
 * The manifest and the prune both hand raw path strings to code that unlinks or
 * renames them, and a record can arrive malformed — hand-edited, written by an
 * installer running against a different home, or carrying a relative fragment
 * that resolves elsewhere. This guard runs first so a path outside the managed
 * home is skipped with a warning before any root-specific logic sees it. The
 * stale-file prune keeps its own stricter containment test against the
 * destination root it was handed.
 *
 * @param {string} candidatePath The absolute path a record names.
 * @param {string} [managedHomeDirectory] The managed home to test against; defaults to ~/.claude.
 * @returns {boolean} True when the path resolves under the managed home.
 */
function isManagedPath(candidatePath, managedHomeDirectory = CLAUDE_HOME) {
    return isInsideDirectory(resolve(candidatePath), resolve(managedHomeDirectory));
}

/**
 * Report whether a manifest record names a file this installer writes and may
 * therefore remove.
 *
 * Most of what an install writes sits under ~/.claude, and `isManagedPath`
 * answers for all of it. `installMypyIniForClaudeHooks` writes `~/.mypy.ini` in
 * the home directory, because that is where mypy reads its configuration, and the
 * install records the path. Naming that one file keeps the permitted set an
 * enumeration: every other path in the home directory stays outside it, so a
 * record pointing anywhere else is still skipped with a warning.
 *
 * @param {string} candidatePath The absolute path a manifest record names.
 * @returns {boolean} True when the installer itself writes the path.
 */
function isRemovableManifestRecord(candidatePath) {
    if (isManagedPath(candidatePath)) return true;
    return comparisonKeyForPath(candidatePath) === comparisonKeyForPath(MYPY_INI_INSTALL_PATH);
}

/**
 * Return the managed top-level directory an installed path sits under.
 *
 * The uninstall walk-up needs a stop root, and ~/.claude is the wrong one: a walk
 * that reaches it would try to remove the user's home configuration directory.
 * Naming the owning managed root keeps the walk inside the tree the installer
 * wrote, and a path under no managed root gets no walk at all.
 *
 * @param {string} installedFilePath The absolute path a manifest record names.
 * @returns {string|null} The absolute managed root, or null when the path sits under none.
 */
function owningManagedRoot(installedFilePath) {
    const resolvedPath = resolve(installedFilePath);
    for (const directoryName of MANAGED_TOP_LEVEL_DIRECTORY_NAMES) {
        const managedRoot = join(CLAUDE_HOME, directoryName);
        if (isInsideDirectory(resolvedPath, managedRoot)) return managedRoot;
    }
    return null;
}

/**
 * Report whether a path the prior manifest recorded is still a plain file this
 * run may move.
 *
 * A path the user already deleted is skipped in silence. A directory or a symlink
 * standing where a file was recorded is skipped with a warning, so the mover
 * never renames a tree and never follows a link out of ~/.claude.
 *
 * @param {string} candidatePath The absolute path the prior manifest recorded.
 * @returns {boolean} True when the path is a plain file that may be moved.
 */
function isMovableStaleFile(candidatePath) {
    let entryStats;
    try {
        entryStats = lstatSync(candidatePath);
    } catch {
        return false;
    }
    if (entryStats.isFile()) return true;
    console.warn(
        `  Warning: leaving ${relative(CLAUDE_HOME, candidatePath)} in place — a directory or link stands where the prior install recorded a file`,
    );
    return false;
}

/**
 * Remove directories emptied by a move, walking from a directory up toward a
 * destination root and stopping at the first directory that still holds content.
 *
 * `rmdirSync` removes only an empty directory, so a directory holding a user file
 * survives. Stopping at the destination root keeps the managed root itself in
 * place for the next install.
 *
 * @param {string} startDirectory The absolute directory the moved file sat in.
 * @param {string} destinationRoot The absolute managed root to stop below.
 * @returns {void}
 */
function removeEmptiedParentDirectories(startDirectory, destinationRoot) {
    let currentDirectory = startDirectory;
    while (isInsideDirectory(currentDirectory, destinationRoot)) {
        try {
            rmdirSync(currentDirectory);
        } catch {
            return;
        }
        currentDirectory = dirname(currentDirectory);
    }
}

/**
 * Move files a prior install wrote under a managed root that the current install
 * no longer writes into the run's backup root.
 *
 * `copyTree` overwrites and adds but never removes, so a file dropped or renamed
 * between two installs survives inside an otherwise current directory. That
 * leaves a skill whose modules come from one revision and whose companions come
 * from another — for example scripts importing constants a stale constants module
 * never defines, which fails at import with nothing in the directory to explain
 * why. Diffing the prior manifest against the paths this run copied confines the
 * move to content the installer itself wrote, so a runtime artifact such as a
 * `__pycache__` entry, a user symlink, and any user-authored file all stay in
 * place.
 *
 * A run whose prunes read the prior record all the way through replaces the
 * manifest's file list wholesale, so the next diff reads as "the package stopped
 * shipping this". Every other run unions what it wrote onto the prior record,
 * which keeps every entry a later pruning install needs. An entry that leaves the
 * record — a path the run rewrote under a fresh spelling, or a record already lost
 * to an older install — sits outside every later diff, so it stays inside the tree
 * once the package stops shipping it.
 *
 * A move that fails is reported through `failedPaths` so the caller records those
 * paths in the fresh manifest. Keeping a failed path on the record holds it inside
 * the next run's diff, which retries the move once the antivirus scanner or open
 * editor that held the file lets go. Leaving it off the record would place the
 * file outside every later diff and strand it inside a live skill.
 *
 * @param {string[]|null} priorInstalledFiles Files the prior manifest recorded, or null when unknown.
 * @param {string[]} currentInstalledFiles Every file this run copied under the root.
 * @param {string} destinationRoot The managed root the diff is confined to.
 * @param {string} backupRoot The run's timestamped backup directory.
 * @param {{isCaseInsensitive?: boolean, managedHomeDirectory?: string}} options `isCaseInsensitive`
 *   sets whether path keys fold letter case, defaulting to this host's filesystem;
 *   `managedHomeDirectory` sets the home the containment guard tests against,
 *   defaulting to ~/.claude.
 * @returns {{prunedCount: number, failedPaths: string[]}} How many files moved, and the paths whose move failed.
 */
export function pruneStaleInstalledFiles(
    priorInstalledFiles, currentInstalledFiles, destinationRoot, backupRoot, options = {},
) {
    if (priorInstalledFiles === null) return { prunedCount: 0, failedPaths: [] };
    const { managedHomeDirectory = CLAUDE_HOME } = options;
    const currentFileKeys = new Set(
        currentInstalledFiles.map(currentFile => comparisonKeyForPath(currentFile, options)),
    );
    const resolvedRoot = resolve(destinationRoot);
    let prunedCount = 0;
    const failedPaths = [];
    for (const priorFile of priorInstalledFiles) {
        const stalePath = resolve(priorFile);
        if (!isInsideDirectory(stalePath, resolvedRoot)) continue;
        if (currentFileKeys.has(comparisonKeyForPath(stalePath, options))) continue;
        if (!isMovableStaleFile(stalePath)) continue;
        const backupRelativePath = relative(resolvedRoot, stalePath);
        const didMove = moveIntoRunBackup(
            stalePath, backupRoot, backupRelativePath, STALE_FILE_REASON_LABEL, managedHomeDirectory,
        );
        if (!didMove) {
            failedPaths.push(stalePath);
            continue;
        }
        prunedCount++;
        removeEmptiedParentDirectories(dirname(stalePath), resolvedRoot);
    }
    return { prunedCount, failedPaths };
}

/**
 * Return the existing directory entry a shipped file name would overwrite
 * through a spelling that differs only in letter case.
 *
 * `copyFileSync` writes its bytes through whatever entry the filesystem resolves
 * the destination to, so on a case-insensitive volume a package shipping
 * `README.md` over an installed `Readme.md` fills the installed entry and leaves
 * the earlier spelling standing. Naming that entry lets the copy rename it to the
 * shipped spelling first. On a case-sensitive volume the two names are two files,
 * so the answer is always null.
 *
 * The `isCaseInsensitive` option carries the platform decision as a value, so a
 * test names the branch it drives and both branches stay covered on a host of
 * either kind.
 *
 * @param {string} shippedFileName The file name the package ships.
 * @param {string[]} existingEntryNames The names already in the destination directory.
 * @param {{isCaseInsensitive?: boolean}} options Whether name comparison folds letter case; defaults to this host's filesystem.
 * @returns {string|null} The existing entry name to rename, or null when none applies.
 */
export function caseOnlyRenameSourceName(shippedFileName, existingEntryNames, options = {}) {
    const { isCaseInsensitive = isCaseInsensitiveFilesystem() } = options;
    if (!isCaseInsensitive) return null;
    if (existingEntryNames.includes(shippedFileName)) return null;
    const foldedShippedName = shippedFileName.toLowerCase();
    const caseOnlyMatchName = existingEntryNames.find(
        existingName => existingName.toLowerCase() === foldedShippedName,
    );
    return caseOnlyMatchName === undefined ? null : caseOnlyMatchName;
}

/**
 * List a directory's entry names, reading each directory once and serving every
 * later request for it from the cache.
 *
 * A copy run asks about the destination directory of every file it writes, and a
 * directory holds many of them, so one listing per directory keeps the case check
 * off the per-file syscall path.
 *
 * @param {string} directoryPath The absolute directory to list.
 * @param {Map<string, string[]>} entryNamesByDirectory The run's listing cache.
 * @returns {string[]} The directory's entry names, empty when it cannot be read.
 */
function cachedDirectoryEntryNames(directoryPath, entryNamesByDirectory) {
    const cachedEntryNames = entryNamesByDirectory.get(directoryPath);
    if (cachedEntryNames !== undefined) return cachedEntryNames;
    let allEntryNames;
    try {
        allEntryNames = readdirSync(directoryPath);
    } catch {
        allEntryNames = [];
    }
    entryNamesByDirectory.set(directoryPath, allEntryNames);
    return allEntryNames;
}

/**
 * Give the destination entry the shipped file's letter case before the bytes
 * land.
 *
 * `renameSync` inside one directory is atomic, so a run interrupted between the
 * rename and the copy leaves the file present under the shipped name holding the
 * earlier content, which the next install overwrites. A rename that fails logs a
 * warning and the copy carries on, so the content is always current even when the
 * name stays as it was.
 *
 * @param {string} destinationFilePath The absolute path the package ships to.
 * @param {Map<string, string[]>} entryNamesByDirectory The run's listing cache.
 * @param {{isCaseInsensitive?: boolean}} options Whether name comparison folds letter case.
 * @returns {void}
 */
function renameCaseOnlyMatchToShippedName(destinationFilePath, entryNamesByDirectory, options) {
    const destinationDirectory = dirname(destinationFilePath);
    const shippedFileName = basename(destinationFilePath);
    const existingEntryNames = cachedDirectoryEntryNames(destinationDirectory, entryNamesByDirectory);
    const caseOnlyMatchName = caseOnlyRenameSourceName(shippedFileName, existingEntryNames, options);
    if (caseOnlyMatchName === null) return;
    try {
        renameSync(join(destinationDirectory, caseOnlyMatchName), destinationFilePath);
    } catch (renameError) {
        console.warn(`  Warning: leaving ${caseOnlyMatchName} under its installed name — the rename to ${shippedFileName} failed (${renameError.message})`);
        return;
    }
    existingEntryNames[existingEntryNames.indexOf(caseOnlyMatchName)] = shippedFileName;
}

/**
 * Copy every file under a source directory into a destination directory,
 * reporting what the run created and what it updated.
 *
 * A destination entry whose name differs from the shipped name only in letter
 * case is renamed to the shipped name before the copy, so the tree carries the
 * spelling the package ships. The directory listing behind that decision is read
 * once per destination directory and reused for every file the run copies there.
 *
 * @param {string} sourceBase The absolute source directory to copy from.
 * @param {string} destBase The absolute destination directory to copy into.
 * @param {{isCaseInsensitive?: boolean}} options Whether name comparison folds letter case; defaults to this host's filesystem.
 * @returns {{created: number, updated: number, paths: string[]}} The counts and the destination paths written.
 */
export function copyTree(sourceBase, destBase, options = {}) {
    const files = collectFiles(sourceBase);
    const stats = { created: 0, updated: 0, paths: [] };
    const entryNamesByDirectory = new Map();
    for (const sourceFile of files) {
        const relativePath = relative(sourceBase, sourceFile);
        const destFile = join(destBase, relativePath);
        mkdirSync(dirname(destFile), { recursive: true });
        const existed = existsSync(destFile);
        renameCaseOnlyMatchToShippedName(destFile, entryNamesByDirectory, options);
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
 * PreToolUse hook script paths the installer manages even though hooks.json
 * carries no standalone entry for them. Most were folded into the PreToolUse
 * dispatcher in Stage 1; md_to_html_blocker is a retired hook with no script on
 * disk. Each path stays in this set so a reinstall from an older settings shape
 * prunes its standalone entry — a folded hook would otherwise double-run
 * alongside the dispatcher, and the retired hook's entry would point at a
 * missing script.
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
    'blocking/env_var_table_code_drift_blocker.py',
    'blocking/pytest_testpaths_orphan_blocker.py',
    'blocking/open_questions_in_plans_blocker.py',
    'blocking/plain_language_blocker.py',
    'blocking/md_to_html_blocker.py',
]);

/**
 * After-write hook script paths the installer manages even though hooks.json
 * carries no standalone entry for them. mypy_validator and auto_formatter run
 * hosted inside the PostToolUse dispatcher; doc_gist_auto_publish and
 * md_to_html_companion are retired hooks with no script on disk. Each path stays
 * in this set so a reinstall from an older settings shape prunes its standalone
 * entry — a hosted hook would otherwise double-run alongside the dispatcher, and
 * a retired hook's entry would point at a missing script.
 */
export const POST_FOLDED_HOOK_RELATIVE_PATHS = new Set([
    'validation/mypy_validator.py',
    'workflow/auto_formatter.py',
    'workflow/doc_gist_auto_publish.py',
    'workflow/md_to_html_companion.py',
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
        const hooksJsonPath = join(sourceRoot, MANAGED_HOOKS_DIRECTORY_NAME, 'hooks.json');
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
 * A command that is not a string belongs to an entry this installer never wrote,
 * so it counts as unmanaged and its entry stays.
 *
 * @param {unknown} commandString The hook command from settings.json.
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {boolean} True when the command references a managed script.
 */
export function commandReferencesManagedHook(commandString, managedHookRelativePaths) {
    if (typeof commandString !== 'string') return false;
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
 * than left to double-run. User-authored hooks outside the managed set stay, and
 * an event whose value is not an array of groups is left as the settings file
 * holds it.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {string} eventType The lifecycle event whose groups are pruned.
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {void}
 */
function pruneManagedHooksFromEvent(settings, eventType, managedHookRelativePaths) {
    const existingGroups = settings.hooks[eventType];
    if (!Array.isArray(existingGroups)) return;
    settings.hooks[eventType] = retainedMatcherGroups(
        existingGroups,
        commandString => commandReferencesManagedHook(commandString, managedHookRelativePaths),
    ).keptGroups;
}

/**
 * Give one event type a list of hook groups to merge into, warning when a value
 * of another shape leaves settings.json.
 *
 * The settings schema holds a list of matcher groups at each event type, so a
 * value of another shape has no place for the groups the package ships for that
 * event, and the merge writes the list in its place. The warning names the event
 * type so the user can recover the value from their own history.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {string} eventType The lifecycle event the package ships groups for.
 * @returns {void}
 */
function startEventFromHookGroupList(settings, eventType) {
    const existingEventValue = settings.hooks[eventType];
    if (Array.isArray(existingEventValue)) return;
    if (existingEventValue !== undefined) {
        console.warn(
            `  Warning: replacing the ${eventType} value in settings.json — it held a value that`
            + ' was not a list of hook groups. Recover it from your own history.'
        );
    }
    settings.hooks[eventType] = [];
}

/**
 * Merges the installer's managed hook groups into a settings object in memory,
 * pruning every prior managed hook (standalone script or inline validators
 * runner) from each event's existing matcher groups before appending the freshly
 * rewritten copies so repeated merges stay idempotent and a managed hook moved to
 * a new matcher group does not double-run. User-authored hooks are preserved as
 * entries, but residual $HOME / ${HOME} / ~/ tokens in every hook and statusLine
 * command are expanded to absolute home paths so hosts that require referenced
 * env vars at load time (a third-party host on Windows) can execute them.
 *
 * The merge reads a settings file another tool or a person may have written, so
 * it recognizes the shapes it writes and steps around the rest: a `hooks` value
 * that is not an object starts from an empty map, and a group carrying no hooks
 * array contributes no user entries. At an event type the package ships groups
 * for, a value that is not a list of hook groups is replaced by that list, with
 * a warning naming the event type.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {{hooks: object}} hooksConfig Parsed hooks.json.
 * @param {string} pluginRootDir Directory ${CLAUDE_PLUGIN_ROOT} resolves to
 *   (the installer's `~/.claude` root; home is its parent directory).
 * @param {string} pythonCommand Interpreter command that replaces python3.
 * @returns {number} Count of matcher groups merged.
 */
export function mergeHooksIntoSettings(settings, hooksConfig, pluginRootDir, pythonCommand) {
    const managedHookRelativePaths = managedHookScriptRelativePaths(hooksConfig);
    const pluginRootForward = pluginRootDir.replace(/\\/g, '/');
    if (!settings.hooks || typeof settings.hooks !== 'object') settings.hooks = {};
    let groupCount = 0;
    for (const [eventType, matcherGroups] of Object.entries(hooksConfig.hooks)) {
        startEventFromHookGroupList(settings, eventType);
        pruneManagedHooksFromEvent(settings, eventType, managedHookRelativePaths);
        for (const sourceGroup of matcherGroups) {
            const rewrittenHooks = sourceGroup.hooks.map(hook => {
                let command = hook.command;
                command = command.replace(
                    /\$\{CLAUDE_PLUGIN_ROOT\}/g,
                    () => pluginRootForward,
                );
                command = command.replace(/^python3\b/, () => pythonCommand);
                return { ...hook, command };
            });
            const existingIndex = settings.hooks[eventType].findIndex(
                group => group?.matcher === sourceGroup.matcher
            );
            if (existingIndex >= 0) {
                const existing = settings.hooks[eventType][existingIndex];
                const userHooks = (groupHookEntries(existing) || []).filter(
                    hook => !commandReferencesManagedHook(hook?.command, managedHookRelativePaths)
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
    expandHomeDirectoryTokensInSettings(settings, dirname(pluginRootDir));
    return groupCount;
}

/**
 * Removes every managed hook (standalone script or inline validators runner)
 * from a settings object in memory, matching each command through
 * commandReferencesManagedHook so entries written with any home-path style
 * ($HOME, ~, ${HOME}, or absolute) and any path separator are pruned. Matcher
 * groups left empty are dropped, and an empty hooks map is removed entirely.
 * User-authored hooks outside the managed set are preserved untouched, and an
 * event whose value is not an array of groups is left as the settings file holds
 * it.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {Set<string>} managedHookRelativePaths Managed script paths under hooks/.
 * @returns {void}
 */
export function pruneManagedHooksFromSettings(settings, managedHookRelativePaths) {
    if (!settings.hooks || typeof settings.hooks !== 'object') return;
    for (const [eventType, matcherGroups] of Object.entries(settings.hooks)) {
        if (!Array.isArray(matcherGroups)) continue;
        const { keptGroups } = retainedMatcherGroups(
            matcherGroups,
            commandString => commandReferencesManagedHook(commandString, managedHookRelativePaths),
        );
        settings.hooks[eventType] = keptGroups;
        if (keptGroups.length === 0) delete settings.hooks[eventType];
    }
    if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
}

/**
 * Build the hook script paths a prior install wrote under ~/.claude/hooks that
 * this run leaves unwritten, each relative to that hooks root.
 *
 * The set comes from the manifest diff alone, so it names this installer's own
 * retired scripts and nothing else: a script the run still writes stays out of it,
 * and a path no install of ours ever recorded never enters it. That is what keeps
 * a user-authored hook out of reach of the settings prune.
 *
 * @param {string[]|null} priorInstalledFiles Files the prior manifest recorded, or null when unknown.
 * @param {string[]} currentInstalledFiles Every file this run copied.
 * @param {string} hooksRoot The absolute installed hooks directory.
 * @returns {Set<string>} Forward-slash relative script paths under the hooks root.
 */
export function retiredManagedHookRelativePaths(
    priorInstalledFiles, currentInstalledFiles, hooksRoot,
) {
    const retiredRelativePaths = new Set();
    if (priorInstalledFiles === null) return retiredRelativePaths;
    const currentFileKeys = new Set(
        currentInstalledFiles.map(currentFile => comparisonKeyForPath(currentFile)),
    );
    const resolvedHooksRoot = resolve(hooksRoot);
    for (const priorFile of priorInstalledFiles) {
        const priorPath = resolve(priorFile);
        if (!isInsideDirectory(priorPath, resolvedHooksRoot)) continue;
        if (currentFileKeys.has(comparisonKeyForPath(priorPath))) continue;
        retiredRelativePaths.add(relative(resolvedHooksRoot, priorPath).replace(/\\/g, '/'));
    }
    return retiredRelativePaths;
}

/**
 * Report whether a settings.json hook command runs one of the retired managed
 * hook scripts.
 *
 * The anchored `/.claude/hooks/<relative>` tail is the same test the merge uses to
 * tell this installer's entries from a user's, so a command whose path is a
 * retired tail plus a suffix stays outside the set. The inline validators-runner
 * shape sits outside this test on purpose: it names no script, so no manifest
 * record can retire it, and the merge writes it fresh on every run.
 *
 * A command that is not a string belongs to an entry this installer never wrote —
 * a hand-edited settings.json, or a third-party entry carrying another shape — so
 * it names no retired script and its entry stays.
 *
 * @param {unknown} commandString The hook command from settings.json.
 * @param {Set<string>} retiredHookRelativePaths Retired script paths under hooks/.
 * @returns {boolean} True when the command runs a retired managed script.
 */
function commandReferencesRetiredHook(commandString, retiredHookRelativePaths) {
    if (typeof commandString !== 'string') return false;
    const normalizedCommand = commandString.replace(/\\/g, '/');
    for (const relativePath of retiredHookRelativePaths) {
        if (commandTailEndsAtManagedHook(normalizedCommand, relativePath)) return true;
    }
    return false;
}

/**
 * Keep the matcher groups of one event, dropping each hook a predicate names and
 * each group the drop leaves empty.
 *
 * Every settings walk shares this pass, so a settings.json a person or another
 * tool wrote meets one set of shape rules. A group carrying no hooks array is
 * handed back untouched, and an entry whose command is not a string reaches the
 * predicate as-is — each predicate reads a non-string command as an entry this
 * installer never wrote — so a shape this installer does not recognize survives.
 *
 * @param {object[]} matcherGroups The event's matcher groups from settings.json.
 * @param {(commandString: unknown) => boolean} shouldRemoveHook Names the hooks that leave.
 * @returns {{keptGroups: object[], removedCount: number}} The surviving groups and how many hooks left.
 */
function retainedMatcherGroups(matcherGroups, shouldRemoveHook) {
    const keptGroups = [];
    let removedCount = 0;
    for (const group of matcherGroups) {
        const hookEntries = groupHookEntries(group);
        if (hookEntries === null) {
            keptGroups.push(group);
            continue;
        }
        const keptHooks = hookEntries.filter(hook => !shouldRemoveHook(hook?.command));
        removedCount += hookEntries.length - keptHooks.length;
        if (keptHooks.length > 0) keptGroups.push({ ...group, hooks: keptHooks });
    }
    return { keptGroups, removedCount };
}

/**
 * Return the hook entries one matcher group holds, or null when the group carries
 * no hooks array.
 *
 * The installer writes every group with a `hooks` array, and a settings.json it
 * reads back can hold a group of any shape. Reading the array through one
 * accessor lets each walk recognize the shape it wrote and hand every other shape
 * back untouched.
 *
 * @param {unknown} group One matcher group read from settings.json.
 * @returns {object[]|null} The group's hook entries, or null when it holds none.
 */
function groupHookEntries(group) {
    return Array.isArray(group?.hooks) ? group.hooks : null;
}

/**
 * Strip every retired managed hook from a settings object in memory.
 *
 * The walk covers each event type the settings file holds rather than the ones the
 * current hooks.json names, so an entry under an event type the package stopped
 * shipping is reached too. An event type left with no groups is dropped.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {Set<string>} retiredHookRelativePaths Retired script paths under hooks/.
 * @returns {number} How many hook entries were removed.
 */
function stripRetiredHookEntries(settings, retiredHookRelativePaths) {
    let removedCount = 0;
    for (const [eventType, matcherGroups] of Object.entries(settings.hooks)) {
        if (!Array.isArray(matcherGroups)) continue;
        const eventOutcome = retainedMatcherGroups(
            matcherGroups,
            commandString => commandReferencesRetiredHook(commandString, retiredHookRelativePaths),
        );
        removedCount += eventOutcome.removedCount;
        if (eventOutcome.keptGroups.length === 0) {
            delete settings.hooks[eventType];
            continue;
        }
        settings.hooks[eventType] = eventOutcome.keptGroups;
    }
    return removedCount;
}

/**
 * Remove every settings.json entry that runs a retired managed hook script,
 * writing the file only when an entry left it.
 *
 * A run that retires no hook leaves settings.json byte-identical, so an install
 * touches the user's settings for a reason a reader can name. A settings file the
 * installer cannot parse is left alone with a warning.
 *
 * @param {string} settingsPath The absolute settings.json path.
 * @param {Set<string>} retiredHookRelativePaths Retired script paths under hooks/.
 * @returns {number} How many hook entries were removed.
 */
export function pruneRetiredHookEntriesFromSettings(settingsPath, retiredHookRelativePaths) {
    if (retiredHookRelativePaths.size === 0) return 0;
    if (!existsSync(settingsPath)) return 0;
    let settings;
    try {
        settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
    } catch (parseError) {
        console.warn(`  Warning: leaving settings.json as it stands — the file holds JSON the installer cannot read (${parseError.message})`);
        return 0;
    }
    if (!settings.hooks || typeof settings.hooks !== 'object') return 0;
    const removedCount = stripRetiredHookEntries(settings, retiredHookRelativePaths);
    if (removedCount === 0) return 0;
    writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
    return removedCount;
}

/**
 * Merge one package source root's hook groups into ~/.claude/settings.json.
 *
 * A settings file holding anything other than a JSON object ends the install with
 * a message naming the file, so the run stops before it writes hook entries onto
 * a shape the harness cannot read.
 *
 * @param {string} hooksSourceRoot The package root whose hooks/hooks.json is merged.
 * @param {string} pythonCommand Interpreter command that replaces python3.
 * @returns {number} Count of matcher groups merged.
 */
function mergeHooks(hooksSourceRoot, pythonCommand) {
    const hooksJsonPath = join(hooksSourceRoot, MANAGED_HOOKS_DIRECTORY_NAME, 'hooks.json');
    if (!existsSync(hooksJsonPath)) return 0;
    const hooksConfig = JSON.parse(readFileSync(hooksJsonPath, 'utf8'));
    const settingsPath = join(CLAUDE_HOME, SETTINGS_FILE_NAME);
    let settings = {};
    if (existsSync(settingsPath)) {
        const raw = readFileSync(settingsPath, 'utf8').trim();
        if (raw) {
            try { settings = JSON.parse(raw); }
            catch { console.error('  ERROR: settings.json is malformed JSON. Fix it and rerun.'); process.exit(1); }
            if (!settings || typeof settings !== 'object' || Array.isArray(settings)) {
                console.error('  ERROR: settings.json holds a value other than a JSON object. Fix it and rerun.');
                process.exit(1);
            }
        }
    }
    const groupCount = mergeHooksIntoSettings(settings, hooksConfig, CLAUDE_HOME, pythonCommand);
    writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
    return groupCount;
}

function writeManifest(installedFiles, skillNames) {
    const manifest = {
        package: PACKAGE_NAME,
        version: PACKAGE_VERSION,
        installedAt: new Date().toISOString(),
        [MANIFEST_FILES_KEY]: installedFiles,
    };
    if (skillNames) {
        manifest[MANIFEST_SKILLS_KEY] = skillNames;
    }
    writeFileSync(MANIFEST_FILE, JSON.stringify(manifest, null, 2) + '\n');
}

/**
 * Read the file list and the skill list the previous install recorded, in one
 * parse of the manifest.
 *
 * A full install's manifest holds thousands of path strings, so the record is
 * read and parsed once and both lists are handed back together.
 *
 * Either list is null when the manifest is missing, unreadable, or holds no array
 * at that key, so a caller treats every such case as "no prior record": the skills
 * list leans on the ever-shipped set to find retired skills, and the files list
 * holds the stale-file prune for that run rather than guessing at what a prior
 * install wrote. A `--update` run purges the manifest before reinstalling, so this
 * read happens at the top of `install()` while the record is still on disk.
 *
 * @returns {{files: string[]|null, skills: string[]|null}} The recorded lists, each null when absent.
 */
function readPriorManifestArrays() {
    const missingRecord = { files: null, skills: null };
    if (!existsSync(MANIFEST_FILE)) return missingRecord;
    try {
        const priorManifest = JSON.parse(readFileSync(MANIFEST_FILE, 'utf8'));
        return {
            files: arrayOrNull(priorManifest[MANIFEST_FILES_KEY]),
            skills: arrayOrNull(priorManifest[MANIFEST_SKILLS_KEY]),
        };
    } catch {
        return missingRecord;
    }
}

/**
 * Return a recorded manifest value when it is an array, and null otherwise.
 *
 * @param {unknown} recordedEntries The value read at a manifest key.
 * @returns {string[]|null} The array, or null when the key holds anything else.
 */
function arrayOrNull(recordedEntries) {
    return Array.isArray(recordedEntries) ? recordedEntries : null;
}

/**
 * Merge two path lists into one, keyed on `comparisonKeyForPath`, with the
 * current run's spelling winning a collision.
 *
 * The current run just wrote the file, so its casing is the on-disk truth; a path
 * carried over from an earlier record keeps its position in the list and takes the
 * fresh spelling. One spelling per file keeps the record and the uninstall purge
 * loop the size of the tree they describe.
 *
 * @param {string[]} carriedOverPaths Paths sourced from an earlier record.
 * @param {string[]} currentRunPaths Paths this run wrote, whose spelling wins.
 * @returns {string[]} The merged list, one entry per comparison key.
 */
function unionOnComparisonKey(carriedOverPaths, currentRunPaths) {
    const pathByComparisonKey = new Map();
    for (const mergedPath of [...carriedOverPaths, ...currentRunPaths]) {
        pathByComparisonKey.set(comparisonKeyForPath(mergedPath), mergedPath);
    }
    return [...pathByComparisonKey.values()];
}

/**
 * Merge two skill-name lists into one, deduped by exact name.
 *
 * A skill name is a directory name the package ships, compared exactly the way
 * `pruneRetiredSkills` compares it, so this union stays case-aware and applies
 * none of the path normalization `unionOnComparisonKey` uses.
 *
 * @param {string[]} carriedOverSkillNames Skill names sourced from an earlier record.
 * @param {string[]} currentRunSkillNames Skill names this run installed.
 * @returns {string[]} The merged list, one entry per name.
 */
function unionOfSkillNames(carriedOverSkillNames, currentRunSkillNames) {
    return [...new Set([...carriedOverSkillNames, ...currentRunSkillNames])];
}

/**
 * Build the file list a full install records: everything this run installed plus
 * every stale path whose move failed and that still sits on disk.
 *
 * A failed move keeps the file inside a live skill, so the record carries it into
 * the next run's diff for a retry. A path that vanished between the stat guard
 * and the rename is dropped, which keeps a phantom out of every later manifest.
 *
 * @param {string[]} installedFiles Every file this run wrote.
 * @param {string[]} failedPrunePaths Stale paths whose move into the backup failed.
 * @returns {string[]} The deduped file list to record.
 */
function manifestFilesWithFailedPrunes(installedFiles, failedPrunePaths) {
    const survivingFailedPaths = failedPrunePaths.filter(failedPath => existsSync(failedPath));
    return unionOnComparisonKey(survivingFailedPaths, installedFiles);
}

/**
 * Move retired skill directories a prior install left under ~/.claude/skills into
 * a timestamped backup directory rather than deleting them.
 *
 * A directory is pruned only when the package no longer ships it and either the
 * prior manifest recorded it or the package once shipped it. Subtracting the
 * just-installed set from the ever-shipped set at call time means restoring a
 * skill to the package protects it — it re-enters the installed set and never
 * counts as retired. Matching is by directory name alone, so a personal
 * directory a user authored under a name that collides with a retired skill
 * (for example `code`, `implement`, `refine`, `gotcha`, `caveman`) is treated as
 * that retired skill and moved to backup; only a name in neither set, and
 * ~/.claude/skills/_shared, are left in place.
 *
 * Each pruned directory is renamed to
 * ~/.claude/.claude-dev-env-pruned/<timestamp>/skills/<skill-name>/ — a backup
 * root outside ~/.claude/skills, so a moved directory is never re-discovered as a
 * skill — under one shared timestamp per run. That mirrors the ~/.claude layout
 * the per-root stale-file prune writes, so one recovery point reads as a copy of
 * the tree it came from. The recovery window runs until the next pruning install:
 * `retainNewestRunBackupOnly` keeps that run's backup and retires the rest, so a
 * user recovers a wrongly-matched directory from the newest backup on disk. One
 * directory whose rename fails
 * (for example a read-only file or a cross-device move) is logged and left in
 * place, never deleted, so a prune failure costs at most a cosmetic leftover.
 *
 * @param {Set<string>} installedSkillNames Skill names this install just wrote.
 * @param {string[]|null} priorManifestSkills The prior manifest's skill names, or null.
 * @returns {void}
 */
function pruneRetiredSkills(installedSkillNames, priorManifestSkills) {
    const skillsDirectory = join(CLAUDE_HOME, MANAGED_SKILLS_DIRECTORY_NAME);
    if (!existsSync(skillsDirectory)) return;
    const retiredSkillNames = new Set(
        [...EVER_SHIPPED_SKILL_NAMES].filter(skillName => !installedSkillNames.has(skillName))
    );
    const priorSkillNames = new Set(priorManifestSkills || []);
    const backupRoot = currentRunBackupRoot();
    const existingSkillDirs = readdirSync(skillsDirectory, { withFileTypes: true })
        .filter(entry => entry.isDirectory());
    for (const skillDir of existingSkillDirs) {
        const skillName = skillDir.name;
        if (NEVER_PRUNED_SKILL_DIRECTORIES.has(skillName)) continue;
        if (installedSkillNames.has(skillName)) continue;
        const isPruneCandidate = priorSkillNames.has(skillName) || retiredSkillNames.has(skillName);
        if (!isPruneCandidate) continue;
        moveIntoRunBackup(
            join(skillsDirectory, skillName),
            backupRoot,
            join(MANAGED_SKILLS_DIRECTORY_NAME, skillName),
            RETIRED_SKILL_REASON_LABEL,
            CLAUDE_HOME,
        );
    }
}

/**
 * Move every file a prior install wrote under a managed root that this run leaves
 * unwritten into the run's backup root, one call per root.
 *
 * `copyTree` adds and overwrites but never removes, so every managed root carries
 * the same drift the skills root does. One call per root hands the containment
 * guard and the emptied-parent walk the root that owns each file, and each root's
 * content lands under `<backupRoot>/<root-name>/<relative>`, so the recovery point
 * mirrors ~/.claude.
 *
 * Nothing moves unless a prior install recorded it. A user-authored file, a
 * runtime artifact, and a recorded path under no managed root — ~/.claude/CLAUDE.md,
 * settings.json, the manifest itself, and ~/.mypy.ini outside the home — all sit
 * outside every root's diff and stay where they are. ~/.claude/_shared and
 * ~/.claude/skills/_shared are distinct absolute paths, so the `_shared` root call
 * and the skills root call each see their own files and neither sees the other's.
 *
 * @param {string[]|null} priorInstalledFiles Files the prior manifest recorded, or null when unknown.
 * @param {string[]} currentInstalledFiles Every file this run copied.
 * @param {string} backupRoot The run's timestamped backup directory.
 * @returns {{prunedCount: number, skillsPrunedCount: number, failedPaths: string[]}}
 *   The summed count, the skills root's own count, and every path whose move failed.
 */
function pruneStaleFilesAcrossManagedRoots(priorInstalledFiles, currentInstalledFiles, backupRoot) {
    let prunedCount = 0;
    let skillsPrunedCount = 0;
    const failedPaths = [];
    for (const rootName of MANAGED_TOP_LEVEL_DIRECTORY_NAMES) {
        const rootOutcome = pruneStaleInstalledFiles(
            priorInstalledFiles,
            currentInstalledFiles,
            join(CLAUDE_HOME, rootName),
            join(backupRoot, rootName),
        );
        prunedCount += rootOutcome.prunedCount;
        failedPaths.push(...rootOutcome.failedPaths);
        if (rootName === MANAGED_SKILLS_DIRECTORY_NAME) {
            skillsPrunedCount = rootOutcome.prunedCount;
        }
    }
    return { prunedCount, skillsPrunedCount, failedPaths };
}

/**
 * Run every prune a full install performs, in the order that keeps ~/.claude
 * consistent at each step.
 *
 * The settings entries of retired hooks go before the file move: a settings.json
 * naming a hook script that has already left ~/.claude/hooks makes every session
 * start invoke a missing script, so the reference leaves first and the script
 * follows.
 *
 * @param {Set<string>} copiedSkillNames Skill directory names this run wrote.
 * @param {string[]|null} priorManifestSkills The prior manifest's skill names, or null.
 * @param {string[]|null} priorManifestFiles The prior manifest's file list, or null.
 * @param {string[]} installedFiles Every file this run copied.
 * @returns {{prunedCount: number, skillsPrunedCount: number, failedPaths: string[]}}
 *   The stale files moved across all roots, the skills root's share, and every
 *   path whose move failed.
 */
function runFullInstallPrunes(
    copiedSkillNames, priorManifestSkills, priorManifestFiles, installedFiles,
) {
    pruneRetiredSkills(copiedSkillNames, priorManifestSkills);
    const removedHookEntryCount = pruneRetiredHookEntriesFromSettings(
        join(CLAUDE_HOME, SETTINGS_FILE_NAME),
        retiredManagedHookRelativePaths(
            priorManifestFiles, installedFiles, join(CLAUDE_HOME, MANAGED_HOOKS_DIRECTORY_NAME),
        ),
    );
    if (removedHookEntryCount > 0) {
        console.log(`  Hook entries: ${removedHookEntryCount} retired entry(s) removed from settings.json`);
    }
    const staleOutcome = pruneStaleFilesAcrossManagedRoots(
        priorManifestFiles, installedFiles, currentRunBackupRoot(),
    );
    retainNewestRunBackupOnly();
    return staleOutcome;
}

/**
 * Copy the package into ~/.claude, merge hook groups into settings.json, and
 * write the manifest record the uninstall purge and the next run's prune read.
 *
 * Three booleans steer the run and answer different questions. `isFullInstall`
 * answers "should this run do work?" and gates the prunes. `didPruneRun` answers
 * "did the prunes start?" and gates the prune call itself. `didPruneFinish`
 * answers "may this run forget a record?" and gates both manifest keys: only a run
 * whose prunes read the prior record all the way through may replace a key
 * wholesale, because wholesale replacement is what makes the next diff mean "the
 * package stopped shipping this". A scoped install, a full install holding its
 * prunes behind an unresolved dependency group, and a run whose prune step throws
 * each merge their record with the prior one, so every path and skill name stays
 * available to a later prune and to uninstall.
 *
 * @param {string[]|null} selectedGroups The `--only` group names, or null for a full install.
 * @param {{isUpdateRefresh?: boolean}} [options] Run options; `isUpdateRefresh` purges before reinstalling.
 * @returns {void}
 */
function install(selectedGroups, options = {}) {
    const { files: priorManifestFiles, skills: priorManifestSkills } = readPriorManifestArrays();
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
    const installedSkillNames = new Set();
    const copiedSkillNames = new Set();
    for (const sourceRoot of allSourceRoots) {
        const skillsSource = join(sourceRoot, MANAGED_SKILLS_DIRECTORY_NAME);
        if (!existsSync(skillsSource)) continue;
        const skillDirs = readdirSync(skillsSource, { withFileTypes: true }).filter(entry => entry.isDirectory());
        for (const skillDir of skillDirs) {
            if (allowedSkills && !allowedSkills.has(skillDir.name)) continue;
            const skillSourceDirectory = join(skillsSource, skillDir.name);
            const skillDestinationDirectory = join(CLAUDE_HOME, MANAGED_SKILLS_DIRECTORY_NAME, skillDir.name);
            const stats = copyTree(skillSourceDirectory, skillDestinationDirectory);
            skillsCreated += stats.created;
            skillsUpdated += stats.updated;
            skillPaths.push(...stats.paths);
            copiedSkillNames.add(skillDir.name);
            if (existsSync(join(skillSourceDirectory, SKILL_MANIFEST_FILENAME))) {
                installedSkillNames.add(skillDir.name);
            }
        }
    }
    summary.skills = { created: skillsCreated, updated: skillsUpdated, pruned: 0, paths: skillPaths };
    allInstalledFiles.push(...skillPaths);
    const shouldInstallAnyHooks = shouldInstallAllHooks || (allowedHookFiles && allowedHookFiles.size > 0);
    if (shouldInstallAnyHooks) {
        let totalHooksCreated = 0;
        let totalHooksUpdated = 0;
        let totalHookGroups = 0;
        for (const sourceRoot of allSourceRoots) {
            const hooksSource = join(sourceRoot, MANAGED_HOOKS_DIRECTORY_NAME);
            if (!existsSync(hooksSource)) continue;
            const hooksDestination = join(CLAUDE_HOME, MANAGED_HOOKS_DIRECTORY_NAME);
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
        allInstalledFiles.push(...gitHookInstallationResult.createdShimPaths);
        if (hooksPathConfigurationAction === 'set') {
            console.log(`  Git hooks: configured core.hooksPath -> ${gitHookInstallationResult.gitHooksDirectory}`);
        } else if (hooksPathConfigurationAction === 'already-set') {
            console.log('  Git hooks: core.hooksPath already points to claude-dev-env, no change');
        } else {
            console.warn(`  Git hooks: ${gitHookInstallationResult.hooksPathConfigurationResult.reason}`);
        }
        console.log(`  Git hook shims: ${gitHookInstallationResult.createdShimPaths.length} files (pre-commit, pre-push, post-commit)`);

        const mypyIniInstallResult = installMypyIniForClaudeHooks({
            homeDirectory: homedir(),
            claudeHooksDirectory: join(CLAUDE_HOME, MANAGED_HOOKS_DIRECTORY_NAME),
        });
        if (mypyIniInstallResult.action === 'created') {
            allInstalledFiles.push(mypyIniInstallResult.path);
            console.log(`  ✓ ${relative(homedir(), mypyIniInstallResult.path)} (new — enables mypy to resolve config.messages imports)`);
        } else if (mypyIniInstallResult.action === 'already-configured') {
            allInstalledFiles.push(mypyIniInstallResult.path);
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
    const isFullInstall = !selectedGroups;
    const didPruneRun = isFullInstall && UNRESOLVED_DEPENDENCY_NAMES.length === 0;
    let failedPrunePaths = [];
    let stalePrunedTotal = 0;
    if (isFullInstall && !didPruneRun) {
        console.log(
            `  Skipping retired-skill and stale-file prune — unresolved dependency group(s): ${UNRESOLVED_DEPENDENCY_NAMES.join(', ')}. `
            + 'A skill that migrated to a dependency package would look retired and its files would look stale, so both prunes are held until every dependency resolves.',
        );
    }
    let didPruneFinish = false;
    if (didPruneRun) {
        try {
            const prunes = runFullInstallPrunes(
                copiedSkillNames, priorManifestSkills, priorManifestFiles, allInstalledFiles,
            );
            summary.skills.pruned = prunes.skillsPrunedCount;
            stalePrunedTotal = prunes.prunedCount;
            failedPrunePaths = prunes.failedPaths;
            didPruneFinish = true;
        } catch (pruneError) {
            console.warn(
                `  Warning: the prune step ended early (${pruneError.message}) — this run merges its manifest record with the prior one, so a later full install still names every file.`,
            );
        }
    }
    const manifestSkillNames = didPruneFinish
        ? [...installedSkillNames].sort()
        : unionOfSkillNames(priorManifestSkills || [], [...installedSkillNames]).sort();
    const manifestFiles = didPruneFinish
        ? manifestFilesWithFailedPrunes(allInstalledFiles, failedPrunePaths)
        : unionOnComparisonKey(priorManifestFiles || [], allInstalledFiles);
    writeManifest(manifestFiles, manifestSkillNames);
    console.log(`\nInstalled ${PACKAGE_NAME}:`);
    for (const directory of CONTENT_DIRECTORIES) {
        if (summary[directory]) {
            const { created, updated } = summary[directory];
            console.log(`  ${directory}: ${created + updated} files (${created} new, ${updated} updated)`);
        }
    }
    if (summary.skills) {
        const { created, updated, pruned } = summary.skills;
        const staleClause = pruned > 0 ? `, ${pruned} stale moved aside` : '';
        console.log(`  skills: ${created + updated} files (${created} new, ${updated} updated${staleClause})`);
    }
    if (stalePrunedTotal > 0) {
        console.log(`  stale files moved aside: ${stalePrunedTotal} across managed roots, kept under ${PRUNED_SKILLS_BACKUP_DIRECTORY_NAME}/${basename(currentRunBackupRoot())}`);
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
    return isCaseInsensitiveFilesystem()
        && normalizedStored.toLowerCase() === normalizedInstalled.toLowerCase();
}


function unsetGlobalGitHooksPathIfOurs() {
    const installedGitHooksDirectory = join(CLAUDE_HOME, MANAGED_HOOKS_DIRECTORY_NAME, 'git-hooks');
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


/**
 * Remove one file the manifest records, tolerating a path that is already gone.
 *
 * A record can outlive the file it names: the user deleted it by hand, or a
 * scoped install carried the entry forward past the file's own removal. A missing
 * path is skipped in silence so an uninstall runs to the end and clears the
 * manifest, and any other failure is reported and stepped over for the same
 * reason.
 *
 * @param {string} filePath The absolute path the manifest records.
 * @returns {boolean} True when this call removed a file.
 */
function removeRecordedFile(filePath) {
    try {
        unlinkSync(filePath);
    } catch (removalError) {
        if (removalError.code !== 'ENOENT') {
            console.warn(`  Warning: could not remove ${relative(CLAUDE_HOME, filePath)} (${removalError.message})`);
        }
        return false;
    }
    console.log(`  ✗ ${relative(CLAUDE_HOME, filePath)} (removed)`);
    return true;
}

/**
 * Remove every file the manifest records, then drop the directories the removals
 * emptied.
 *
 * A record is removed when it names a path the installer writes: anything under
 * ~/.claude, plus the `~/.mypy.ini` the install writes in the home directory.
 * Every other record is skipped with a warning and counted, so one malformed
 * entry costs that entry alone: the purge removes every legitimate record, clears
 * the manifest, and leaves the user with a whole uninstall rather than a
 * half-removed install.
 *
 * Directory cleanup runs after the file loop so a directory holding two recorded
 * files is judged once both are gone. Each walk stops at the managed root the
 * purged file sits under, which keeps ~/.claude itself and every unmanaged
 * sibling directory in place.
 *
 * @param {{requireManifest: boolean}} options `requireManifest` exits when no manifest exists.
 * @returns {number|void} 0 when no manifest exists and none is required.
 */
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
    let skippedUnmanagedCount = 0;
    const managedRootByEmptiedDirectory = new Map();
    for (const filePath of manifest.files) {
        if (!isRemovableManifestRecord(filePath)) {
            console.warn(`  Warning: skipping ${filePath} — the manifest record names no path this installer writes`);
            skippedUnmanagedCount++;
            continue;
        }
        if (removeRecordedFile(filePath)) removed++;
        const managedRoot = owningManagedRoot(filePath);
        if (managedRoot) managedRootByEmptiedDirectory.set(dirname(resolve(filePath)), managedRoot);
    }
    for (const [emptiedDirectory, managedRoot] of managedRootByEmptiedDirectory) {
        removeEmptiedParentDirectories(emptiedDirectory, managedRoot);
    }
    if (skippedUnmanagedCount > 0) {
        console.warn(`  ${skippedUnmanagedCount} manifest record(s) skipped — each names a path outside ${CLAUDE_HOME} and outside ${MYPY_INI_INSTALL_PATH}`);
    }
    const settingsPath = join(CLAUDE_HOME, SETTINGS_FILE_NAME);
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
    for (const directory of MANAGED_TOP_LEVEL_DIRECTORY_NAMES) {
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

/**
 * Print the usage text, listing the install groups this run resolved.
 *
 * The group list is read from `INSTALL_GROUPS`, so it names the built-in groups
 * and every dependency group that resolved on this machine — the same set
 * `--only` accepts.
 *
 * @returns {void}
 */
function printHelp() {
    const groupLines = Object.entries(INSTALL_GROUPS)
        .map(([groupName, group]) => `  ${groupName} — ${group.description}`)
        .join('\n');
    console.log(`
${PACKAGE_NAME} - Claude Code development standards installer

Usage:
  npx ${PACKAGE_NAME}              Install everything
  npx ${PACKAGE_NAME} --update     Full install: remove prior manifest-tracked files first, then reinstall
  npx ${PACKAGE_NAME} --only X     Install specific groups
  npx ${PACKAGE_NAME} --uninstall  Remove installed files
  npx ${PACKAGE_NAME} --help       Show this help

Groups:
${groupLines}

Examples:
  npx ${PACKAGE_NAME} --only core
  npx ${PACKAGE_NAME} --only core,journal

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
