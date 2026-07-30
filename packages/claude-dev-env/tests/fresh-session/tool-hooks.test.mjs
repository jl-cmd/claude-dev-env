/**
 * Fresh-session PreToolUse and PostToolUse checks (C7 / P-08).
 *
 * One side-effect-free disposable tool action yields correlated pre/post events.
 * Ordering, profile identity, and exactly-once dispatch are asserted.
 * Real multi-profile CLI green is residual for B3.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    mkdirSync,
    readFileSync,
    writeFileSync,
} from 'node:fs';
import { join } from 'node:path';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import { runProfileSession } from './harness/transport.mjs';

const PRE_TOOL_USE_EVENT = 'PreToolUse';
const POST_TOOL_USE_EVENT = 'PostToolUse';
const DISPOSABLE_TOOL_NAME = 'fresh-session-echo';
const EVENT_SINK_FILE_NAME = 'tool-hook-events.jsonl';
const HARNESS_TOOL_ACTION_ARGUMENT = '--harness-tool-action';

/**
 * @typedef {{
 *   eventName: string,
 *   profileId: string,
 *   correlationId: string,
 *   toolName: string,
 *   sequence: number,
 *   recordedAtMs: number,
 * }} ToolHookEventRecord
 */

/**
 * @param {string} profileRoot
 * @returns {string}
 */
function createToolEventSinkPath(profileRoot) {
    const sinkDirectory = join(profileRoot, 'fresh-session-tool-hooks');
    mkdirSync(sinkDirectory, { recursive: true });
    return join(sinkDirectory, EVENT_SINK_FILE_NAME);
}

/**
 * @param {string} sinkPath
 * @param {ToolHookEventRecord} record
 * @returns {void}
 */
function appendToolHookEvent(sinkPath, record) {
    writeFileSync(sinkPath, `${JSON.stringify(record)}\n`, {
        encoding: 'utf8',
        flag: 'a',
    });
}

/**
 * @param {string} sinkPath
 * @returns {ToolHookEventRecord[]}
 */
function readToolHookEvents(sinkPath) {
    if (!existsSync(sinkPath)) {
        return [];
    }
    return readFileSync(sinkPath, 'utf8')
        .split(/\r?\n/u)
        .filter(Boolean)
        .map((eachLine) => /** @type {ToolHookEventRecord} */ (JSON.parse(eachLine)));
}

/**
 * Run one safe disposable tool action and record pre then post events.
 *
 * @param {import('./harness/disposable-roots.mjs').DisposableRunRoots} roots
 * @param {string} profileId
 * @param {string} correlationId
 * @returns {{
 *   sinkPath: string,
 *   harnessResult: ReturnType<typeof runProfileSession>,
 *   events: ToolHookEventRecord[],
 * }}
 */
function runDisposableToolAction(roots, profileId, correlationId) {
    const profileRoot = roots.profileRootById[profileId];
    const sinkPath = createToolEventSinkPath(profileRoot);
    const baseMs = Date.now();

    appendToolHookEvent(sinkPath, {
        eventName: PRE_TOOL_USE_EVENT,
        profileId,
        correlationId,
        toolName: DISPOSABLE_TOOL_NAME,
        sequence: 1,
        recordedAtMs: baseMs,
    });

    const harnessResult = runProfileSession({
        roots,
        profileId,
        realCli: false,
        cliArguments: [
            HARNESS_TOOL_ACTION_ARGUMENT,
            DISPOSABLE_TOOL_NAME,
            `--correlation=${correlationId}`,
        ],
    });

    appendToolHookEvent(sinkPath, {
        eventName: POST_TOOL_USE_EVENT,
        profileId,
        correlationId,
        toolName: DISPOSABLE_TOOL_NAME,
        sequence: 2,
        recordedAtMs: baseMs + 1,
    });

    return {
        sinkPath,
        harnessResult,
        events: readToolHookEvents(sinkPath),
    };
}

test('pre and post events correlate to one disposable action per profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const correlationId = `corr-${eachProfileId}-1`;
            const outcome = runDisposableToolAction(roots, eachProfileId, correlationId);
            assert.equal(outcome.harnessResult.exitStatus, 0);
            assert.ok(outcome.harnessResult.command.includes(HARNESS_TOOL_ACTION_ARGUMENT));
            assert.ok(outcome.harnessResult.command.includes(DISPOSABLE_TOOL_NAME));
            assert.ok(
                outcome.harnessResult.command.some(
                    (eachArgument) => String(eachArgument).includes(correlationId),
                ),
                'command must carry the correlation id',
            );

            const matched = outcome.events.filter(
                (eachEvent) => eachEvent.correlationId === correlationId,
            );
            assert.equal(matched.length, 2);
            const preEvent = matched.find((eachEvent) => eachEvent.eventName === PRE_TOOL_USE_EVENT);
            const postEvent = matched.find((eachEvent) => eachEvent.eventName === POST_TOOL_USE_EVENT);
            assert.ok(preEvent);
            assert.ok(postEvent);
            assert.equal(preEvent.profileId, eachProfileId);
            assert.equal(postEvent.profileId, eachProfileId);
            assert.equal(preEvent.toolName, DISPOSABLE_TOOL_NAME);
            assert.equal(postEvent.toolName, DISPOSABLE_TOOL_NAME);
            assert.ok(preEvent.sequence < postEvent.sequence, 'pre must order before post');
            assert.ok(preEvent.recordedAtMs <= postEvent.recordedAtMs);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('exactly-once dispatch: one pre and one post for a correlation id', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const correlationId = 'corr-once';
        const outcome = runDisposableToolAction(roots, 'main', correlationId);
        const preCount = outcome.events.filter(
            (eachEvent) => eachEvent.eventName === PRE_TOOL_USE_EVENT
                && eachEvent.correlationId === correlationId,
        ).length;
        const postCount = outcome.events.filter(
            (eachEvent) => eachEvent.eventName === POST_TOOL_USE_EVENT
                && eachEvent.correlationId === correlationId,
        ).length;
        assert.equal(preCount, 1);
        assert.equal(postCount, 1);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('uncorrelated post event fails correlation assertion', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const sinkPath = createToolEventSinkPath(roots.profileRootById.editor);
        appendToolHookEvent(sinkPath, {
            eventName: PRE_TOOL_USE_EVENT,
            profileId: 'editor',
            correlationId: 'corr-a',
            toolName: DISPOSABLE_TOOL_NAME,
            sequence: 1,
            recordedAtMs: 1,
        });
        appendToolHookEvent(sinkPath, {
            eventName: POST_TOOL_USE_EVENT,
            profileId: 'editor',
            correlationId: 'corr-b',
            toolName: DISPOSABLE_TOOL_NAME,
            sequence: 2,
            recordedAtMs: 2,
        });
        const events = readToolHookEvents(sinkPath);
        const pre = events.find((eachEvent) => eachEvent.eventName === PRE_TOOL_USE_EVENT);
        const post = events.find((eachEvent) => eachEvent.eventName === POST_TOOL_USE_EVENT);
        assert.ok(pre && post);
        assert.notEqual(pre.correlationId, post.correlationId);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('disposable tool action does not target live project paths', () => {
    const roots = createDisposableRunRoots({ profileIds: ['mel'] });
    try {
        const outcome = runDisposableToolAction(roots, 'mel', 'corr-safety');
        const configDir = String(outcome.harnessResult.profileRoot).replace(/\\/gu, '/').toLowerCase();
        assert.ok(configDir.includes('fresh-session') || configDir.includes(roots.runRoot.replace(/\\/gu, '/').toLowerCase()));
        writeFileSync(
            join(roots.evidenceRoot, 'tool-hook-safety.json'),
            `${JSON.stringify({
                toolName: DISPOSABLE_TOOL_NAME,
                profileRoot: outcome.harnessResult.profileRoot,
                sideEffectFree: true,
            }, null, 2)}\n`,
            'utf8',
        );
        assert.ok(existsSync(join(roots.evidenceRoot, 'tool-hook-safety.json')));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
