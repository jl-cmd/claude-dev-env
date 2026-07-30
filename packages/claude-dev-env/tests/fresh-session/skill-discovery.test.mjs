/**
 * Fresh-session skill metadata discovery vs full-body load (C5 / P-06).
 *
 * Startup discovery reads skill name/description only.
 * Full load reads the SKILL.md body marker after activation.
 * Real multi-profile CLI green is residual for B3.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    cpSync,
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
const FIXTURE_SKILL_SOURCE_DIRECTORY = join(
    TEST_DIRECTORY,
    'fixtures',
    'skill-discovery',
    'fixture-skill',
);
const FIXTURE_SKILL_NAME = 'fixture-skill';
const SKILLS_DIRECTORY_NAME = 'skills';
const SKILL_FILE_NAME = 'SKILL.md';
const METADATA_MARKER = 'FIXTURE_SKILL_METADATA_OK';
const BODY_MARKER = 'FIXTURE_SKILL_BODY_LOADED';
const HARNESS_DISCOVER_SKILL_ARGUMENT = '--harness-discover-skill';
const HARNESS_LOAD_SKILL_ARGUMENT = '--harness-load-skill';

/**
 * @typedef {{
 *   installed: boolean,
 *   discovered: boolean,
 *   activated: boolean,
 *   behaviorally_verified: boolean,
 *   metadataName: string | null,
 *   hasMetadataMarker: boolean,
 *   hasBodyMarker: boolean,
 * }} SkillStateRecord
 */

/**
 * Absolute path to the installed fixture SKILL.md under a profile root.
 *
 * @param {string} profileRoot
 * @returns {string}
 */
function fixtureSkillMarkdownPath(profileRoot) {
    return join(
        profileRoot,
        SKILLS_DIRECTORY_NAME,
        FIXTURE_SKILL_NAME,
        SKILL_FILE_NAME,
    );
}

/**
 * Install the disposable fixture skill into one profile root.
 *
 * @param {string} profileRoot
 * @returns {string} Path to the installed SKILL.md
 */
function installFixtureSkill(profileRoot) {
    const destinationDirectory = join(
        profileRoot,
        SKILLS_DIRECTORY_NAME,
        FIXTURE_SKILL_NAME,
    );
    mkdirSync(join(profileRoot, SKILLS_DIRECTORY_NAME), { recursive: true });
    cpSync(FIXTURE_SKILL_SOURCE_DIRECTORY, destinationDirectory, { recursive: true });
    return fixtureSkillMarkdownPath(profileRoot);
}

/**
 * Read skill frontmatter name without treating the body as loaded evidence.
 *
 * @param {string} skillMarkdownPath
 * @returns {{name: string, description: string, frontmatter: string, body: string}}
 */
function splitSkillMarkdown(skillMarkdownPath) {
    const text = readFileSync(skillMarkdownPath, 'utf8');
    const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/u.exec(text);
    assert.ok(match, 'SKILL.md must use YAML frontmatter');
    const frontmatter = match[1];
    const body = match[2];
    const nameMatch = /^name:\s*([^\r\n]+)/mu.exec(frontmatter);
    const descriptionMatch = /^description:\s*([^\r\n]+)/mu.exec(frontmatter);
    assert.ok(nameMatch, 'skill frontmatter requires name');
    assert.ok(descriptionMatch, 'skill frontmatter requires description');
    return {
        name: nameMatch[1].trim(),
        description: descriptionMatch[1].trim(),
        frontmatter,
        body,
    };
}

/**
 * Build the four-state record for one profile.
 *
 * @param {string} profileRoot
 * @param {{activated: boolean, behaviorally_verified: boolean}} flags
 * @returns {SkillStateRecord}
 */
function buildSkillStateRecord(profileRoot, flags) {
    const skillPath = fixtureSkillMarkdownPath(profileRoot);
    const installed = existsSync(skillPath);
    if (!installed) {
        return {
            installed: false,
            discovered: false,
            activated: false,
            behaviorally_verified: false,
            metadataName: null,
            hasMetadataMarker: false,
            hasBodyMarker: false,
        };
    }
    const parts = splitSkillMarkdown(skillPath);
    const discovered = parts.name === FIXTURE_SKILL_NAME && parts.description.length > 0;
    return {
        installed: true,
        discovered,
        activated: flags.activated,
        behaviorally_verified: flags.behaviorally_verified,
        metadataName: parts.name,
        hasMetadataMarker: parts.frontmatter.includes(METADATA_MARKER)
            || parts.body.includes(METADATA_MARKER),
        hasBodyMarker: parts.body.includes(BODY_MARKER),
    };
}

test('fixture skill separates metadata marker from body-load marker', () => {
    const parts = splitSkillMarkdown(join(FIXTURE_SKILL_SOURCE_DIRECTORY, SKILL_FILE_NAME));
    assert.equal(parts.name, FIXTURE_SKILL_NAME);
    assert.ok(parts.body.includes(METADATA_MARKER), 'metadata marker lives in body text');
    assert.ok(parts.body.includes(BODY_MARKER), 'body marker lives outside frontmatter');
    assert.ok(
        !parts.frontmatter.includes(BODY_MARKER),
        'body marker must not appear in frontmatter alone',
    );
    assert.ok(
        !parts.frontmatter.includes(METADATA_MARKER),
        'metadata marker is body content, not frontmatter name/description',
    );
});

test('metadata discovery does not require body-load activation', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const profileRoot = roots.profileRootById[eachProfileId];
            installFixtureSkill(profileRoot);

            const discoveryResult = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: false,
                cliArguments: [HARNESS_DISCOVER_SKILL_ARGUMENT, FIXTURE_SKILL_NAME],
            });
            assert.equal(discoveryResult.exitStatus, 0);
            assert.ok(discoveryResult.command.includes(HARNESS_DISCOVER_SKILL_ARGUMENT));
            assert.ok(!discoveryResult.command.includes(HARNESS_LOAD_SKILL_ARGUMENT));

            const state = buildSkillStateRecord(profileRoot, {
                activated: false,
                behaviorally_verified: false,
            });
            assert.equal(state.installed, true);
            assert.equal(state.discovered, true);
            assert.equal(state.activated, false);
            assert.equal(state.behaviorally_verified, false);
            assert.equal(state.hasMetadataMarker, true);
            assert.equal(state.hasBodyMarker, true);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('full-body load records body marker activation separately from metadata discovery', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const profileRoot = roots.profileRootById[eachProfileId];
            installFixtureSkill(profileRoot);

            const loadResult = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: false,
                cliArguments: [
                    HARNESS_LOAD_SKILL_ARGUMENT,
                    FIXTURE_SKILL_NAME,
                    `--body-marker=${BODY_MARKER}`,
                ],
            });
            assert.equal(loadResult.exitStatus, 0);
            assert.ok(loadResult.command.includes(HARNESS_LOAD_SKILL_ARGUMENT));
            assert.ok(!loadResult.command.includes(HARNESS_DISCOVER_SKILL_ARGUMENT));

            const state = buildSkillStateRecord(profileRoot, {
                activated: true,
                behaviorally_verified: true,
            });
            assert.equal(state.installed, true);
            assert.equal(state.discovered, true);
            assert.equal(state.activated, true);
            assert.equal(state.behaviorally_verified, true);
            assert.equal(state.hasMetadataMarker, true);
            assert.equal(state.hasBodyMarker, true);

            writeFileSync(
                join(roots.evidenceRoot, `${eachProfileId}-skill-state.json`),
                `${JSON.stringify(state, null, 2)}\n`,
                'utf8',
            );
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('skill directory without fixture reports not installed and not discovered', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        mkdirSync(join(roots.profileRootById.editor, SKILLS_DIRECTORY_NAME), { recursive: true });
        const skillNames = readdirSync(join(roots.profileRootById.editor, SKILLS_DIRECTORY_NAME));
        assert.ok(!skillNames.includes(FIXTURE_SKILL_NAME));
        const state = buildSkillStateRecord(roots.profileRootById.editor, {
            activated: false,
            behaviorally_verified: false,
        });
        assert.equal(state.installed, false);
        assert.equal(state.discovered, false);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
