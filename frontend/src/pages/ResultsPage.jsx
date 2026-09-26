import { useCallback, useEffect, useRef, useState } from 'react';
import { finalizeInterview, getInterviewSession, getIntegrityEvents } from '../services/api';
import CandidateEvidenceMap, { displayLabel, EvidenceReferences, EvidenceStatements } from '../components/CandidateEvidenceMap';
import InterviewTranscript from '../components/InterviewTranscript';
import IntegrityTimeline from '../components/IntegrityTimeline';

function Comparison({ item, practice, onTurn }) {
  if (!item) return <p>{practice ? 'Teach → new challenge was not used.' : 'Changed-condition challenge was not assessed.'}</p>;
  return <article><div className="comparison"><div><h3>{practice ? 'First attempt' : 'Original approach'}</h3><p className="answer-text">{practice ? item.first_attempt : item.original_approach}</p></div><div><h3>{practice ? 'Quick coaching' : 'Changed condition'}</h3><p>{practice ? item.teaching_note : item.changed_condition}</p></div><div><h3>{practice ? 'New challenge' : 'Revised approach'}</h3>{practice && <p>{item.new_question}</p>}<p className="answer-text">{practice ? item.second_attempt : item.revised_approach}</p></div></div><h3>{practice ? 'Observed change' : 'Adaptation evidence'}</h3><p>{item.interpretation}</p><EvidenceReferences turns={[item.original_turn, item.challenge_turn]} onTurn={onTurn} /></article>;
}

export default function ResultsPage({ interviewId }) {
  const [session, setSession] = useState(null), [report, setReport] = useState(null);
  const [events, setEvents] = useState([]), [eventError, setEventError] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [tab, setTab] = useState('evidence');
  const mounted = useRef(false), loading = useRef(false);
  const refreshEvents = useCallback(async () => {
    try { const data = await getIntegrityEvents(interviewId); if (mounted.current) { setEvents(data); setEventError(''); } }
    catch (failure) { if (mounted.current) setEventError(failure.message); }
  }, [interviewId]);
  const load = useCallback(async () => {
    if (loading.current) return;
    loading.current = true; setBusy(true); setError('');
    try {
      const data = await getInterviewSession(interviewId);
      if (mounted.current) setSession(data);
      if (data.completed) {
        const result = await finalizeInterview(interviewId);
        if (mounted.current) setReport(result.report);
      }
    } catch (failure) { if (mounted.current) setError(failure.message); }
    finally { loading.current = false; if (mounted.current) setBusy(false); }
  }, [interviewId]);
  useEffect(() => {
    mounted.current = true; load(); refreshEvents();
    return () => { mounted.current = false; };
  }, [load, refreshEvents]);
  const practice = session?.mode === 'practice';
  function onTurn(number) {
    setTab('transcript');
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const node = document.getElementById(`turn-${number}`);
      node?.scrollIntoView({ behavior: 'smooth', block: 'center' }); node?.focus({ preventScroll: true });
    }));
  }
  const tabs = [['evidence', practice ? 'Skill evidence' : 'Evidence Map'], ...(!practice ? [['claims', 'Resume Claims']] : []), ['adaptation', 'Adaptation'], ...(practice ? [['coaching', 'Teach → New Challenge']] : []), ['integrity', practice ? 'Behaviour feedback' : 'Integrity'], ['transcript', 'Transcript']];
  return <><header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><a href="#history">Saved interviews</a></header><main className="results-main"><div className="intro"><p className="eyebrow">INTERVIEW #{interviewId} · {session?.status || 'LOADING'}</p><h1>{practice ? 'Mock Interview Results' : 'Candidate Interview Report'}</h1><p>{session?.job_title}</p><p>{practice ? 'Use this evidence to plan your next practice session.' : 'AI-generated interview evidence supports human review. The recruiter makes the final decision.'}</p></div>{busy && <p className="loading" role="status">Analyzing interview evidence, mapping relevant answers and preparing your report. Transcript and observations remain available below.</p>}{error && <div className="error" role="alert">{error}<div><button className="secondary" disabled={busy} onClick={load}>Retry report generation</button></div></div>}{session && !session.completed && <p className="loading">Complete the interview to generate results. <a href={`#interview/${interviewId}`}>Continue interview</a></p>}{report && <section className="card report-summary"><h2>{practice ? 'Your progress' : 'Evidence summary'}</h2><EvidenceStatements items={report.summary} onTurn={onTurn} /><div className="mode-grid"><div><h3>{practice ? 'Your strengths' : 'Strengths observed'}</h3><EvidenceStatements items={report.strengths} onTurn={onTurn} /></div><div><h3>{practice ? 'Areas to improve' : 'Areas requiring follow-up'}</h3><EvidenceStatements items={report.gaps} onTurn={onTurn} /></div></div></section>}<nav className="report-tabs" aria-label="Report sections">{tabs.map(([id, label]) => <button key={id} className={tab === id ? 'primary' : 'secondary'} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</nav>{tab === 'transcript' && (session ? <InterviewTranscript turns={session.turns} practice={practice} /> : <p>Loading transcript…</p>)}{tab === 'integrity' && <IntegrityTimeline events={events} practice={practice} error={eventError} onRefresh={refreshEvents} />}{!report && !['transcript', 'integrity'].includes(tab) && <section className="card"><p>{busy ? 'Report preparation is in progress.' : 'Report not available yet.'} You can inspect the transcript and integrity observations independently.</p></section>}{report && tab === 'evidence' && <><CandidateEvidenceMap skills={report.skill_evidence} onTurn={onTurn} practice={practice} /><section className="card"><h2>{practice ? 'Practice recommendations' : 'Suggested follow-up questions'}</h2><EvidenceStatements items={practice ? report.practice_recommendations : report.areas_for_follow_up} onTurn={onTurn} /></section></>}{report && tab === 'claims' && !practice && <section className="card"><h2>Resume claim → interview evidence → remaining gap</h2><p className="field-help">Relevant answers were retrieved by semantic similarity. An explanation does not independently verify an external claim.</p>{report.resume_claims.length ? report.resume_claims.map((claim, index) => <article className="claim-card" key={index}><p className="eyebrow">{claim.claim_type.replaceAll('_', ' ')} · {claim.related_skill}</p><h3>{claim.claim_text}</h3><span className="chip">{displayLabel(claim.status)}</span><p>{claim.evidence}</p><EvidenceReferences turns={claim.supporting_turns} onTurn={onTurn} /><p><strong>Remaining gap:</strong> {claim.remaining_gap}</p></article>) : <p>No suitable job-relevant claims were extracted.</p>}</section>}{report && tab === 'adaptation' && <section className="card"><h2>Reasoning under changed conditions</h2><Comparison item={report.adaptation_evidence} onTurn={onTurn} /></section>}{report && tab === 'coaching' && practice && <section className="card"><h2>Teach → New Challenge</h2><Comparison item={report.practice_improvement} practice onTurn={onTurn} /></section>}<p className="field-help"><a href={`#interview/${interviewId}`}>Return to interview and add observation explanations</a></p></main></>;
}
