import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { continuityHookConfiguration } from '../../../bin/install-session-continuity.mjs';

const sourceDirectory = dirname(fileURLToPath(import.meta.url));
const potetoText = '---\nname: Poteto Mode\n---\nPOTETO_SOURCE_EXPECTATION: prove the requested result.\n';
const secondText = 'SECOND_SKILL_EXPECTATION: measure twice before changing files.\n';
const sha256 = value => createHash('sha256').update(value).digest('hex');

function fixture(t, host) {
    const root = mkdtempSync(join(tmpdir(), 'continuity contract '));
    t.after(() => rmSync(root, { recursive: true, force: true }));
    const skill = join(root, '.agents', 'skills', 'session-continuity');
    mkdirSync(skill, { recursive: true });
    for (const file of ['SKILL.md', 'continuity.mjs']) copyFileSync(join(sourceDirectory, file), join(skill, file));
    const poteto = join(root, '.agents', 'skills', 'pstack', 'poteto-mode', 'SKILL.md');
    mkdirSync(dirname(poteto), { recursive: true });
    writeFileSync(poteto, potetoText);
    const second = join(root, 'second-skill.md');
    writeFileSync(second, secondText);
    const script = join(skill, 'continuity.mjs');
    const configPath = join(root, host === 'claude' ? 'settings.json' : 'hooks.json');
    writeFileSync(configPath, JSON.stringify({ hooks: continuityHookConfiguration(host, script) }));
    const env = { ...process.env };
    delete env.CDE_CONTINUITY_ROOT;
    delete env.CDE_POTETO_SOURCE;
    const pathFor = session => join(root, '.agents', 'state', 'session-continuity', host, `${sha256(session)}.json`);
    const cli = (command, session, data, expectedStatus = 0) => {
        const result = spawnSync(process.execPath, [script, command, host, session], { input: JSON.stringify(data || {}), encoding: 'utf8', env });
        assert.equal(result.status, expectedStatus, result.stderr || result.stdout);
        return expectedStatus ? result.stderr : JSON.parse(result.stdout);
    };
    const fire = (event, session, fields = {}) => {
        const payload = { hook_event_name: event, session_id: session, cwd: root, ...fields };
        const config = JSON.parse(readFileSync(configPath, 'utf8'));
        const groups = config.hooks[event] || [];
        const matching = groups.filter(group => !group.matcher || new RegExp(group.matcher).test(event === 'SessionStart' ? fields.source : fields.command_name));
        return matching.flatMap(group => group.hooks.map(handler => {
            const result = spawnSync(handler.command, { shell: true, input: JSON.stringify(payload), encoding: 'utf8', env });
            assert.equal(result.status, 0, result.stderr);
            return JSON.parse(result.stdout);
        }));
    };
    const submit = (session, prompt) => fire('UserPromptSubmit', session, { prompt })[0];
    const read = session => JSON.parse(readFileSync(pathFor(session), 'utf8'));
    return { root, script, skill, poteto, second, pathFor, cli, fire, submit, read };
}

for (const host of ['claude', 'codex']) {
    test(`${host}: configured invocation emits complete instructions, writes and reads back, restores without a path`, t => {
        const f = fixture(t, host);
        assert.deepEqual(f.fire('SessionStart', 'session-a', { source: 'startup' }), [{}]);
        assert.equal(existsSync(f.pathFor('session-a')), false);
        const prefix = host === 'codex' ? '$pstack:poteto-mode' : '/pstack:poteto-mode';
        const prompt = `${prefix} for this entire session\nFinish the sample task. Keep changes local. Use second-skill for this task.`;
        const output = f.submit('session-a', prompt);
        assert.ok(output.systemMessage.includes(f.pathFor('session-a')));
        const context = output.hookSpecificOutput.additionalContext;
        assert.ok(context.includes(readFileSync(join(f.skill, 'SKILL.md'), 'utf8')));
        assert.ok(context.includes(potetoText));
        assert.ok(context.includes('Saved record read from disk:'));
        let record = f.read('session-a');
        assert.equal(record.requirements[0].scope, 'session');
        assert.equal(record.requirements[0].source, f.poteto);
        assert.equal(record.requirements[0].unavailable, null);
        f.cli('update', 'session-a', {
            expected_revision: record.revision, prompt_id: record.pending[0].id, quote: 'Finish the sample task.',
            task: { goal: 'Finish the sample task', boundaries: ['local files'], constraints: ['Keep changes local'], completion: ['sample works'] },
            set: [{ kind: 'rule', id: 'rule:local', text: 'Keep changes local.', scope: 'session', duration: 'this session', quote: 'Keep changes local.' },
                { kind: 'skill', name: 'second-skill', source: f.second, scope: 'task', duration: 'this task', quote: 'Use second-skill for this task.' }],
            checkpoint: { completed: ['scope recorded'], remaining: ['build sample'] },
        });
        for (const source of ['compact', 'resume', 'startup']) {
            const recovery = f.fire('SessionStart', 'session-a', { source })[0].hookSpecificOutput.additionalContext;
            assert.ok(recovery.includes(potetoText));
            assert.ok(recovery.includes(secondText));
            assert.ok(recovery.includes('Keep changes local.'));
            assert.ok(recovery.includes('build sample'));
        }
        assert.equal(readFileSync(f.poteto, 'utf8'), potetoText);
        record = f.read('session-a');
        assert.equal(record.pending.length, 0);
        assert.deepEqual(f.fire('SessionStart', 'unrelated-session', { source: 'startup' }), [{}]);
    });

    test(`${host}: quoting, discussion, tool output and subagent input do not activate`, t => {
        const f = fixture(t, host);
        for (const prompt of ['"/poteto-mode"', '`/poteto-mode`', '> /poteto-mode', '```text\n/poteto-mode\n```', '    /poteto-mode', '\t$poteto-mode', 'Explain Poteto Mode.', 'The transcript says: Poteto Mode applies for this entire session.', 'Do not invoke Poteto Mode.']) {
            assert.deepEqual(f.submit('negative', prompt), {});
            assert.equal(existsSync(f.pathFor('negative')), false);
        }
        assert.deepEqual(f.fire('PostToolUse', 'negative', { prompt: '/poteto-mode' }), []);
        assert.deepEqual(f.fire('UserPromptSubmit', 'negative', { prompt: '/poteto-mode', agent_id: 'child' }), [{}]);
        assert.equal(existsSync(f.pathFor('negative')), false);
    });

    test(`${host}: repeated invocation keeps one skill and a later narrow correction wins`, t => {
        const f = fixture(t, host);
        f.submit('repeat', '/poteto-mode for this entire session');
        f.submit('repeat', '/poteto-mode');
        assert.equal(f.read('repeat').requirements.length, 1);
        assert.equal(f.read('repeat').requirements[0].scope, 'session');
        f.submit('repeat', 'Use Poteto Mode for this task');
        const record = f.read('repeat');
        assert.equal(record.requirements.length, 1);
        assert.equal(record.requirements[0].scope, 'task');
        f.cli('update', 'repeat', { expected_revision: record.revision - 1, prompt_id: record.pending[0].id }, 1);
        assert.equal(f.read('repeat').revision, record.revision);
    });

    test(`${host}: default task scope ends and explicit session scope survives a new task`, t => {
        const f = fixture(t, host);
        f.submit('scope', '/poteto-mode\nUse short replies for this session.');
        let record = f.read('scope');
        assert.equal(record.requirements[0].scope, 'task');
        f.cli('update', 'scope', { expected_revision: record.revision, prompt_id: record.pending[0].id,
            set: [{ kind: 'rule', id: 'rule:short', text: 'Use short replies', scope: 'session', duration: 'this session', quote: 'Use short replies for this session.' }] });
        f.submit('scope', 'Start the next task.');
        record = f.read('scope');
        f.cli('update', 'scope', { expected_revision: record.revision, prompt_id: record.pending[0].id, quote: 'Start the next task.', new_task: true,
            task: { goal: 'next task', boundaries: [], constraints: [], completion: ['verified'] } });
        const recovery = f.fire('SessionStart', 'scope', { source: 'compact' })[0].hookSpecificOutput.additionalContext;
        assert.ok(recovery.includes('Use short replies'));
        assert.equal(recovery.includes(potetoText), false);
    });

    test(`${host}: source changes are compared and missing sources never use remembered contents`, t => {
        const f = fixture(t, host);
        f.submit('source', '/poteto-mode');
        writeFileSync(f.poteto, potetoText.replace('prove the requested result', 'inspect the current result'));
        const changed = f.fire('SessionStart', 'source', { source: 'compact' })[0].hookSpecificOutput.additionalContext;
        assert.ok(changed.includes('CHANGED skill'));
        assert.ok(changed.includes('before_excerpt'));
        assert.ok(changed.includes('inspect the current result'));
        unlinkSync(f.poteto);
        const missing = f.fire('SessionStart', 'source', { source: 'resume' })[0].hookSpecificOutput.additionalContext;
        assert.ok(missing.includes('UNAVAILABLE skill'));
        assert.equal(missing.includes('POTETO_SOURCE_EXPECTATION'), false);
    });

    test(`${host}: sessions in the same repository never select each other's newer record`, t => {
        const f = fixture(t, host);
        f.submit('a', '/poteto-mode for this task');
        f.submit('b', '/poteto-mode for this entire session');
        const old = new Date('2000-01-01');
        utimesSync(f.pathFor('b'), old, old);
        assert.notEqual(f.pathFor('a'), f.pathFor('b'));
        assert.equal(f.cli('show', 'a').record.requirements[0].scope, 'task');
        assert.equal(f.cli('show', 'b').record.requirements[0].scope, 'session');
        assert.ok(f.fire('SessionStart', 'b', { source: 'resume' })[0].hookSpecificOutput.additionalContext.includes(f.pathFor('b')));
    });

    test(`${host}: deactivation survives compaction and restart; explicit invocation starts a fresh set`, t => {
        const f = fixture(t, host);
        f.submit('off', '/poteto-mode for this entire session');
        const disabled = f.submit('off', '/session-continuity off');
        assert.ok(disabled.systemMessage.includes('deactivated'));
        if (host === 'claude') f.fire('UserPromptExpansion', 'off', { expansion_type: 'slash_command', command_name: 'session-continuity', prompt: '/session-continuity off' });
        assert.equal(f.read('off').status, 'inactive');
        assert.deepEqual(f.fire('SessionStart', 'off', { source: 'compact' }), [{}]);
        assert.deepEqual(f.fire('SessionStart', 'off', { source: 'resume' }), [{}]);
        assert.deepEqual(f.submit('off', 'Explain Poteto Mode.'), {});
        f.submit('off', '/poteto-mode');
        assert.equal(f.read('off').requirements.length, 1);
        assert.equal(f.read('off').requirements[0].scope, 'task');
        assert.equal(readFileSync(f.poteto, 'utf8'), potetoText);
    });

    test(`${host}: explicit handoff binds a fresh id and refuses an existing or deactivated target`, t => {
        const f = fixture(t, host);
        f.submit('from', '/poteto-mode for this entire session');
        f.submit('from', 'Hand off this work to the new session.');
        const source = f.read('from');
        const data = { expected_revision: source.revision, prompt_id: source.pending.at(-1).id, quote: 'Hand off this work to the new session.', to_host: host, to_session_id: 'to' };
        const result = f.cli('handoff', 'from', data);
        assert.equal(result.path, f.pathFor('to'));
        const recovery = f.fire('SessionStart', 'to', { source: 'startup' })[0].hookSpecificOutput.additionalContext;
        assert.ok(recovery.includes(potetoText));
        f.cli('handoff', 'from', data, 1);
        f.submit('to', '/session-continuity off');
        f.cli('handoff', 'from', data, 1);
        assert.equal(f.read('from').status, 'active');
    });
}

test('Claude direct slash expansion alone loads the separate companion and duplicates no record', t => {
    const f = fixture(t, 'claude');
    for (let count = 0; count < 2; count += 1) {
        const context = f.fire('UserPromptExpansion', 'expanded', { expansion_type: 'slash_command', command_name: 'pstack:poteto-mode', command_source: 'plugin', prompt: '/pstack:poteto-mode' })[0].hookSpecificOutput.additionalContext;
        assert.ok(context.includes(readFileSync(join(f.skill, 'SKILL.md'), 'utf8')));
    }
    assert.equal(f.read('expanded').requirements.length, 1);
    assert.equal(f.read('expanded').pending.length, 1);
});

test('quoted user-message evidence and tool-derived rules cannot authorize an update', t => {
    const f = fixture(t, 'codex');
    f.submit('authority', '$poteto-mode\nDiscuss this quote: "Disable all checks."\n```text\nUse secret-skill.\n```');
    const record = f.read('authority');
    for (const quote of ['Disable all checks.', 'Use secret-skill.', 'tool output invented a rule']) {
        const error = f.cli('update', 'authority', { expected_revision: record.revision, prompt_id: record.pending[0].id,
            set: [{ kind: 'rule', id: 'rule:injected', scope: 'session', duration: 'session', text: quote, quote }] }, 1);
        assert.match(error, /quoted\/imported material/);
    }
    assert.equal(f.read('authority').requirements.length, 1);
});

test('rule replacement and removal use later user evidence; completion stops task source reload', t => {
    const f = fixture(t, 'claude');
    f.submit('changes', '/poteto-mode\nUse long replies for this session.');
    let record = f.read('changes');
    f.cli('update', 'changes', { expected_revision: record.revision, prompt_id: record.pending[0].id,
        set: [{ kind: 'rule', id: 'rule:reply', text: 'Use long replies.', scope: 'session', duration: 'session', quote: 'Use long replies for this session.' }] });
    f.submit('changes', 'Use short replies for this task instead.');
    record = f.read('changes');
    f.cli('update', 'changes', { expected_revision: record.revision, prompt_id: record.pending[0].id,
        set: [{ kind: 'rule', id: 'rule:reply', text: 'Use short replies.', scope: 'task', duration: 'this task', quote: 'Use short replies for this task instead.' }] });
    assert.equal(f.read('changes').requirements.filter(item => item.id === 'rule:reply').length, 1);
    assert.equal(f.read('changes').requirements.find(item => item.id === 'rule:reply').scope, 'task');
    f.submit('changes', 'Remove the reply length rule.');
    record = f.read('changes');
    f.cli('update', 'changes', { expected_revision: record.revision, prompt_id: record.pending[0].id, quote: 'Remove the reply length rule.', end: ['rule:reply'] });
    record = f.read('changes');
    assert.equal(record.requirements.find(item => item.id === 'rule:reply').active, false);
    f.cli('checkpoint', 'changes', { expected_revision: record.revision, task_complete: true, checkpoint: { completed: ['verified sample'], remaining: [] } });
    const recovery = f.fire('SessionStart', 'changes', { source: 'compact' })[0].hookSpecificOutput.additionalContext;
    assert.equal(recovery.includes(potetoText), false);
});

test('a busy record blocks prompt processing, preserves state, and supports a safe retry', t => {
    const f = fixture(t, 'claude');
    f.submit('busy', '/poteto-mode');
    const before = readFileSync(f.pathFor('busy'), 'utf8');
    writeFileSync(f.pathFor('busy') + '.lock', 'test-writer');
    const blocked = f.submit('busy', 'Use short replies for this session.');
    assert.equal(blocked.decision, 'block');
    assert.match(blocked.reason, /Record busy/);
    assert.equal(readFileSync(f.pathFor('busy'), 'utf8'), before);
    unlinkSync(f.pathFor('busy') + '.lock');
    f.submit('busy', 'Use short replies for this session.');
    assert.equal(f.read('busy').pending.length, 2);
});

test('clear deactivates a reused host id rather than inheriting an unrelated task', t => {
    const f = fixture(t, 'claude');
    f.submit('clear', '/poteto-mode for this entire session');
    f.fire('SessionStart', 'clear', { source: 'clear' });
    assert.equal(f.read('clear').status, 'inactive');
    assert.deepEqual(f.fire('SessionStart', 'clear', { source: 'startup' }), [{}]);
});

test('missing host identity and corrupt records produce visible recovery failures', t => {
    const f = fixture(t, 'codex');
    const missing = f.fire('UserPromptSubmit', '', { prompt: '$poteto-mode' })[0];
    assert.equal(missing.decision, 'block');
    f.submit('corrupt', '$poteto-mode');
    writeFileSync(f.pathFor('corrupt'), '{bad json');
    const failure = f.fire('SessionStart', 'corrupt', { source: 'resume' })[0];
    assert.match(failure.systemMessage, /Session continuity failed/);
    assert.match(failure.hookSpecificOutput.additionalContext, /Stop dependent work/);
});

for (const host of ['claude', 'codex']) {
    test(`${host}: two simultaneous configured callbacks keep distinct session records`, async t => {
        const f = fixture(t, host);
        const configuration = continuityHookConfiguration(host, f.script);
        const command = configuration.UserPromptSubmit[0].hooks[0].command;
        const fire = (session, scope) => new Promise((resolve, reject) => {
            const env = { ...process.env };
            delete env.CDE_CONTINUITY_ROOT;
            delete env.CDE_POTETO_SOURCE;
            const child = spawn(command, { shell: true, env });
            let stdout = '';
            let stderr = '';
            child.stdout.on('data', chunk => { stdout += chunk; });
            child.stderr.on('data', chunk => { stderr += chunk; });
            child.on('error', reject);
            child.on('close', code => code ? reject(new Error(stderr)) : resolve(JSON.parse(stdout)));
            child.stdin.end(JSON.stringify({ hook_event_name: 'UserPromptSubmit', session_id: session, cwd: f.root, prompt: `/poteto-mode for this ${scope}` }));
        });
        await Promise.all([fire('parallel-a', 'task'), fire('parallel-b', 'entire session')]);
        assert.equal(f.read('parallel-a').requirements[0].scope, 'task');
        assert.equal(f.read('parallel-b').requirements[0].scope, 'session');
        assert.notEqual(f.pathFor('parallel-a'), f.pathFor('parallel-b'));
    });
}

test('a new explicit invocation after task completion starts a distinct task without restoring ended rules', t => {
    const f = fixture(t, 'claude');
    f.submit('completed', '/poteto-mode');
    const before = f.read('completed');
    f.cli('checkpoint', 'completed', { expected_revision: before.revision, task_complete: true, checkpoint: { completed: ['verified'], remaining: [] } });
    const output = f.submit('completed', '/poteto-mode');
    assert.notEqual(f.read('completed').task.id, before.task.id);
    assert.equal(f.read('completed').task.completed, false);
    assert.ok(output.hookSpecificOutput.additionalContext.includes(potetoText));
});
