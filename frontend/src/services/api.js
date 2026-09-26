const API_URL = 'http://127.0.0.1:8000';

export async function createInterview({ jobTitle, jobDescription, skills, resume, mode = 'recruiter' }) {
  const form = new FormData();
  form.append('job_title', jobTitle.trim());
  form.append('job_description', jobDescription.trim());
  form.append('required_skills', JSON.stringify(skills));
  form.append('resume', resume);
  form.append('mode', mode);
  return request('/api/interviews', { method: 'POST', body: form });
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Cannot reach the backend. Check that FastAPI is running on 127.0.0.1:8000.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc?.at(-1) || 'Input'}: ${item.msg}`).join(' ')
      : detail;
    const failure = new Error(typeof message === 'string' ? message : 'The request failed. Please try again.');
    failure.status = response.status;
    throw failure;
  }
  if (!data || typeof data !== 'object') throw new Error('The backend returned an invalid response. Please reload the session.');
  return data;
}

export function createPracticeInterview(values) {
  return createInterview({ ...values, mode: 'practice' });
}

const pendingStarts = new Map();

export function startInterview(id) {
  if (pendingStarts.has(id)) return pendingStarts.get(id);
  const pending = waitForStart(id).finally(() => pendingStarts.delete(id));
  pendingStarts.set(id, pending);
  return pending;
}

async function waitForStart(id) {
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const data = await request(`/api/interviews/${id}/start`, { method: 'POST' });
    if (data.status !== 'starting') return data;
    // A reload can overlap the original AI request. Reuse its saved result.
    await new Promise((resolve) => setTimeout(resolve, 2000));
    const saved = await getInterviewSession(id);
    if (saved.status !== 'created') return saved;
  }
  throw new Error('Interview preparation is taking longer than expected. Retry to check its progress; your interview is saved.');
}

export function submitAnswer(id, answerText, turnNumber) {
  return request(`/api/interviews/${id}/answer`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer_text: answerText, turn_number: turnNumber }),
  });
}

export function getInterviewSession(id) {
  return request(`/api/interviews/${id}/session`);
}

export function listInterviews() { return request('/api/interviews'); }
export function getReport(id) { return request(`/api/interviews/${id}/report`); }
const pendingReports = new Map();
export function finalizeInterview(id) {
  if (pendingReports.has(id)) return pendingReports.get(id);
  const pending = prepareReport(id).finally(() => pendingReports.delete(id));
  pendingReports.set(id, pending);
  return pending;
}
async function prepareReport(id) {
  try { return await getReport(id); }
  catch (failure) { if (failure.status !== 404) throw failure; }
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const result = await request(`/api/interviews/${id}/finalize`, { method: 'POST' });
    if (result.status !== 'generating') return result;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error('Report preparation is taking longer than expected. Your interview is saved. Retry to check progress.');
}

export function createIntegrityEvent(id, event) {
  return request(`/api/interviews/${id}/integrity-events`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event), keepalive: true,
  });
}

export function getIntegrityEvents(id) {
  return request(`/api/interviews/${id}/integrity-events`);
}

export function addIntegrityExplanation(id, eventId, explanation) {
  return request(`/api/interviews/${id}/integrity-events/${eventId}/explanation`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ explanation }),
  });
}

export async function transcribeAnswer(id, audioBlob, signal) {
  const type = audioBlob.type.split(';')[0];
  const extension = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'm4a' : type.includes('wav') ? 'wav' : 'webm';
  const form = new FormData();
  form.append('audio', audioBlob, `recording.${extension}`);
  const result = await request(`/api/interviews/${id}/transcribe`, { method: 'POST', body: form, signal });
  if (typeof result.text !== 'string' || !result.text.trim()) throw new Error('No clear speech was detected. Record again or type your answer.');
  return result;
}
