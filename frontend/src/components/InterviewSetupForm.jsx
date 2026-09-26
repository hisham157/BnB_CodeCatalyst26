import { useState } from 'react';
import { createInterview, createPracticeInterview } from '../services/api';

const MAX_BYTES = 5 * 1024 * 1024;

export default function InterviewSetupForm({ onCreated, mode = 'recruiter' }) {
  const practice = mode === 'practice';
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [skillInput, setSkillInput] = useState('');
  const [skills, setSkills] = useState([]);
  const [resume, setResume] = useState(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function addSkill() {
    const value = skillInput.trim();
    if (value && !skills.some((skill) => skill.toLowerCase() === value.toLowerCase())) {
      setSkills([...skills, value]);
    }
    setSkillInput('');
  }

  function selectResume(event) {
    const file = event.target.files[0];
    setResume(null);
    setError('');
    if (!file) return;
    const message = !/\.(pdf|docx)$/i.test(file.name)
      ? 'Unsupported resume type. Upload a PDF or DOCX file.'
      : file.size > MAX_BYTES ? 'Resume must be 5 MB or smaller.' : '';
    if (message) {
      setError(message);
      event.target.value = '';
    } else {
      setResume(file);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    const message = !jobTitle.trim() ? 'Enter a job title.'
      : !practice && !jobDescription.trim() ? 'Enter a job description.'
      : !practice && !skills.length ? 'Add at least one required skill.'
      : !resume ? 'Select a PDF or DOCX resume.' : '';
    setError(message);
    if (message) return;
    setSubmitting(true);
    try {
      const create = practice ? createPracticeInterview : createInterview;
      onCreated(await create({ jobTitle, jobDescription, skills, resume }));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={submit} noValidate>
      <div className="card-heading"><span className="step">01</span><div><h2>Build your interview brief</h2><p>Define the role and add one candidate’s resume.</p></div></div>
      <fieldset disabled={submitting}>
        <label htmlFor="job-title">{practice ? 'Target Role' : 'Job Title'} <span>*</span></label>
        <input id="job-title" value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="e.g. Backend Developer" required />

        <label htmlFor="job-description">Job Description <span>{practice ? '(optional)' : '*'}</span></label>
        <textarea id="job-description" rows="6" value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} placeholder="Describe the responsibilities, experience, and expectations for this role…" required={!practice} />

        <label htmlFor="required-skills">{practice ? 'Focus Skills (optional)' : 'Required Skills *'}</label>
        <p className="field-help" id="skills-help">Type a skill, then press Enter or Add.</p>
        <div className="skill-entry">
          <input id="required-skills" aria-describedby="skills-help" value={skillInput} onChange={(e) => setSkillInput(e.target.value)} placeholder="e.g. Python" onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} />
          <button className="secondary" type="button" onClick={addSkill} disabled={submitting || !skillInput.trim()}>Add</button>
        </div>
        <div className="chips" aria-live="polite">{skills.map((skill) => <span className="chip" key={skill}>{skill}<button type="button" aria-label={`Remove ${skill}`} onClick={() => setSkills(skills.filter((item) => item !== skill))}>×</button></span>)}</div>

        <label htmlFor="resume">Candidate Resume <span>*</span></label>
        <div className="upload-box">
          <input id="resume" type="file" accept=".pdf,.docx" onChange={selectResume} aria-describedby="resume-help" required />
          <p id="resume-help">PDF or DOCX · Up to 5 MB · Text-based documents only</p>
          {resume && <p className="filename">Selected: {resume.name}</p>}
        </div>
      </fieldset>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="form-footer"><p>{practice ? 'Target role and resume are required.' : 'All fields are required.'}</p><button className="primary" type="submit" disabled={submitting}>{submitting ? 'Creating Interview…' : practice ? 'Create Practice Interview' : 'Create Interview'}</button></div>
    </form>
  );
}
