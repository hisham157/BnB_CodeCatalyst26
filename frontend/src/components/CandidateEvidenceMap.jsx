export const displayLabel = (label) => label.replaceAll('_', ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase());

export function EvidenceReferences({ turns, onTurn }) {
  return <div className="evidence-sources"><span>Interview evidence: </span>{turns.length ? turns.map((number) => <button type="button" className="source-link" key={number} onClick={() => onTurn(number)}>Question {number}</button>) : <span>Not assessed</span>}</div>;
}

export function EvidenceStatements({ items, onTurn }) {
  return items.length ? <ul className="evidence-list">{items.map((item, index) => <li key={index}><p>{item.text}</p><EvidenceReferences turns={item.supporting_turns} onTurn={onTurn} /></li>)}</ul> : <p>Not sufficiently assessed.</p>;
}

export default function CandidateEvidenceMap({ skills, onTurn, practice }) {
  return <section className="card"><h2>{practice ? 'Skill evidence' : 'Candidate Evidence Map'}</h2><p className="field-help">Evidence from this conversation, not a probability of success. Levels summarize stored rubric signals and require human interpretation.</p>{skills.map((item) => <article className="skill-evidence" key={item.skill}><div className="skill-heading"><h3>{item.skill}</h3><span>{displayLabel(item.label)}</span></div><div className="evidence-bar" role="img" aria-label={`${item.skill}: ${displayLabel(item.label)}`} >{[1, 2, 3, 4, 5].map((step) => <span key={step} className={step <= item.evidence_level ? 'filled' : ''} />)}</div><details><summary>Why?</summary><p>{item.why}</p><EvidenceReferences turns={item.supporting_turns} onTurn={onTurn} /><p><strong>Remaining gap:</strong> {item.remaining_gap}</p></details></article>)}</section>;
}
