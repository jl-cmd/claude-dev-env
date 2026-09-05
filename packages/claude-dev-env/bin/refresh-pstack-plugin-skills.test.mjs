import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    mkdirSync,
    readFileSync,
    rmSync,
    symlinkSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import {
    PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH,
    findPstackSkillDirectoryNames,
    refreshPstackPluginManifest,
} from '../scripts/refresh_pstack_plugin_skills.mjs';

function buildPluginRoot(homeDirectory, skillNames, manifest) {
    const pluginRoot = join(homeDirectory, 'pstack');
    for (const eachSkillName of skillNames) {
        const skillDirectory = join(pluginRoot, eachSkillName);
        mkdirSync(skillDirectory, { recursive: true });
        writeFileSync(join(skillDirectory, 'SKILL.md'), '---\n');
    }
    const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
    mkdirSync(join(pluginRoot, '.claude-plugin'), { recursive: true });
    if (manifest !== null) {
        writeFileSync(manifestPath, JSON.stringify(manifest));
    }
    return pluginRoot;
}

function withTemporaryHome(runAssertions) {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-manifest-'));
    try {
        runAssertions(homeDirectory);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
}

test('finds only sub-folders that hold a skill entry file', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how', 'why'], { skills: [] });
        mkdirSync(join(pluginRoot, 'docs'), { recursive: true });
        writeFileSync(join(pluginRoot, '.claude-plugin', 'SKILL.md'), '---\n');

        assert.deepEqual(findPstackSkillDirectoryNames(pluginRoot), ['how', 'why']);
    });
});

test('writes a manifest when the plugin folder has none', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], null);

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.equal(outcome.didWrite, true);
        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        const written = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.equal(written.name, 'pstack');
        assert.deepEqual(written.skills, ['./how']);
    });
});

test('adds a skill folder the manifest does not list', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how', 'why'], {
            name: 'pstack',
            skills: ['./how'],
        });

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.equal(outcome.didWrite, true);
        assert.deepEqual(outcome.previousSkillPaths, ['./how']);
        assert.deepEqual(outcome.currentSkillPaths, ['./how', './why']);
    });
});

test('leaves the manifest byte for byte when nothing changed', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], {
            name: 'pstack',
            skills: ['./how'],
        });
        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        writeFileSync(manifestPath, JSON.stringify({ name: 'pstack', skills: ['./how'] }));
        const before = readFileSync(manifestPath, 'utf8');

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.equal(outcome.didWrite, false);
        assert.equal(readFileSync(manifestPath, 'utf8'), before);
    });
});

test('reads a string skills value as a one-entry list', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], {
            name: 'pstack',
            skills: './',
        });

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.deepEqual(outcome.previousSkillPaths, ['./']);
        assert.deepEqual(outcome.currentSkillPaths, ['./how']);
    });
});

test('keeps manifest fields the refresher does not own', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], {
            name: 'pstack',
            version: '9.9.9',
            description: 'a description the user edited',
            skills: [],
        });

        refreshPstackPluginManifest(pluginRoot);

        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        const written = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.equal(written.version, '9.9.9');
        assert.equal(written.description, 'a description the user edited');
    });
});

test('refuses a folder that is itself one skill', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], null);
        writeFileSync(join(pluginRoot, 'SKILL.md'), '---\n');

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.equal(outcome.didWrite, false);
        assert.equal(outcome.reason, 'plugin root is itself a skill');
    });
});

test('running the file directly reports what it did', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], null);
        const modulePath = join(
            dirname(dirname(fileURLToPath(import.meta.url))),
            'scripts',
            'refresh_pstack_plugin_skills.mjs',
        );

        const firstRun = execFileSync('node', [modulePath, pluginRoot], { encoding: 'utf8' });
        const secondRun = execFileSync('node', [modulePath, pluginRoot], { encoding: 'utf8' });

        assert.match(firstRun, /Updated\. 1 skills listed\./);
        assert.match(secondRun, /No change\. 1 skills listed\./);
    });
});

test('running the file through a directory link still reports what it did', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, ['how'], null);
        const scriptsDirectory = join(
            dirname(dirname(fileURLToPath(import.meta.url))),
            'scripts',
        );
        const linkedScriptsDirectory = join(homeDirectory, 'linked-scripts');
        symlinkSync(scriptsDirectory, linkedScriptsDirectory, 'junction');
        const linkedModulePath = join(linkedScriptsDirectory, 'refresh_pstack_plugin_skills.mjs');

        const output = execFileSync('node', [linkedModulePath, pluginRoot], { encoding: 'utf8' });

        assert.match(output, /Updated\. 1 skills listed\./);
    });
});

test('with no folder argument it follows CLAUDE_CONFIG_DIR', () => {
    withTemporaryHome((homeDirectory) => {
        const claudeConfigDirectory = join(homeDirectory, 'profile', '.claude');
        const pluginRoot = join(claudeConfigDirectory, 'skills', 'pstack');
        mkdirSync(join(pluginRoot, 'how'), { recursive: true });
        writeFileSync(join(pluginRoot, 'how', 'SKILL.md'), '---\n');
        const modulePath = join(
            dirname(dirname(fileURLToPath(import.meta.url))),
            'scripts',
            'refresh_pstack_plugin_skills.mjs',
        );

        const output = execFileSync('node', [modulePath], {
            encoding: 'utf8',
            env: { ...process.env, CLAUDE_CONFIG_DIR: claudeConfigDirectory },
        });

        assert.match(output, /Updated\. 1 skills listed\./);
        const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
        assert.deepEqual(JSON.parse(readFileSync(manifestPath, 'utf8')).skills, ['./how']);
    });
});

test('refuses a folder that holds no skills', () => {
    withTemporaryHome((homeDirectory) => {
        const pluginRoot = buildPluginRoot(homeDirectory, [], null);

        const outcome = refreshPstackPluginManifest(pluginRoot);

        assert.equal(outcome.didWrite, false);
        assert.equal(outcome.reason, 'plugin root holds no skills');
    });
});
