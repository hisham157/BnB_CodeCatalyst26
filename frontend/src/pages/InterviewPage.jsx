import { useEffect, useRef, useState } from 'react';
import { getInterviewSession, startInterview, submitAnswer } from '../services/api';
import useAudioRecorder from '../hooks/useAudioRecorder';
import useSpeechSynthesis from '../hooks/useSpeechSynthesis';
import IntegrityMonitor from '../components/IntegrityMonitor';
import { SpecialTurn } from '../components/InterviewTranscript';

export default function InterviewPage({ interviewId, voiceEnabled = false }) {
  const [session, setSession] = useState(null);
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const starting = useRef(null);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [speechAllowed, setSpeechAllowed] = useState(voiceEnabled);
  const [activity, setActivity] = useState('Generating interview plan and first question…');
  const spokenQuestion = useRef(null);
  const speech = useSpeechSynthesis();
  const audio = useAudioRecorder(interviewId, (text) => {
    setAnswer((draft) => draft.trim() ? `${draft.trim()}\n${text}` : text);
  });
  const current = session?.current_turn;
  const spokenText = current ? [current.changed_condition, session?.mode === 'practice' ? current.teaching_note : null, current.question].filter(Boolean).join(' ') : '';
  const { speak, stop: stopSpeech } = speech;

  useEffect(() => {
    if (current && autoSpeak && speechAllowed && !audio.busy && !busy && spokenQuestion.current !== current.turn_number) {
      spokenQuestion.current = current.turn_number;
      speak(spokenText);
    }
  }, [current, spokenText, autoSpeak, speechAllowed, audio.busy, busy, speak]);

  useEffect(() => {
    if (session?.completed) stopSpeech();
  }, [session?.completed, stopSpeech]);

  function speakQuestion() {
    setSpeechAllowed(true);
    spokenQuestion.current = current.turn_number;
    speak(spokenText);
  }

  function record() {
    stopSpeech();
    setSpeechAllowed(true);
    spokenQuestion.current = current.turn_number;
    audio.start();
  }

  async function load() {
    if (audio.busy || busy) return;
    stopSpeech();
    setBusy(true);
    setActivity('Loading saved interview / generating the first question…');
    setError('');
    try {
      let data = await getInterviewSession(interviewId);
      if (data.status === 'created') data = await startInterview(interviewId);
      if (session?.current_turn?.turn_number !== data.current_turn?.turn_number) setAnswer('');
      setSession(data);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    let active = true;
    setBusy(true);
    // Share initialization across React StrictMode's development effect replay.
    starting.current ||= getInterviewSession(interviewId).then((data) =>
      data.status === 'created' ? startInterview(interviewId) : data);
    starting.current.then((data) => { if (active) setSession(data); })
      .catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) { setBusy(false); starting.current = null; } });
    return () => { active = false; };
  }, [interviewId]);

  async function submit(event) {
    event.preventDefault();
    if (busy || audio.busy) return;
    if (!answer.trim()) { setError('Enter an answer before submitting.'); return; }
    setBusy(true);
    stopSpeech();
    setSpeechAllowed(true);
    setActivity('Evaluating answer and generating the next question…');
    setError('');
    try {
      setSession(await submitAnswer(interviewId, answer.trim(), session.current_turn.turn_number));
      audio.cancel();
      setAnswer('');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  const answered = session?.turns.filter((turn) => turn.answer_text !== null) || [];
  const hint = answered.at(-1)?.practice_feedback;
  return (
    <>
      <header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><span className="phase-badge">{session?.mode === 'practice' ? 'PRACTICE INTERVIEW' : 'INTERVIEW SESSION'}</span></header>
      <main className="session-main">
        <div className="intro"><p className="eyebrow">INTERVIEW #{interviewId}</p><h1>{session?.job_title || 'Preparing your interview'}</h1><p>Your progress is saved. Keep this page’s URL to return to this session.</p></div>
        {busy && <p role="status" className="loading">{activity}</p>}
        {error && <div className="error" role="alert">{error}<div><button className="secondary" disabled={busy || audio.busy} onClick={load}>Reload / Retry Session</button></div></div>}
        {hint && session?.mode === 'practice' && <div className="feedback" role="status"><strong>Improvement:</strong> {hint}</div>}
        <div className="interview-layout"><div>
        {session?.completed ? <section className="card"><span className="success-icon">✓</span><h2>Interview Complete</h2><p>All {session.max_questions} answers have been saved.</p><a href={`#results/${interviewId}`} className="primary action-link">{session.mode === 'practice' ? 'View Practice Feedback' : 'View Candidate Report'}</a><p><a href="#">Back to home</a></p></section> : current && (
          <form className="card" onSubmit={submit}>
            <div className="question-meta"><span>Question {current.turn_number} of {session.max_questions}</span><span>{current.skill}</span><span>Difficulty {current.difficulty}/5</span></div>
            <SpecialTurn turn={current} practice={session.mode === 'practice'} />
            <h2 className="question">{current.question}</h2>
            <div className="voice-controls">
              <button type="button" className="secondary" disabled={!speech.supported || busy || audio.busy} onClick={speakQuestion}>Speak Question</button>
              <button type="button" className="secondary" disabled={!speech.supported} onClick={stopSpeech}>Stop Speech</button>
              <label className="toggle"><input type="checkbox" checked={autoSpeak} disabled={!speech.supported} onChange={(event) => { setAutoSpeak(event.target.checked); setSpeechAllowed(true); if (!event.target.checked) stopSpeech(); }} />Auto-speak questions</label>
            </div>
            {!speech.supported && <p className="field-help">Speech playback is unavailable in this browser. Read the question and continue.</p>}
            {speech.error && <p className="field-help" role="status">{speech.error}</p>}
            <label htmlFor="answer">Your answer / editable transcript</label>
            <div className="recording-panel">
              <div className="voice-controls">
                <button type="button" className="primary" disabled={!audio.supported || busy || audio.busy} onClick={record}>Start Recording</button>
                <button type="button" className="secondary" disabled={audio.state !== 'recording'} onClick={audio.stop}>Stop Recording</button>
                {audio.busy && <button type="button" className="secondary" onClick={audio.cancel}>Cancel</button>}
              </div>
              <p role="status" className={audio.state === 'recording' ? 'recording-status' : 'field-help'}>
                {audio.state === 'requesting_permission' ? 'Waiting for microphone permission…'
                  : audio.state === 'recording' ? `Listening… ${String(Math.floor(audio.seconds / 60)).padStart(2, '0')}:${String(audio.seconds % 60).padStart(2, '0')}`
                  : audio.state === 'processing' ? 'Transcribing… Your recording is processed locally; the first model load can take a few minutes.'
                  : audio.state === 'ready' ? 'Transcript ready. Review and correct it before submitting.'
                  : 'Speak for up to 3 minutes, or type below. Recording adds text to your current draft.'}
              </p>
              {!audio.supported && <p className="field-help">Voice recording is unavailable in this browser. You can continue using text.</p>}
              {audio.error && <p className="error" role="alert">{audio.error}</p>}
            </div>
            <textarea id="answer" rows="7" maxLength={20000} disabled={busy || audio.busy} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Type an answer or record one above. Review the transcript before submitting." />
            <div className="form-footer"><p>Raw audio is temporary. Only submitted text is saved.</p><button className="primary" disabled={busy || audio.busy} type="submit">{busy ? 'Evaluating…' : 'Submit Answer'}</button></div>
          </form>
        )}
        {session?.plan_summary && <p className="field-help home-note">Interview focus: {session.plan_summary.focus_skills.join(' · ')}</p>}
        </div><aside className="session-sidebar">
        {session && <IntegrityMonitor interviewId={interviewId} turnNumber={current?.turn_number ?? answered.at(-1)?.turn_number} completed={session.completed} mode={session.mode} />}
        {session && <section className="card"><h2>Interview progress</h2><p>{answered.length} of {session.max_questions} answers submitted</p><progress value={answered.length} max={session.max_questions} aria-label="Interview progress" />{current && <p>Current skill: <strong>{current.skill}</strong><br />Difficulty: {current.difficulty}/5</p>}<p>Voice is optional. You can type throughout the interview.</p></section>}
        {!!answered.length && <section className="card transcript"><h2>Conversation so far</h2>{answered.map((turn) => <article key={turn.turn_number}><p><strong>Q{turn.turn_number}</strong> {turn.question}</p><p className="answer-text"><strong>A{turn.turn_number}</strong> {turn.answer_text}</p></article>)}</section>}
        </aside></div>
      </main>
    </>
  );
}
