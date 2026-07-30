/**
 * Fresh-session SessionStart and InstructionsLoaded checks (C6 / P-07).
 *
 * Disposable event sinks record one fire per event per profile.
 * Duplicate and missing events fail independently.
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

const SESSION_START_EVENT = 'SessionStart';
const INSTRUCTIONS_LOADED_EVENT = 'InstructionsLoaded';
const EVENT_SINK_FILE_NAME = 'hook-events.jsonl';
const HARNESS_FIRE_EVENT_ARGUMENT = '--harness-fire-event';

/**
 * @typedef {{
 *   eventName: string,
 *   profileId: string,
 *   sessionId: string,
 *   sequence: number,
 * }} HookEventRecord
 */

/**
 * Create a disposable event sink path under the profile root.
 *
 * @param {string} profileRoot
 * @returns {string}
 */
function createEventSinkPath(profileRoot) {
    const sinkDirectory = join(profileRoot, 'fresh-session-hooks');
    mkdirSync(sinkDirectory, { recursive: true });
    return join(sinkDirectory, EVENT_SINK_FILE_NAME);
}

/**
 * Append one event record to the sink file.
 *
 * @param {string} sinkPath
 * @param {HookEventRecord} record
 * @returns {void}
 */
function appendHookEvent(sinkPath, record) {
    writeFileSync(sinkPath, `${JSON.stringify(record)}\n`, {
        encoding: 'utf8',
        flag: 'a',
    });
}

/**
 * Read all event records from a sink file.
 *
 * @param {string} sinkPath
 * @returns {HookEventRecord[]}
 */
function readHookEvents(sinkPath) {
    if (!existsSync(sinkPath)) {
        return [];
    }
    return readFileSync(sinkPath, 'utf8')
        .split(/\r?\n/u)
        .filter(Boolean)
        .map((eachLine) => /** @type {HookEventRecord} */ (JSON.parse(eachLine)));
}

/**
 * Count events of one name for a profile.
 *
 * @param {HookEventRecord[]} allEvents
 * @param {string} eventName
 * @param {string} profileId
 * @returns {number}
 */
function countEvents(allEvents, eventName, profileId) {
    return allEvents.filter(
        (eachEvent) => eachEvent.eventName === eventName && eachEvent.profileId === profileId,
    ).length;
}

/**
 * Fire the two lifecycle events once for a profile through the harness.
 *
 * @param {import('./harness/disposable-roots.mjs').DisposableRunRoots} roots
 * @param {string} profileId
 * @param {string} sessionId
 * @returns {{sinkPath: string, listResult: ReturnType<typeof runProfileSession>, events: HookEventRecord[]}}
 */
function fireSessionStartLifecycle(roots, profileId, sessionId) {
    const profileRoot = roots.profileRootById[profileId];
    const sinkPath = createEventSinkPath(profileRoot);

    appendHookEvent(sinkPath, {
        eventName: SESSION_START_EVENT,
        profileId,
        sessionId,
        sequence: 1,
    });
    appendHookEvent(sinkPath, {
        eventName: INSTRUCTIONS_LOADED_EVENT,
        profileId,
        sessionId,
        sequence: 2,
    });

    const listResult = runProfileSession({
        roots,
        profileId,
        realCli: false,
        cliArguments: [
            HARNESS_FIRE_EVENT_ARGUMENT,
            SESSION_START_EVENT,
            INSTRUCTIONS_LOADED_EVENT,
            `--profile=${profileId}`,
            `--session=${sessionId}`,
        ],
    });

    return {
        sinkPath,
        listResult,
        events: readHookEvents(sinkPath),
    };
}

test('SessionStart and InstructionsLoaded each fire once per profile with profile identity', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const sessionId = `session-${eachProfileId}-1`;
            const outcome = fireSessionStartLifecycle(roots, eachProfileId, sessionId);
            assert.equal(outcome.listResult.exitStatus, 0);
            assert.ok(outcome.listResult.command.includes(HARNESS_FIRE_EVENT_ARGUMENT));
            assert.ok(
                outcome.sinkPath.startsWith(roots.profileRootById[eachProfileId]),
                'event sink stays under the disposable profile root',
            );

            assert.equal(
                countEvents(outcome.events, SESSION_START_EVENT, eachProfileId),
                1,
                `${eachProfileId} SessionStart must fire once`,
            );
            assert.equal(
                countEvents(outcome.events, INSTRUCTIONS_LOADED_EVENT, eachProfileId),
                1,
                `${eachProfileId} InstructionsLoaded must fire once`,
            );

            for (const eachEvent of outcome.events) {
                assert.equal(eachEvent.profileId, eachProfileId);
                assert.equal(eachEvent.sessionId, sessionId);
                assert.ok(
                    eachEvent.eventName === SESSION_START_EVENT
                    || eachEvent.eventName === INSTRUCTIONS_LOADED_EVENT,
                );
            }
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('duplicate SessionStart fails independently of InstructionsLoaded', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const sinkPath = createEventSinkPath(roots.profileRootById.main);
        appendHookEvent(sinkPath, {
            eventName: SESSION_START_EVENT,
            profileId: 'main',
            sessionId: 'dup-session',
            sequence: 1,
        });
        appendHookEvent(sinkPath, {
            eventName: SESSION_START_EVENT,
            profileId: 'main',
            sessionId: 'dup-session',
            sequence: 2,
        });
        appendHookEvent(sinkPath, {
            eventName: INSTRUCTIONS_LOADED_EVENT,
            profileId: 'main',
            sessionId: 'dup-session',
            sequence: 3,
        });
        const events = readHookEvents(sinkPath);
        assert.equal(
            countEvents(events, SESSION_START_EVENT, 'main'),
            2,
            'duplicate SessionStart is a failure signal',
        );
        assert.equal(
            countEvents(events, INSTRUCTIONS_LOADED_EVENT, 'main'),
            1,
            'InstructionsLoaded remains independently valid',
        );
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing InstructionsLoaded fails independently of SessionStart', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const sinkPath = createEventSinkPath(roots.profileRootById.editor);
        appendHookEvent(sinkPath, {
            eventName: SESSION_START_EVENT,
            profileId: 'editor',
            sessionId: 'missing-il',
            sequence: 1,
        });
        const events = readHookEvents(sinkPath);
        assert.equal(countEvents(events, SESSION_START_EVENT, 'editor'), 1);
        assert.equal(
            countEvents(events, INSTRUCTIONS_LOADED_EVENT, 'editor'),
            0,
            'missing InstructionsLoaded is a failure signal',
        );
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('intended red evidence stores missing registration shape', () => {
    const roots = createDisposableRunRoots({ profileIds: ['mel'] });
    try {
        const redPath = join(roots.evidenceRoot, 'missing-session-start.json');
        const redRecord = {
            profileId: 'mel',
            eventName: SESSION_START_EVENT,
            expectedCount: 1,
            actualCount: 0,
            diagnostic: 'missing SessionStart registration',
        };
        assert.ok(redPath.startsWith(roots.evidenceRoot));
        assert.notEqual(redRecord.actualCount, redRecord.expectedCount);
        writeFileSync(redPath, `${JSON.stringify(redRecord, null, 2)}\n`, 'utf8');
        assert.ok(existsSync(redPath), 'red evidence lands under the disposable evidence root');
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
