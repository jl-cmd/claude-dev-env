#!/usr/bin/env node
/**
 * Install playtest: run the shipped package the way a session loads it.
 *
 * The driver installs this package into a scratch home, reads the hook roster
 * the install wrote into `settings.json`, starts one SessionStart hook and one
 * PreToolUse hook from that installed tree against fixture payloads, and reads
 * the output envelope each one returns.
 *
 * Every stage writes the envelope it read to the evidence directory and prints
 * one line carrying the stage name, the artifact path and the artifact's
 * SHA-256 digest::
 *
 *     every stage read the envelope it expected -> exit 0
 *     one stage read something else             -> exit 1
 *
 * Usage::
 *
 *     node scripts/ci/install-playtest.mjs
 *     node scripts/ci/install-playtest.mjs --home <dir> --evidence <dir>
 *     node scripts/ci/install-playtest.mjs --home <dir> --skip-install
 *
 * `--home` names the scratch home to install into and keeps it after the run.
 * `--skip-install` grades the tree already installed in that home, which is how
 * a broken install is read back.
 */

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createScratchHome, removeScratchHome, runInstaller, scratchHomeEnvironment } from './scratch-home-install.mjs';

export const EVIDENCE_PREFIX = 'cde-playtest-';
export const SETTINGS_RELATIVE_PATH = join('.claude', 'settings.json');
export const HOOK_TIMEOUT_MILLISECONDS = 60_000;
export const PASS_MARK = 'PASS';
export const FAIL_MARK = 'FAIL';
export const DIGEST_ALGORITHM = 'sha256';
export const INSTALL_STAGE_NAME = 'install';
export const SESSION_START_STAGE_NAME = 'session_start_hook';
export const BLOCKING_STAGE_NAME = 'blocking_hook';
export const SESSION_START_EVENT_NAME = 'SessionStart';
export const PRE_TOOL_USE_EVENT_NAME = 'PreToolUse';
export const SESSION_START_HOOK_SCRIPT_NAME = 'working_style_prompt.py';
export const BASH_HOOK_SCRIPT_NAME = 'bash_pre_tool_use_dispatcher.py';
export const BASH_MATCHER = 'Bash';
export const ALLOW_DECISION = 'allow';

export const SESSION_START_PAYLOAD = {
    hook_event_name: SESSION_START_EVENT_NAME,
    source: 'startup',
};

export const BASH_HOOK_PAYLOAD = {
    tool_name: BASH_MATCHER,
    tool_input: { command: 'git show origin/main:.claude/settings.json' },
};

export const REWRITE_MARKER = 'MSYS2_ARG_CONV_EXCL';

/**
 * Parse the driver's arguments.
 *
 * @param {string[]} argv Arguments after the script name.
 * @returns {{homePath: string | null, evidencePath: string | null, shouldSkipInstall: boolean}} The parsed options.
 */
export function parseArguments(argv) {
    let homePath = null;
    let evidencePath = null;
    let shouldSkipInstall = false;
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === '--home') {
            homePath = argv[index + 1] ?? null;
            index += 1;
        } else if (token === '--evidence') {
            evidencePath = argv[index + 1] ?? null;
            index += 1;
        } else if (token === '--skip-install') {
            shouldSkipInstall = true;
        }
    }
    return { homePath, evidencePath, shouldSkipInstall };
}

/**
 * Read the SHA-256 digest of a file.
 *
 * @param {string} filePath Path of the file to digest.
 * @returns {string} The hexadecimal digest.
 */
export function fileDigest(filePath) {
    return createHash(DIGEST_ALGORITHM).update(readFileSync(filePath)).digest('hex');
}

/**
 * Read every hook command the installed settings file declares for one event.
 *
 * @param {string} settingsPath Path of the installed settings file.
 * @param {string} eventName Hook event name, such as `SessionStart`.
 * @returns {{matcher: string, command: string}[]} Each declared hook command.
 */
export function hookCommandsForEvent(settingsPath, eventName) {
    const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
    const allMatcherGroups = settings.hooks?.[eventName] ?? [];
    const allCommands = [];
    for (const eachGroup of allMatcherGroups) {
        for (const eachHook of eachGroup.hooks ?? []) {
            allCommands.push({ matcher: eachGroup.matcher ?? '', command: eachHook.command });
        }
    }
    return allCommands;
}

/**
 * Select the one installed hook command a stage drives.
 *
 * @param {{matcher: string, command: string}[]} allCommands Declared hook commands.
 * @param {string} scriptName Basename of the hook script the stage drives.
 * @returns {string} The command line the install wrote.
 * @throws {Error} The installed roster declares no such hook.
 */
export function selectHookCommand(allCommands, scriptName) {
    const selected = allCommands.find((each) => each.command.includes(scriptName));
    if (!selected) {
        throw new Error(`The installed hook roster declares no ${scriptName}`);
    }
    return selected.command;
}

/**
 * Run one installed hook command against a payload and return its output.
 *
 * @param {string} command The command line the install wrote.
 * @param {string} scratchHome Scratch home the install wrote into.
 * @param {object} payload The hook payload written to standard input.
 * @returns {{status: number | null, stdout: string, stderr: string}} The hook's result.
 */
export function runInstalledHook(command, scratchHome, payload) {
    const hookProcess = spawnSync(command, {
        shell: true,
        input: JSON.stringify(payload),
        encoding: 'utf8',
        cwd: scratchHome,
        timeout: HOOK_TIMEOUT_MILLISECONDS,
        env: scratchHomeEnvironment(scratchHome),
    });
    return {
        status: hookProcess.status,
        stdout: hookProcess.stdout ?? '',
        stderr: hookProcess.stderr ?? '',
    };
}

/**
 * Read a hook's standard output as an envelope for one event.
 *
 * @param {string} stdout The hook's standard output.
 * @param {string} eventName The event name the envelope must name.
 * @returns {object} The `hookSpecificOutput` object.
 * @throws {Error} The output is not an envelope for that event.
 */
export function readEnvelope(stdout, eventName) {
    const trimmed = stdout.trim();
    if (!trimmed) {
        throw new Error(`The hook wrote no ${eventName} envelope`);
    }
    const parsed = JSON.parse(trimmed);
    const hookSpecificOutput = parsed.hookSpecificOutput;
    if (!hookSpecificOutput || hookSpecificOutput.hookEventName !== eventName) {
        throw new Error(`The hook envelope names ${hookSpecificOutput?.hookEventName} rather than ${eventName}`);
    }
    return hookSpecificOutput;
}

function writeEvidence(evidenceDirectory, stageName, body) {
    const evidencePath = join(evidenceDirectory, `${stageName}.json`);
    writeFileSync(evidencePath, `${body}\n`);
    return evidencePath;
}

function reportStage(stageName, evidencePath) {
    process.stdout.write(`[${PASS_MARK}] playtest ${stageName} ${evidencePath} ${DIGEST_ALGORITHM}=${fileDigest(evidencePath)}\n`);
}

function reportFailure(stageName, detail) {
    process.stdout.write(`[${FAIL_MARK}] playtest ${stageName} ${detail}\n`);
}

function runInstallStage(scratchHome, evidenceDirectory, shouldSkipInstall) {
    if (!shouldSkipInstall) {
        const install = runInstaller(scratchHome, []);
        if (install.status !== 0) {
            throw new Error(`The installer exited ${install.status}: ${install.stderr.trim()}`);
        }
    }
    const settingsPath = join(scratchHome, SETTINGS_RELATIVE_PATH);
    if (!existsSync(settingsPath)) {
        throw new Error(`The install wrote no ${settingsPath}`);
    }
    const evidencePath = writeEvidence(
        evidenceDirectory,
        INSTALL_STAGE_NAME,
        JSON.stringify({ settingsPath, digest: fileDigest(settingsPath) }),
    );
    reportStage(INSTALL_STAGE_NAME, evidencePath);
    return settingsPath;
}

function runSessionStartStage(settingsPath, scratchHome, evidenceDirectory) {
    const command = selectHookCommand(
        hookCommandsForEvent(settingsPath, SESSION_START_EVENT_NAME),
        SESSION_START_HOOK_SCRIPT_NAME,
    );
    const hookResult = runInstalledHook(command, scratchHome, SESSION_START_PAYLOAD);
    const envelope = readEnvelope(hookResult.stdout, SESSION_START_EVENT_NAME);
    if (typeof envelope.additionalContext !== 'string' || envelope.additionalContext.length === 0) {
        throw new Error('The SessionStart envelope carries no additionalContext');
    }
    const evidencePath = writeEvidence(evidenceDirectory, SESSION_START_STAGE_NAME, JSON.stringify(envelope));
    reportStage(SESSION_START_STAGE_NAME, evidencePath);
}

function runBlockingStage(settingsPath, scratchHome, evidenceDirectory) {
    const command = selectHookCommand(
        hookCommandsForEvent(settingsPath, PRE_TOOL_USE_EVENT_NAME),
        BASH_HOOK_SCRIPT_NAME,
    );
    const hookResult = runInstalledHook(command, scratchHome, BASH_HOOK_PAYLOAD);
    const envelope = readEnvelope(hookResult.stdout, PRE_TOOL_USE_EVENT_NAME);
    if (envelope.permissionDecision !== ALLOW_DECISION) {
        throw new Error(`The PreToolUse envelope decided ${envelope.permissionDecision}`);
    }
    const rewrittenCommand = envelope.updatedInput?.command ?? '';
    if (!rewrittenCommand.includes(REWRITE_MARKER)) {
        throw new Error(`The PreToolUse envelope left the command unrewritten: ${rewrittenCommand}`);
    }
    const evidencePath = writeEvidence(evidenceDirectory, BLOCKING_STAGE_NAME, JSON.stringify(envelope));
    reportStage(BLOCKING_STAGE_NAME, evidencePath);
}

/**
 * Run every playtest stage and return the driver's exit code.
 *
 * @param {string[]} argv Arguments after the script name.
 * @returns {number} Zero when every stage read the envelope it expected.
 */
export function runPlaytest(argv) {
    const options = parseArguments(argv);
    const scratchHome = options.homePath ?? createScratchHome();
    if (options.homePath) {
        mkdirSync(scratchHome, { recursive: true });
        const gitConfigPath = join(scratchHome, '.gitconfig-sandbox');
        if (!existsSync(gitConfigPath)) {
            writeFileSync(gitConfigPath, '[safe]\n\tdirectory = *\n');
        }
    }
    const evidenceDirectory = options.evidencePath ?? mkdtempSync(join(tmpdir(), EVIDENCE_PREFIX));
    mkdirSync(evidenceDirectory, { recursive: true });
    let stageName = INSTALL_STAGE_NAME;
    try {
        const settingsPath = runInstallStage(scratchHome, evidenceDirectory, options.shouldSkipInstall);
        stageName = SESSION_START_STAGE_NAME;
        runSessionStartStage(settingsPath, scratchHome, evidenceDirectory);
        stageName = BLOCKING_STAGE_NAME;
        runBlockingStage(settingsPath, scratchHome, evidenceDirectory);
    } catch (error) {
        reportFailure(stageName, error instanceof Error ? error.message : String(error));
        return 1;
    } finally {
        if (!options.homePath) {
            removeScratchHome(scratchHome);
        }
    }
    process.stdout.write('install playtest: every stage read its envelope\n');
    return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
    process.exit(runPlaytest(process.argv.slice(2)));
}
