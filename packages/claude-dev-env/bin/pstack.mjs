#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { installPstack, releaseLease, verifyInstallation, verifyRelease } from '../scripts/pstack/install.mjs';
import { putFile } from '../scripts/pstack/adapter.mjs';

export function parseArguments(args) {
    const command = args.shift() ?? 'help';
    const options = { root: resolve(process.env.CLAUDE_PROJECT_DIR ?? process.cwd()) };
    let child = [];
    while (args.length) {
        const option = args.shift();
        if (option === '--') { child = args; break; }
        if (option === '--offline') { options.offline = true; continue; }
        if (option === '--force-check') { options.checkIntervalMs = 0; continue; }
        if (!['--root', '--host', '--source', '--lock'].includes(option)) {
            throw new Error(`Unknown option: ${option}`);
        }
        const value = args.shift();
        if (!value || value.startsWith('--')) throw new Error(`Missing value for ${option}`);
        if (option === '--lock') options.lock = JSON.parse(readFileSync(value, 'utf8'));
        else options[option.slice(2)] = value;
    }
    options.root = resolve(options.root);
    return { command, options, child };
}

function report(result) {
    if (result.warning) process.stderr.write(`pstack: ${result.warning}\n`);
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}

export async function runHook(options, input) {
    const sessionKey = createHash('sha256').update(String(input.session_id ?? 'unknown')).digest('hex');
    const sessionPath = join(options.root, '.claude', 'pstack', 'sessions', `${sessionKey}.json`);
    let result;
    if (process.env.CDE_PSTACK_RELEASE) {
        result = verifyInstallation(options.root);
        if (result.release !== process.env.CDE_PSTACK_RELEASE) throw new Error('Launch release changed before SessionStart');
    } else if (['resume', 'compact'].includes(input.source) && existsSync(sessionPath)) {
        const saved = JSON.parse(readFileSync(sessionPath, 'utf8'));
        const record = verifyRelease(options.root, saved.generation);
        result = { ...saved, upstreamCommit: record.lock.upstreamCommit };
    } else {
        result = await installPstack({ ...options, checkIntervalMs: 0 });
    }
    putFile(sessionPath, JSON.stringify({ generation: result.generation, release: result.release }));
    if (result.warning) process.stderr.write(`pstack: ${result.warning}\n`);
    return {
        hookSpecificOutput: {
            hookEventName: 'SessionStart',
            additionalContext: `Pstack installation checked. Upstream ${result.upstreamCommit}. `
                + `PSTACK_RELEASE: ${result.release}. For any pstack workflow, read `
                + `${JSON.stringify(join(result.release, 'compatibility.md'))} first. `
                + 'Carry this immutable release into subagent prompts. '
                + 'Installation checks cover files and adapters; live tool availability is checked in the session.'
                + (result.warning ? ` Installer warning: ${result.warning}` : ''),
        },
    };
}

export async function launch(options, command) {
    if (!command.length) throw new Error('launch requires -- followed by the agent executable and its arguments');
    const result = await installPstack({ ...options, leasePid: process.pid });
    if (result.warning) process.stderr.write(`pstack: ${result.warning}\n`);
    try {
        return await new Promise((accept, reject) => {
            const child = spawn(command[0], command.slice(1), {
                cwd: options.root, stdio: 'inherit', shell: false,
                env: { ...process.env, CDE_PSTACK_RELEASE: result.release },
            });
            const handlers = ['SIGINT', 'SIGTERM'].map(signal => {
                const handler = () => child.kill(signal);
                process.on(signal, handler);
                return [signal, handler];
            });
            const cleanup = () => handlers.forEach(([signal, handler]) => process.off(signal, handler));
            child.on('error', error => { cleanup(); reject(error); });
            child.on('close', (code, signal) => { cleanup(); accept(code ?? (signal === 'SIGINT' ? 130 : 143)); });
        });
    } finally { releaseLease(options.root); }
}

export async function main(args = process.argv.slice(2)) {
    const { command, options, child } = parseArguments([...args]);
    if (['help', '--help', '-h'].includes(command)) {
        process.stdout.write('Usage: cde-pstack <install|verify|hook|launch> --host <claude|codex|cursor> [--root PATH]\n'
            + '  --force-check          Check the verified channel now\n'
            + '  --offline              Use the checked installation without network\n'
            + '  --source DIR --lock FILE  Install a clean checkout at an exact pinned commit\n'
            + '  launch ... -- EXECUTABLE [ARGS...]  Install, then start and protect an agent session\n');
        return 0;
    }
    if (command === 'verify') { report(verifyInstallation(options.root)); return 0; }
    if (command === 'install') { report(await installPstack(options)); return 0; }
    if (command === 'launch') return await launch(options, child);
    if (command === 'hook') {
        let input = '';
        for await (const chunk of process.stdin) input += chunk;
        report(await runHook(options, input.trim() ? JSON.parse(input) : {}));
        return 0;
    }
    throw new Error(`Unknown command: ${command}`);
}

const invokedPath = process.argv[1] && existsSync(process.argv[1]) ? realpathSync(process.argv[1]) : null;
if (fileURLToPath(import.meta.url) === invokedPath) {
    try { process.exitCode = await main(); } catch (error) {
        process.stderr.write(`pstack: ${error.message}\n`);
        process.exitCode = 1;
    }
}
