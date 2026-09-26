import InterviewSetupForm from '../components/InterviewSetupForm';

export default function CandidatePracticeSetupPage({ onCreated }) {
  return (
    <>
      <header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><span className="phase-badge">CANDIDATE PRACTICE</span></header>
      <main>
        <div className="intro"><p className="eyebrow">MAKE ROOM TO PRACTICE</p><h1>Practice Interview</h1><p>Choose a target role and upload your resume. Add a job description or skills if you have them.</p></div>
        <div className="layout"><InterviewSetupForm mode="practice" onCreated={onCreated} /><aside><h2>A conversation that adapts.</h2><p>Answer six questions in writing. Receive a short improvement hint after each answer.</p><p>Questions use your professional experience and target role. No company-specific requirements are assumed when no job description is supplied.</p><p>Your resume text and answers are stored locally. Relevant excerpts are sent to Gemini when you start or answer.</p></aside></div>
      </main>
    </>
  );
}
