#!/usr/bin/env node

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, copyFileSync, unlinkSync, rmSync } from 'node:fs';
import { join, dirname, resolve, relative } from 'node:path';
import { homedir } from 'node:os';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const CLAUDE_HOME = join(homedir(), '.claude');
const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MANIFEST_FILE = join(CLAUDE_HOME, '.claude-dev-env-manifest.json');
const PACKAGE_NAME = 'claude-dev-env';
const packageRequire = createRequire(import.meta.url);

const CONTENT_DIRECTORIES = ['rules', 'docs', 'commands', 'agents', 'system-prompts', 'scripts'];

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
            'anthropic-plan', 'everything-search', 'ingest',
            'npm-creator', 'pr-review-responder', 'readability-review',
            'recall', 'remember', 'rule-audit', 'rule-creator',
            'skill-writer', 'tdd-team'
        ],
        includeDirectories: ['rules', 'docs', 'commands', 'agents'],
        includeAllHooks: true,
    },
    journal: {
        description: 'Session logging and memory',
        skills: ['dream', 'session-log', 'session-tidy'],
    },
    research: {
        description: 'Deep research and citation tools',
        skills: ['deep-research', 'research-mode'],
    },
    ...discoverDependencyGroups(),
};

function detectPython() {
    const candidates = [
        { command: 'python3', versionFlag: '--version' },
        { command: 'python', versionFlag: '--version' },
        { command: 'py -3', versionFlag: '--version' },
    ];
    for (const { command, versionFlag } of candidates) {
        try {
            const version = execSync(`${command} ${versionFlag}`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
            if (version.includes('Python 3.')) {
                return command;
            }
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
    if (!settings.hooks) settings.hooks = {};
    const installedHooksDir = join(CLAUDE_HOME, 'hooks');
    const pluginRootDir = CLAUDE_HOME;
    let groupCount = 0;
    for (const [eventType, matcherGroups] of Object.entries(hooksConfig.hooks)) {
        if (!settings.hooks[eventType]) settings.hooks[eventType] = [];
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
                    hook => !hook.command.includes(installedHooksDir.replace(/\\/g, '/'))
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
    writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
    return groupCount;
}

function writeManifest(installedFiles) {
    const manifest = { package: PACKAGE_NAME, version: '1.0.0', installedAt: new Date().toISOString(), files: installedFiles };
    writeFileSync(MANIFEST_FILE, JSON.stringify(manifest, null, 2) + '\n');
}

function install(selectedGroups) {
    const groupLabel = selectedGroups ? `groups: ${selectedGroups.join(', ')}` : 'all';
    console.log(`\nInstalling ${PACKAGE_NAME} (${groupLabel})...\n`);
    const pythonCommand = detectPython();
    if (!pythonCommand) {
        console.error('ERROR: Python 3 not found. Install Python 3.8+ and ensure python3, python, or py is on PATH.');
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

function uninstall() {
    console.log(`\nUninstalling ${PACKAGE_NAME}...\n`);
    if (!existsSync(MANIFEST_FILE)) {
        console.error('No installation manifest found. Nothing to uninstall.');
        process.exit(1);
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
            const installedHooksDir = join(CLAUDE_HOME, 'hooks').replace(/\\/g, '/');
            for (const [eventType, matcherGroups] of Object.entries(settings.hooks)) {
                settings.hooks[eventType] = matcherGroups
                    .map(group => ({
                        ...group,
                        hooks: group.hooks.filter(hook => !hook.command.includes(installedHooksDir)),
                    }))
                    .filter(group => group.hooks.length > 0);
                if (settings.hooks[eventType].length === 0) delete settings.hooks[eventType];
            }
            if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
            writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');
            console.log('  Hook entries removed from settings.json');
        }
    }
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

function printHelp() {
    console.log(`
${PACKAGE_NAME} - Claude Code development standards installer

Usage:
  npx ${PACKAGE_NAME}              Install everything
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

const args = process.argv.slice(2);
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
    install(selectedGroups);
}
