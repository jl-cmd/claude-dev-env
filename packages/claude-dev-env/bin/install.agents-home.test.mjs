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
    readdirSync,
    realpathSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CONTENT_DIRECTORIES } from './install.mjs';
import {
    MANAGED_AGENTS_DIRECTORY_NAME,
    MANAGED_SKILLS_DIRECTORY_NAME,
} from './install-constants.mjs';
import { isDirectoryPointerTo } from './publish-directory-pointer.mjs';
import { resolvePackageManagedDirectory } from './resolve-package-managed-directory.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);
const SHIPPED_SKILL_NAME = 'privacy-hygiene';
const ELI5_SKILL_NAME = 'eli5';
const E_CODE_REVIEW_SKILL_NAME = 'e-code-review';
const TEAM_ADVISOR_SKILL_NAME = 'team-advisor';
const REFERENCE_DIRECTORY_NAME = 'reference';
const SHIPPED_AGENT_FILE_NAME = 'AGENTS.md';
const RETIRED_AGENT_FILE_NAMES = ['clean-coder.md', 'code-quality-agent.md', 'pr-description-writer.md'];
const PERSONAL_SKILL_NAME = 'my-notes';
const PREFLIGHT_PROPOSAL_FILE_NAME = 'preflight-proposal.md';

/**
 * @param {string} homeDirectory
 * @param {string[]} extraArguments
 * @param {Record<string, string | undefined>} [environmentOverrides]
 * @returns {string}
 */
function runInstaller(homeDirectory, extraArguments, environmentOverrides = {}) {
    const installerEnvironment = {
        ...process.env,
        CDE_INSTALL_PSTACK: '0',
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        CODEX_HOME: join(homeDirectory, '.codex'),
        ...environmentOverrides,
    };
    for (const [eachName, eachValue] of Object.entries(environmentOverrides)) {
        if (eachValue === undefined) delete installerEnvironment[eachName];
    }
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: installerEnvironment,
    });
}

/**
 * @param {{ skillsInstallDirectory: string }} installationPaths
 */
function assertProposalContractInstallation(installationPaths) {
    const { skillsInstallDirectory } = installationPaths;
    const allContractPathSegments = [
        E_CODE_REVIEW_SKILL_NAME,
        REFERENCE_DIRECTORY_NAME,
        PREFLIGHT_PROPOSAL_FILE_NAME,
    ];
    const installedContractPath = join(skillsInstallDirectory, ...allContractPathSegments);
    const sourceSkillsDirectory = resolvePackageManagedDirectory(
        PACKAGE_DIRECTORY,
        MANAGED_SKILLS_DIRECTORY_NAME,
    );
    const sourceContractPath = join(sourceSkillsDirectory, ...allContractPathSegments);

    assert.equal(existsSync(installedContractPath), true);
    assert.equal(readFileSync(installedContractPath, 'utf8'), readFileSync(sourceContractPath, 'utf8'));
}


test('CONTENT_DIRECTORIES omits agents because that tree installs to the agents home', () => {
    assert.equal(CONTENT_DIRECTORIES.includes(MANAGED_AGENTS_DIRECTORY_NAME), false);
});

test('full install archives recorded retired agents and preserves third-party agents', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agent-retirement-'));
    try {
        runInstaller(homeDirectory, []);
        const agentsDirectory = join(homeDirectory, '.agents', 'agents');
        const retiredPath = join(agentsDirectory, 'clean-coder.md');
        const pluginPath = join(agentsDirectory, 'poteto-agent.md');
        const activePath = join(agentsDirectory, 'AGENTS.md');
        const sourcePluginPath = join(PACKAGE_DIRECTORY, '.agents', 'agents', 'poteto-agent.md');
        assert.equal(readFileSync(pluginPath, 'utf8'), readFileSync(sourcePluginPath, 'utf8'));
        writeFileSync(retiredPath, 'recover this retired definition\n');
        writeFileSync(pluginPath, 'preserve this plugin definition\n');
        const manifestPath = join(homeDirectory, '.claude', '.claude-dev-env-manifest.json');
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        manifest.files.push(retiredPath);
        manifest.files.push(activePath);
        writeFileSync(manifestPath, JSON.stringify(manifest));

        runInstaller(homeDirectory, []);

        assert.equal(existsSync(retiredPath), false);
        assert.ok(existsSync(activePath));
        const backupRoot = join(homeDirectory, '.claude', '.claude-dev-env-pruned');
        const backupNames = readdirSync(backupRoot, { recursive: true });
        const retiredBackup = backupNames.find(name => name.endsWith('clean-coder.md'));
        assert.ok(retiredBackup);
        assert.equal(readFileSync(join(backupRoot, retiredBackup), 'utf8'), 'recover this retired definition\n');
        assert.equal(readFileSync(pluginPath, 'utf8'), 'preserve this plugin definition\n');
        const updatedManifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.equal(updatedManifest.files.includes(retiredPath), false);
        runInstaller(homeDirectory, []);
        assert.equal(readFileSync(pluginPath, 'utf8'), 'preserve this plugin definition\n');
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
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
        const canonicalEli5SkillFile = join(
            skillsInstallDirectory, ELI5_SKILL_NAME, 'SKILL.md',
        );
        const lookupSkillFile = join(
            skillsLookupDirectory, SHIPPED_SKILL_NAME, 'SKILL.md',
        );
        const lookupEli5SkillFile = join(
            skillsLookupDirectory, ELI5_SKILL_NAME, 'SKILL.md',
        );
        const canonicalAgentFile = join(agentsInstallDirectory, SHIPPED_AGENT_FILE_NAME);
        const lookupAgentFile = join(agentsLookupDirectory, SHIPPED_AGENT_FILE_NAME);

        assert.equal(existsSync(canonicalSkillFile), true, 'skill file lives under .agents/skills');
        assert.equal(existsSync(canonicalEli5SkillFile), true, 'ELI5 skill file lives under .agents/skills');
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
        assert.equal(
            readFileSync(lookupEli5SkillFile, 'utf8'),
            readFileSync(canonicalEli5SkillFile, 'utf8'),
        );
        assert.equal(realpathSync(lookupSkillFile), realpathSync(canonicalSkillFile));
        assert.equal(realpathSync(lookupEli5SkillFile), realpathSync(canonicalEli5SkillFile));
        assertProposalContractInstallation({ skillsInstallDirectory });
        const projectedAdvisorPaths = [
            join(skillsInstallDirectory, TEAM_ADVISOR_SKILL_NAME, 'SKILL.md'),
            join(claudeHome, 'docs', 'references', 'advisor-tool.md'),
            join(claudeHome, '_shared', 'advisor', 'advisor-protocol.md'),
            join(agentsInstallDirectory, 'poteto-agent.md'),
        ];
        for (const eachPath of projectedAdvisorPaths) {
            assert.ok(existsSync(eachPath), eachPath);
        }
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

/**
 * @param {string} hubPath
 * @returns {string}
 */
function resolveHubImportTarget(hubPath) {
    const hubText = readFileSync(hubPath, 'utf8').trim();
    assert.match(hubText, /^@\S+$/, 'the Claude hub holds one import line');
    return resolve(dirname(hubPath), hubText.slice(1));
}

for (const eachLayout of [
    { label: 'default home', extraArguments: [], claudeHomeName: '.claude', agentsHomeName: '.agents' },
    {
        label: 'profile root',
        extraArguments: ['--target', '.claude-profile-a'],
        claudeHomeName: '.claude-profile-a',
        agentsHomeName: '.claude-profile-a.agents',
    },
]) {
    test(`a ${eachLayout.label} install loads the package guidance from the agents home through the Claude hub`, () => {
        const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agents-hub-'));
        const claudeHome = join(homeDirectory, eachLayout.claudeHomeName);
        const sharedGuidancePath = join(homeDirectory, eachLayout.agentsHomeName, 'AGENTS.md');
        try {
            runInstaller(homeDirectory, eachLayout.extraArguments.map(
                (eachArgument) => (eachArgument.startsWith('.') ? join(homeDirectory, eachArgument) : eachArgument),
            ));

            assert.equal(
                readFileSync(sharedGuidancePath, 'utf8'),
                readFileSync(join(PACKAGE_DIRECTORY, 'AGENTS.md'), 'utf8'),
                'the package guidance lives once in the agents home',
            );
            assert.equal(
                resolveHubImportTarget(join(claudeHome, 'CLAUDE.md')),
                sharedGuidancePath,
                'the Claude hub import resolves to the shared guidance file',
            );
            assert.equal(
                existsSync(join(claudeHome, 'AGENTS.md')),
                false,
                'no second guidance copy lands in the Claude home',
            );
        } finally {
            rmSync(homeDirectory, { recursive: true, force: true });
        }
    });
}

test('an upgrade moves the guidance copy an earlier install left in the Claude home into the run backup', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-agents-hub-upgrade-'));
    const claudeHome = join(homeDirectory, '.claude');
    const retiredGuidancePath = join(claudeHome, 'AGENTS.md');
    const retiredGuidanceText = 'guidance an earlier install copied here\n';
    try {
        runInstaller(homeDirectory, []);
        writeFileSync(retiredGuidancePath, retiredGuidanceText);
        const manifestPath = join(claudeHome, '.claude-dev-env-manifest.json');
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        manifest.files.push(retiredGuidancePath);
        writeFileSync(manifestPath, JSON.stringify(manifest));

        runInstaller(homeDirectory, []);

        assert.equal(existsSync(retiredGuidancePath), false, 'the old Claude-home copy is gone');
        const backupRoot = join(claudeHome, '.claude-dev-env-pruned');
        const backupName = readdirSync(backupRoot, { recursive: true })
            .find(name => name.endsWith('AGENTS.md'));
        assert.ok(backupName, 'the old copy sits in the run backup');
        assert.equal(readFileSync(join(backupRoot, backupName), 'utf8'), retiredGuidanceText);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('installs omit retired agents in each active agents home', () => {
    const runRoot = mkdtempSync(join(tmpdir(), 'cdev-active-roots-'));
    const homeDirectory = join(runRoot, 'home');
    const configRoot = join(runRoot, 'config-profile');
    const explicitRoot = join(runRoot, 'explicit-target');
    const inheritedProfilesRoot = join(runRoot, 'inherited-profiles');
    const inheritedProfileMarker = join(inheritedProfilesRoot, 'untouched.txt');
    mkdirSync(homeDirectory, { recursive: true });
    mkdirSync(inheritedProfilesRoot, { recursive: true });
    writeFileSync(inheritedProfileMarker, 'leave this profile root alone\n');
    try {
        const installCases = [
            {
                name: 'default',
                arguments: ['--only', 'core'],
                environment: { CLAUDE_CONFIG_DIR: undefined },
                managedRoot: join(homeDirectory, '.claude'),
                agentsHome: join(homeDirectory, '.agents'),
            },
            {
                name: 'CLAUDE_CONFIG_DIR',
                arguments: ['--only', 'core'],
                environment: { CLAUDE_CONFIG_DIR: configRoot },
                managedRoot: configRoot,
                agentsHome: `${configRoot}.agents`,
            },
            {
                name: 'named profile',
                arguments: ['--profile', 'editor', '--only', 'core'],
                environment: {
                    CLAUDE_CONFIG_DIR: undefined,
                    LLM_SETTINGS_PROFILES_ROOT: undefined,
                },
                managedRoot: join(homeDirectory, '.claude-profiles', 'editor'),
                agentsHome: join(homeDirectory, '.claude-profiles', 'editor.agents'),
            },
            {
                name: 'explicit target',
                arguments: ['--target', explicitRoot, '--only', 'core'],
                environment: { CLAUDE_CONFIG_DIR: configRoot },
                managedRoot: explicitRoot,
                agentsHome: `${explicitRoot}.agents`,
            },
        ];

        for (const eachInstallCase of installCases) {
            runInstaller(
                homeDirectory,
                eachInstallCase.arguments,
                {
                    LLM_SETTINGS_PROFILES_ROOT: inheritedProfilesRoot,
                    ...eachInstallCase.environment,
                },
            );
            for (const eachAgentFileName of RETIRED_AGENT_FILE_NAMES) {
                const installedAgentPath = join(
                    eachInstallCase.agentsHome,
                    MANAGED_AGENTS_DIRECTORY_NAME,
                    eachAgentFileName,
                );
                assert.equal(
                    existsSync(installedAgentPath),
                    false,
                    `${eachInstallCase.name}: retired agent is absent`,
                );
            }
            assert.equal(
                isDirectoryPointerTo(
                    join(eachInstallCase.managedRoot, MANAGED_AGENTS_DIRECTORY_NAME),
                    join(eachInstallCase.agentsHome, MANAGED_AGENTS_DIRECTORY_NAME),
                ),
                true,
                `${eachInstallCase.name}: lookup path points to the active agents home`,
            );
        }
        assert.equal(
            readFileSync(inheritedProfileMarker, 'utf8'),
            'leave this profile root alone\n',
            'an inherited profile root stays untouched',
        );
        assert.equal(
            existsSync(join(inheritedProfilesRoot, 'editor')),
            false,
            'the named profile does not use the inherited profile root',
        );
    } finally {
        rmSync(runRoot, { recursive: true, force: true });
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
