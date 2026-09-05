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
import { resolvePackageManagedDirectory } from './resolve-package-managed-directory.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);
const SHIPPED_SKILL_NAME = 'privacy-hygiene';
const ELI5_SKILL_NAME = 'eli5';
const E_CODE_REVIEW_SKILL_NAME = 'e-code-review';
const REFERENCE_DIRECTORY_NAME = 'reference';
const SHIPPED_AGENT_FILE_NAME = 'clean-coder.md';
const SHIPPED_AGENT_FILE_NAMES = [
    SHIPPED_AGENT_FILE_NAME,
    'code-quality-agent.md',
    'pr-description-writer.md',
];
const CLEAN_CODER_POLICY_REFERENCES = [
    [
        '<managed-root>/docs/CODE_RULES.md',
        'packages/claude-dev-env/docs/CODE_RULES.md',
    ],
    [
        '<managed-root>/hooks/blocking/code_rules_enforcer.py',
        'packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py',
    ],
    [
        '<managed-root>/rules/code-standards.md',
        'packages/claude-dev-env/rules/code-standards.md',
    ],
    [
        '<managed-root>/rules/file-global-constants.md',
        'packages/claude-dev-env/rules/file-global-constants.md',
    ],
    [
        '<managed-root>/rules/windows-filesystem-safe.md',
        'packages/claude-dev-env/rules/windows-filesystem-safe.md',
    ],
    [
        '<managed-root>/rules/gh-cli-conventions.md',
        'packages/claude-dev-env/rules/gh-cli-conventions.md',
    ],
    [
        '<managed-root>/rules/plain-illustrative-docstrings.md',
        'packages/claude-dev-env/rules/plain-illustrative-docstrings.md',
    ],
];
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

/**
 * @param {string} agentFilePath
 * @param {string} layoutName
 * @param {string} managedRoot
 * @returns {string[]}
 */
function cleanCoderPolicyReferenceProblems(agentFilePath, layoutName, managedRoot) {
    const agentBody = readFileSync(agentFilePath, 'utf8');
    const missingReferences = [];
    for (const [installedReference, sourceReference] of CLEAN_CODER_POLICY_REFERENCES) {
        const eachReference = layoutName === 'source'
            ? sourceReference
            : installedReference;
        const eachTargetPath = sourceReference.replace('packages/claude-dev-env/', '');
        if (!agentBody.includes(eachReference)) {
            missingReferences.push(eachReference + ' is absent');
        }
        const resolvedPath = layoutName === 'source'
            ? join(PACKAGE_DIRECTORY, eachTargetPath)
            : join(managedRoot, eachTargetPath);
        if (!existsSync(resolvedPath)) {
            missingReferences.push(layoutName + ': ' + resolvedPath);
        }
    }
    return missingReferences.map((reference) => layoutName + ': ' + reference);
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
        assert.equal(
            readFileSync(lookupAgentFile, 'utf8'),
            readFileSync(canonicalAgentFile, 'utf8'),
        );
        const sourceAgentFile = join(
            resolvePackageManagedDirectory(
                PACKAGE_DIRECTORY,
                MANAGED_AGENTS_DIRECTORY_NAME,
            ),
            SHIPPED_AGENT_FILE_NAME,
        );
        const brokenPolicyReferences = [
            ...cleanCoderPolicyReferenceProblems(sourceAgentFile, 'source', claudeHome),
            ...cleanCoderPolicyReferenceProblems(canonicalAgentFile, 'installed', claudeHome),
        ];
        assert.deepEqual(brokenPolicyReferences, [], 'Clean Coder has broken policy references');
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

test('real installs place the Clean Coder in each active agents home', () => {
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
            for (const eachAgentFileName of SHIPPED_AGENT_FILE_NAMES) {
                const installedAgentPath = join(
                    eachInstallCase.agentsHome,
                    MANAGED_AGENTS_DIRECTORY_NAME,
                    eachAgentFileName,
                );
                assert.equal(
                    existsSync(installedAgentPath),
                    true,
                    `${eachInstallCase.name}: agent is under the active agents home`,
                );
                const installedAgentText = readFileSync(installedAgentPath, 'utf8');
                assert.match(installedAgentText, /active managed root/i);
                assert.match(installedAgentText, /active agents home/i);
                assert.match(installedAgentText, /<managed-root>\//);
                assert.match(installedAgentText, /<agents-home>\//);
            }
            const installedCleanCoderPath = join(
                eachInstallCase.agentsHome,
                MANAGED_AGENTS_DIRECTORY_NAME,
                SHIPPED_AGENT_FILE_NAME,
            );
            const policyReferenceProblems = cleanCoderPolicyReferenceProblems(
                installedCleanCoderPath,
                'installed',
                eachInstallCase.managedRoot,
            );
            assert.deepEqual(
                policyReferenceProblems,
                [],
                `${eachInstallCase.name}: Clean Coder has broken policy references`,
            );
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
