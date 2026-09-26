import { useEffect, useState } from 'react';
import { listInterviews } from '../services/api';

export default function InterviewHistoryPage() {
  const [items, setItems] = useState(null), [error, setError] = useState('');
  useEffect(() => { let active = true; listInterviews().then((data) => { if (active) setItems(data); }).catch((failure) => { if (active) setError(failure.message); }); return () => { active = false; }; }, []);
  return <><header className="topbar"><a className="brand" href="#">Interview<span>Lens</span></a><a href="#recruiter">Create interview</a></header><main><div className="intro"><h1>Saved interviews</h1><p>Recent local recruiter interviews and practice sessions.</p></div>{error && <p className="error" role="alert">{error}</p>}{!items && !error && <p role="status">Loading interviews…</p>}<div className="card">{items?.length === 0 && <p>No interviews yet.</p>}{items?.map((item) => <article className="history-row" key={item.id}><div><h2>{item.job_title}</h2><p>#{item.id} · {item.mode} · {item.status} · {new Date(item.created_at).toLocaleDateString()}</p></div><a className="secondary action-link" href={`#${item.status === 'completed' ? 'results' : 'interview'}/${item.id}`}>{item.status === 'completed' ? (item.mode === 'practice' ? 'View Practice Feedback' : 'View Candidate Report') : 'Continue interview'}</a></article>)}</div></main></>;
}
