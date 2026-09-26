import { useState } from 'react';
import InterviewSetupForm from '../components/InterviewSetupForm';

export default function RecruiterSetupPage({ onStart }) {
  const [interview, setInterview] = useState(null);
  return (
    <>
      <header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><span className="phase-badge">RECRUITER SETUP</span></header>
      <main>
        <div className="intro"><p className="eyebrow">A GOOD INTERVIEW STARTS WITH CONTEXT</p><h1>AI Interview Setup</h1><p>Bring the role, the skills, and the candidate together.</p></div>
        <div className="layout">
          {interview ? (
            <section className="card success" aria-live="polite">
              <span className="success-icon" aria-hidden="true">✓</span>
              <h2>Interview Created</h2><p>Your interview brief has been saved successfully.</p>
              <dl>
                <dt>Interview ID</dt><dd>#{interview.id}</dd>
                <dt>Job Title</dt><dd>{interview.job_title}</dd>
                <dt>Required Skills</dt><dd className="chips">{interview.required_skills.map((skill) => <span className="chip" key={skill}>{skill}</span>)}</dd>
                <dt>Resume Filename</dt><dd>{interview.resume_filename}</dd>
                <dt>Extracted text</dt><dd>{interview.resume_character_count.toLocaleString()} characters</dd>
              </dl>
              <button className="primary" onClick={() => onStart(interview.id)}>Start Interview</button>
              <p className="field-help">Start a personalized, six-question text interview.</p>
              <button className="secondary" onClick={() => setInterview(null)}>Create another interview</button>
            </section>
          ) : <InterviewSetupForm onCreated={setInterview} />}
          <aside><div className="aside-label">THE INTERVIEW BRIEF</div><h2>Set the foundation.</h2><p>A clear brief keeps the role requirements and candidate experience in one place.</p><ol><li><strong>Define the role</strong><span>Add a title and the full job description.</span></li><li><strong>Choose the skills</strong><span>Highlight the skills that matter for this role.</span></li><li><strong>Add the candidate</strong><span>We’ll extract readable text from their resume.</span></li></ol><div className="privacy-note"><strong>Only the text stays.</strong><p>Uploaded files are not permanently saved. Resume text is stored locally for this prototype.</p></div></aside>
        </div>
        <footer>InterviewLens · Recruiter workspace</footer>
      </main>
    </>
  );
}
