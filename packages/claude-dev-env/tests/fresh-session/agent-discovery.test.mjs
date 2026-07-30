/**
 * Fresh-session agent discovery and invocation checks (C4 / P-05).
 *
 * Discovery lists installed agent definitions under each disposable profile.
 * Invocation records a separate harness invoke pass for the fixture agent.
 * Real multi-profile CLI green is residual for B3.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    copyFileSync,
    existsSync,
    mkdirSync,
    readdirSync,
    readFileSync,
    writeFileSync,
} from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import { runProfileSession } from './harness/transport.mjs';

const TEST_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const FIXTURE_AGENT_SOURCE_PATH = join(
    TEST_DIRECTORY,
    'fixtures',
    'agent-discovery',
    'fixture-discoverable.md',
);
const FIXTURE_AGENT_FILE_NAME = 'fixture-discoverable.md';
const FIXTURE_AGENT_NAME = 'fixture-discoverable';
const AGENTS_DIRECTORY_NAME = 'agents';
const HARNESS_LIST_AGENTS_ARGUMENT = '--harness-list-agents';
const HARNESS_INVOKE_AGENT_ARGUMENT = '--harness-invoke-agent';
const INVOCATION_MARKER = 'FIXTURE_AGENT_INVOKE_OK';

/**
 * Install the disposable fixture agent into one profile root.
 *
 * @param {string} profileRoot
 * @returns {string} installed agent path
 */
function installFixtureAgent(profileRoot) {
    const agentsDirectory = join(profileRoot, AGENTS_DIRECTORY_NAME);
    mkdirSync(agentsDirectory, { recursive: true });
    const installedPath = join(agentsDirectory, FIXTURE_AGENT_FILE_NAME);
    copyFileSync(FIXTURE_AGENT_SOURCE_PATH, installedPath);
    return installedPath;
}

/**
 * List discoverable agent basenames from a profile agents directory.
 *
 * @param {string} profileRoot
 * @returns {string[]}
 */
function discoverInstalledAgents(profileRoot) {
    const agentsDirectory = join(profileRoot, AGENTS_DIRECTORY_NAME);
    if (!existsSync(agentsDirectory)) {
        return [];
    }
    return readdirSync(agentsDirectory)
        .filter((eachName) => eachName.endsWith('.md'))
        .map((eachName) => eachName.replace(/\.md$/u, ''))
        .sort();
}

/**
 * Parse the fixture agent name from YAML frontmatter.
 *
 * @param {string} agentSourcePath
 * @returns {string}
 */
function readFixtureAgentName(agentSourcePath) {
    const body = readFileSync(agentSourcePath, 'utf8');
    const match = /^name:\s*([^\r\n]+)/mu.exec(body);
    assert.ok(match, 'fixture agent must declare name frontmatter');
    return match[1].trim();
}

test('fixture agent source declares a stable name and invocation marker', () => {
    assert.ok(existsSync(FIXTURE_AGENT_SOURCE_PATH));
    const body = readFileSync(FIXTURE_AGENT_SOURCE_PATH, 'utf8');
    assert.equal(readFixtureAgentName(FIXTURE_AGENT_SOURCE_PATH), FIXTURE_AGENT_NAME);
    assert.match(body, new RegExp(INVOCATION_MARKER));
});

test('discovery lists the fixture agent independently of invocation for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const profileRoot = roots.profileRootById[eachProfileId];
            installFixtureAgent(profileRoot);

            const discoveredNames = discoverInstalledAgents(profileRoot);
            assert.ok(
                discoveredNames.includes(FIXTURE_AGENT_NAME),
                `profile ${eachProfileId} discovery must list ${FIXTURE_AGENT_NAME}`,
            );

            const listResult = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: false,
                cliArguments: [HARNESS_LIST_AGENTS_ARGUMENT, FIXTURE_AGENT_NAME],
            });
            assert.equal(listResult.exitStatus, 0);
            assert.ok(listResult.command.includes(HARNESS_LIST_AGENTS_ARGUMENT));
            assert.ok(
                listResult.command.includes(FIXTURE_AGENT_NAME),
                'list pass records the fixture agent name in argv',
            );
            assert.ok(
                !listResult.command.includes(HARNESS_INVOKE_AGENT_ARGUMENT),
                'discovery pass must not include the invoke argument',
            );
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('invocation records the fixture agent separately from discovery for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const profileRoot = roots.profileRootById[eachProfileId];
            const installedPath = installFixtureAgent(profileRoot);
            const fixtureBody = readFileSync(installedPath, 'utf8');
            assert.match(fixtureBody, new RegExp(INVOCATION_MARKER));

            const invokeResult = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: false,
                cliArguments: [
                    HARNESS_INVOKE_AGENT_ARGUMENT,
                    FIXTURE_AGENT_NAME,
                    `--marker=${INVOCATION_MARKER}`,
                ],
            });
            assert.equal(invokeResult.exitStatus, 0);
            assert.ok(invokeResult.command.includes(HARNESS_INVOKE_AGENT_ARGUMENT));
            assert.ok(invokeResult.command.includes(FIXTURE_AGENT_NAME));
            assert.ok(
                !invokeResult.command.includes(HARNESS_LIST_AGENTS_ARGUMENT),
                'invocation pass must not include the list argument',
            );

            const evidence = JSON.parse(readFileSync(invokeResult.evidencePath, 'utf8'));
            assert.equal(evidence.profileId, eachProfileId);
            assert.equal(evidence.exitStatus, 0);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing fixture agent fails discovery for the affected profile only', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main', 'editor'] });
    try {
        installFixtureAgent(roots.profileRootById.main);
        const mainNames = discoverInstalledAgents(roots.profileRootById.main);
        const editorNames = discoverInstalledAgents(roots.profileRootById.editor);
        assert.ok(mainNames.includes(FIXTURE_AGENT_NAME));
        assert.ok(!editorNames.includes(FIXTURE_AGENT_NAME));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('fixture agent installs only under disposable profile roots', () => {
    const roots = createDisposableRunRoots({ profileIds: ['mel'] });
    try {
        const installedPath = installFixtureAgent(roots.profileRootById.mel);
        const normalized = installedPath.replace(/\\/gu, '/').toLowerCase();
        assert.ok(normalized.includes('fresh-session') || normalized.includes(roots.runRoot.replace(/\\/gu, '/').toLowerCase()));
        assert.ok(!normalized.includes('/.claude/agents/'));
        writeFileSync(
            join(roots.evidenceRoot, 'agent-discovery-install.json'),
            `${JSON.stringify({ installedPath, profileId: 'mel' }, null, 2)}\n`,
            'utf8',
        );
        assert.ok(existsSync(join(roots.evidenceRoot, 'agent-discovery-install.json')));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
