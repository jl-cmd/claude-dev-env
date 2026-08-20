/**
 * End-to-end install layout: skills and agents live under the agents home,
 * and the Claude lookup paths are directory pointers to that home.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import {
    existsSync,
    lstatSync,
    mkdirSync,
    mkdtempSync,
    readFileSync,
    realpathSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CONTENT_DIRECTORIES } from './install.mjs';
import {
    MANAGED_AGENTS_DIRECTORY_NAME,
    MANAGED_SKILLS_DIRECTORY_NAME,
} from './install-constants.mjs';
import { isDirectoryPointerTo } from './publish-directory-pointer.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);
const SHIPPED_SKILL_NAME = 'privacy-hygiene';
const SHIPPED_AGENT_FILE_NAME = 'clean-coder.md';
const PERSONAL_SKILL_NAME = 'my-notes';

/**
 * @param {string} homeDirectory
 * @param {string[]} extraArguments
 * @returns {string}
 */
function runInstaller(homeDirectory, extraArguments) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
            CODEX_HOME: join(homeDirectory, '.codex'),
        },
    });
}

test('CONTENT_DIRECTORIES omits agents because that tree installs to the agents home', () => {
    assert.equal(CONTENT_DIRECTORIES.includes(MANAGED_AGENTS_DIRECTORY_NAME), false);
});

test('a full install writes skills and agents under .agents and points .claude at them', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agents-home-'));
    const claudeHome = join(homeDirectory, '.claude');
    const agentsHome = join(homeDirectory, '.agents');
    const skillsInstallDirectory = join(agentsHome, MANAGED_SKILLS_DIRECTORY_NAME);
    const agentsInstallDirectory = join(agentsHome, MANAGED_AGENTS_DIRECTORY_NAME);
    const skillsLookupDirectory = join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME);
    const agentsLookupDirectory = join(claudeHome, MANAGED_AGENTS_DIRECTORY_NAME);
    try {
        runInstaller(homeDirectory, []);

        const canonicalSkillFile = join(
            skillsInstallDirectory, SHIPPED_SKILL_NAME, 'SKILL.md',
        );
        const lookupSkillFile = join(
            skillsLookupDirectory, SHIPPED_SKILL_NAME, 'SKILL.md',
        );
        const canonicalAgentFile = join(agentsInstallDirectory, SHIPPED_AGENT_FILE_NAME);
        const lookupAgentFile = join(agentsLookupDirectory, SHIPPED_AGENT_FILE_NAME);

        assert.equal(existsSync(canonicalSkillFile), true, 'skill file lives under .agents/skills');
        assert.equal(existsSync(canonicalAgentFile), true, 'agent file lives under .agents/agents');
        assert.equal(lstatSync(skillsLookupDirectory).isSymbolicLink(), true);
        assert.equal(lstatSync(agentsLookupDirectory).isSymbolicLink(), true);
        assert.equal(
            isDirectoryPointerTo(skillsLookupDirectory, skillsInstallDirectory),
            true,
        );
        assert.equal(
            isDirectoryPointerTo(agentsLookupDirectory, agentsInstallDirectory),
            true,
        );
        assert.equal(
            readFileSync(lookupSkillFile, 'utf8'),
            readFileSync(canonicalSkillFile, 'utf8'),
        );
        assert.equal(realpathSync(lookupSkillFile), realpathSync(canonicalSkillFile));
        assert.equal(
            readFileSync(lookupAgentFile, 'utf8'),
            readFileSync(canonicalAgentFile, 'utf8'),
        );
        assert.equal(realpathSync(lookupAgentFile), realpathSync(canonicalAgentFile));
        assert.equal(
            lstatSync(skillsInstallDirectory).isSymbolicLink(),
            false,
            'the agents-home skills directory is a real directory',
        );
        assert.equal(
            lstatSync(agentsInstallDirectory).isSymbolicLink(),
            false,
            'the agents-home agents directory is a real directory',
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('a real skills directory from an older install lands in .agents and stays readable through the pointer', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agents-relocate-'));
    const claudeHome = join(homeDirectory, '.claude');
    const skillsLookupDirectory = join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME);
    const personalSkillFile = join(
        skillsLookupDirectory, PERSONAL_SKILL_NAME, 'notes.md',
    );
    try {
        mkdirSync(join(skillsLookupDirectory, PERSONAL_SKILL_NAME), { recursive: true });
        writeFileSync(personalSkillFile, 'keep this personal skill\n');

        runInstaller(homeDirectory, []);

        const canonicalPersonalFile = join(
            homeDirectory, '.agents', MANAGED_SKILLS_DIRECTORY_NAME,
            PERSONAL_SKILL_NAME, 'notes.md',
        );
        assert.equal(lstatSync(join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME)).isSymbolicLink(), true);
        assert.equal(existsSync(canonicalPersonalFile), true);
        assert.equal(
            readFileSync(join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME, PERSONAL_SKILL_NAME, 'notes.md'), 'utf8'),
            'keep this personal skill\n',
        );
        assert.equal(
            realpathSync(join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME, PERSONAL_SKILL_NAME, 'notes.md')),
            realpathSync(canonicalPersonalFile),
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall removes managed skill files from the agents home and leaves a personal skill reachable through the pointer', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agents-uninstall-'));
    const claudeHome = join(homeDirectory, '.claude');
    const skillsLookupDirectory = join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME);
    try {
        mkdirSync(join(skillsLookupDirectory, PERSONAL_SKILL_NAME), { recursive: true });
        writeFileSync(
            join(skillsLookupDirectory, PERSONAL_SKILL_NAME, 'notes.md'),
            'keep this personal skill\n',
        );
        runInstaller(homeDirectory, []);
        runInstaller(homeDirectory, ['--uninstall']);

        const shippedSkillFile = join(
            homeDirectory, '.agents', MANAGED_SKILLS_DIRECTORY_NAME,
            SHIPPED_SKILL_NAME, 'SKILL.md',
        );
        const personalSkillFile = join(
            homeDirectory, '.agents', MANAGED_SKILLS_DIRECTORY_NAME,
            PERSONAL_SKILL_NAME, 'notes.md',
        );
        assert.equal(existsSync(shippedSkillFile), false);
        assert.equal(existsSync(personalSkillFile), true);
        assert.equal(
            isDirectoryPointerTo(
                join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME),
                join(homeDirectory, '.agents', MANAGED_SKILLS_DIRECTORY_NAME),
            ),
            true,
            'the lookup pointer stays so a personal skill remains discoverable',
        );
        assert.equal(
            readFileSync(join(claudeHome, MANAGED_SKILLS_DIRECTORY_NAME, PERSONAL_SKILL_NAME, 'notes.md'), 'utf8'),
            'keep this personal skill\n',
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});
