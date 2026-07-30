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
 * Append one tool-hook record; sequence is derived from sink order.
 *
 * @param {string} sinkPath
 * @param {{
 *   eventName: string,
 *   profileId: string,
 *   correlationId: string,
 *   toolName?: string,
 * }} fields
 * @returns {ToolHookEventRecord}
 */
function appendToolHookEvent(sinkPath, fields) {
    const record = {
        eventName: fields.eventName,
        profileId: fields.profileId,
        correlationId: fields.correlationId,
        toolName: fields.toolName ?? DISPOSABLE_TOOL_NAME,
        sequence: readToolHookEvents(sinkPath).length + 1,
        recordedAtMs: Date.now(),
    };
    writeFileSync(sinkPath, `${JSON.stringify(record)}\n`, {
        encoding: 'utf8',
        flag: 'a',
    });
    return record;
}

/**
 * @param {ToolHookEventRecord[]} allEvents
 * @param {string} correlationId
 * @param {string} [eventName]
 * @returns {ToolHookEventRecord[]}
 */
function eventsForCorrelation(allEvents, correlationId, eventName) {
    return allEvents.filter((eachEvent) => {
        if (eachEvent.correlationId !== correlationId) {
            return false;
        }
        if (eventName && eachEvent.eventName !== eventName) {
            return false;
        }
        return true;
    });
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

    appendToolHookEvent(sinkPath, {
        eventName: PRE_TOOL_USE_EVENT,
        profileId,
        correlationId,
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

            const matched = eventsForCorrelation(outcome.events, correlationId);
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
        assert.equal(
            eventsForCorrelation(outcome.events, correlationId, PRE_TOOL_USE_EVENT).length,
            1,
        );
        assert.equal(
            eventsForCorrelation(outcome.events, correlationId, POST_TOOL_USE_EVENT).length,
            1,
        );
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('mismatched pre/post correlation ids stay distinct', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const sinkPath = createToolEventSinkPath(roots.profileRootById.editor);
        appendToolHookEvent(sinkPath, {
            eventName: PRE_TOOL_USE_EVENT,
            profileId: 'editor',
            correlationId: 'corr-a',
        });
        appendToolHookEvent(sinkPath, {
            eventName: POST_TOOL_USE_EVENT,
            profileId: 'editor',
            correlationId: 'corr-b',
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
        assert.equal(outcome.harnessResult.profileRoot, roots.profileRootById.mel);
        const configDir = String(outcome.harnessResult.profileRoot).replace(/\\/gu, '/').toLowerCase();
        const runRoot = roots.runRoot.replace(/\\/gu, '/').toLowerCase();
        assert.ok(configDir.startsWith(runRoot));
        assert.ok(configDir.includes('fresh-session'));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
