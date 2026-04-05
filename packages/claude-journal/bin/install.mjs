#!/usr/bin/env node

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, copyFileSync, unlinkSync, rmSync } from 'node:fs';
import { join, dirname, resolve, relative } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';

const CLAUDE_HOME = join(homedir(), '.claude');
const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MANIFEST_FILE = join(CLAUDE_HOME, '.claude-journal-manifest.json');
const PACKAGE_NAME = 'claude-journal';

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

function install() {
    console.log(`\nInstalling ${PACKAGE_NAME}...\n`);
    mkdirSync(CLAUDE_HOME, { recursive: true });
    const allInstalledFiles = [];
    const skillsSource = join(PACKAGE_ROOT, 'skills');
    const skillDirs = readdirSync(skillsSource, { withFileTypes: true }).filter(entry => entry.isDirectory());
    let skillsCreated = 0;
    let skillsUpdated = 0;
    for (const skillDir of skillDirs) {
        const stats = copyTree(join(skillsSource, skillDir.name), join(CLAUDE_HOME, 'skills', skillDir.name));
        skillsCreated += stats.created;
        skillsUpdated += stats.updated;
        allInstalledFiles.push(...stats.paths);
    }
    const manifest = { package: PACKAGE_NAME, version: '1.0.0', installedAt: new Date().toISOString(), files: allInstalledFiles };
    writeFileSync(MANIFEST_FILE, JSON.stringify(manifest, null, 2) + '\n');
    console.log(`\nInstalled ${PACKAGE_NAME}: ${skillsCreated + skillsUpdated} files (${skillsCreated} new, ${skillsUpdated} updated)\n`);
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
    unlinkSync(MANIFEST_FILE);
    for (const skillDir of readdirSync(join(CLAUDE_HOME, 'skills'), { withFileTypes: true })) {
        const dirPath = join(CLAUDE_HOME, 'skills', skillDir.name);
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
${PACKAGE_NAME} - Claude Code journal skills installer

Usage:
  npx ${PACKAGE_NAME}              Install journal skills (dream, session-log, session-tidy)
  npx ${PACKAGE_NAME} --uninstall  Remove installed skills
  npx ${PACKAGE_NAME} --help       Show this help

Install location: ~/.claude/skills/
`);
}

const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) printHelp();
else if (args.includes('--uninstall')) uninstall();
else install();
