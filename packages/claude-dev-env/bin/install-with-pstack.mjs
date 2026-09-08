#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync, realpathSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { installPstack } from './pstack.mjs';

async function selectedRoots(args) {
    const { parseInstallTargetSelectionFromArgv, stripTargetSelectionFlagsFromArgv, resolveProfilesRootDirectory } = await import('./select-install-targets.mjs');
    const { resolveInstallRoot } = await import('./resolve-install-root.mjs');
    if (stripTargetSelectionFlagsFromArgv(args).length) return [];
    const selection = parseInstallTargetSelectionFromArgv(args);
    if (selection.mode !== 'profiles') return [resolveInstallRoot({ explicitTarget: selection.explicitTarget }).managedRoot];
    const root = resolveProfilesRootDirectory({ homeDirectory: homedir(), environment: process.env });
    const byIdentity = new Map();
    for (const entry of readdirSync(root, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const path = join(root, entry.name, '.claude-dev-env-manifest.json');
        if (!existsSync(path)) continue;
        const record = JSON.parse(readFileSync(path, 'utf8'));
        if (selection.allProfileIds.includes(record.targetIdentity)) byIdentity.set(record.targetIdentity, join(root, entry.name));
    }
    return selection.allProfileIds.map(identity => {
        if (!byIdentity.has(identity)) throw new Error(`Missing installed profile manifest: ${identity}`);
        return byIdentity.get(identity);
    });
}

export async function runInstaller(args, dependencies = {}) {
    const runBase = dependencies.runBase ?? (forwarded => spawnSync(process.execPath, [join(dirname(fileURLToPath(import.meta.url)), 'install.mjs'), ...forwarded], { stdio: 'inherit', env: process.env }));
    const base = runBase(args);
    if (base.error) throw base.error;
    if (base.status !== 0) return base.status ?? 1;
    const roots = await (dependencies.selectedRoots ?? selectedRoots)(args);
    for (const root of roots) {
        const installation = (dependencies.install ?? installPstack)({ root });
        console.log(`Pstack ${installation.commit}: ${installation.status}.`);
        if (installation.warning) console.error(`Pstack kept the previous release: ${installation.warning}`);
    }
    return 0;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try { process.exitCode = await runInstaller(process.argv.slice(2)); }
    catch (error) { console.error(`Pstack installation: ${error.message}`); process.exitCode = 1; }
}
