import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { finalizeInterview } from '../src/services/api.js';

// Render the actual JSX components without a camera, browser or extra test framework.
const bundle = await build({ stdin: { contents: `
  import React from 'react';
  import { renderToStaticMarkup } from 'react-dom/server';
  import InterviewTranscript from './src/components/InterviewTranscript.jsx';
  import CandidateEvidenceMap from './src/components/CandidateEvidenceMap.jsx';
  import IntegrityTimeline from './src/components/IntegrityTimeline.jsx';
  export const transcript = (props) => renderToStaticMarkup(<InterviewTranscript {...props} />);
  export const evidence = (props) => renderToStaticMarkup(<CandidateEvidenceMap {...props} />);
  export const timeline = (props) => renderToStaticMarkup(<IntegrityTimeline {...props} />);
`, resolveDir: process.cwd(), loader: 'jsx' }, bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', write: false });
const module = { exports: {} };
new Function('require', 'module', 'exports', bundle.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
const render = module.exports;

test('transcript renders normal and challenge turns, hides teaching from recruiter', () => {
  const turns = [
    { turn_number: 1, question: 'Original question', answer_text: 'Original answer', skill: 'Analysis' },
    { turn_number: 2, question: 'Revised question', answer_text: 'Revised answer', skill: 'Analysis', turn_type: 'CHANGE_CONSTRAINT', changed_condition: 'Budget is fixed.' },
    { turn_number: 3, question: 'New application', answer_text: null, skill: 'Analysis', turn_type: 'TEACH_NEW_CHALLENGE', teaching_note: 'Subtract costs.' },
  ];
  const recruiter = render.transcript({ turns, practice: false });
  assert.match(recruiter, /Original answer/);
  assert.match(recruiter, /Budget is fixed/);
  assert.doesNotMatch(recruiter, /Subtract costs/);
  assert.match(render.transcript({ turns, practice: true }), /Subtract costs/);
});

test('evidence map exposes labels and why, including old unassessed skills', () => {
  const html = render.evidence({ skills: [{ skill: 'Leadership', evidence_level: 0, label: 'NOT_ASSESSED', why: 'Not sufficiently assessed.', remaining_gap: 'Ask more questions.', supporting_turns: [] }], onTurn() {} });
  assert.match(html, /Leadership: Not assessed/);
  assert.match(html, /Why\?/);
  assert.doesNotMatch(html, /class="filled"/);
});

test('integrity timeline preserves candidate explanation and unknown duration', () => {
  const html = render.timeline({ events: [{ id: 1, event_type: 'MONITORING_UNAVAILABLE', started_at_seconds: 62, duration_seconds: null, ended_at_seconds: null, occurrence_number: 1, candidate_explanation: 'Permission denied.', metadata: {} }], onRefresh() {} });
  assert.match(html, /01:02/);
  assert.match(html, /not measured/);
  assert.match(html, /Permission denied/);
});

test('cached report does not finalize; concurrent report loads share one request', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(url); return { ok: true, json: async () => ({ report: { mode: 'recruiter' } }) }; };
  try {
    const result = finalizeInterview(77);
    assert.equal(finalizeInterview(77), result);
    assert.equal((await result).report.mode, 'recruiter');
    assert.equal(calls.length, 1);
    assert.ok(calls[0].endsWith('/report'));
  } finally { globalThis.fetch = original; }
});

test('missing report generates once and errors remain retryable', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return url.endsWith('/report') ? { ok: false, status: 404, json: async () => ({ detail: 'Not generated' }) } : { ok: true, json: async () => ({ report: { mode: 'practice' } }) };
  };
  try {
    assert.equal((await finalizeInterview(88)).report.mode, 'practice');
    assert.equal(calls.length, 2);
    globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Unavailable' }) });
    await assert.rejects(finalizeInterview(99), /Unavailable/);
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ report: {} }) });
    await finalizeInterview(99);
  } finally { globalThis.fetch = original; }
});
