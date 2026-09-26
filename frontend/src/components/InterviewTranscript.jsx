export function SpecialTurn({ turn, practice }) {
  if (turn.turn_type === 'CHANGE_CONSTRAINT') return <div className="challenge-note"><p className="eyebrow">CHANGED CONDITION</p><p>{turn.changed_condition}</p><strong>AI question</strong></div>;
  if (practice && turn.turn_type === 'TEACH_NEW_CHALLENGE') return <div className="challenge-note"><p className="eyebrow">QUICK COACHING</p><p>{turn.teaching_note}</p><strong>New challenge</strong></div>;
  return null;
}

export default function InterviewTranscript({ turns, practice }) {
  return <section className="card transcript"><h2>Interview transcript</h2>{turns.map((turn) => <article key={turn.turn_number} id={`turn-${turn.turn_number}`} tabIndex="-1"><p className="eyebrow">QUESTION {turn.turn_number} · {turn.skill}</p><SpecialTurn turn={turn} practice={practice} /><h3>{turn.question}</h3><p className="answer-text">{turn.answer_text ?? 'Not answered.'}</p></article>)}</section>;
}
