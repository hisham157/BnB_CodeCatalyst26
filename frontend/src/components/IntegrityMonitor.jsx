import { useCallback, useEffect, useRef, useState } from 'react';
import useFaceLandmarker from '../hooks/useFaceLandmarker';
import { createIntegrityTracker } from '../services/integrityState';
import { createIntegrityEvent, getIntegrityEvents, addIntegrityExplanation } from '../services/api';

const labels = { LOOKING_AWAY: 'Head turned away', FACE_MISSING: 'Face not detected', MULTIPLE_FACES: 'Multiple faces detected', MONITORING_UNAVAILABLE: 'Monitoring unavailable' };

function Explanation({ event, interviewId, onSaved }) {
  const [text, setText] = useState(event.candidate_explanation || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    setBusy(true); setError('');
    try { onSaved(await addIntegrityExplanation(interviewId, event.id, text)); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <article className="observation"><strong>{labels[event.event_type]} · #{event.occurrence_number}</strong><p>{event.duration_seconds === null ? 'Duration not measured' : `${event.duration_seconds.toFixed(1)} sec`} · {event.started_at_seconds.toFixed(1)} sec from monitoring start{event.turn_number ? ` · Q${event.turn_number}` : ''}</p>{event.metadata.reason && <p>{event.metadata.reason.replaceAll('_', ' ').toLowerCase()}</p>}<label htmlFor={`explanation-${event.id}`}>Your explanation (optional)</label><textarea id={`explanation-${event.id}`} rows="2" maxLength={2000} value={text} disabled={busy} onChange={(e) => setText(e.target.value)} /><button type="button" className="secondary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save explanation'}</button>{error && <p role="alert">{error}</p>}</article>;
}

export default function IntegrityMonitor({ interviewId, turnNumber, completed, mode }) {
  const video = useRef(null);
  const turn = useRef(turnNumber); turn.current = turnNumber;
  const [enabled, setEnabled] = useState(true);
  const [events, setEvents] = useState([]);
  const [syncError, setSyncError] = useState('');
  const [pendingCount, setPendingCount] = useState(0);
  const queue = useRef([]), sending = useRef(false), mounted = useRef(true);
  const sessionId = useRef(crypto.randomUUID());
  const unavailable = useRef(null);
  const clock = useRef(null);
  const storageKey = `integrity-pending-${interviewId}`;
  if (!clock.current) {
    let started = Date.now();
    try { started = Number(sessionStorage.getItem(`integrity-start-${interviewId}`)) || started; sessionStorage.setItem(`integrity-start-${interviewId}`, String(started)); queue.current = JSON.parse(sessionStorage.getItem(storageKey) || '[]'); } catch { /* Memory-only fallback if storage is blocked. */ }
    clock.current = { offset: Math.max(0, Date.now() - started), origin: performance.now() };
  }
  const now = useCallback(() => clock.current.offset + performance.now() - clock.current.origin, []);
  const persist = useCallback(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify(queue.current)); } catch { /* Uploads still work without browser storage. */ }
    if (mounted.current) setPendingCount(queue.current.length);
  }, [storageKey]);
  const drain = useCallback(async () => {
    if (sending.current) return;
    sending.current = true;
    try {
      while (queue.current.length) {
        const stored = await createIntegrityEvent(interviewId, queue.current[0]);
        queue.current.shift(); persist();
        if (mounted.current) { setEvents((items) => [...items.filter((item) => item.id !== stored.id), stored].sort((a, b) => a.started_at_seconds - b.started_at_seconds)); setSyncError(''); }
      }
    } catch { if (mounted.current) setSyncError('Observation upload pending. Keep this page open or retry; your interview can continue.'); }
    finally { sending.current = false; }
  }, [interviewId, persist]);
  const emit = useCallback((event) => {
    queue.current.push({ ...event, client_event_id: crypto.randomUUID(), metadata: { ...event.metadata, session_id: sessionId.current } });
    persist(); drain();
  }, [persist, drain]);
  const tracker = useRef(null);
  if (!tracker.current) tracker.current = createIntegrityTracker(emit);
  const fail = useCallback((reason) => {
    tracker.current.flush(now(), reason === 'PAGE_HIDDEN' ? 'page_hidden' : 'unavailable');
    if (unavailable.current?.metadata.reason === reason) return;
    // Store the onset immediately, with unknown duration, so permanent permission denial is visible.
    emit({ event_type: 'MONITORING_UNAVAILABLE', turn_number: turn.current ?? null, started_at_seconds: now() / 1000, metadata: { reason, monitoring_quality: 'unavailable' } });
    unavailable.current = { metadata: { reason } };
  }, [now, emit]);
  // Availability episodes are onset observations; no synthetic duration is assigned.
  const observe = useCallback((observation) => {
    unavailable.current = null;
    tracker.current.update(observation, now(), turn.current);
  }, [now]);
  const active = enabled && !completed;
  const monitor = useFaceLandmarker(video, active, observe, fail);
  const refresh = useCallback(() => {
    return getIntegrityEvents(interviewId).then((items) => { if (mounted.current) { setEvents((previous) => [...new Map([...items, ...previous].map((item) => [item.id, item])).values()].sort((a, b) => a.started_at_seconds - b.started_at_seconds)); setSyncError(''); } }).catch(() => { if (mounted.current) setSyncError('Could not load saved observations. Retry when the backend is available.'); });
  }, [interviewId]);

  useEffect(() => {
    mounted.current = true;
    refresh();
    drain();
    const interval = setInterval(drain, 10000);
    const leaving = () => { tracker.current.flush(now()); persist(); drain(); };
    window.addEventListener('pagehide', leaving);
    return () => { tracker.current.flush(now()); mounted.current = false; clearInterval(interval); window.removeEventListener('pagehide', leaving); persist(); drain(); };
  }, [refresh, drain, now, persist]);
  useEffect(() => { if (!active) tracker.current.flush(now()); }, [active, now]);

  function stopMonitoring() { fail('MONITORING_STOPPED'); setEnabled(false); }
  function retry() { tracker.current.flush(now()); unavailable.current = null; setEnabled(true); if (enabled) monitor.retry(); }
  function saved(event) { setEvents((items) => items.map((item) => item.id === event.id ? event : item)); }
  return <section className="card integrity-card"><h2>Integrity Monitoring</h2><p role="status">{completed ? 'Stopped · Interview completed' : monitor.status}</p><video ref={video} autoPlay playsInline muted className="webcam-preview" hidden={!active} /><p className="field-help">Camera processing stays in this browser. Only observation metadata is saved. Events do not determine cheating or affect answer scores.</p>{!completed && <div className="voice-controls"><button type="button" className="secondary" onClick={retry}>Retry / Recalibrate</button><button type="button" className="secondary" disabled={!enabled} onClick={stopMonitoring}>Stop Camera</button></div>}{import.meta.env.VITE_INTEGRITY_DEBUG === 'true' && <pre>{JSON.stringify(monitor.debug, null, 2)}</pre>}{syncError && <p role="status" className="error">{syncError}<button type="button" className="secondary" onClick={async () => { await refresh(); drain(); }}>Retry uploads ({pendingCount})</button></p>}<details open={completed}><summary>Review observations ({events.length})</summary><p className="field-help">{mode === 'practice' ? 'Practice observations for your review.' : 'Add context for the recruiter here or after completion.'} Explanations do not change the observation.</p>{events.map((event) => <Explanation key={event.id} event={event} interviewId={interviewId} onSaved={saved} />)}{!events.length && <p>No saved observations yet.</p>}</details></section>;
}
