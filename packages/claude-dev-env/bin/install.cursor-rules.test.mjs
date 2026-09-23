import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
    copyFileSync,
    rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import {
    resolveInstallRoot,
    isAllowedInstallDestination,
} from './resolve-install-root.mjs';
import {
    DEFAULT_CURSOR_DIRECTORY_NAME,
    CURSOR_RULES_DIRECTORY_NAME,
} from './install-constants.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);

function runInstaller(homeDirectory, extraArguments, environmentOverrides = {}) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            CDE_INSTALL_PSTACK: '0',
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            CODEX_HOME: join(homeDirectory, '.codex'),
            CLAUDE_CONFIG_DIR: join(homeDirectory, '.claude'),
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
            ...environmentOverrides,
        },
    });
}

test('resolveInstallRoot names ~/.cursor/rules and allows generated mdc files under it', () => {
    const homeDirectory = join(tmpdir(), 'cdev-cursor-rules-home');
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: {},
        explicitTarget: null,
    });
    const expectedDirectory = join(
        homeDirectory,
        DEFAULT_CURSOR_DIRECTORY_NAME,
        CURSOR_RULES_DIRECTORY_NAME,
    );
    assert.equal(resolution.cursorRulesInstallDirectory, expectedDirectory);
    assert.equal(
        isAllowedInstallDestination(join(expectedDirectory, 'asd-ste100-language.mdc'), resolution),
        true,
    );
    assert.equal(
        isAllowedInstallDestination(join(homeDirectory, '.ssh', 'id_rsa'), resolution),
        false,
    );
});

test('a full install writes stem-named Cursor rules and leaves a local extra mdc in place', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-cursor-install-'));
    try {
        const extraRulePath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'user-local.mdc',
        );
        mkdirSync(dirname(extraRulePath), { recursive: true });
        writeFileSync(extraRulePath, 'keep-me\n');

        runInstaller(homeDirectory, []);

        const generatedPath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'asd-ste100-language.mdc',
        );
        assert.equal(existsSync(generatedPath), true);
        const generatedText = readFileSync(generatedPath, 'utf8');
        assert.equal(generatedText.includes('alwaysApply: true'), true);
        assert.equal(readFileSync(extraRulePath, 'utf8'), 'keep-me\n');
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('--only journal is rejected before Cursor rules change; --only core writes them', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-cursor-groups-'));
    try {
        const generatedPath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'asd-ste100-language.mdc',
        );
        const policyPath = join(homeDirectory, '.agents', 'rules', 'subagent-model-policy.json');
        assert.throws(
            () => runInstaller(homeDirectory, ['--only', 'journal']),
            error => error.status === 1 && /Unknown group\(s\): journal/.test(error.stderr),
        );
        assert.equal(existsSync(generatedPath), false);
        assert.equal(existsSync(policyPath), false);

        runInstaller(homeDirectory, ['--only', 'core']);
        assert.equal(existsSync(generatedPath), true);
        assert.equal(existsSync(policyPath), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});


test('seeds one editable policy and one native Codex routing hook', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-install-'));
    try {
        const resolution = resolveInstallRoot({
            homeDirectory,
            environment: {},
            explicitTarget: null,
        });
        const policyPath = join(resolution.agentsHome, 'rules', 'subagent-model-policy.json');
        const installedRulesPolicyPath = join(
            resolution.managedRoot,
            'rules',
            'subagent-model-policy.json',
        );
        const codexHooksPath = join(homeDirectory, '.codex', 'hooks.json');

        runInstaller(homeDirectory, ['--only', 'core']);

        assert.equal(existsSync(policyPath), true);
        assert.equal(existsSync(installedRulesPolicyPath), false);
        const firstCodexHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        const firstRoutingGroups = firstCodexHooks.hooks.PreToolUse.filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        assert.equal(firstRoutingGroups.length, 1);
        assert.equal(firstRoutingGroups[0].hooks.length, 1);
        assert.match(firstRoutingGroups[0].hooks[0].command, /subagent_model_routing\.mjs/);
        const firstSpawnPromptGroups = firstCodexHooks.hooks.PreToolUse.filter(
            group => group.matcher === 'Agent|Task',
        );
        assert.equal(firstSpawnPromptGroups.length, 1);
        assert.match(firstSpawnPromptGroups[0].hooks[0].command, /skill_loaded_reminder\.py/);
        assert.deepEqual(Object.keys(firstCodexHooks.hooks), ['PreToolUse']);
        assert.equal(
            firstCodexHooks.hooks.PreToolUse.some(group => group.matcher === 'Write|Edit|MultiEdit|apply_patch'),
            false,
        );

        const editedPolicy = '{"schemaVersion":1,"edited":true}\n';
        writeFileSync(policyPath, editedPolicy);
        firstCodexHooks.hooks.PreToolUse.push({
            matcher: 'custom',
            hooks: [{ type: 'command', command: 'python user-hook.py' }],
        });
        writeFileSync(codexHooksPath, JSON.stringify(firstCodexHooks, null, 2) + '\n');

        runInstaller(homeDirectory, ['--only', 'core']);

        assert.equal(readFileSync(policyPath, 'utf8'), editedPolicy);
        const secondCodexHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        assert.equal(
            secondCodexHooks.hooks.PreToolUse.filter(
                group => group.matcher === 'multi_agent_v1__spawn_agent',
            ).length,
            1,
        );
        assert.equal(
            secondCodexHooks.hooks.PreToolUse.some(
                group => group.matcher === 'custom'
                    && group.hooks.some(hook => hook.command === 'python user-hook.py'),
            ),
            true,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('reinstall moves the old routing hook and keeps user hooks', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-hook-upgrade-'));
    try {
        const resolution = resolveInstallRoot({
            homeDirectory,
            environment: {},
            explicitTarget: null,
        });
        const codexHooksPath = join(homeDirectory, '.codex', 'hooks.json');
        const manifestPath = resolution.manifestFilePath;
        const routingHookPath = join(
            homeDirectory,
            '.codex',
            'hooks',
            'routing',
            'subagent_model_routing.mjs',
        );
        const oldRoutingHookPath = join(
            homeDirectory,
            '.codex',
            'hooks',
            'blocking',
            'subagent_model_routing.mjs',
        );

        runInstaller(homeDirectory, []);
        const firstCodexHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        const firstRoutingGroup = firstCodexHooks.hooks.PreToolUse.find(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        firstRoutingGroup.hooks[0].command = firstRoutingGroup.hooks[0].command.replace(
            /routing([\\/])subagent_model_routing\.mjs$/,
            'blocking$1subagent_model_routing.mjs',
        );
        firstCodexHooks.hooks.PreToolUse.push({
            matcher: 'custom',
            hooks: [{ type: 'command', command: 'node user-hook.mjs' }],
        });
        writeFileSync(codexHooksPath, JSON.stringify(firstCodexHooks, null, 2) + '\n');
        copyFileSync(routingHookPath, oldRoutingHookPath);
        rmSync(routingHookPath);

        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        manifest.files = manifest.files.map(file => file.replace(
            /([\\/])routing([\\/]subagent_model_routing\.mjs)$/,
            '$1blocking$2',
        ));
        writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

        runInstaller(homeDirectory, []);

        const secondCodexHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        const routingGroups = secondCodexHooks.hooks.PreToolUse.filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        assert.equal(routingGroups.length, 1);
        assert.match(routingGroups[0].hooks[0].command, /[\\/]hooks[\\/]routing[\\/]subagent_model_routing\.mjs/);
        assert.doesNotMatch(
            JSON.stringify(secondCodexHooks),
            /[\\/]hooks[\\/]blocking[\\/]subagent_model_routing\.mjs/,
        );
        assert.equal(existsSync(routingHookPath), true);
        assert.equal(existsSync(oldRoutingHookPath), false);
        assert.equal(
            secondCodexHooks.hooks.PreToolUse.some(
                group => group.matcher === 'custom'
                    && group.hooks.some(hook => hook.command === 'node user-hook.mjs'),
            ),
            true,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall removes the routing hook and keeps a Codex user hook', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-uninstall-'));
    try {
        const profileRoot = join(homeDirectory, 'named-profile');
        const codexHooksPath = join(profileRoot, '.codex', 'hooks.json');
        const targetArguments = ['--target', profileRoot];
        runInstaller(homeDirectory, [...targetArguments, '--only', 'core']);
        const codexHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        codexHooks.hooks.PreToolUse.push({
            matcher: 'custom',
            hooks: [{ type: 'command', command: 'python user-hook.py' }],
        });
        writeFileSync(codexHooksPath, JSON.stringify(codexHooks, null, 2) + '\n');

        runInstaller(homeDirectory, [...targetArguments, '--uninstall']);

        const remainingHooks = JSON.parse(readFileSync(codexHooksPath, 'utf8'));
        assert.equal(
            remainingHooks.hooks.PreToolUse.some(group => group.matcher === 'multi_agent_v1__spawn_agent'),
            false,
        );
        assert.equal(
            remainingHooks.hooks.PreToolUse.some(
                group => group.matcher === 'custom'
                    && group.hooks.some(hook => hook.command === 'python user-hook.py'),
            ),
            true,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('malformed Codex hooks restore the staged install', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-malformed-'));
    try {
        const codexHooksPath = join(homeDirectory, '.codex', 'hooks.json');
        const claudeSettingsPath = join(homeDirectory, '.claude', 'settings.json');
        const originalCodexHooks = '{ malformed\n';
        const originalClaudeSettings = '{"hooks":{"PreToolUse":[{"matcher":"user","hooks":[{"type":"command","command":"user-hook"}]}]}}\n';
        mkdirSync(dirname(codexHooksPath), { recursive: true });
        mkdirSync(dirname(claudeSettingsPath), { recursive: true });
        writeFileSync(codexHooksPath, originalCodexHooks);
        writeFileSync(claudeSettingsPath, originalClaudeSettings);

        assert.throws(
            () => runInstaller(homeDirectory, ['--only', 'core']),
            error => error.status === 1,
        );
        assert.equal(readFileSync(codexHooksPath, 'utf8'), originalCodexHooks);
        assert.equal(readFileSync(claudeSettingsPath, 'utf8'), originalClaudeSettings);
        assert.equal(existsSync(join(homeDirectory, '.claude', 'hooks')), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('malformed Codex hooks restore an uninstall', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-uninstall-malformed-'));
    try {
        runInstaller(homeDirectory, ['--only', 'core']);
        const codexHooksPath = join(homeDirectory, '.codex', 'hooks.json');
        const manifestPath = join(homeDirectory, '.claude', '.claude-dev-env-manifest.json');
        const managedHookPath = join(
            homeDirectory,
            '.claude',
            'hooks',
            'routing',
            'subagent_model_routing.mjs',
        );
        writeFileSync(codexHooksPath, '{ malformed\n');

        assert.throws(
            () => runInstaller(homeDirectory, ['--uninstall']),
            error => error.status === 1,
        );
        assert.equal(existsSync(manifestPath), true);
        assert.equal(existsSync(managedHookPath), true);
        assert.equal(readFileSync(codexHooksPath, 'utf8'), '{ malformed\n');
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('two profiles keep separate Codex routing hooks', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-profiles-'));
    try {
        const profileRoot = join(homeDirectory, 'named-profile');
        const mainCodexHooksPath = join(homeDirectory, '.codex', 'hooks.json');
        const profileCodexHooksPath = join(profileRoot, '.codex', 'hooks.json');
        runInstaller(homeDirectory, ['--only', 'core']);
        runInstaller(homeDirectory, ['--target', profileRoot, '--only', 'core']);

        const mainCodexHooks = JSON.parse(readFileSync(mainCodexHooksPath, 'utf8'));
        const profileCodexHooks = JSON.parse(readFileSync(profileCodexHooksPath, 'utf8'));
        const mainRoutingGroups = (mainCodexHooks.hooks?.PreToolUse ?? []).filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        const profileRoutingGroups = profileCodexHooks.hooks.PreToolUse.filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        assert.equal(mainRoutingGroups.length, 1);
        assert.equal(profileRoutingGroups.length, 1);
        assert.match(mainRoutingGroups[0].hooks[0].command, /[\\/]\.codex[\\/]hooks[\\/]routing[\\/]subagent_model_routing\.mjs/);
        assert.match(profileRoutingGroups[0].hooks[0].command, /named-profile[\\/]\.codex[\\/]hooks[\\/]routing[\\/]subagent_model_routing\.mjs/);
        assert.notEqual(mainRoutingGroups[0].hooks[0].command, profileRoutingGroups[0].hooks[0].command);

        const profileHookPath = join(
            profileRoot,
            '.codex',
            'hooks',
            'routing',
            'subagent_model_routing.mjs',
        );
        const profileHookResponse = JSON.parse(execFileSync(
            'node',
            [profileHookPath],
            {
                encoding: 'utf8',
                input: JSON.stringify({
                    tool_name: 'multi_agent_v1__spawn_agent',
                    tool_input: { model: 'Terra', reasoning_effort: 'medium' },
                }),
            },
        ));
        assert.equal(
            profileHookResponse.hookSpecificOutput.updatedInput.model,
            'gpt-5.6-luna',
        );
        assert.equal(
            profileHookResponse.hookSpecificOutput.updatedInput.reasoning_effort,
            'xhigh',
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstalling one profile keeps routing for another installed profile', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-routing-profile-uninstall-'));
    try {
        const profileRoot = join(homeDirectory, 'named-profile');
        const mainCodexHooksPath = join(homeDirectory, '.codex', 'hooks.json');
        const profileCodexHooksPath = join(profileRoot, '.codex', 'hooks.json');
        runInstaller(homeDirectory, ['--only', 'core']);
        runInstaller(homeDirectory, ['--target', profileRoot, '--only', 'core']);
        runInstaller(homeDirectory, ['--uninstall']);

        const mainCodexHooks = JSON.parse(readFileSync(mainCodexHooksPath, 'utf8'));
        const profileCodexHooks = JSON.parse(readFileSync(profileCodexHooksPath, 'utf8'));
        const mainRoutingGroups = (mainCodexHooks.hooks?.PreToolUse ?? []).filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        const profileRoutingGroups = profileCodexHooks.hooks.PreToolUse.filter(
            group => group.matcher === 'multi_agent_v1__spawn_agent',
        );
        assert.equal(mainRoutingGroups.length, 0);
        assert.equal(profileRoutingGroups.length, 1);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('a blocked shared rule destination rolls back generated Cursor files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-rollback-'));
    try {
        const sharedRulesPath = join(homeDirectory, '.agents', 'rules');
        mkdirSync(dirname(sharedRulesPath), { recursive: true });
        writeFileSync(sharedRulesPath, 'keep-existing-file');
        assert.throws(() => runInstaller(homeDirectory, ['--only', 'core']));
        assert.equal(readFileSync(sharedRulesPath, 'utf8'), 'keep-existing-file');
        assert.equal(existsSync(join(homeDirectory, '.cursor', 'rules', 'pstack-models.mdc')), false);
        assert.equal(existsSync(join(homeDirectory, '.cursor', '.sync-manifest.json')), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

