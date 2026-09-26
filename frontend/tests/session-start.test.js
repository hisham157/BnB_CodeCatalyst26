import test from 'node:test';
import assert from 'node:assert/strict';
import { startInterview } from '../src/services/api.js';

test('overlapping start waits for saved session and shares the request', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => url.endsWith('/start') ? { status: 'starting' } : { status: 'in_progress', current_turn: { turn_number: 1 } } };
  };
  try {
    const first = startInterview(123);
    assert.equal(startInterview(123), first);
    assert.equal((await first).current_turn.turn_number, 1);
    assert.equal(calls.length, 2);
    assert.ok(calls[1].endsWith('/session'));
  } finally { globalThis.fetch = original; }
});

test('failed start can be retried instead of caching rejection', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('offline'); };
  try {
    await assert.rejects(startInterview(456), /Cannot reach/);
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ status: 'in_progress' }) });
    assert.equal((await startInterview(456)).status, 'in_progress');
  } finally { globalThis.fetch = original; }
});
