import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');

const RETIRED_SKILL_DIRECTORIES = [
    'findbugs',
    'fixbugs',
    'pr-scope-resolve',
    'post-audit-findings',
    'pr-consistency-audit',
    'bdd-protocol',
];
const PERSONAL_SKILL_DIRECTORIES = ['balatro', 'midjourney-sref', 'credit-card-picker'];
const SHIPPED_SKILL_DIRECTORY = 'autoconverge';

/**
 * Create an isolated ~/.claude sandbox and return the paths a prune test reads.
 *
 * The returned home directory becomes the installer's HOME, so every file the
 * install writes and every skill directory the prune inspects stays inside the
 * temp tree and never touches the machine's real ~/.claude.
 *
 * @returns {{homeDirectory: string, claudeDirectory: string, skillsDirectory: string, manifestPath: string}}
 */
function createSandbox() {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-prune-home-'));
    const claudeDirectory = join(homeDirectory, '.claude');
    const skillsDirectory = join(claudeDirectory, 'skills');
    mkdirSync(skillsDirectory, { recursive: true });
    const manifestPath = join(claudeDirectory, '.claude-dev-env-manifest.json');
    return { homeDirectory, claudeDirectory, skillsDirectory, manifestPath };
}

/**
 * Plant a skill directory under the sandbox with a single marker file.
 *
 * A personal directory is planted with no ``SKILL.md`` so it never looks like a
 * shipped skill; a retired directory is planted with a ``SKILL.md`` so it mirrors
 * a real skill the package once installed and later dropped.
 *
 * @param {string} skillsDirectory The sandbox skills directory.
 * @param {string} skillName The directory name to plant.
 * @param {boolean} withSkillManifest Whether to write a ``SKILL.md`` marker.
 */
function plantSkillDirectory(skillsDirectory, skillName, withSkillManifest) {
    const skillDirectory = join(skillsDirectory, skillName);
    mkdirSync(skillDirectory, { recursive: true });
    const markerName = withSkillManifest ? 'SKILL.md' : 'notes.md';
    writeFileSync(join(skillDirectory, markerName), `seeded ${skillName}\n`);
}

/**
 * Run the real installer against the sandbox home and return its combined output.
 *
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @param {string[]} extraArguments Installer arguments (for example ``['--only', 'core']``).
 * @returns {string} The installer's stdout.
 */
function runInstaller(homeDirectory, extraArguments) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: THIS_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        },
    });
}

function readManifest(manifestPath) {
    return JSON.parse(readFileSync(manifestPath, 'utf8'));
}

test('a full reinstall over a pre-manifest dirty tree prunes retired skills and keeps personal ones', () => {
    const sandbox = createSandbox();
    try {
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, retiredSkill, true);
        }
        for (const personalSkill of PERSONAL_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, personalSkill, false);
        }
        assert.equal(existsSync(sandbox.manifestPath), false, 'sandbox starts with no manifest');

        runInstaller(sandbox.homeDirectory, []);

        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned`,
            );
        }
        for (const personalSkill of PERSONAL_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, personalSkill)),
                true,
                `personal skill ${personalSkill} should survive`,
            );
        }
        assert.equal(
            existsSync(join(sandbox.skillsDirectory, SHIPPED_SKILL_DIRECTORY)),
            true,
            'shipped skills should install',
        );
        const manifest = readManifest(sandbox.manifestPath);
        assert.ok(Array.isArray(manifest.skills), 'manifest gains a skills array');
        assert.ok(manifest.skills.includes(SHIPPED_SKILL_DIRECTORY), 'manifest skills lists shipped skills');
        assert.equal(manifest.skills.includes('_shared'), false, 'manifest skills omits _shared');
        assert.equal(manifest.skills.includes('__pycache__'), false, 'manifest skills omits __pycache__');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall over an old-format manifest without a skills key still prunes via the ever-shipped fallback', () => {
    const sandbox = createSandbox();
    try {
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, retiredSkill, true);
        }
        writeFileSync(
            sandbox.manifestPath,
            JSON.stringify({
                package: 'claude-dev-env',
                version: '0.0.0',
                installedAt: new Date().toISOString(),
                files: [join(sandbox.skillsDirectory, 'findbugs', 'SKILL.md')],
            }, null, 2) + '\n',
        );

        runInstaller(sandbox.homeDirectory, []);

        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned via the ever-shipped fallback`,
            );
        }
        const manifest = readManifest(sandbox.manifestPath);
        assert.ok(Array.isArray(manifest.skills), 'the reinstall writes the skills key onto the old-format manifest');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall prunes a manifest-recorded skill absent from the package and keeps a personal directory', () => {
    const sandbox = createSandbox();
    try {
        const retiredManifestSkill = 'ghost-skill';
        const personalSkill = 'balatro';
        plantSkillDirectory(sandbox.skillsDirectory, retiredManifestSkill, true);
        plantSkillDirectory(sandbox.skillsDirectory, personalSkill, false);
        writeFileSync(
            sandbox.manifestPath,
            JSON.stringify({
                package: 'claude-dev-env',
                version: '0.0.0',
                installedAt: new Date().toISOString(),
                files: [],
                skills: [SHIPPED_SKILL_DIRECTORY, retiredManifestSkill],
            }, null, 2) + '\n',
        );

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            existsSync(join(sandbox.skillsDirectory, retiredManifestSkill)),
            false,
            'a skill the prior manifest recorded but the package no longer ships is pruned',
        );
        assert.equal(
            existsSync(join(sandbox.skillsDirectory, personalSkill)),
            true,
            'a personal directory in neither the manifest nor the ever-shipped set survives',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped --only install leaves retired skills in place because prune runs on full installs only', () => {
    const sandbox = createSandbox();
    try {
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, retiredSkill, true);
        }

        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                true,
                `retired skill ${retiredSkill} should survive a scoped install`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall keeps pr-fix-protocol because the package ships it again', () => {
    const sandbox = createSandbox();
    try {
        plantSkillDirectory(sandbox.skillsDirectory, 'pr-fix-protocol', true);
        writeFileSync(join(sandbox.skillsDirectory, 'pr-fix-protocol', 'SKILL.md'), 'stale seeded copy\n');

        runInstaller(sandbox.homeDirectory, []);

        const restoredSkillPath = join(sandbox.skillsDirectory, 'pr-fix-protocol', 'SKILL.md');
        assert.equal(existsSync(restoredSkillPath), true, 'pr-fix-protocol survives and is reinstalled');
        assert.notEqual(
            readFileSync(restoredSkillPath, 'utf8'),
            'stale seeded copy\n',
            'the shipped pr-fix-protocol overwrites the stale seeded copy',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});
