import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createInterface } from 'node:readline';
import test from 'node:test';
import { verifyInstallation } from './pstack.mjs';

const executable = process.env.CDE_CODEX_EXECUTABLE;
const project = process.env.CDE_PSTACK_PROOF_PROJECT;

test('native Codex discovers every installed pstack skill and its real entry path', {
    skip: !executable || !project ? 'Set CDE_CODEX_EXECUTABLE and CDE_PSTACK_PROOF_PROJECT for native discovery' : false,
    timeout: 60000,
}, async t => {
    const installation = verifyInstallation({ project });
    const release = join(resolve(project), '.claude', 'pstack', 'releases', installation.release);
    const manifest = JSON.parse(readFileSync(join(release, 'release.json'), 'utf8'));
    const home = mkdtempSync(join(tmpdir(), 'pstack codex home '));
    const codexHome = join(home, '.codex');
    mkdirSync(codexHome);
    const env = { PATH: process.env.PATH, HOME: home, CODEX_HOME: codexHome };
    const version = spawnSync(executable, ['--version'], { env, encoding: 'utf8', timeout: 15000 });
    assert.equal(version.status, 0, version.stderr || version.error?.message);
    const child = spawn(executable, ['app-server'], { cwd: project, env, stdio: ['pipe', 'pipe', 'pipe'] });
    const lines = createInterface({ input: child.stdout });
    let stderr = '';
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.stdin.on('error', () => {});
    t.after(async () => {
        lines.close();
        const stopped = child.exitCode !== null || child.signalCode !== null
            ? Promise.resolve() : new Promise(accept => child.once('close', accept));
        child.kill();
        await stopped;
        rmSync(home, { recursive: true, force: true });
    });
    const transcript = [];
    const send = message => child.stdin.write(JSON.stringify(message) + '\n');
    const request = (id, method, params) => new Promise((accept, reject) => {
        const timer = setTimeout(() => finish(new Error(`Codex ${method} timed out: ${stderr}`)), 15000);
        const failed = error => finish(error);
        const closed = code => finish(new Error(`Codex exited ${code}: ${stderr}`));
        const receive = line => {
            let message;
            try { message = JSON.parse(line); } catch (error) { finish(error); return; }
            transcript.push(message);
            if (message.id === id) finish(message.error ? new Error(JSON.stringify(message.error)) : null, message.result);
        };
        const finish = (error, response) => {
            clearTimeout(timer);
            child.off('error', failed);
            child.off('close', closed);
            lines.off('line', receive);
            if (error) reject(error); else accept(response);
        };
        child.once('error', failed);
        child.once('close', closed);
        lines.on('line', receive);
        send({ id, method, params });
    });
    await request(0, 'initialize', { clientInfo: { name: 'skillcheck', version: '1.0.0' } });
    send({ method: 'initialized', params: {} });
    const discovered = await request(1, 'skills/list', { cwds: [resolve(project)], forceReload: true });
    const evidence = { verification: 'native-codex-skill-discovery', codexVersion: version.stdout.trim(),
        upstreamCommit: installation.commit, adapterDigest: installation.adapterDigest, transcript };
    if (process.env.CDE_PSTACK_DISCOVERY_REPORT) writeFileSync(process.env.CDE_PSTACK_DISCOVERY_REPORT, JSON.stringify(evidence, null, 2) + '\n');
    const workspace = discovered.data.find(entry => resolve(entry.cwd) === resolve(project));
    assert.ok(workspace, 'Codex returned the requested workspace');
    assert.deepEqual(workspace.errors, []);
    for (const expected of manifest.skills) {
        const found = workspace.skills.filter(skill => skill.name === expected.name);
        assert.equal(found.length, 1, `Codex discovers ${expected.name} once`);
        assert.equal(found[0].enabled, true, expected.name);
        assert.equal(realpathSync(found[0].path), realpathSync(join(release, expected.path, 'SKILL.md')));
    }
    t.diagnostic(`${version.stdout.trim()}: ${manifest.skills.length} installed skills discovered through Codex`);
});
