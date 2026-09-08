import test from 'node:test';
import assert from 'node:assert/strict';
import { runInstaller } from './install-with-pstack.mjs';

test('full installer preserves original arguments and installs each selected profile', async () => {
    const calls = [];
    const status = await runInstaller(['--profiles', 'alpha,beta'], {
        runBase: args => { calls.push(['base', args]); return { status: 0 }; },
        selectedRoots: async () => ['/profiles/alpha', '/profiles/beta'],
        install: options => { calls.push(['pstack', options.root]); return { commit: 'test', status: 'installed' }; },
    });
    assert.equal(status, 0);
    assert.deepEqual(calls, [['base', ['--profiles', 'alpha,beta']], ['pstack', '/profiles/alpha'], ['pstack', '/profiles/beta']]);
});

test('base installer failure leaves pstack untouched', async () => {
    assert.equal(await runInstaller([], {
        runBase: () => ({ status: 7 }),
        selectedRoots: () => assert.fail('roots resolved after base failure'),
        install: () => assert.fail('pstack ran after base failure'),
    }), 7);
});

test('management commands with no install roots leave pstack untouched', async () => {
    assert.equal(await runInstaller(['--help'], {
        runBase: args => { assert.deepEqual(args, ['--help']); return { status: 0 }; },
        selectedRoots: () => [],
        install: () => assert.fail('unexpected install'),
    }), 0);
});

test('first pstack install failure is visible to the package caller', async () => {
    await assert.rejects(runInstaller([], {
        runBase: () => ({ status: 0 }), selectedRoots: () => ['/profile'],
        install: () => { throw new Error('source unavailable'); },
    }), /source unavailable/);
});
