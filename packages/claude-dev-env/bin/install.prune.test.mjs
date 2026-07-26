import { test, after } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync, spawnSync } from 'node:child_process';
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
const PERSONAL_SKILL_DIRECTORIES = ['credit-card-picker', 'midjourney-sref'];
const SHIPPED_SKILL_DIRECTORY = 'autoconverge';
const PRUNED_BACKUP_DIRECTORY_NAME = '.claude-dev-env-pruned';
const SKIP_PRUNE_NOTICE_MARKER = 'Skipping retired-skill and stale-file prune';
const STALE_SKILL_FILE_RELATIVE_SEGMENTS = ['scripts', 'retired_module.py'];
const RUNTIME_ARTIFACT_RELATIVE_SEGMENTS = ['scripts', '__pycache__', 'helper.cpython-312.pyc'];
const SCOPED_GROUP_SKILL_DIRECTORY = 'orchestrator';
const CORE_REVIEW_GUIDE_SKILL_DIRECTORIES = [
    'small-cl',
];
const PRIOR_RUN_BACKUP_DIRECTORY_NAMES = [
    '2020-01-01T00-00-00-000Z',
    '2021-06-15T12-30-45-123Z',
    '2022-11-30T23-59-59-999Z',
];
const SKILLS_DIRECTORY_NAME = 'skills';
const HOOKS_DIRECTORY_NAME = 'hooks';
const SETTINGS_FILE_NAME = 'settings.json';
const MANIFEST_FILE_NAME = '.claude-dev-env-manifest.json';
const CLAUDE_HUB_FILE_NAME = 'CLAUDE.md';
const RULES_DIRECTORY_NAME = 'rules';
const SHARED_DIRECTORY_NAME = '_shared';
const STALE_RULE_FILE_NAME = 'retired-rule.md';
const STALE_SHARED_FILE_SEGMENTS = ['pr-loop', 'retired_shared.md'];
const STALE_SHARED_SKILL_FILE_SEGMENTS = [SHARED_DIRECTORY_NAME, 'retired_skill_shared.md'];
const RETIRED_HOOK_RELATIVE_SEGMENTS = ['blocking', 'retired_gate.py'];
const USER_HOOK_COMMAND = 'python3 my_own_gate.py --user-authored';
const RETIRED_HOOK_EVENT_TYPE = 'PreToolUse';
const DROPPED_HOOK_EVENT_TYPE = 'PreCompact';
const RETIRED_HOOK_MATCHER = 'Write|Edit|MultiEdit';
const UNMANAGED_SIBLING_DIRECTORY = 'my-notes';
const NESTED_SKILL_DIRECTORY = 'foo';
const NESTED_SKILL_FILE_SEGMENTS = [NESTED_SKILL_DIRECTORY, 'scripts', 'a.py'];
const MYPY_INI_FILE_NAME = '.mypy.ini';
const SKIPPED_RECORD_SUMMARY_MARKER = 'manifest record(s) skipped';
const DEPENDENCY_STUB_PACKAGE_SEGMENTS = ['@jl-cmd', 'prompt-generator'];
const PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST = 'probe-skill-without-manifest';
const PROBE_SKILL_FILE_SEGMENTS = ['scripts', 'probe_helper.py'];
const PYTHON_BYTECODE_CACHE_DIRECTORY_NAME = '__pycache__';
const PYTHON_BYTECODE_FILE_NAME = 'probe_helper.cpython-312.pyc';

let isolatedInstallerPath = null;
let isolatedPackageCopyRoot = null;

function ensureIsolatedInstallerPath() {
    if (isolatedInstallerPath !== null) return isolatedInstallerPath;
    isolatedPackageCopyRoot = copyPackageWithoutModules();
    isolatedInstallerPath = installerPathUnder(isolatedPackageCopyRoot);
    return isolatedInstallerPath;
}

function copyPackageWithoutModules() {
    const packageCopyRoot = mkdtempSync(join(tmpdir(), 'cdev-prune-package-'));
    cpSync(PACKAGE_DIRECTORY, packageCopyRoot, {
        recursive: true,
        filter: sourcePath => basename(sourcePath) !== EXCLUDED_PACKAGE_COPY_DIRECTORY,
    });
    return packageCopyRoot;
}

function installerPathUnder(packageSourceRoot) {
    if (!packageSourceRoot) return INSTALLER_PATH;
    return join(packageSourceRoot, 'bin', 'install.mjs');
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
 * Report whether a path under one managed root landed in a run backup.
 *
 * Each run backup mirrors ~/.claude, so a moved skill directory and a moved skill
 * file both sit under `<timestamp>/skills/`, and content from another managed root
 * sits under that root's own name.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @param {string} rootRelativePath The path to look for, relative to ~/.claude.
 * @returns {boolean} True when a timestamped backup holds the path.
 */
function prunedBackupContains(claudeDirectory, rootRelativePath) {
    const backupRoot = join(claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME);
    if (!existsSync(backupRoot)) return false;
    return readdirSync(backupRoot, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .some(timestampDir => existsSync(join(backupRoot, timestampDir.name, rootRelativePath)));
}

/**
 * Report whether a skill path landed in a run backup under the skills root.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @param {string} skillsRelativePath The path to look for, relative to ~/.claude/skills.
 * @returns {boolean} True when a timestamped backup holds the path.
 */
function prunedSkillBackupContains(claudeDirectory, skillsRelativePath) {
    return prunedBackupContains(claudeDirectory, join(SKILLS_DIRECTORY_NAME, skillsRelativePath));
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
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @param {string[]} extraArguments Installer arguments (for example ``['--only', 'core']``).
 * @returns {string} The installer's stdout.
 */
function runInstaller(homeDirectory, extraArguments, options = {}) {
    const { installerPath, childEnvironment } = resolveInstallerInvocation(homeDirectory, options);
    return execFileSync('node', [installerPath, ...extraArguments], {
        cwd: dirname(installerPath),
        encoding: 'utf8',
        env: childEnvironment,
    });
}

/**
 * Build the installer path and child environment one sandbox run uses.
 *
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @returns {{installerPath: string, childEnvironment: object}} The invocation inputs.
 */
function resolveInstallerInvocation(homeDirectory, options = {}) {
    const dependencyResolvable = options.dependencyResolvable !== false;
    const childEnvironment = {
        ...process.env,
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        CODEX_HOME: join(homeDirectory, '.codex'),
    };
    if (dependencyResolvable) {
        childEnvironment.NODE_PATH = ensureDependencyStub(homeDirectory);
        return { installerPath: installerPathUnder(options.packageSourceRoot), childEnvironment };
    }
    delete childEnvironment.NODE_PATH;
    return { installerPath: ensureIsolatedInstallerPath(), childEnvironment };
}

/**
 * Run the real installer against the sandbox home and return both output streams.
 *
 * A warning the installer prints reaches stderr, so a test asserting that a run
 * warns about nothing reads the two streams together.
 *
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @param {string[]} extraArguments Installer arguments (for example ``['--uninstall']``).
 * @returns {string} The child's stdout and stderr, joined.
 */
function runInstallerReadingBothStreams(homeDirectory, extraArguments) {
    const { installerPath, childEnvironment } = resolveInstallerInvocation(homeDirectory, {});
    const completedRun = spawnSync('node', [installerPath, ...extraArguments], {
        cwd: dirname(installerPath),
        encoding: 'utf8',
        env: childEnvironment,
    });
    assert.equal(completedRun.status, 0, `the installer run exited with ${completedRun.status}`);
    return `${completedRun.stdout}${completedRun.stderr}`;
}

function readManifest(manifestPath) {
    return JSON.parse(readFileSync(manifestPath, 'utf8'));
}

/**
 * Write a file, creating the directories leading to it.
 *
 * @param {string} filePath The absolute file path to write.
 * @param {string} contents The file contents.
 */
function writeFileWithParents(filePath, contents) {
    mkdirSync(dirname(filePath), { recursive: true });
    writeFileSync(filePath, contents);
}

/**
 * Seed a shipped skill with a stale file the prior manifest records and a runtime
 * artifact it does not, so one run exercises both sides of the manifest diff.
 *
 * @param {{skillsDirectory: string, manifestPath: string}} sandbox The sandbox paths.
 * @returns {{staleFilePath: string, runtimeArtifactPath: string}} The seeded paths.
 */
function seedStaleSkillFile(sandbox) {
    const staleFilePath = join(
        sandbox.skillsDirectory, SHIPPED_SKILL_DIRECTORY, ...STALE_SKILL_FILE_RELATIVE_SEGMENTS,
    );
    const runtimeArtifactPath = join(
        sandbox.skillsDirectory, SHIPPED_SKILL_DIRECTORY, ...RUNTIME_ARTIFACT_RELATIVE_SEGMENTS,
    );
    writeFileWithParents(staleFilePath, 'a module an earlier revision shipped\n');
    writeFileWithParents(runtimeArtifactPath, 'compiled bytecode no install ever wrote\n');
    const manifest = readManifest(sandbox.manifestPath);
    manifest.files.push(staleFilePath);
    writeFileSync(sandbox.manifestPath, JSON.stringify(manifest, null, 2) + '\n');
    return { staleFilePath, runtimeArtifactPath };
}

/**
 * Plant one run backup directory per name an earlier install would have written,
 * each holding a marker file.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @returns {string} The pruned-backup directory the planted runs sit under.
 */
function plantPriorRunBackups(claudeDirectory) {
    const prunedBackupDirectory = join(claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME);
    for (const runDirectoryName of PRIOR_RUN_BACKUP_DIRECTORY_NAMES) {
        const runDirectory = join(prunedBackupDirectory, runDirectoryName);
        mkdirSync(runDirectory, { recursive: true });
        writeFileSync(join(runDirectory, 'recovered.md'), `content ${runDirectoryName} holds\n`);
    }
    return prunedBackupDirectory;
}

/**
 * List the run backup directory names sitting under the pruned-backup directory.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @returns {string[]} The directory names, in readdir order.
 */
function listRunBackupDirectoryNames(claudeDirectory) {
    const prunedBackupDirectory = join(claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME);
    if (!existsSync(prunedBackupDirectory)) return [];
    return readdirSync(prunedBackupDirectory, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .map(entry => entry.name);
}

/**
 * Append absolute paths to the sandbox manifest's file list.
 *
 * @param {string} manifestPath The sandbox manifest path.
 * @param {string[]} recordedPaths The absolute paths to record.
 */
function appendManifestFiles(manifestPath, recordedPaths) {
    const manifest = readManifest(manifestPath);
    manifest.files.push(...recordedPaths);
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
}

/**
 * Build an absolute path under this platform's system root that no test creates.
 *
 * The path names a real, protected location so the containment guard is
 * exercised against the shape a malformed record takes on this host. Nothing
 * writes it and nothing removes it: the guard skips the record before the
 * uninstall reaches any filesystem call.
 *
 * @returns {string} The absolute system-root path to record.
 */
function systemRootPathNeverWritten() {
    const windowsSystemRoot = process.env.SystemRoot || 'C:\\Windows';
    return process.platform === 'win32'
        ? join(windowsSystemRoot, 'claude-dev-env-never-written.txt')
        : '/etc/claude-dev-env-never-written.txt';
}

test('a full reinstall moves a manifest-recorded skill file the package no longer ships and keeps runtime artifacts', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { staleFilePath, runtimeArtifactPath } = seedStaleSkillFile(sandbox);

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            existsSync(staleFilePath),
            false,
            'the file the prior manifest recorded and this run no longer writes leaves the skill',
        );
        assert.equal(
            prunedSkillBackupContains(
                sandbox.claudeDirectory,
                join(SHIPPED_SKILL_DIRECTORY, ...STALE_SKILL_FILE_RELATIVE_SEGMENTS),
            ),
            true,
            'the stale file lands under its mirrored relative path in the prune backup',
        );
        assert.equal(
            existsSync(runtimeArtifactPath),
            true,
            'a __pycache__ artifact no install ever wrote stays in place',
        );
        assert.match(
            installerOutput,
            /skills: \d+ files \(\d+ new, \d+ updated, 1 stale moved aside\)/,
            'the summary line reports the stale count',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a stale file whose move fails stays on the manifest record for the next run to retry', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { staleFilePath } = seedStaleSkillFile(sandbox);
        writeFileSync(
            join(sandbox.claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME),
            'a file standing where the backup root belongs\n',
        );

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(existsSync(staleFilePath), true, 'the failed move leaves the file in the skill');
        const recordedFiles = readManifest(sandbox.manifestPath).files;
        assert.equal(
            recordedFiles.filter(recordedPath => recordedPath === staleFilePath).length,
            1,
            'the fresh manifest carries the failed path exactly once',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped --only install leaves a manifest-recorded stale skill file in place', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { staleFilePath } = seedStaleSkillFile(sandbox);

        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        assert.equal(
            existsSync(staleFilePath),
            true,
            'the stale-file prune runs on full installs only',
        );
        assert.equal(
            prunedSkillBackupContains(
                sandbox.claudeDirectory,
                join(SHIPPED_SKILL_DIRECTORY, ...STALE_SKILL_FILE_RELATIVE_SEGMENTS),
            ),
            false,
            'a scoped install moves nothing to the prune backup',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped --only install keeps prior manifest file entries it did not itself write', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { staleFilePath } = seedStaleSkillFile(sandbox);
        const filesBeforeScopedInstall = readManifest(sandbox.manifestPath).files;

        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        const recordedFiles = new Set(readManifest(sandbox.manifestPath).files);
        assert.equal(
            recordedFiles.has(staleFilePath),
            true,
            'the entry a later full install needs to spot the stale file stays on the record',
        );
        const droppedEntries = filesBeforeScopedInstall
            .filter(priorPath => !recordedFiles.has(priorPath));
        assert.deepEqual(droppedEntries, [], 'a scoped install drops no prior entry');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full install after a scoped one still moves the stale file the scoped run carried forward', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { staleFilePath } = seedStaleSkillFile(sandbox);
        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(existsSync(staleFilePath), false, 'the carried-forward entry reaches the next full diff');
        assert.equal(
            prunedSkillBackupContains(
                sandbox.claudeDirectory,
                join(SHIPPED_SKILL_DIRECTORY, ...STALE_SKILL_FILE_RELATIVE_SEGMENTS),
            ),
            true,
            'the stale file lands in the prune backup',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('one install run collects retired skill directories and stale files under a single timestamped backup root', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const retiredSkillName = 'ghost-skill';
        plantSkillDirectory(sandbox.skillsDirectory, retiredSkillName, true);
        const { staleFilePath } = seedStaleSkillFile(sandbox);
        const manifest = readManifest(sandbox.manifestPath);
        manifest.skills.push(retiredSkillName);
        writeFileSync(sandbox.manifestPath, JSON.stringify(manifest, null, 2) + '\n');

        runInstaller(sandbox.homeDirectory, []);

        const backupRoot = join(sandbox.claudeDirectory, PRUNED_BACKUP_DIRECTORY_NAME);
        const allTimestampDirectories = readdirSync(backupRoot, { withFileTypes: true })
            .filter(entry => entry.isDirectory())
            .map(entry => entry.name);
        assert.equal(allTimestampDirectories.length, 1, 'one run leaves one recovery point');
        const runBackupRoot = join(backupRoot, allTimestampDirectories[0]);
        assert.equal(
            existsSync(join(runBackupRoot, SKILLS_DIRECTORY_NAME, retiredSkillName)),
            true,
            'the retired skill directory sits under the shared root, mirroring ~/.claude/skills',
        );
        assert.equal(
            existsSync(join(
                runBackupRoot, SKILLS_DIRECTORY_NAME, SHIPPED_SKILL_DIRECTORY,
                ...STALE_SKILL_FILE_RELATIVE_SEGMENTS,
            )),
            true,
            'the stale file mirrors its own path under the same shared root',
        );
        assert.equal(existsSync(staleFilePath), false, 'the stale file left the installed skill');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

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
                prunedSkillBackupContains(sandbox.claudeDirectory, retiredSkill),
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
                prunedSkillBackupContains(sandbox.claudeDirectory, retiredSkill),
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
        const personalSkill = 'credit-card-picker';
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
            prunedSkillBackupContains(sandbox.claudeDirectory, retiredManifestSkill),
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
                prunedSkillBackupContains(sandbox.claudeDirectory, retiredSkill),
                false,
                `retired skill ${retiredSkill} should not be moved to backup by a scoped install`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall keeps autoconverge because the package ships it again', () => {
    const sandbox = createSandbox();
    try {
        plantSkillDirectory(sandbox.skillsDirectory, 'autoconverge', true);
        writeFileSync(join(sandbox.skillsDirectory, 'autoconverge', 'SKILL.md'), 'stale seeded copy\n');

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the full install runs the prune rather than skipping it',
        );
        const restoredSkillPath = join(sandbox.skillsDirectory, 'autoconverge', 'SKILL.md');
        assert.equal(existsSync(restoredSkillPath), true, 'autoconverge survives and is reinstalled');
        assert.notEqual(
            readFileSync(restoredSkillPath, 'utf8'),
            'stale seeded copy\n',
            'the shipped autoconverge overwrites the stale seeded copy',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped --only install records the skill names it installed', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        const recordedSkills = new Set(readManifest(sandbox.manifestPath).skills);
        assert.equal(
            existsSync(join(sandbox.skillsDirectory, SCOPED_GROUP_SKILL_DIRECTORY)),
            true,
            'the scoped install writes the group skill',
        );
        assert.equal(
            recordedSkills.has(SCOPED_GROUP_SKILL_DIRECTORY),
            true,
            'the skill the scoped run installed reaches the record uninstall reads',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped core install ships the canonical review guide skills', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        const missingGuideSkillNames = CORE_REVIEW_GUIDE_SKILL_DIRECTORIES.filter(
            eachSkillName => !existsSync(join(sandbox.skillsDirectory, eachSkillName, 'SKILL.md')),
        );
        assert.deepEqual(missingGuideSkillNames, []);

        const recordedSkillNames = new Set(readManifest(sandbox.manifestPath).skills);
        for (const eachSkillName of CORE_REVIEW_GUIDE_SKILL_DIRECTORIES) {
            assert.equal(recordedSkillNames.has(eachSkillName), true);
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a scoped core install leaves retired skills in place; a later full install prunes them', () => {
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

        const fullOutput = runInstaller(sandbox.homeDirectory, []);
        assert.equal(
            fullOutput.includes(SKIP_PRUNE_NOTICE_MARKER),
            false,
            'the full install runs the prune',
        );
        for (const retiredSkill of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(
                existsSync(join(sandbox.skillsDirectory, retiredSkill)),
                false,
                `retired skill ${retiredSkill} should be pruned on the full install`,
            );
            assert.equal(
                prunedSkillBackupContains(sandbox.claudeDirectory, retiredSkill),
                true,
                `retired skill ${retiredSkill} should be moved to the prune backup`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an install that prunes leaves its own run backup as the only one under the pruned-backup directory', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        seedStaleSkillFile(sandbox);
        plantPriorRunBackups(sandbox.claudeDirectory);

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        const remainingBackupNames = listRunBackupDirectoryNames(sandbox.claudeDirectory);
        assert.equal(remainingBackupNames.length, 1, 'the newest run backup is the one that stays');
        assert.equal(
            PRIOR_RUN_BACKUP_DIRECTORY_NAMES.includes(remainingBackupNames[0]),
            false,
            'the survivor is the run this install wrote',
        );
        assert.match(
            installerOutput,
            /Prune backups: 3 older run backup\(s\) removed/,
            'the install reports how many older backups it retired',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an install whose only move is a retired skill directory still retires the older run backups', () => {
    const sandbox = createSandbox();
    const retiredSkillName = RETIRED_SKILL_DIRECTORIES[0];
    try {
        runInstaller(sandbox.homeDirectory, []);
        plantSkillDirectory(sandbox.skillsDirectory, retiredSkillName, true);
        plantPriorRunBackups(sandbox.claudeDirectory);

        runInstaller(sandbox.homeDirectory, []);

        const remainingBackupNames = listRunBackupDirectoryNames(sandbox.claudeDirectory);
        assert.equal(remainingBackupNames.length, 1, 'the retired-skill move is enough to retire the rest');
        assert.equal(
            PRIOR_RUN_BACKUP_DIRECTORY_NAMES.includes(remainingBackupNames[0]),
            false,
            'the survivor is the run this install wrote',
        );
        assert.equal(
            prunedSkillBackupContains(sandbox.claudeDirectory, retiredSkillName),
            true,
            'the surviving backup holds the retired skill directory the run moved',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an install that prunes nothing leaves every existing run backup in place', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        plantPriorRunBackups(sandbox.claudeDirectory);

        runInstaller(sandbox.homeDirectory, []);

        assert.deepEqual(
            listRunBackupDirectoryNames(sandbox.claudeDirectory).sort(),
            [...PRIOR_RUN_BACKUP_DIRECTORY_NAMES].sort(),
            'a run with no backup root of its own keeps every recovery point the user has',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

/**
 * Seed a file under one managed root that a prior install recorded and the
 * package no longer ships.
 *
 * @param {{claudeDirectory: string, manifestPath: string}} sandbox The sandbox paths.
 * @param {string[]} homeRelativeSegments The path segments under ~/.claude.
 * @returns {string} The seeded absolute path.
 */
function seedStaleFileUnderManagedRoot(sandbox, homeRelativeSegments) {
    const stalePath = join(sandbox.claudeDirectory, ...homeRelativeSegments);
    writeFileWithParents(stalePath, `content ${homeRelativeSegments.join('/')} once held\n`);
    appendManifestFiles(sandbox.manifestPath, [stalePath]);
    return stalePath;
}

/**
 * Read the sandbox settings.json.
 *
 * @param {string} claudeDirectory The sandbox ~/.claude directory.
 * @returns {object} The parsed settings object.
 */
function readSettings(claudeDirectory) {
    return JSON.parse(readFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), 'utf8'));
}

/**
 * List every hook command the settings file holds, across all event types.
 *
 * @param {object} settings The parsed settings object.
 * @returns {string[]} Each hook command in the file.
 */
function allHookCommands(settings) {
    return Object.values(settings.hooks || {})
        .flat()
        .flatMap(group => group.hooks || [])
        .map(hook => hook.command);
}

/**
 * Plant a hook script a prior install recorded and the settings entries that run
 * it: one in a live matcher group beside a user-authored entry, and one under an
 * event type the current hooks.json leaves out.
 *
 * @param {{claudeDirectory: string, manifestPath: string}} sandbox The sandbox paths.
 * @returns {{retiredHookPath: string, retiredHookCommand: string, lookalikeHookCommand: string}}
 *   The planted script, its command, and a user command whose path is that tail plus a suffix.
 */
function seedRetiredManagedHook(sandbox) {
    const retiredHookPath = join(
        sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, ...RETIRED_HOOK_RELATIVE_SEGMENTS,
    );
    writeFileWithParents(retiredHookPath, 'a gate an earlier revision shipped\n');
    appendManifestFiles(sandbox.manifestPath, [retiredHookPath]);
    const retiredHookCommand = `python3 "${retiredHookPath.replace(/\\/g, '/')}"`;
    const lookalikeHookCommand = `python3 "${retiredHookPath.replace(/\\/g, '/')}.bak"`;
    const settings = readSettings(sandbox.claudeDirectory);
    const liveGroup = settings.hooks[RETIRED_HOOK_EVENT_TYPE]
        .find(group => group.matcher === RETIRED_HOOK_MATCHER);
    liveGroup.hooks.push({ type: 'command', command: retiredHookCommand });
    liveGroup.hooks.push({ type: 'command', command: USER_HOOK_COMMAND });
    liveGroup.hooks.push({ type: 'command', command: lookalikeHookCommand });
    settings.hooks[DROPPED_HOOK_EVENT_TYPE] = [
        { matcher: '*', hooks: [{ type: 'command', command: retiredHookCommand }] },
    ];
    writeFileSync(
        join(sandbox.claudeDirectory, SETTINGS_FILE_NAME),
        JSON.stringify(settings, null, 4) + '\n',
    );
    return { retiredHookPath, retiredHookCommand, lookalikeHookCommand };
}

test('a full reinstall moves a stale file out of every managed root into that root\'s backup folder', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const staleRulePath = seedStaleFileUnderManagedRoot(
            sandbox, [RULES_DIRECTORY_NAME, STALE_RULE_FILE_NAME],
        );
        const staleSharedPath = seedStaleFileUnderManagedRoot(
            sandbox, [SHARED_DIRECTORY_NAME, ...STALE_SHARED_FILE_SEGMENTS],
        );
        const staleSkillSharedPath = seedStaleFileUnderManagedRoot(
            sandbox, [SKILLS_DIRECTORY_NAME, ...STALE_SHARED_SKILL_FILE_SEGMENTS],
        );

        runInstaller(sandbox.homeDirectory, []);

        for (const movedPath of [staleRulePath, staleSharedPath, staleSkillSharedPath]) {
            assert.equal(existsSync(movedPath), false, `${movedPath} leaves its managed root`);
        }
        assert.equal(
            prunedBackupContains(
                sandbox.claudeDirectory, join(RULES_DIRECTORY_NAME, STALE_RULE_FILE_NAME),
            ),
            true,
            'the rules file mirrors its path under the rules folder of the backup',
        );
        assert.equal(
            prunedBackupContains(
                sandbox.claudeDirectory, join(SHARED_DIRECTORY_NAME, ...STALE_SHARED_FILE_SEGMENTS),
            ),
            true,
            'the ~/.claude/_shared file mirrors its path under the _shared folder of the backup',
        );
        assert.equal(
            prunedSkillBackupContains(
                sandbox.claudeDirectory, join(...STALE_SHARED_SKILL_FILE_SEGMENTS),
            ),
            true,
            'the ~/.claude/skills/_shared file lands under the skills folder, so neither root prunes the other\'s content',
        );
        assert.equal(
            prunedBackupContains(
                sandbox.claudeDirectory, join(SHARED_DIRECTORY_NAME, ...STALE_SHARED_SKILL_FILE_SEGMENTS),
            ),
            false,
            'the skills _shared file reaches the _shared root backup through no second move',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall leaves a manifest-recorded path under no managed root in place', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const topLevelPaths = [
            join(sandbox.claudeDirectory, CLAUDE_HUB_FILE_NAME),
            join(sandbox.claudeDirectory, SETTINGS_FILE_NAME),
            join(sandbox.claudeDirectory, MANIFEST_FILE_NAME),
        ];
        appendManifestFiles(sandbox.manifestPath, topLevelPaths);

        runInstaller(sandbox.homeDirectory, []);

        for (const topLevelPath of topLevelPaths) {
            assert.equal(existsSync(topLevelPath), true, `${topLevelPath} stays at the top level`);
            assert.equal(
                prunedBackupContains(sandbox.claudeDirectory, basename(topLevelPath)),
                false,
                `${topLevelPath} reaches no run backup`,
            );
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall drops a retired hook script and its settings entry in one run', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const {
            retiredHookPath, retiredHookCommand, lookalikeHookCommand,
        } = seedRetiredManagedHook(sandbox);

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(existsSync(retiredHookPath), false, 'the retired hook script leaves ~/.claude/hooks');
        assert.equal(
            prunedBackupContains(
                sandbox.claudeDirectory, join(HOOKS_DIRECTORY_NAME, ...RETIRED_HOOK_RELATIVE_SEGMENTS),
            ),
            true,
            'the retired hook script lands under the hooks folder of the backup',
        );
        const settingsCommands = allHookCommands(readSettings(sandbox.claudeDirectory));
        assert.equal(
            settingsCommands.includes(retiredHookCommand),
            false,
            'no settings entry is left pointing at the script the run removed',
        );
        assert.equal(
            settingsCommands.includes(USER_HOOK_COMMAND),
            true,
            'the user-authored entry sharing the matcher group survives untouched',
        );
        assert.equal(
            settingsCommands.includes(lookalikeHookCommand),
            true,
            'a user command whose path is the retired tail plus a suffix names another file and stays',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall removes a retired hook entry under an event type the current config leaves out', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const { retiredHookCommand } = seedRetiredManagedHook(sandbox);

        runInstaller(sandbox.homeDirectory, []);

        const settings = readSettings(sandbox.claudeDirectory);
        assert.equal(
            allHookCommands(settings).includes(retiredHookCommand),
            false,
            'the entry under the dropped event type goes with the script',
        );
        assert.equal(
            Object.hasOwn(settings.hooks, DROPPED_HOOK_EVENT_TYPE),
            false,
            'the event type left with no entries is dropped',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an uninstall skips a manifest record outside ~/.claude and still removes the managed records', () => {
    const sandbox = createSandbox();
    const outsideDirectory = mkdtempSync(join(tmpdir(), 'cdev-outside-home-'));
    try {
        runInstaller(sandbox.homeDirectory, []);
        const outsideFilePath = join(outsideDirectory, 'user-file.txt');
        writeFileSync(outsideFilePath, 'a file no install ever wrote\n');
        const managedFilePath = join(sandbox.skillsDirectory, SHIPPED_SKILL_DIRECTORY, 'SKILL.md');
        assert.equal(existsSync(managedFilePath), true, 'the install wrote the managed file the purge targets');
        appendManifestFiles(
            sandbox.manifestPath,
            [outsideFilePath, systemRootPathNeverWritten()],
        );

        runInstaller(sandbox.homeDirectory, ['--uninstall']);

        assert.equal(existsSync(outsideFilePath), true, 'a record outside ~/.claude leaves its file untouched');
        assert.equal(existsSync(managedFilePath), false, 'every legitimate record is still removed');
        assert.equal(existsSync(sandbox.manifestPath), false, 'the uninstall runs to the end and clears the manifest');
    } finally {
        rmSync(outsideDirectory, { recursive: true, force: true });
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an uninstall removes the home-directory .mypy.ini the install wrote and skips only a genuinely foreign record', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const mypyIniPath = join(sandbox.homeDirectory, MYPY_INI_FILE_NAME);
        assert.equal(
            existsSync(mypyIniPath),
            true,
            'the install writes the mypy configuration in the home directory and records it',
        );
        const foreignRecordPath = systemRootPathNeverWritten();
        appendManifestFiles(sandbox.manifestPath, [foreignRecordPath]);

        const installerOutput = runInstallerReadingBothStreams(
            sandbox.homeDirectory, ['--uninstall'],
        );

        assert.equal(
            existsSync(mypyIniPath),
            false,
            'the uninstall removes the mypy configuration the install writes outside ~/.claude',
        );
        assert.equal(
            installerOutput.includes(`skipping ${mypyIniPath}`),
            false,
            'the containment guard raises no warning about a path the installer itself writes',
        );
        assert.match(
            installerOutput,
            /1 manifest record\(s\) skipped/,
            'the record naming a path no install wrote is the only one skipped',
        );
        assert.equal(existsSync(foreignRecordPath), false, 'the skipped record never existed on disk');
        assert.equal(
            existsSync(sandbox.manifestPath),
            false,
            'the uninstall runs to the end and clears the manifest',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a second install records the home-directory .mypy.ini it finds already configured so the uninstall still removes it', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const mypyIniPath = join(sandbox.homeDirectory, MYPY_INI_FILE_NAME);

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            readManifest(sandbox.manifestPath).files.includes(mypyIniPath),
            true,
            'the run that finds the file already configured records it on the fresh manifest',
        );

        const installerOutput = runInstallerReadingBothStreams(
            sandbox.homeDirectory, ['--uninstall'],
        );

        assert.equal(
            existsSync(mypyIniPath),
            false,
            'the uninstall reads the record and removes the mypy configuration',
        );
        assert.equal(
            installerOutput.includes(mypyIniPath),
            false,
            'the containment guard raises no warning naming the mypy configuration',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('an uninstall of a clean install skips no manifest record at all', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);

        const installerOutput = runInstallerReadingBothStreams(
            sandbox.homeDirectory, ['--uninstall'],
        );

        assert.equal(
            installerOutput.includes(SKIPPED_RECORD_SUMMARY_MARKER),
            false,
            'every record a plain install writes passes the containment guard',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

function plantSourceSkillDirectoryWithoutManifest(packageSourceRoot) {
    const skillsSourceDirectory = join(
        packageSourceRoot, '.agents', SKILLS_DIRECTORY_NAME,
    );
    const probeSourceDirectory = join(
        skillsSourceDirectory, PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST,
    );
    writeFileWithParents(
        join(probeSourceDirectory, ...PROBE_SKILL_FILE_SEGMENTS),
        'a helper the skill directory ships without a SKILL.md\n',
    );
    writeFileWithParents(
        join(skillsSourceDirectory, PYTHON_BYTECODE_CACHE_DIRECTORY_NAME, PYTHON_BYTECODE_FILE_NAME),
        'compiled bytecode a contributor test run left in the source\n',
    );
    return probeSourceDirectory;
}

test('a shipped skill directory without a SKILL.md reaches the manifest and is pruned once the package drops it', () => {
    const sandbox = createSandbox();
    const packageSourceRoot = copyPackageWithoutModules();
    try {
        const probeSourceDirectory = plantSourceSkillDirectoryWithoutManifest(packageSourceRoot);

        runInstaller(sandbox.homeDirectory, [], { packageSourceRoot });

        const installedProbeDirectory = join(
            sandbox.skillsDirectory, PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST,
        );
        assert.equal(existsSync(installedProbeDirectory), true);
        const manifestAfterShipping = readManifest(sandbox.manifestPath);
        assert.equal(
            manifestAfterShipping.skills.includes(PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST),
            true,
        );
        assert.equal(manifestAfterShipping.skills.includes(SHARED_DIRECTORY_NAME), false);
        assert.equal(
            manifestAfterShipping.skills.includes(PYTHON_BYTECODE_CACHE_DIRECTORY_NAME),
            false,
        );

        rmSync(probeSourceDirectory, { recursive: true, force: true });
        runInstaller(sandbox.homeDirectory, [], { packageSourceRoot });

        assert.equal(existsSync(installedProbeDirectory), false);
        assert.equal(
            prunedSkillBackupContains(
                sandbox.claudeDirectory, PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST,
            ),
            true,
        );
        assert.equal(
            readManifest(sandbox.manifestPath).skills
                .includes(PROBE_SKILL_DIRECTORY_WITHOUT_MANIFEST),
            false,
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
        rmSync(packageSourceRoot, { recursive: true, force: true });
    }
});

test('an uninstall removes the nested directories its records emptied and keeps unmanaged siblings', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const nestedFilePath = join(sandbox.skillsDirectory, ...NESTED_SKILL_FILE_SEGMENTS);
        writeFileWithParents(nestedFilePath, 'a module an earlier install wrote\n');
        appendManifestFiles(sandbox.manifestPath, [nestedFilePath]);
        const unmanagedDirectory = join(sandbox.claudeDirectory, UNMANAGED_SIBLING_DIRECTORY);
        mkdirSync(unmanagedDirectory, { recursive: true });
        writeFileSync(join(unmanagedDirectory, 'note.md'), 'a file the user authored\n');

        runInstaller(sandbox.homeDirectory, ['--uninstall']);

        assert.equal(
            existsSync(join(sandbox.skillsDirectory, NESTED_SKILL_DIRECTORY, 'scripts')),
            false,
            'the directory the removed file emptied is gone',
        );
        assert.equal(
            existsSync(join(sandbox.skillsDirectory, NESTED_SKILL_DIRECTORY)),
            false,
            'the walk climbs to the skill directory the nested removal emptied',
        );
        assert.equal(existsSync(sandbox.claudeDirectory), true, 'the managed home itself stays');
        assert.equal(existsSync(unmanagedDirectory), true, 'a directory the installer never wrote stays');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});
