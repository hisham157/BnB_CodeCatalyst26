import test from 'node:test';
import assert from 'node:assert/strict';
import { createIntegrityTracker } from '../src/services/integrityState.js';
import { orientationScore } from '../src/services/integrityConfig.js';

const normal = { faceCount: 1, orientationScore: 0 };
const away = { faceCount: 1, orientationScore: 2 };
const missing = { faceCount: 0, orientationScore: null };
const multiple = { faceCount: 2, orientationScore: 2 };

function setup() {
  const events = [];
  return { events, tracker: createIntegrityTracker((event) => events.push(event)) };
}
function hold(tracker, state, from, until, turn = 1) {
  for (let time = from; time <= until; time += 200) tracker.update(state, time, turn);
}

test('short glance and brief tracking loss produce no events', () => {
  const { events, tracker } = setup();
  hold(tracker, away, 0, 400); hold(tracker, normal, 600, 1200);
  hold(tracker, missing, 1400, 2000); hold(tracker, normal, 2200, 2800);
  tracker.flush(3000); assert.equal(events.length, 0);
});

for (const [state, type] of [[away, 'LOOKING_AWAY'], [missing, 'FACE_MISSING'], [multiple, 'MULTIPLE_FACES']]) {
  test(`sustained ${type} creates one event on stable recovery`, () => {
    const { events, tracker } = setup();
    hold(tracker, state, 0, 3000, 2);
    assert.equal(events.length, 0);
    hold(tracker, normal, 3200, 4000, 3);
    assert.equal(events.length, 1);
    assert.equal(events[0].event_type, type);
    assert.equal(events[0].turn_number, 2);
    assert.equal(events[0].duration_seconds, 3.2);
    tracker.flush(5000); assert.equal(events.length, 1);
  });
}

test('brief recovery merges a sustained episode rather than duplicating it', () => {
  const { events, tracker } = setup();
  hold(tracker, away, 0, 1800);
  tracker.update(normal, 2000, 1);
  hold(tracker, away, 2200, 3000);
  hold(tracker, normal, 3200, 3800);
  assert.equal(events.length, 1);
});

test('separate sustained episodes generate separate observations', () => {
  const { events, tracker } = setup();
  hold(tracker, away, 0, 1800); hold(tracker, normal, 2000, 2600);
  hold(tracker, away, 2800, 4600); hold(tracker, normal, 4800, 5400);
  assert.equal(events.length, 2);
});

test('completion flushes one confirmed event and discards brief candidates', () => {
  const { events, tracker } = setup();
  hold(tracker, missing, 0, 2400); tracker.flush(2500);
  assert.equal(events.length, 1); assert.equal(events[0].duration_seconds, 2.4);
  hold(tracker, away, 2600, 3000); tracker.flush(3100);
  assert.equal(events.length, 1);
});

test('sampling gaps are not inferred as sustained behavior', () => {
  const { events, tracker } = setup();
  tracker.update(away, 0, 1); tracker.update(away, 10000, 1);
  tracker.update(normal, 10200, 1); tracker.flush(10400);
  assert.equal(events.length, 0);
});

test('missing and multiple faces never produce a looking-away observation', () => {
  const { events, tracker } = setup();
  hold(tracker, multiple, 0, 2000); hold(tracker, missing, 2200, 4800);
  hold(tracker, normal, 5000, 5600);
  assert.deepEqual(events.map((event) => event.event_type), ['MULTIPLE_FACES', 'FACE_MISSING']);
});

test('orientation score is relative, symmetric, and unavailable before calibration', () => {
  const baseline = { horizontal: 0, vertical: 0.2 };
  assert.equal(orientationScore(baseline, baseline), 0);
  assert.equal(orientationScore(baseline, null), null);
  assert.equal(orientationScore({ horizontal: 0.44, vertical: 0.2 }, baseline), 2);
  assert.equal(orientationScore({ horizontal: -0.44, vertical: 0.2 }, baseline), 2);
});
