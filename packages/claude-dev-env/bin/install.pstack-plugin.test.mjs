import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
    rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { resolveInstallRoot } from './resolve-install-root.mjs';
import { PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH } from '../scripts/refresh_pstack_plugin_skills.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);

function runInstaller(homeDirectory, extraArguments) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            CODEX_HOME: join(homeDirectory, '.codex'),
            CLAUDE_CONFIG_DIR: join(homeDirectory, '.claude'),
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        },
    });
}

function seedPstackSkills(agentsHome, skillNames) {
    const pluginRoot = join(agentsHome, 'skills', 'pstack');
    for (const eachSkillName of skillNames) {
        const skillDirectory = join(pluginRoot, eachSkillName);
        mkdirSync(skillDirectory, { recursive: true });
        writeFileSync(join(skillDirectory, 'SKILL.md'), '---\nname: ' + eachSkillName + '\n---\n');
    }
    return pluginRoot;
}

function withTemporaryHome(runAssertions) {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-plugin-'));
    try {
        const resolution = resolveInstallRoot({
            homeDirectory,
            environment: {},
            explicitTarget: null,
        });
        runAssertions(homeDirectory, resolution);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
}

test('a pstack folder the user installed gains a plugin manifest', () => {
    withTemporaryHome((homeDirectory, resolution) => {
        const pluginRoot = seedPstackSkills(resolution.agentsHome, ['how', 'why']);

        runInstaller(homeDirectory, ['--only', 'core']);

        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        assert.equal(existsSync(manifestPath), true);
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.equal(manifest.name, 'pstack');
        assert.deepEqual(manifest.skills, ['./how', './why']);
    });
});

test('a second install leaves an unchanged manifest byte for byte', () => {
    withTemporaryHome((homeDirectory, resolution) => {
        const pluginRoot = seedPstackSkills(resolution.agentsHome, ['how']);

        runInstaller(homeDirectory, ['--only', 'core']);
        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        const afterFirstInstall = readFileSync(manifestPath, 'utf8');
        runInstaller(homeDirectory, ['--only', 'core']);

        assert.equal(readFileSync(manifestPath, 'utf8'), afterFirstInstall);
    });
});

test('a later install lists a skill a pstack update added', () => {
    withTemporaryHome((homeDirectory, resolution) => {
        const pluginRoot = seedPstackSkills(resolution.agentsHome, ['how']);
        runInstaller(homeDirectory, ['--only', 'core']);

        seedPstackSkills(resolution.agentsHome, ['why']);
        runInstaller(homeDirectory, ['--only', 'core']);

        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.deepEqual(manifest.skills, ['./how', './why']);
    });
});

test('an install with no pstack folder writes no manifest and does not fail', () => {
    withTemporaryHome((homeDirectory, resolution) => {
        runInstaller(homeDirectory, ['--only', 'core']);

        const manifestPath = join(
            resolution.agentsHome,
            'skills',
            'pstack',
            PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH,
        );
        assert.equal(existsSync(manifestPath), false);
    });
});
