#!/usr/bin/env node
/**
 * Session probe CLI for C1 CLAUDE.md activation.
 *
 * Reads CLAUDE.md under CLAUDE_CONFIG_DIR and records activation evidence.
 * simulation=true marks this as a harness probe (B3 may require real CLI later).
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

function main() {
    const profileId = process.env.FRESH_SESSION_PROFILE_ID ?? 'unknown';
    const evidencePath = process.env.FRESH_SESSION_EVIDENCE_PATH;
    const expectedMarker = process.env.FRESH_SESSION_CLAUDE_MD_MARKER ?? '';
    const configDir = process.env.CLAUDE_CONFIG_DIR;

    if (!configDir) {
        process.stderr.write('claude-md probe: CLAUDE_CONFIG_DIR is required\n');
        process.exit(2);
    }

    const claudeMdPath = join(configDir, 'CLAUDE.md');
    const filePresent = existsSync(claudeMdPath);
    /** @type {string[]} */
    let loadedMarkers = [];
    if (filePresent && expectedMarker.length > 0 && readFileSync(claudeMdPath, 'utf8').includes(expectedMarker)) {
        loadedMarkers = [expectedMarker];
    }

    const isActivated = loadedMarkers.length > 0;
    const record = {
        transport: 'fake-probe',
        profileId,
        probe: 'claude-md',
        environment: {
            CLAUDE_CONFIG_DIR: configDir,
            HOME: process.env.HOME ?? null,
        },
        filePresent,
        activation: {
            channel: 'session-probe',
            simulation: true,
            loadedMarkers,
            isActivated,
            expectedMarker,
        },
        exitStatus: 0,
        recordedAt: new Date().toISOString(),
    };

    if (evidencePath) {
        mkdirSync(dirname(evidencePath), { recursive: true });
        writeFileSync(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
    }

    process.stdout.write(
        `claude-md-probe profile=${profileId} activated=${isActivated} markers=${loadedMarkers.join(',')}\n`,
    );
    process.exit(0);
}

main();
