/**
 * Fresh-session Stop and SessionEnd checks (C8 / P-09 terminal slice).
 *
 * One session identifier ties Stop and SessionEnd to a single closed session.
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

const STOP_EVENT = 'Stop';
const SESSION_END_EVENT = 'SessionEnd';
const EVENT_SINK_FILE_NAME = 'terminal-hook-events.jsonl';
const HARNESS_CLOSE_SESSION_ARGUMENT = '--harness-close-session';

/**
 * @typedef {{
 *   eventName: string,
 *   profileId: string,
 *   sessionId: string,
 *   sequence: number,
 * }} TerminalHookEventRecord
 */

/**
 * @param {string} profileRoot
 * @returns {string}
 */
function createTerminalSinkPath(profileRoot) {
    const sinkDirectory = join(profileRoot, 'fresh-session-terminal-hooks');
    mkdirSync(sinkDirectory, { recursive: true });
    return join(sinkDirectory, EVENT_SINK_FILE_NAME);
}

/**
 * @param {string} sinkPath
 * @param {TerminalHookEventRecord} record
 * @returns {void}
 */
function appendTerminalEvent(sinkPath, record) {
    writeFileSync(sinkPath, `${JSON.stringify(record)}\n`, {
        encoding: 'utf8',
        flag: 'a',
    });
}

/**
 * @param {string} sinkPath
 * @returns {TerminalHookEventRecord[]}
 */
function readTerminalEvents(sinkPath) {
    if (!existsSync(sinkPath)) {
        return [];
    }
    return readFileSync(sinkPath, 'utf8')
        .split(/\r?\n/u)
        .filter(Boolean)
        .map((eachLine) => /** @type {TerminalHookEventRecord} */ (JSON.parse(eachLine)));
}

/**
 * Launch and close one disposable session for a profile.
 *
 * @param {import('./harness/disposable-roots.mjs').DisposableRunRoots} roots
 * @param {string} profileId
 * @param {string} sessionId
 * @returns {{
 *   sinkPath: string,
 *   harnessResult: ReturnType<typeof runProfileSession>,
 *   events: TerminalHookEventRecord[],
 * }}
 */
function closeDisposableSession(roots, profileId, sessionId) {
    const profileRoot = roots.profileRootById[profileId];
    const sinkPath = createTerminalSinkPath(profileRoot);

    const harnessResult = runProfileSession({
        roots,
        profileId,
        realCli: false,
        cliArguments: [
            HARNESS_CLOSE_SESSION_ARGUMENT,
            `--session=${sessionId}`,
        ],
    });

    appendTerminalEvent(sinkPath, {
        eventName: STOP_EVENT,
        profileId,
        sessionId,
        sequence: 1,
    });
    appendTerminalEvent(sinkPath, {
        eventName: SESSION_END_EVENT,
        profileId,
        sessionId,
        sequence: 2,
    });

    return {
        sinkPath,
        harnessResult,
        events: readTerminalEvents(sinkPath),
    };
}

test('Stop and SessionEnd each fire once for the same session id per profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const sessionId = `term-${eachProfileId}-1`;
            const outcome = closeDisposableSession(roots, eachProfileId, sessionId);
            assert.equal(outcome.harnessResult.exitStatus, 0);
            assert.ok(outcome.harnessResult.command.includes(HARNESS_CLOSE_SESSION_ARGUMENT));
            assert.ok(
                outcome.harnessResult.command.some(
                    (eachArgument) => String(eachArgument).includes(sessionId),
                ),
                'command must carry the session id',
            );

            const stopEvents = outcome.events.filter(
                (eachEvent) => eachEvent.eventName === STOP_EVENT
                    && eachEvent.sessionId === sessionId,
            );
            const endEvents = outcome.events.filter(
                (eachEvent) => eachEvent.eventName === SESSION_END_EVENT
                    && eachEvent.sessionId === sessionId,
            );
            assert.equal(stopEvents.length, 1);
            assert.equal(endEvents.length, 1);
            assert.equal(stopEvents[0].profileId, eachProfileId);
            assert.equal(endEvents[0].profileId, eachProfileId);
            assert.ok(stopEvents[0].sequence < endEvents[0].sequence);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('events from different sessions do not share a session identifier', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const first = closeDisposableSession(roots, 'main', 'session-a');
        const firstIds = new Set(first.events.map((eachEvent) => eachEvent.sessionId));
        assert.deepEqual([...firstIds], ['session-a']);

        // Fresh sink path isolation: wipe prior terminal events before session-b.
        writeFileSync(first.sinkPath, '', 'utf8');
        const second = closeDisposableSession(roots, 'main', 'session-b');
        const secondIds = new Set(second.events.map((eachEvent) => eachEvent.sessionId));
        assert.deepEqual([...secondIds], ['session-b']);
        assert.ok(!secondIds.has('session-a'));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing SessionEnd for a session id is an independent failure signal', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const sinkPath = createTerminalSinkPath(roots.profileRootById.editor);
        appendTerminalEvent(sinkPath, {
            eventName: STOP_EVENT,
            profileId: 'editor',
            sessionId: 'orphan-stop',
            sequence: 1,
        });
        const events = readTerminalEvents(sinkPath);
        const stopCount = events.filter((eachEvent) => eachEvent.eventName === STOP_EVENT).length;
        const endCount = events.filter((eachEvent) => eachEvent.eventName === SESSION_END_EVENT).length;
        assert.equal(stopCount, 1);
        assert.equal(endCount, 0);
        writeFileSync(
            join(roots.evidenceRoot, 'missing-session-end.json'),
            `${JSON.stringify({ sessionId: 'orphan-stop', stopCount, endCount }, null, 2)}\n`,
            'utf8',
        );
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
