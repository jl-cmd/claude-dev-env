import { test } from 'node:test';
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
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { detectPython } from './install.mjs';
const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const INSTALLER_PROCESS_TIMEOUT_MS = 60_000;
const EXCLUDED_PACKAGE_COPY_DIRECTORY = 'node_modules';

const RETIRED_SKILL_DIRECTORIES = [
    'findbugs',
    'fixbugs',
    'pr-scope-resolve',
    'post-audit-findings',
    'pr-consistency-audit',
    'bdd-protocol',
    'hitl',
    'autoconverge',
    'pr-cleanup',
    'pr-name-by-capability',
    'pr-plain-language-cleanup',
    'pr-refinement',
    'pr-shared-extraction',
    'pr-small-cl',
    'pr-title-description',
    'prototype',
    'rebase',
    'review-router',
    'review-tier',
    'run-claude-dev-env',
    'session-log',
    'session-tidy',
    'source-command-sr-loop',
    'update',
];
const PERSONAL_SKILL_DIRECTORIES = ['credit-card-picker', 'midjourney-sref'];
const SHIPPED_SKILL_DIRECTORY = 'e-code-review';
const PRUNED_BACKUP_DIRECTORY_NAME = '.claude-dev-env-pruned';
const SKIP_PRUNE_NOTICE_MARKER = 'Skipping retired-skill and stale-file prune';
const STALE_SKILL_FILE_RELATIVE_SEGMENTS = ['scripts', 'retired_module.py'];
const RUNTIME_ARTIFACT_RELATIVE_SEGMENTS = ['scripts', '__pycache__', 'helper.cpython-312.pyc'];
const SCOPED_GROUP_SKILL_DIRECTORY = 'orchestrator';
const CORE_SKILL_DIRECTORIES = [
    'orchestrator',
    'orchestrator-refresh',
    'team-advisor',
    'grok-spawn',
    'everything-search',
    'test-runner',
    'privacy-hygiene',
    'issue-tracker',
    'task-build',
    'eli5',
];
const PRIOR_RUN_BACKUP_DIRECTORY_NAMES = [
    '2020-01-01T00-00-00-000Z',
    '2021-06-15T12-30-45-123Z',
    '2022-11-30T23-59-59-999Z',
];
const SKILLS_DIRECTORY_NAME = 'skills';
const HOOKS_DIRECTORY_NAME = 'hooks';
const GIT_HOOKS_DIRECTORY_NAME = 'git-hooks';
const PRE_COMMIT_HOOK_NAME = 'pre-commit';
const PRE_PUSH_HOOK_NAME = 'pre-push';
const POST_COMMIT_HOOK_NAME = 'post-commit';
const FOREIGN_HOOK_NAME = 'foreign-hook';
const SETTINGS_FILE_NAME = 'settings.json';
const MANIFEST_FILE_NAME = '.claude-dev-env-manifest.json';
const CLAUDE_HUB_FILE_NAME = 'CLAUDE.md';
const RULES_DIRECTORY_NAME = 'rules';
const SHARED_DIRECTORY_NAME = '_shared';
const STALE_RULE_FILE_NAME = 'retired-rule.md';
const STALE_SHARED_FILE_SEGMENTS = ['pr-loop', 'retired_shared.md'];
const STALE_SHARED_SKILL_FILE_SEGMENTS = [SHARED_DIRECTORY_NAME, 'retired_skill_shared.md'];
const RETIRED_HOOK_RELATIVE_SEGMENTS = ['blocking', 'retired_gate.py'];
const RETIRED_HOOK_SEEDED_CONTENTS = 'a gate an earlier revision shipped\n';
const FOLDED_RETIRED_HOOK_RELATIVE_SEGMENTS = ['blocking', 'ask_user_question_shape_blocker.py'];
const USER_HOOK_COMMAND = 'python3 my_own_gate.py --user-authored';
const RETIRED_HOOK_EVENT_TYPE = 'PreToolUse';
const DROPPED_HOOK_EVENT_TYPE = 'PreCompact';
const DISPATCHER_HOOK_COMMAND_SEGMENT = 'pre_tool_use_dispatcher.py';
const UNMANAGED_SIBLING_DIRECTORY = 'my-notes';
const NESTED_SKILL_DIRECTORY = 'foo';
const NESTED_SKILL_FILE_SEGMENTS = [NESTED_SKILL_DIRECTORY, 'scripts', 'a.py'];
const MYPY_INI_FILE_NAME = '.mypy.ini';
const SKIPPED_RECORD_SUMMARY_MARKER = 'manifest record(s) skipped';
const RETIRED_PULL_REQUEST_HOOK_RELATIVE_PATHS = [
    '_gh_pr_author_swap_utils.py',
    'test__gh_pr_author_swap_utils.py',
    'blocking/conventional_pr_title_gate.py',
    'blocking/gh_body_arg_blocker.py',
    'blocking/gh_pr_author_enforcer.py',
    'blocking/gh_pr_author_restore.py',
    'blocking/pr_description_writer_gate.py',
    'blocking/test_conventional_pr_title_gate.py',
    'blocking/test_gh_body_arg_blocker.py',
    'blocking/test_gh_pr_author_enforcer.py',
    'blocking/test_gh_pr_author_restore.py',
    'blocking/test_gh_pr_author_swap_utils.py',
    'blocking/test_pr_description_writer_gate.py',
    'blocking/test_volatile_path_in_post_blocker.py',
    'blocking/volatile_path_in_post_blocker.py',
    'hooks_constants/conventional_pr_title_gate_constants.py',
    'hooks_constants/gh_pr_author_swap_constants.py',
    'hooks_constants/pr_description_writer_gate_constants.py',
    'hooks_constants/volatile_path_in_post_blocker_constants.py',
    'observability/pr_description_writer_spawn_tracker.py',
    'observability/test_pr_description_writer_spawn_tracker.py',
    'session/gh_pr_author_session_cleanup.py',
    'session/test_gh_pr_author_session_cleanup.py',
];
const RETIRED_PULL_REQUEST_REGISTRATION_PATHS = [
    'blocking/conventional_pr_title_gate.py',
    'blocking/gh_body_arg_blocker.py',
    'blocking/gh_pr_author_enforcer.py',
    'blocking/gh_pr_author_restore.py',
    'blocking/pr_description_writer_gate.py',
    'blocking/volatile_path_in_post_blocker.py',
    'observability/pr_description_writer_spawn_tracker.py',
    'session/gh_pr_author_session_cleanup.py',
];

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
function createSandbox(homeDirectoryPrefix = 'cdev-prune-home-') {
    const homeDirectory = mkdtempSync(join(tmpdir(), homeDirectoryPrefix));
    const claudeDirectory = join(homeDirectory, '.claude');
    const skillsDirectory = join(claudeDirectory, 'skills');
    mkdirSync(skillsDirectory, { recursive: true });
    const manifestPath = join(claudeDirectory, '.claude-dev-env-manifest.json');
    return { homeDirectory, claudeDirectory, skillsDirectory, manifestPath };
}

test('a core install runs the spaced-path Write dispatcher and allows the write', () => {
    const sandbox = createSandbox('cdev prune & (home)-');
    try {
        runInstaller(sandbox.homeDirectory, ['--only', 'core']);
        const settings = readSettings(sandbox.claudeDirectory);
        const dispatcherHooks = settings.hooks.PreToolUse
            .flatMap(eachGroup => eachGroup.hooks)
            .filter(eachHook => /(?:^|[\\/])pre_tool_use_dispatcher\.py["']?(?:\s|$)/.test(eachHook.command));
        assert.equal(dispatcherHooks.length, 1, 'the core install writes one PreToolUse dispatcher');

        const protectedFilePath = join(sandbox.homeDirectory, 'protected file.txt');
        writeFileSync(protectedFilePath, 'existing content\n');
        const writePayload = JSON.stringify({
            tool_name: 'Write',
            tool_input: { file_path: protectedFilePath, content: 'replacement content\n' },
        });
        const { childEnvironment } = resolveInstallerInvocation(sandbox.homeDirectory);
        const dispatcherRun = spawnSync(dispatcherHooks[0].command, {
            cwd: dirname(INSTALLER_PATH),
            encoding: 'utf8',
            env: childEnvironment,
            input: `${writePayload}\n`,
            shell: true,
            timeout: 30000,
        });

        assert.equal(dispatcherRun.status, 0, dispatcherRun.stderr);
        assert.equal(dispatcherRun.stdout.trim(), '', 'no hosted hook denies a Write');
        assert.equal(readFileSync(protectedFilePath, 'utf8'), 'existing content\n');
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

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
function runInstaller(homeDirectory, extraArguments) {
    const { installerPath, childEnvironment } = resolveInstallerInvocation(homeDirectory);
    return execFileSync('node', [installerPath, ...extraArguments], {
        cwd: dirname(installerPath),
        encoding: 'utf8',
        env: childEnvironment,
        timeout: INSTALLER_PROCESS_TIMEOUT_MS,
    });
}

/**
 * Build the installer path and child environment one sandbox run uses.
 *
 * @param {string} homeDirectory The sandbox home the installer writes into.
 * @returns {{installerPath: string, childEnvironment: object}} The invocation inputs.
 */
function resolveInstallerInvocation(homeDirectory) {
    const childEnvironment = {
        ...process.env,
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        CODEX_HOME: join(homeDirectory, '.codex'),
    };
    return { installerPath: INSTALLER_PATH, childEnvironment };
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
    const { installerPath, childEnvironment } = resolveInstallerInvocation(homeDirectory);
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

test('a full reinstall keeps the skill-builder stub and archives its obsolete support files', () => {
    const sandbox = createSandbox();
    try {
        const skillName = 'skill-builder';
        plantSkillDirectory(sandbox.skillsDirectory, skillName, true);
        const stubPath = join(sandbox.skillsDirectory, skillName, 'SKILL.md');
        const obsoleteReferencePath = join(sandbox.skillsDirectory, skillName, 'references', 'retired.md');
        writeFileWithParents(obsoleteReferencePath, 'obsolete skill-builder guidance\n');
        writeFileSync(sandbox.manifestPath, JSON.stringify({
            package: 'claude-dev-env',
            version: '0.0.0',
            installedAt: new Date().toISOString(),
            files: [stubPath, obsoleteReferencePath],
            skills: [skillName],
        }, null, 2) + '\n');

        const installerOutput = runInstaller(sandbox.homeDirectory, []);

        assert.equal(installerOutput.includes(SKIP_PRUNE_NOTICE_MARKER), false);
        assert.equal(existsSync(stubPath), true, 'the requested stub stays installed');
        assert.match(readFileSync(stubPath, 'utf8'), /TODO: Rework to follow pstack philosophy\./);
        assert.ok(readManifest(sandbox.manifestPath).skills.includes(skillName));
        assert.equal(existsSync(obsoleteReferencePath), false);
        assert.equal(
            prunedSkillBackupContains(sandbox.claudeDirectory, join(skillName, 'references', 'retired.md')),
            true,
            'old implementation files move to the recovery backup while the stub stays',
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

test('a fresh scoped core install ships active skills and omits retired skills', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, ['--only', 'core']);

        const missingSkillNames = CORE_SKILL_DIRECTORIES.filter(
            eachSkillName => !existsSync(join(sandbox.skillsDirectory, eachSkillName, 'SKILL.md')),
        );
        assert.deepEqual(missingSkillNames, []);

        const recordedSkillNames = new Set(readManifest(sandbox.manifestPath).skills);
        for (const eachSkillName of CORE_SKILL_DIRECTORIES) {
            assert.equal(recordedSkillNames.has(eachSkillName), true);
        }
        for (const eachSkillName of RETIRED_SKILL_DIRECTORIES) {
            assert.equal(existsSync(join(sandbox.skillsDirectory, eachSkillName)), false);
            assert.equal(recordedSkillNames.has(eachSkillName), false);
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
    writeFileWithParents(retiredHookPath, RETIRED_HOOK_SEEDED_CONTENTS);
    appendManifestFiles(sandbox.manifestPath, [retiredHookPath]);
    const retiredHookCommand = `python3 "${retiredHookPath.replace(/\\/g, '/')}"`;
    const lookalikeHookCommand = `python3 "${retiredHookPath.replace(/\\/g, '/')}.bak"`;
    const settings = readSettings(sandbox.claudeDirectory);
    const liveGroup = settings.hooks[RETIRED_HOOK_EVENT_TYPE]
        .find(group => group.hooks.some(
            hook => hook.command.includes(DISPATCHER_HOOK_COMMAND_SEGMENT),
        ));
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

test('a reinstall regenerates a stale post-commit shim and preserves a foreign git hook', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const gitHooksDirectory = join(
            sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, GIT_HOOKS_DIRECTORY_NAME,
        );
        const postCommitShimPath = join(gitHooksDirectory, POST_COMMIT_HOOK_NAME);
        const foreignHookPath = join(gitHooksDirectory, FOREIGN_HOOK_NAME);
        const foreignHookContentBytes = Buffer.from('foreign hook content\n', 'utf8');
        const staleShimContent = 'generated by an earlier install\n';
        writeFileWithParents(postCommitShimPath, staleShimContent);
        writeFileWithParents(foreignHookPath, foreignHookContentBytes);
        appendManifestFiles(sandbox.manifestPath, [postCommitShimPath]);

        runInstaller(sandbox.homeDirectory, []);

        const freshManifest = readManifest(sandbox.manifestPath);
        assert.notEqual(readFileSync(postCommitShimPath, 'utf8'), staleShimContent);
        assert.deepEqual(readFileSync(foreignHookPath), foreignHookContentBytes);
        assert.equal(freshManifest.files.includes(foreignHookPath), false);
        for (const gitHookName of [PRE_COMMIT_HOOK_NAME, PRE_PUSH_HOOK_NAME, POST_COMMIT_HOOK_NAME]) {
            const generatedShimPath = join(gitHooksDirectory, gitHookName);
            assert.equal(existsSync(generatedShimPath), true);
            assert.equal(freshManifest.files.includes(generatedShimPath), true);
        }
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall retires a hook script and leaves an inert stand-in the open session can still run', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const {
            retiredHookPath, retiredHookCommand, lookalikeHookCommand,
        } = seedRetiredManagedHook(sandbox);

        const installOutput = runInstallerReadingBothStreams(sandbox.homeDirectory, []);

        assert.notEqual(
            readFileSync(retiredHookPath, 'utf8'),
            RETIRED_HOOK_SEEDED_CONTENTS,
            'the retired gate itself no longer runs at that path',
        );
        const standInRun = spawnSync(detectPython(), [retiredHookPath], { encoding: 'utf8' });
        assert.equal(
            standInRun.status,
            0,
            'a session holding the old registration runs the stand-in and gets an allow',
        );
        assert.equal(standInRun.stdout, '', 'the stand-in writes nothing to stdout');
        assert.equal(standInRun.stderr, '', 'the stand-in writes nothing to stderr');
        assert.match(
            installOutput,
            /Restart open sessions: this install retired blocking\/retired_gate\.py/,
            'the run names the retired registration and asks for a restart',
        );
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

        runInstaller(sandbox.homeDirectory, []);

        assert.equal(
            existsSync(retiredHookPath),
            false,
            'the next run finds no registration naming the stand-in, so the stand-in leaves too',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall leaves a stand-in for a registration the package itself stopped shipping', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const retiredHookPath = join(
            sandbox.claudeDirectory,
            HOOKS_DIRECTORY_NAME,
            ...FOLDED_RETIRED_HOOK_RELATIVE_SEGMENTS,
        );
        writeFileWithParents(retiredHookPath, RETIRED_HOOK_SEEDED_CONTENTS);
        appendManifestFiles(sandbox.manifestPath, [retiredHookPath]);
        const retiredHookCommand = `python3 "${retiredHookPath.replace(/\\/g, '/')}"`;
        const settings = readSettings(sandbox.claudeDirectory);
        settings.hooks[RETIRED_HOOK_EVENT_TYPE].push({
            matcher: 'AskUserQuestion',
            hooks: [{ type: 'command', command: retiredHookCommand }],
        });
        writeFileSync(
            join(sandbox.claudeDirectory, SETTINGS_FILE_NAME),
            JSON.stringify(settings, null, 4) + '\n',
        );

        const installOutput = runInstallerReadingBothStreams(sandbox.homeDirectory, []);

        assert.equal(
            allHookCommands(readSettings(sandbox.claudeDirectory)).includes(retiredHookCommand),
            false,
            'the registration the package stopped shipping leaves settings.json',
        );
        const standInRun = spawnSync(detectPython(), [retiredHookPath], { encoding: 'utf8' });
        assert.equal(
            standInRun.status,
            0,
            'a session still holding that registration runs a stand-in and gets an allow',
        );
        assert.match(
            installOutput,
            /Restart open sessions: this install retired blocking\/ask_user_question_shape_blocker\.py/,
            'the run names the registration the merge would otherwise drop in silence',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall removes the retired Everything path rewriter and keeps a foreign hook neighbor', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const retiredHookPath = join(
            sandbox.claudeDirectory,
            HOOKS_DIRECTORY_NAME,
            'blocking',
            'es_exe_path_rewriter.py',
        );
        writeFileWithParents(retiredHookPath, 'a hook an earlier install wrote\n');
        appendManifestFiles(sandbox.manifestPath, [retiredHookPath]);

        const foreignHookPath = join(
            sandbox.claudeDirectory,
            HOOKS_DIRECTORY_NAME,
            'blocking',
            'foreign_search_hook.py',
        );
        const foreignHookBytes = Buffer.from('a user hook the installer never wrote\n');
        writeFileWithParents(foreignHookPath, foreignHookBytes);

        runInstaller(sandbox.homeDirectory, []);

        const freshManifest = readManifest(sandbox.manifestPath);
        const installedDispatcherConstantsPath = join(
            sandbox.claudeDirectory,
            HOOKS_DIRECTORY_NAME,
            'hooks_constants',
            'bash_pre_tool_use_dispatcher_constants.py',
        );
        assert.equal(existsSync(retiredHookPath), false, 'the retired search hook leaves the installed hooks');
        assert.equal(
            freshManifest.files.includes(retiredHookPath),
            false,
            'the fresh manifest drops the retired search hook',
        );
        assert.equal(
            freshManifest.files.includes(foreignHookPath),
            false,
            'the fresh manifest does not claim the foreign hook',
        );
        assert.deepEqual(
            readFileSync(foreignHookPath),
            foreignHookBytes,
            'the foreign hook keeps its original bytes',
        );
        assert.equal(
            readFileSync(installedDispatcherConstantsPath, 'utf8').includes(
                'es_exe_path_rewriter.py',
            ),
            false,
            'the installed dispatcher constants omit the retired search hook',
        );
    } finally {
        rmSync(sandbox.homeDirectory, { recursive: true, force: true });
    }
});

test('a full reinstall removes retired pull request hooks and preserves foreign and recovery state', () => {
    const sandbox = createSandbox();
    try {
        runInstaller(sandbox.homeDirectory, []);
        const retiredPaths = RETIRED_PULL_REQUEST_HOOK_RELATIVE_PATHS.map(relativePath => (
            join(sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, ...relativePath.split('/'))
        ));
        for (const retiredPath of retiredPaths) {
            writeFileWithParents(retiredPath, 'an earlier install managed this file\n');
        }
        appendManifestFiles(sandbox.manifestPath, retiredPaths);
        const foreignHookPath = join(
            sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, 'blocking', 'foreign_pr_hook.py',
        );
        const foreignHookBytes = Buffer.from('a user hook the installer never wrote\n', 'utf8');
        writeFileWithParents(foreignHookPath, foreignHookBytes);
        const recoveryStatePath = join(
            sandbox.homeDirectory, 'pending', 'gh_pr_author_swap_session-a.json',
        );
        const recoveryStateBytes = Buffer.from('{"original_account":"prior"}\n', 'utf8');
        writeFileWithParents(recoveryStatePath, recoveryStateBytes);
        const settings = readSettings(sandbox.claudeDirectory);
        settings.hooks.PreToolUse.push({
            matcher: 'Bash',
            hooks: [
                ...RETIRED_PULL_REQUEST_REGISTRATION_PATHS.map(relativePath => ({
                    type: 'command',
                    command: `python3 "${join(sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, ...relativePath.split('/')).replace(/\\/g, '/')}"`,
                })),
                { type: 'command', command: `python3 "${foreignHookPath.replace(/\\/g, '/')}"` },
            ],
        });
        writeFileSync(
            join(sandbox.claudeDirectory, SETTINGS_FILE_NAME),
            JSON.stringify(settings, null, 4) + '\n',
        );

        runInstaller(sandbox.homeDirectory, []);

        const freshManifest = readManifest(sandbox.manifestPath);
        const allCommands = allHookCommands(readSettings(sandbox.claudeDirectory));
        const registeredRetiredPaths = new Set(RETIRED_PULL_REQUEST_REGISTRATION_PATHS);
        for (const relativePath of RETIRED_PULL_REQUEST_HOOK_RELATIVE_PATHS) {
            const retiredPath = join(
                sandbox.claudeDirectory, HOOKS_DIRECTORY_NAME, ...relativePath.split('/'),
            );
            if (registeredRetiredPaths.has(relativePath)) {
                assert.equal(
                    spawnSync(detectPython(), [retiredPath], { encoding: 'utf8' }).status,
                    0,
                    `${relativePath} keeps an inert stand-in while a session still registers it`,
                );
                assert.ok(
                    freshManifest.files.includes(retiredPath),
                    `${relativePath} is recorded, so a later run retires the stand-in`,
                );
                continue;
            }
            assert.equal(existsSync(retiredPath), false, `${retiredPath} leaves installed hooks`);
            assert.equal(freshManifest.files.includes(retiredPath), false);
        }
        for (const relativePath of RETIRED_PULL_REQUEST_REGISTRATION_PATHS) {
            assert.ok(allCommands.every(command => !command.includes(relativePath)));
        }
        assert.deepEqual(readFileSync(foreignHookPath), foreignHookBytes);
        assert.deepEqual(readFileSync(recoveryStatePath), recoveryStateBytes);
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
