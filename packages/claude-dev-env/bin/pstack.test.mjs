import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, readlinkSync, realpathSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { installPstack, prepareRelease, validateLock, verifyInstallation, verifyRelease } from './pstack.mjs';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const baseLock = JSON.parse(readFileSync(join(packageRoot, 'scripts', 'pstack.lock.json'), 'utf8'));

function put(path, content) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content);
}

function fixture(t) {
    const temporary = mkdtempSync(join(tmpdir(), 'cde-pstack-'));
    t.after(() => rmSync(temporary, { recursive: true, force: true }));
    const checkout = join(temporary, 'checkout');
    for (const [component, names] of Object.entries(baseLock.requiredSkills)) {
        for (const name of names) put(join(checkout, component, 'skills', name, 'SKILL.md'), `---\nname: ${name}\ndescription: Test ${name}.\n---\n\nRun ${name}.\n`);
        put(join(checkout, component, 'LICENSE'), `${component} license\n`);
        put(join(checkout, component, '.cursor-plugin', 'plugin.json'), JSON.stringify({ name: component, skills: './skills' }));
    }
    put(join(checkout, 'pstack', 'skills', 'poteto-mode', 'playbooks', 'feature.md'), 'Build a small task, delegate, and verify it.\n');
    put(join(checkout, 'pstack', 'agents', 'poteto-agent.md'), 'Read poteto-mode and report complete findings.\n');
    put(join(checkout, 'pstack', 'scripts', 'proof.sh'), '#!/bin/sh\nprintf proof\n');
    chmodSync(join(checkout, 'pstack', 'scripts', 'proof.sh'), 0o755);
    put(join(checkout, 'pstack', 'assets', 'example.png'), Buffer.from([137, 80, 78, 71, 0, 255]));
    const project = join(temporary, 'project with spaces');
    const options = { project, lock: structuredClone(baseLock), packageRoot };
    const dependencies = { fetchSource: (_lock, destination) => cpSync(checkout, destination, { recursive: true }), now: 10000000 };
    return { temporary, checkout, options, dependencies, store: join(project, '.claude', 'pstack') };
}

for (const host of ['claude', 'codex', 'cursor']) {
    test(`clean ${host} filesystem install publishes all entry points and supporting files`, t => {
        const f = fixture(t);
        const result = installPstack({ ...f.options, host }, f.dependencies);
        assert.equal(result.status, 'installed');
        assert.equal(result.skillCount, 5);
        assert.equal(result.commit, '27e2a62ff94f9af4b5e68435e41cdceacadb840c');
        assert.equal(result.verification, 'filesystem-only');
        const release = join(f.store, 'releases', result.release);
        const expected = ['cde-create-skill', 'cursor-team-kit-control-cli', 'cursor-team-kit-control-ui', 'cursor-team-kit-deslop', 'pstack'];
        for (const home of ['.claude', '.agents']) {
            const skillsHome = join(f.options.project, home, 'skills');
            assert.deepEqual(readdirSync(skillsHome).sort(), expected);
            const pstackRoot = join(skillsHome, 'pstack');
            assert.equal(lstatSync(pstackRoot).isSymbolicLink(), true);
            const entry = join(pstackRoot, 'poteto-mode');
            assert.equal(realpathSync(entry), join(release, 'runtime', 'pstack', 'skills', 'poteto-mode'));
            const text = readFileSync(join(entry, 'SKILL.md'), 'utf8');
            assert.match(text, /name: pstack-poteto-mode/);
            assert.ok(text.includes(JSON.stringify(join(release, 'compat', 'common.md'))));
            assert.equal(readFileSync(join(entry, 'playbooks', 'feature.md'), 'utf8'), 'Build a small task, delegate, and verify it.\n');
            const manifest = JSON.parse(readFileSync(join(pstackRoot, '.claude-plugin', 'plugin.json'), 'utf8'));
            assert.equal(manifest.name, 'pstack');
            assert.deepEqual(manifest.skills, ['./poteto-mode']);
        }
        assert.equal(existsSync(join(f.options.project, '.cursor')), false);
        for (const component of baseLock.components) {
            assert.equal(existsSync(join(release, 'runtime', component, '.cursor-plugin', 'plugin.json')), false);
            assert.equal(readFileSync(join(release, 'upstream', component, '.cursor-plugin', 'plugin.json'), 'utf8'),
                readFileSync(join(f.checkout, component, '.cursor-plugin', 'plugin.json'), 'utf8'));
        }
        assert.equal(readFileSync(join(release, 'upstream', 'pstack', 'skills', 'poteto-mode', 'SKILL.md'), 'utf8'), readFileSync(join(f.checkout, 'pstack', 'skills', 'poteto-mode', 'SKILL.md'), 'utf8'));
        assert.deepEqual(readFileSync(join(release, 'upstream', 'pstack', 'assets', 'example.png')), Buffer.from([137, 80, 78, 71, 0, 255]));
        assert.equal(readFileSync(join(release, 'runtime', 'pstack', 'agents', 'poteto-agent.md'), 'utf8'), 'Read poteto-mode and report complete findings.\n');
        assert.equal(readFileSync(join(release, 'upstream', 'cursor-team-kit', 'LICENSE'), 'utf8'), 'cursor-team-kit license\n');
        if (process.platform !== 'win32') assert.equal(statSync(join(release, 'runtime', 'pstack', 'scripts', 'proof.sh')).mode & 0o777, 0o755);
    });
}

test('unchanged install avoids another upstream fetch', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const second = installPstack(f.options, { fetchSource: () => assert.fail('unexpected fetch') });
    assert.equal(second.status, 'unchanged');
    assert.equal(second.release, first.release);
    assert.deepEqual(second.links, first.links);
});

test('changed, added, and removed skills converge while old releases remain readable', t => {
    const f = fixture(t);
    put(join(f.checkout, 'pstack', 'skills', 'old', 'SKILL.md'), '---\nname: old\ndescription: Old skill.\n---\nOld body.\n');
    const before = installPstack(f.options, f.dependencies);
    const oldRelease = join(f.store, 'releases', before.release);
    const firstBody = readFileSync(join(oldRelease, 'runtime', 'pstack', 'skills', 'poteto-mode', 'SKILL.md'), 'utf8');
    rmSync(join(f.checkout, 'pstack', 'skills', 'old'), { recursive: true });
    put(join(f.checkout, 'pstack', 'skills', 'new', 'SKILL.md'), '---\nname: new\ndescription: New skill.\n---\nNew body.\n');
    put(join(f.checkout, 'pstack', 'skills', 'poteto-mode', 'playbooks', 'feature.md'), 'Changed playbook.\n');
    const after = installPstack({ ...f.options, lock: { ...baseLock, commit: 'b'.repeat(40) } }, f.dependencies);
    assert.equal(after.skillCount, 6);
    for (const home of ['.claude', '.agents']) {
        const pstackRoot = join(f.options.project, home, 'skills', 'pstack');
        assert.equal(existsSync(join(pstackRoot, 'old')), false);
        assert.equal(readFileSync(join(pstackRoot, 'new', 'SKILL.md'), 'utf8').endsWith('New body.\n'), true);
        assert.equal(readFileSync(join(pstackRoot, 'poteto-mode', 'playbooks', 'feature.md'), 'utf8'), 'Changed playbook.\n');
        const manifest = JSON.parse(readFileSync(join(pstackRoot, '.claude-plugin', 'plugin.json'), 'utf8'));
        assert.deepEqual(manifest.skills, ['./new', './poteto-mode']);
    }
    assert.equal(readFileSync(join(oldRelease, 'runtime', 'pstack', 'skills', 'poteto-mode', 'SKILL.md'), 'utf8'), firstBody);
});

test('missing required dependency retains the previous complete installation', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const priorBytes = readFileSync(join(f.store, 'installed.json'), 'utf8');
    rmSync(join(f.checkout, 'cursor-team-kit', 'skills', 'control-ui'), { recursive: true });
    const result = installPstack({ ...f.options, lock: { ...baseLock, commit: 'c'.repeat(40) } }, f.dependencies);
    assert.equal(result.status, 'retained');
    assert.match(result.warning, /Missing dependency: cursor-team-kit:control-ui/);
    assert.equal(result.release, first.release);
    assert.equal(readFileSync(join(f.store, 'installed.json'), 'utf8'), priorBytes);
    assert.equal(verifyInstallation(f.options).skillCount, 5);
});

test('a failed first install returns failure and publishes no skills', t => {
    const f = fixture(t);
    assert.throws(() => installPstack(f.options, { fetchSource: () => { throw new Error('network unavailable'); } }), /network unavailable/);
    assert.equal(existsSync(join(f.options.project, '.claude', 'skills')), false);
    assert.equal(existsSync(join(f.store, '.install-lock')), false);
});

test('unmanaged pstack root collision preserves user files', t => {
    const f = fixture(t);
    const userFile = join(f.options.project, '.claude', 'skills', 'pstack', 'poteto-mode', 'SKILL.md');
    put(userFile, 'Personal workflow\n');
    assert.throws(() => installPstack(f.options, f.dependencies), /Keep existing unmanaged path/);
    assert.equal(readFileSync(userFile, 'utf8'), 'Personal workflow\n');
    assert.equal(existsSync(join(f.store, 'installed.json')), false);
});

test('existing shared skills-directory pointer is preserved', t => {
    const f = fixture(t);
    const agents = join(f.options.project, '.agents', 'skills');
    mkdirSync(agents, { recursive: true });
    mkdirSync(join(f.options.project, '.claude'), { recursive: true });
    symlinkSync(agents, join(f.options.project, '.claude', 'skills'), process.platform === 'win32' ? 'junction' : 'dir');
    const before = readlinkSync(join(f.options.project, '.claude', 'skills'));
    const result = installPstack(f.options, f.dependencies);
    assert.equal(Object.keys(result.links).length, 5);
    assert.equal(readlinkSync(join(f.options.project, '.claude', 'skills')), before);
});

test('offline reuse checks installed bytes and rejects corruption', t => {
    const f = fixture(t);
    const result = installPstack(f.options, f.dependencies);
    assert.equal(installPstack({ ...f.options, offline: true }).release, result.release);
    put(join(f.store, 'releases', result.release, 'runtime', 'pstack', 'skills', 'poteto-mode', 'SKILL.md'), 'corrupted');
    assert.throws(() => installPstack({ ...f.options, offline: true }), /Changed installed file/);
});

test('unknown namespaced upstream dependency requires adapter review', t => {
    const f = fixture(t);
    put(join(f.checkout, 'pstack', 'skills', 'poteto-mode', 'reference.md'), 'Invoke cursor-team-kit:missing-skill.\n');
    assert.throws(() => installPstack(f.options, f.dependencies), /Unresolved skill dependency/);
});

test('source symlinks are rejected before publication', t => {
    const f = fixture(t);
    const outside = join(f.temporary, 'outside-source');
    mkdirSync(outside);
    put(join(outside, 'personal.txt'), 'Retain this file.');
    const dependencies = { ...f.dependencies, fetchSource: (lock, destination) => {
        f.dependencies.fetchSource(lock, destination);
        const link = join(destination, 'pstack', 'escape');
        symlinkSync(outside, link, process.platform === 'win32' ? 'junction' : 'dir');
        assert.equal(lstatSync(link).isSymbolicLink(), true);
    } };
    assert.throws(() => installPstack(f.options, dependencies), /symlinks require review/);
    assert.equal(readFileSync(join(outside, 'personal.txt'), 'utf8'), 'Retain this file.');
});

test('update checks use the shared record and respect the interval', t => {
    const f = fixture(t);
    const shared = { ...baseLock, commit: 'd'.repeat(40) };
    let calls = 0;
    const dependencies = { ...f.dependencies, readCentralLock: () => { calls++; return shared; } };
    const first = installPstack({ ...f.options, refresh: true }, dependencies);
    assert.equal(first.commit, 'd'.repeat(40));
    const second = installPstack({ ...f.options, refresh: true }, { ...dependencies, now: dependencies.now + 100 });
    assert.equal(second.commit, 'd'.repeat(40));
    assert.equal(calls, 1);
    installPstack({ ...f.options, refresh: true }, { ...dependencies, now: dependencies.now + 3600001 });
    assert.equal(calls, 2);
});

test('failed shared-record refresh retains and reports the previous revision', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const result = installPstack({ ...f.options, refresh: true }, { ...f.dependencies, readCentralLock: () => { throw new Error('record unavailable'); } });
    assert.equal(result.release, first.release);
    assert.equal(result.warning, 'record unavailable');
});

test('an active launcher lease defers updating shared instructions', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    put(join(f.store, 'sessions', String(process.pid)), first.release);
    const result = installPstack({ ...f.options, lock: { ...baseLock, commit: 'e'.repeat(40) } }, { fetchSource: () => assert.fail('updated during an active session') });
    assert.equal(result.status, 'retained');
    assert.equal(result.release, first.release);
});

test('unsupported lock input fails before source fetch', t => {
    const f = fixture(t);
    for (const change of [{ commit: 'main' }, { adapterVersion: 2 }, { repository: 'https://example.test/repo' }, { components: ['../outside'] }, { requiredSkills: {} }]) {
        assert.throws(() => installPstack({ ...f.options, lock: { ...baseLock, ...change } }, { fetchSource: () => assert.fail('unexpected fetch') }));
    }
    assert.equal(validateLock(baseLock), baseLock);
});

test('CLI exposes deterministic verification and rejects unknown flags', t => {
    const f = fixture(t);
    installPstack(f.options, f.dependencies);
    const command = join(packageRoot, 'bin', 'pstack.mjs');
    const verified = spawnSync(process.execPath, [command, 'verify', '--project', f.options.project], { encoding: 'utf8' });
    assert.equal(verified.status, 0, verified.stderr);
    assert.equal(JSON.parse(verified.stdout).skillCount, 5);
    const invalid = spawnSync(process.execPath, [command, 'install', '--host', 'unknown'], { encoding: 'utf8' });
    assert.equal(invalid.status, 1);
    assert.match(invalid.stderr, /Host must be/);
    const help = spawnSync(process.execPath, [command, '--help'], { encoding: 'utf8' });
    assert.equal(help.status, 0);
    assert.match(help.stdout, /cde-pstack/);
});

test('resumed Claude hook retains the cached release and emits native hook JSON', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const result = spawnSync(process.execPath, [join(packageRoot, 'bin', 'pstack.mjs'), 'hook', '--project', f.options.project], {
        encoding: 'utf8', input: JSON.stringify({ source: 'resume' }),
    });
    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.hookSpecificOutput.hookEventName, 'SessionStart');
    assert.ok(output.hookSpecificOutput.additionalContext.includes(first.commit));
    assert.ok(output.hookSpecificOutput.additionalContext.includes('common.md'));
});

test('release validation catches missing files and escaping manifest paths', t => {
    const f = fixture(t);
    const result = installPstack(f.options, f.dependencies);
    const root = join(f.store, 'releases', result.release);
    assert.equal(verifyRelease(root).skills.length, 5);
    const manifest = JSON.parse(readFileSync(join(root, 'release.json'), 'utf8'));
    manifest.fileDigests['../../outside'] = 'bad';
    put(join(root, 'release.json'), JSON.stringify(manifest));
    assert.throws(() => verifyRelease(root), /Invalid release path/);
});

test('state-write failure restores the old published pointers', t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const priorBytes = readFileSync(join(f.store, 'installed.json'), 'utf8');
    mkdirSync(join(f.store, 'installed.next.json'));
    const result = installPstack({ ...f.options, lock: { ...baseLock, commit: 'f'.repeat(40) } }, f.dependencies);
    assert.equal(result.status, 'retained');
    assert.equal(result.release, first.release);
    assert.equal(readFileSync(join(f.store, 'installed.json'), 'utf8'), priorBytes);
    assert.equal(verifyInstallation(f.options).commit, first.commit);
});

test('npm-style linked CLI runs its entry point', t => {
    const f = fixture(t);
    if (process.platform === 'win32') return;
    const link = join(f.temporary, 'cde-pstack');
    symlinkSync(join(packageRoot, 'bin', 'pstack.mjs'), link);
    const result = spawnSync(process.execPath, [link, '--help'], { encoding: 'utf8' });
    assert.equal(result.status, 0);
    assert.match(result.stdout, /Usage: cde-pstack/);
});

test('session reservation is recorded before install releases its lock', t => {
    const f = fixture(t);
    const result = installPstack({ ...f.options, reserveSession: true }, f.dependencies);
    assert.equal(readFileSync(join(f.store, 'sessions', String(process.pid)), 'utf8'), result.release);
    assert.equal(existsSync(join(f.store, '.install-lock')), false);
});


test('a changed installer creates a fresh generation for the same upstream pin', async t => {
    const f = fixture(t);
    const first = installPstack(f.options, f.dependencies);
    const copied = join(f.temporary, 'updated-installer', 'bin', 'pstack.mjs');
    put(copied, readFileSync(join(packageRoot, 'bin', 'pstack.mjs'), 'utf8') + '\n');
    const updated = await import(pathToFileURL(copied).href);
    const second = updated.installPstack(f.options, f.dependencies);
    assert.equal(second.commit, first.commit);
    assert.notEqual(second.adapterDigest, first.adapterDigest);
    assert.notEqual(second.release, first.release);
    assert.equal(verifyInstallation(f.options).release, second.release);
});
