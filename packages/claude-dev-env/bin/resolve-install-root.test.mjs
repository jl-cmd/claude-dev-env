import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { join } from 'node:path';
import {
    resolveInstallRoot,
    CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE,
    DEFAULT_CLAUDE_DIRECTORY_NAME,
} from './resolve-install-root.mjs';
import {
    CODEX_HOME_ENVIRONMENT_VARIABLE,
    CODEX_HOOKS_DIRECTORY_NAME,
    CODEX_RULES_DIRECTORY_NAME,
    DEFAULT_CODEX_DIRECTORY_NAME,
    MANAGED_SKILLS_DIRECTORY_NAME,
    PACKAGE_AGENTS_HOME_DIRECTORY_NAME,
} from './install-constants.mjs';

const HOME_DIRECTORY = join('/tmp', 'cdev-resolve-roots-home');

function resolveFrom(environment, explicitTarget = null) {
    return resolveInstallRoot({ homeDirectory: HOME_DIRECTORY, environment, explicitTarget });
}

test('the managed root falls back to the default Claude directory under the home', () => {
    const resolution = resolveFrom({});
    assert.equal(resolution.managedRoot, join(HOME_DIRECTORY, DEFAULT_CLAUDE_DIRECTORY_NAME));
    assert.equal(resolution.source, 'default-home');
});

test('CLAUDE_CONFIG_DIR names the managed root and an explicit target outranks it', () => {
    const configuredRoot = join('/tmp', 'cdev-configured');
    const explicitRoot = join('/tmp', 'cdev-explicit');
    const configured = resolveFrom({ [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: configuredRoot });
    assert.equal(configured.managedRoot, configuredRoot);
    assert.equal(configured.source, 'claude-config-dir');

    const explicit = resolveFrom(
        { [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: configuredRoot },
        explicitRoot,
    );
    assert.equal(explicit.managedRoot, explicitRoot);
    assert.equal(explicit.source, 'explicit-target');
});

test('the Codex home is the directory holding the rules and hooks destinations', () => {
    const resolution = resolveFrom({});
    const codexHome = join(HOME_DIRECTORY, DEFAULT_CODEX_DIRECTORY_NAME);
    assert.equal(resolution.codexHomeDirectory, codexHome);
    assert.equal(resolution.codexRulesInstallDirectory, join(codexHome, CODEX_RULES_DIRECTORY_NAME));
    assert.equal(resolution.codexHooksInstallDirectory, join(codexHome, CODEX_HOOKS_DIRECTORY_NAME));
});

test('CODEX_HOME relocates the Codex home the pstack plugin step installs into', () => {
    const relocatedHome = join('/tmp', 'cdev-relocated-codex');
    const resolution = resolveFrom({ [CODEX_HOME_ENVIRONMENT_VARIABLE]: relocatedHome });
    assert.equal(resolution.codexHomeDirectory, relocatedHome);
    assert.equal(resolution.codexRulesInstallDirectory, join(relocatedHome, CODEX_RULES_DIRECTORY_NAME));
});

test('a managed root named .claude pairs with the sibling agents home', () => {
    const resolution = resolveFrom({});
    assert.equal(resolution.agentsHome, join(HOME_DIRECTORY, PACKAGE_AGENTS_HOME_DIRECTORY_NAME));
    assert.equal(resolution.skillsInstallDirectory, join(HOME_DIRECTORY, PACKAGE_AGENTS_HOME_DIRECTORY_NAME, MANAGED_SKILLS_DIRECTORY_NAME));
    assert.equal(
        resolution.skillsLookupDirectory,
        join(HOME_DIRECTORY, DEFAULT_CLAUDE_DIRECTORY_NAME, MANAGED_SKILLS_DIRECTORY_NAME),
    );
});
