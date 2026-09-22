#!/usr/bin/env node
/**
 * Install this package into a scratch home directory.
 *
 * The installer writes into `$HOME/.claude` and rewrites the global git
 * configuration. Both are redirected here so a run leaves the caller's own home
 * untouched.
 */

import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIRECTORY = dirname(fileURLToPath(import.meta.url));

export const PACKAGE_ROOT = resolve(SCRIPT_DIRECTORY, '..', '..');
export const INSTALL_ENTRY = join(PACKAGE_ROOT, 'bin', 'install.mjs');
export const SCRATCH_HOME_PREFIX = 'cde-driver-';
export const SANDBOX_GIT_CONFIG_NAME = '.gitconfig-sandbox';
export const SANDBOX_GIT_CONFIG_BODY = '[safe]\n\tdirectory = *\n';

/**
 * Create a scratch home with an isolated global git configuration.
 *
 * @returns {string} The scratch home directory path.
 */
export function createScratchHome() {
    const scratchHome = mkdtempSync(join(tmpdir(), SCRATCH_HOME_PREFIX));
    writeFileSync(join(scratchHome, SANDBOX_GIT_CONFIG_NAME), SANDBOX_GIT_CONFIG_BODY);
    return scratchHome;
}

/**
 * Build the environment an installer run and an installed hook both read.
 *
 * @param {string} scratchHome Scratch home directory path.
 * @returns {NodeJS.ProcessEnv} The environment for a child process.
 */
export function scratchHomeEnvironment(scratchHome) {
    return {
        ...process.env,
        HOME: scratchHome,
        USERPROFILE: scratchHome,
        GIT_CONFIG_GLOBAL: join(scratchHome, SANDBOX_GIT_CONFIG_NAME),
    };
}

/**
 * Run `bin/install.mjs` against a scratch home.
 *
 * @param {string} scratchHome Scratch home directory path.
 * @param {string[]} installerArguments Arguments passed to the installer.
 * @returns {import('node:child_process').SpawnSyncReturns<string>} The installer result.
 */
export function runInstaller(scratchHome, installerArguments) {
    return spawnSync(process.execPath, [INSTALL_ENTRY, ...installerArguments], {
        cwd: PACKAGE_ROOT,
        encoding: 'utf8',
        env: scratchHomeEnvironment(scratchHome),
    });
}

/**
 * Remove a scratch home and everything the install wrote into it.
 *
 * @param {string} scratchHome Scratch home directory path.
 * @returns {void}
 */
export function removeScratchHome(scratchHome) {
    rmSync(scratchHome, { recursive: true, force: true });
}
