import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { adapterDigest, installPstack, releaseLease, validateLock, verifyInstallation, verifyRelease } from '../scripts/pstack/install.mjs';
import { nativeAgentFiles, putFile, skillNames } from '../scripts/pstack/adapter.mjs';
import { parseArguments, runHook } from './pstack.mjs';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cli = join(packageRoot, 'bin', 'pstack.mjs');

function git(source, args) {
    return execFileSync('git', args, { cwd: source, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

function skill(source, plugin, name, body = 'Read the local evidence.') {
    putFile(join(source, plugin, 'skills', name, 'SKILL.md'),
        `---\nname: ${name}\ndescription: Fixture ${name} workflow.\n---\n\n${body}\n`);
}

function commit(source) {
    git(source, ['add', '.']);
    git(source, ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture revision']);
    return { schemaVersion: 1, adapterVersion: 1, adapterDigest: adapterDigest(packageRoot), upstreamCommit: git(source, ['rev-parse', 'HEAD']), verification: 'install-contract' };
}

function fixture(t) {
    const folder = mkdtempSync(join(tmpdir(), 'pstack behavior '));
    t.after(() => rmSync(folder, { recursive: true, force: true }));
    const source = join(folder, 'source');
    putFile(join(source, 'LICENSE'), 'Fixture license\n');
    git(source, ['init', '-q']);
    git(source, ['config', 'core.autocrlf', 'false']);
    for (const name of ['poteto-mode', 'how', 'old-skill']) skill(source, 'pstack', name);
    for (const name of ['deslop', 'control-cli', 'control-ui']) skill(source, 'cursor-team-kit', name);
    for (const name of ['feature', 'bug-fix']) {
        putFile(join(source, 'pstack', 'skills', 'poteto-mode', 'playbooks', `${name}.md`), `Run the ${name} fixture.\n`);
    }
    for (const name of ['poteto-agent', 'comment-sicko']) {
        putFile(join(source, 'pstack', 'agents', `${name}.md`), `Return the complete ${name} fixture findings.\n`);
    }
    putFile(join(source, 'pstack', 'assets', 'fixture.bin'), Buffer.from([0, 255, 0, 123]));
    const lock = commit(source);
    return { root: join(folder, 'workspace with spaces'), source, lock, host: 'claude', folder };
}

for (const host of ['claude', 'codex', 'cursor']) {
    test(`${host} clean install retains sources, dependencies, playbooks and native bindings`, async t => {
        const options = { ...fixture(t), host };
        const result = await installPstack(options);
        const checked = verifyInstallation(options.root);
        assert.equal(checked.upstreamCommit, options.lock.upstreamCommit);
        assert.equal(checked.skills.length, 7);
        assert.deepEqual(skillNames(join(options.source, 'pstack')), ['how', 'old-skill', 'poteto-mode']);
        assert.equal(readFileSync(join(result.release, 'upstream/pstack/skills/poteto-mode/playbooks/feature.md'), 'utf8'), 'Run the feature fixture.\n');
        assert.deepEqual(readFileSync(join(result.release, 'upstream/pstack/assets/fixture.bin')), Buffer.from([0, 255, 0, 123]));
        const wrapper = readFileSync(join(options.root, '.agents/skills/poteto-mode/SKILL.md'), 'utf8');
        assert.match(wrapper, /PSTACK_RELEASE:/);
        assert.ok(wrapper.includes(result.release));
        assert.match(wrapper, /compatibility\.md/);
        assert.ok(nativeAgentFiles(options.root).every(file => readFileSync(file.path, 'utf8') === file.content));
        assert.equal(existsSync(join(options.root, '.cursor/skills')), false);
        assert.equal(verifyRelease(options.root, result.generation).skills.length, 7);
    });
}

test('second install keeps the generation and host preferences', async t => {
    const options = fixture(t);
    const first = await installPstack(options);
    const preference = join(options.root, '.claude/pstack/preferences/pstack-model-preferences.codex.json');
    putFile(preference, '{"host":"codex","modelsByRole":{"bug-fix":["my-model"]}}');
    const second = await installPstack(options);
    assert.equal(second.generation, first.generation);
    assert.match(readFileSync(preference, 'utf8'), /my-model/);
});

test('update carries changed, added and removed skills to both discovery roots', async t => {
    const options = fixture(t);
    const first = await installPstack(options);
    skill(options.source, 'pstack', 'how', 'Changed workflow.');
    skill(options.source, 'pstack', 'new-skill');
    rmSync(join(options.source, 'pstack/skills/old-skill'), { recursive: true });
    options.lock = commit(options.source);
    const second = await installPstack(options);
    assert.notEqual(second.generation, first.generation);
    for (const path of ['.claude/skills/pstack', '.agents/skills']) {
        assert.equal(existsSync(join(options.root, path, 'new-skill/SKILL.md')), true);
        assert.equal(existsSync(join(options.root, path, 'old-skill')), false);
    }
    assert.match(readFileSync(join(second.release, 'upstream/pstack/skills/how/SKILL.md'), 'utf8'), /Changed workflow/);
    assert.match(readFileSync(join(first.release, 'upstream/pstack/skills/how/SKILL.md'), 'utf8'), /local evidence/);
});

test('missing dependency update keeps the working release and reports the cause', async t => {
    const options = fixture(t);
    const first = await installPstack(options);
    rmSync(join(options.source, 'cursor-team-kit/skills/control-ui'), { recursive: true });
    options.lock = commit(options.source);
    const result = await installPstack(options);
    assert.equal(result.generation, first.generation);
    assert.match(result.warning, /Missing dependency: cursor-team-kit:control-ui/);
    assert.equal(verifyInstallation(options.root).generation, first.generation);
});

test('failed verified-channel check retains an installed release', async t => {
    const options = fixture(t);
    const first = await installPstack(options);
    const result = await installPstack({
        root: options.root, host: 'codex', checkIntervalMs: 0,
        fetchLock: async () => { throw new Error('network fixture unavailable'); },
    });
    assert.equal(result.generation, first.generation);
    assert.match(result.warning, /network fixture unavailable/);
});

test('unowned discovery paths are preserved and publication fails visibly', async t => {
    const options = fixture(t);
    putFile(join(options.root, '.agents/skills/poteto-mode/SKILL.md'), 'Personal workflow.');
    await assert.rejects(installPstack(options), /Unmanaged discovery path/);
    assert.equal(readFileSync(join(options.root, '.agents/skills/poteto-mode/SKILL.md'), 'utf8'), 'Personal workflow.');
    assert.equal(existsSync(join(options.root, '.claude/pstack/state.json')), false);
});

test('dirty input and invalid lock records fail before publication', async t => {
    const options = fixture(t);
    putFile(join(options.source, 'pstack/untracked.md'), 'Uncommitted.');
    await assert.rejects(installPstack(options), /uncommitted changes/);
    assert.throws(() => validateLock({ ...options.lock, adapterVersion: 2 }), /unsupported adapter/);
    assert.throws(() => validateLock({ ...options.lock, upstreamCommit: '../main' }), /Invalid pstack lock/);
});

test('integrity verification detects changed source bytes', async t => {
    const options = fixture(t);
    const result = await installPstack(options);
    putFile(join(result.release, 'upstream/pstack/skills/how/SKILL.md'), 'Changed after install.');
    assert.throws(() => verifyInstallation(options.root), /Installed file changed/);
    await assert.rejects(installPstack(options), /Installed file changed/);
});

test('active launch lease defers a new generation until the session ends', async t => {
    const options = fixture(t);
    const first = await installPstack({ ...options, leasePid: process.pid });
    skill(options.source, 'pstack', 'new-skill');
    options.lock = commit(options.source);
    const deferred = await installPstack(options);
    assert.equal(deferred.deferred, true);
    assert.equal(deferred.generation, first.generation);
    releaseLease(options.root);
    assert.notEqual((await installPstack(options)).generation, first.generation);
});

test('SessionStart emits host instructions and resume keeps the session release', async t => {
    const options = fixture(t);
    const first = await runHook(options, { session_id: 'fixture/session', source: 'startup' });
    const old = verifyInstallation(options.root);
    assert.match(first.hookSpecificOutput.additionalContext, /PSTACK_RELEASE/);
    skill(options.source, 'pstack', 'new-skill');
    options.lock = commit(options.source);
    await installPstack(options);
    const resumed = await runHook(options, { session_id: 'fixture/session', source: 'resume' });
    assert.ok(resumed.hookSpecificOutput.additionalContext.includes(old.release));
});

test('CLI preserves child arguments, release binding and exit status', async t => {
    const options = fixture(t);
    const lockPath = join(options.folder, 'lock.json');
    putFile(lockPath, JSON.stringify(options.lock));
    const childPath = join(options.folder, 'child.mjs');
    putFile(childPath, "console.log(JSON.stringify({argument:process.argv[2],release:process.env.CDE_PSTACK_RELEASE}));process.exitCode=7;");
    const result = spawnSync(process.execPath, [cli, 'launch', '--host', 'codex', '--root', options.root,
        '--source', options.source, '--lock', lockPath, '--', process.execPath, childPath, 'one argument with spaces'], { encoding: 'utf8' });
    assert.equal(result.status, 7, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.argument, 'one argument with spaces');
    assert.match(output.release, /releases/);
});

test('CLI parser rejects ambiguous options and keeps command arguments', () => {
    assert.throws(() => parseArguments(['install', '--host']), /Missing value/);
    assert.throws(() => parseArguments(['install', '--wat']), /Unknown option/);
    const parsed = parseArguments(['launch', '--host', 'claude', '--', 'claude', '--help']);
    assert.deepEqual(parsed.child, ['claude', '--help']);
    assert.equal(parsed.options.host, 'claude');
});

test('a channel revision checked with another adapter retains the working release', async t => {
    const options = fixture(t);
    const first = await installPstack(options);
    const result = await installPstack({ ...options, lock: { ...options.lock, adapterDigest: '0'.repeat(64) } });
    assert.equal(result.generation, first.generation);
    assert.match(result.warning, /update claude-dev-env first/);
});

test('installed selector reads separate host preferences and preserves diversity requirements', async t => {
    const options = fixture(t);
    const result = await installPstack(options);
    const preferencesDirectory = join(options.root, '.claude/pstack/preferences');
    putFile(join(preferencesDirectory, 'pstack-model-preferences.codex.json'), JSON.stringify({host:'codex',modelsByRole:{'bug-fix':['native-code-model']}}));
    const input = {
        host:'codex', inventoryHost:'codex', role:'bug-fix', delegationIndex:0,
        availableModelIds:['native-code-model'], confirmedSuitableModelIds:[],
        parentFallback:{isAllowed:true,hasMaterialCapabilityLoss:false}, preferencesDirectory,
    };
    const select = value => JSON.parse(execFileSync(process.execPath, [join(result.release, 'scripts/select_pstack_models.mjs')], {input:JSON.stringify(value),encoding:'utf8'}));
    assert.deepEqual(select(input).nativeSpawnArguments, {model:'native-code-model'});
    assert.equal(select({...input,host:'claude',inventoryHost:'claude'}).omitNativeModelArgument, true);
    assert.equal(select({...input,panel:{agentCount:2,requiresDistinctModels:true}}).canDelegate, false);
});


test('wrappers preserve invocation flags while removing host-specific model and agent metadata', async t => {
    const options = fixture(t);
    putFile(join(options.source, 'pstack/skills/how/SKILL.md'),
        '---\nname: Human Name\ndescription: |\n  A folded description.\nmodel: cursor-only\ncontext: fork\nagent: cursor-only\ndisable-model-invocation: true\n---\nRead evidence.\n');
    options.lock = commit(options.source);
    await installPstack(options);
    const wrapper = readFileSync(join(options.root, '.agents/skills/how/SKILL.md'), 'utf8');
    assert.match(wrapper, /name: how/);
    assert.match(wrapper, /A folded description/);
    assert.match(wrapper, /disable-model-invocation: true/);
    assert.doesNotMatch(wrapper, /cursor-only|context: fork/);
});
