import { useEffect, useState } from 'react';
import RecruiterSetupPage from './pages/RecruiterSetupPage';
import CandidatePracticeSetupPage from './pages/CandidatePracticeSetupPage';
import InterviewPage from './pages/InterviewPage';
import ResultsPage from './pages/ResultsPage';
import InterviewHistoryPage from './pages/InterviewHistoryPage';

export default function App() {
  const [route, setRoute] = useState(window.location.hash);
  const [voiceStartId, setVoiceStartId] = useState(null);
  useEffect(() => {
    const change = () => setRoute(window.location.hash);
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  function openInterview(id) { setVoiceStartId(id); window.location.hash = `interview/${id}`; }
  const match = route.match(/^#interview\/(\d+)$/);
  const results = route.match(/^#results\/(\d+)$/);
  if (results) return <ResultsPage key={results[1]} interviewId={Number(results[1])} />;
  if (route === '#history') return <InterviewHistoryPage />;
  if (match) return <InterviewPage key={match[1]} interviewId={Number(match[1])} voiceEnabled={voiceStartId === Number(match[1])} />;
  if (route === '#recruiter') return <RecruiterSetupPage onStart={openInterview} />;
  if (route === '#practice') return <CandidatePracticeSetupPage onCreated={(interview) => openInterview(interview.id)} />;
  return (
    <>
      <header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><span className="phase-badge">YOUR NEXT CONVERSATION STARTS HERE</span></header>
      <main>
        <div className="intro"><p className="eyebrow">ROLE-RELEVANT CONVERSATIONS</p><h1>AI Interview Platform</h1><p>Create an interview brief or practice for your next opportunity.</p></div>
        <div className="mode-grid">
          <section className="card"><p className="eyebrow">FOR RECRUITERS</p><h2>Recruiter</h2><p>Create structured interviews grounded in a candidate’s experience and your role requirements.</p><a className="primary action-link" href="#recruiter">Create an interview</a></section>
          <section className="card"><p className="eyebrow">FOR CANDIDATES</p><h2>Practice Interview</h2><p>Practice a mock interview for any target role and receive concise improvement hints.</p><a className="secondary action-link" href="#practice">Practice Interview</a></section>
        </div>
        <p className="field-help home-note">Six questions per session. AI interview signals support human review; they do not make hiring decisions.</p><a className="secondary action-link" href="#history">Open saved interviews and results</a>
      </main>
    </>
  );
}
