#!/usr/bin/env node
/**
 * Smoke driver for the claude-dev-env installer.
 *
 * The installer (bin/install.mjs) writes into os.homedir()/.claude and has
 * three global side effects: it copies files under ~/.claude/, sets
 * `git config --global core.hooksPath`, and writes ~/.mypy.ini. There is no
 * flag to redirect the target, so this driver isolates every side effect by
 * spawning the installer with HOME, USERPROFILE, and GIT_CONFIG_GLOBAL all
 * pointed at a throwaway sandbox directory. Node's os.homedir() follows
 * USERPROFILE on Windows and HOME on POSIX, so setting both redirects the
 * install target on either platform without touching the real ~/.claude/.
 *
 * The isolated GIT_CONFIG_GLOBAL is seeded with `safe.directory = *` so the
 * installer's `git status` source-conflict guard runs even when the checkout
 * lives somewhere git flags as dubious ownership (for example a UNC network
 * share), while the installer's `git config --global core.hooksPath` write
 * still lands only in the sandbox config.
 *
 * It runs the three lifecycle commands an agent cares about — `--help`, a full
 * install, and `--uninstall` — and asserts the observable result of each
 * against the sandbox tree. Exit code 0 means every assertion held.
 *
 * Usage: node .claude/skills/run-claude-dev-env/driver.mjs
 */

import { spawnSync } from 'node:child_process';
import {
    mkdtempSync,
    existsSync,
    readFileSync,
    writeFileSync,
    readdirSync,
    rmSync,
} from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const DRIVER_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = resolve(DRIVER_DIRECTORY, '..', '..', '..');
const INSTALL_ENTRY = join(PACKAGE_ROOT, 'bin', 'install.mjs');

const checks = [];

function record(label, passed, detail) {
    checks.push({ label, passed, detail });
    const mark = passed ? 'PASS' : 'FAIL';
    console.log(`  [${mark}] ${label}${detail ? ` — ${detail}` : ''}`);
}

function collectFilesRecursive(directory) {
    const collected = [];
    if (!existsSync(directory)) return collected;
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const entryPath = join(directory, entry.name);
        if (entry.isDirectory()) {
            collected.push(...collectFilesRecursive(entryPath));
        } else {
            collected.push(entryPath);
        }
    }
    return collected;
}

function runInstaller(sandboxHome, installerArguments) {
    const gitConfigGlobal = join(sandboxHome, '.gitconfig-sandbox');
    const result = spawnSync(process.execPath, [INSTALL_ENTRY, ...installerArguments], {
        cwd: PACKAGE_ROOT,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: sandboxHome,
            USERPROFILE: sandboxHome,
            GIT_CONFIG_GLOBAL: gitConfigGlobal,
        },
    });
    return result;
}

function main() {
    const sandboxHome = mkdtempSync(join(tmpdir(), 'cde-driver-'));
    const claudeHome = join(sandboxHome, '.claude');
    writeFileSync(join(sandboxHome, '.gitconfig-sandbox'), '[safe]\n\tdirectory = *\n');
    console.log(`Sandbox HOME: ${sandboxHome}`);
    console.log(`Install entry: ${INSTALL_ENTRY}\n`);

    try {
        console.log('Step 1: node bin/install.mjs --help');
        const help = runInstaller(sandboxHome, ['--help']);
        record('--help exits 0', help.status === 0, `exit=${help.status}`);
        record('--help prints usage', /Usage:/.test(help.stdout), '');
        record('--help wrote nothing to ~/.claude', !existsSync(claudeHome), '');

        console.log('\nStep 2: node bin/install.mjs (full install)');
        const install = runInstaller(sandboxHome, []);
        if (install.status !== 0) {
            console.log(install.stdout);
            console.log(install.stderr);
        }
        record('install exits 0', install.status === 0, `exit=${install.status}`);

        const manifestPath = join(claudeHome, '.claude-dev-env-manifest.json');
        let manifest = null;
        if (existsSync(manifestPath)) {
            manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        }
        record('manifest written', manifest !== null, manifestPath);
        record(
            'manifest names this package',
            manifest?.package === 'claude-dev-env',
            manifest ? `package=${manifest.package} version=${manifest.version}` : 'missing',
        );
        record(
            'manifest tracks installed files',
            Array.isArray(manifest?.files) && manifest.files.length > 0,
            manifest?.files ? `${manifest.files.length} files` : 'none',
        );

        const skillsDirectory = join(claudeHome, 'skills');
        const installedSkills = existsSync(skillsDirectory)
            ? readdirSync(skillsDirectory, { withFileTypes: true }).filter((entry) => entry.isDirectory())
            : [];
        record('skills installed', installedSkills.length > 0, `${installedSkills.length} skill dirs`);

        const hookFiles = collectFilesRecursive(join(claudeHome, 'hooks')).filter((file) =>
            file.endsWith('.py'),
        );
        record('hook scripts installed', hookFiles.length > 0, `${hookFiles.length} .py files`);

        const ruleFiles = existsSync(join(claudeHome, 'rules'))
            ? readdirSync(join(claudeHome, 'rules')).filter((name) => name.endsWith('.md'))
            : [];
        record('rules installed', ruleFiles.length > 0, `${ruleFiles.length} .md files`);

        record('CLAUDE.md hub installed', existsSync(join(claudeHome, 'CLAUDE.md')), '');

        const settingsPath = join(claudeHome, 'settings.json');
        let managedHookCount = 0;
        if (existsSync(settingsPath)) {
            const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
            for (const matcherGroups of Object.values(settings.hooks ?? {})) {
                for (const group of matcherGroups) {
                    for (const hook of group.hooks ?? []) {
                        if (hook.command.replace(/\\/g, '/').includes('/.claude/hooks')) {
                            managedHookCount += 1;
                        }
                    }
                }
            }
        }
        record('settings.json carries managed hooks', managedHookCount > 0, `${managedHookCount} hook commands`);

        const gitConfigGlobalPath = join(sandboxHome, '.gitconfig-sandbox');
        const gitHooksPathRedirectedIntoSandbox =
            existsSync(gitConfigGlobalPath) &&
            readFileSync(gitConfigGlobalPath, 'utf8').replace(/\\/g, '/').includes('/.claude/hooks/git-hooks');
        record(
            'global git hooksPath isolated to sandbox',
            gitHooksPathRedirectedIntoSandbox,
            'GIT_CONFIG_GLOBAL kept the real ~/.gitconfig untouched',
        );

        const sampleInstalledFile = manifest?.files?.find((file) => existsSync(file));

        console.log('\nStep 3: node bin/install.mjs --uninstall');
        const uninstall = runInstaller(sandboxHome, ['--uninstall']);
        if (uninstall.status !== 0) {
            console.log(uninstall.stdout);
            console.log(uninstall.stderr);
        }
        record('uninstall exits 0', uninstall.status === 0, `exit=${uninstall.status}`);
        record('manifest removed', !existsSync(manifestPath), '');
        record(
            'tracked file removed',
            sampleInstalledFile ? !existsSync(sampleInstalledFile) : false,
            sampleInstalledFile ? sampleInstalledFile : 'no sample file captured',
        );
    } finally {
        rmSync(sandboxHome, { recursive: true, force: true });
        console.log(`\nSandbox removed: ${sandboxHome}`);
    }

    const failures = checks.filter((check) => !check.passed);
    console.log(`\n${checks.length - failures.length}/${checks.length} checks passed.`);
    if (failures.length > 0) {
        console.log('FAILED:');
        for (const failure of failures) {
            console.log(`  - ${failure.label}`);
        }
        process.exit(1);
    }
    console.log('ALL CHECKS PASSED');
}

main();
