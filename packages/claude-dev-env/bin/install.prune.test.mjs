import { test, after } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import {
    mkdtempSync,
    mkdirSync,
    writeFileSync,
    existsSync,
    readFileSync,
    readdirSync,
    rmSync,
    cpSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);
const EXCLUDED_PACKAGE_COPY_DIRECTORY = 'node_modules';

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
const PRUNED_BACKUP_DIRECTORY_NAME = '.claude-dev-env-pruned';
const SKIP_PRUNE_NOTICE_MARKER = 'Skipping retired-skill prune';
const DEPENDENCY_STUB_PACKAGE_SEGMENTS = ['@jl-cmd', 'prompt-generator'];

/**
 * Create a stub node_modules tree the installer can resolve the declared
 * dependency package from, and return its root for the child's NODE_PATH.
 *
 * The installer resolves `@jl-cmd/prompt-generator/package.json`; a lone
 * package.json at that path is enough for `createRequire.resolve` to succeed.
 * The stub makes the dependency resolvable inside the sandbox so a full install
 * exercises the real prune path. It does not prove the real private package
 * resolves in a real install — CI cannot host that package — only that the
 * resolved-dependency branch prunes as designed.
 *
 * @param {string} homeDirectory The sandbox home the stub is nested under.
 * @returns {string} The stub modules root to place on the child's NODE_PATH.
 */
let isolatedInstallerPath = null;
let isolatedPackageCopyRoot = null;

/**
 * Copy the package into a temp directory without node_modules and return the
 * copy's installer path.
 *
 * The installer resolves its declared dependencies with Node's regular
 * node_modules walk starting at its own file, so the real installer under the
 * repo always finds `@jl-cmd/prompt-generator` once `npm install` has run —
 * removing NODE_PATH from the child cannot make the dependency unresolvable
 * there. Running the copy makes resolution genuinely fail through the
 * installer's own catch path: no node_modules sits in the copy's ancestry and
 * the child gets no NODE_PATH. The copy is created once and shared by every
 * unresolved-dependency install; installs write only into their sandbox HOME.
 *
 * @returns {string} The path to `bin/install.mjs` inside the package copy.
 */
function ensureIsolatedInstallerPath() {
    if (isolatedInstallerPath !== null) return isolatedInstallerPath;
    isolatedPackageCopyRoot = mkdtempSync(join(tmpdir(), 'cdev-prune-package-'));
    cpSync(PACKAGE_DIRECTORY, isolatedPackageCopyRoot, {
        recursive: true,
        filter: sourcePath => basename(sourcePath) !== EXCLUDED_PACKAGE_COPY_DIRECTORY,
    });
    isolatedInstallerPath = join(isolatedPackageCopyRoot, 'bin', 'install.mjs');
    return isolatedInstallerPath;
}

after(() => {
    if (isolatedPackageCopyRoot !== null) {
        rmSync(isolatedPackageCopyRoot, { recursive: true, force: true });
    }
});

function ensureDependencyStub(homeDirectory) {
    const stubModulesRoot = join(homeDirectory, 'dependency-stub-modules');
    const stubPackageDirectory = join(stubModulesRoot, ...DEPENDENCY_STUB_PACKAGE_SEGMENTS);
    mkdirSync(stubPackageDirectory, { recursive: true });
    writeFileSync(
        join(stubPackageDirectory, 'package.json'),
        JSON.stringify({
            name: DEPENDENCY_STUB_PACKAGE_SEGMENTS.join('/'),
            version: '1.0.0',
            description: 'sandbox dependency stub',
        }) + '\n',
    );
    return stubModulesRoot;
}

/**
 * Report whether a retired skill directory landed under the prune backup root.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @param {string} skillName The retired skill directory name to look for.
 * @returns {boolean} True when a timestamped backup holds the skill directory.
 */
function prunedBackupContains(claudeDirectory, skillName) {
    const backupRoot = join(claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME);
    if (!existsSync(backupRoot)) return false;
    return readdirSync(backupRoot, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .some(timestampDir => existsSync(join(backupRoot, timestampDir.name, skillName)));
}

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
 * Run the real installer against the sandbox home and return its stdout.
 *
 * The declared dependency package is resolvable by default: the child's
 * NODE_PATH points at a sandbox stub so `createRequire.resolve` finds it and the
 * full-install prune runs. Passing ``{ dependencyResolvable: false }`` runs the
 * installer from an isolated package copy with no node_modules in its ancestry
 * and no NODE_PATH, so the dependency fails to resolve and the installer skips
 * the prune.
 *
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @param {string[]} extraArguments Installer arguments (for example ``['--only', 'core']``).
 * @param {{dependencyResolvable?: boolean}} options Whether the dependency resolves.
 * @returns {string} The installer's stdout.
 */
function runInstaller(homeDirectory, extraArguments, options = {}) {
    const dependencyResolvable = options.dependencyResolvable !== false;
    const childEnvironment = {
        ...process.env,
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
    };
    let installerPath;
    if (dependencyResolvable) {
        childEnvironment.NODE_PATH = ensureDependencyStub(homeDirectory);
        installerPath = INSTALLER_PATH;
    } else {
        delete childEnvironment.NODE_PATH;
        installerPath = ensureIsolatedInstallerPath();
    }
    return execFileSync('node', [installerPath, ...extraArguments], {
        cwd: dirname(installerPath),
        encoding: 'utf8',
        env: childEnvironment,
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

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the resolvable-dependency install runs the prune rather than skipping it',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned`,
            );
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, retiredSkill),
                true,
                `retired skill ${retiredSkill} should be moved to the prune backup`,
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

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the resolvable-dependency install runs the prune rather than skipping it',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned via the ever-shipped fallback`,
            );
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, retiredSkill),
                true,
                `retired skill ${retiredSkill} should be moved to the prune backup`,
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

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the resolvable-dependency install runs the prune rather than skipping it',
        );
        assert.equal(
            existsSync(join(sandbox.skillsDirectory, retiredManifestSkill)),
            false,
            'a skill the prior manifest recorded but the package no longer ships is pruned',
        );
        assert.equal(
            prunedBackupContains(sandbox.claudeDirectory, retiredManifestSkill),
            true,
            'the manifest-recorded retired skill is moved to the prune backup',
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
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, retiredSkill),
                false,
                `retired skill ${retiredSkill} should not be moved to backup by a scoped install`,
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

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the resolvable-dependency install runs the prune rather than skipping it',
        );
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

test('a full reinstall with an unresolved dependency skips the prune and leaves retired skills untouched', () => {
    const sandbox = createSandbox();
    try {
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, retiredSkill, true);
        }

        const installerOutput = runInstaller(sandbox.homeDirectory, [], { dependencyResolvable: false });

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            true,
            'the installer logs a notice that it is skipping the prune',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                true,
                `retired skill ${retiredSkill} should survive when a dependency is unresolved`,
            );
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, retiredSkill),
                false,
                `retired skill ${retiredSkill} should not be moved to backup when the prune is skipped`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('the prune skip is scoped: once the dependency resolves a later full install prunes normally', () => {
    const sandbox = createSandbox();
    try {
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            plantSkillDirectory(sandbox.skillsDirectory, retiredSkill, true);
        }

        const skippedOutput = runInstaller(sandbox.homeDirectory, [], { dependencyResolvable: false });
        assert.equal(
            skippedOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            true,
            'the unresolved-dependency install skips the prune',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                true,
                `retired skill ${retiredSkill} should still be present after the skipped prune`,
            );
        }

        const resolvedOutput = runInstaller(sandbox.homeDirectory, [], { dependencyResolvable: true });
        assert.equal(
            resolvedOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the resolved-dependency install runs the prune, proving the skip is not a permanent disable',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned once the dependency resolves`,
            );
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, retiredSkill),
                true,
                `retired skill ${retiredSkill} should be moved to the prune backup on the resolved install`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});
