# Interview Bot — Phases 1–5

## Recommended backend startup (prevents duplicate-server errors)

From the workspace root, run:

```powershell
.\interview-bot\start-backend.cmd
```

From an existing backend terminal, run:

```powershell
.\.venv\Scripts\python.exe run.py
```

This checks the health and identity of the server on port 8000 and reuses an already-running Interview Bot. Keep the original server terminal open. To apply backend code changes, stop that original server with Ctrl+C, then run the launcher again. Optional development reload: `run.py --reload`.

Do not repeatedly run raw `uvicorn` commands when the backend is already running. On Windows this can produce WinError 10013. The launcher reports unrelated occupied/reserved ports clearly; it does not kill processes or alter system networking. Port 8000 remains the frontend API address.

A local recruiter setup workflow: enter a role, add required skills, upload one PDF or DOCX resume, and save the interview to SQLite. React + Vite (JavaScript and CSS), FastAPI, SQLAlchemy, and Pydantic.

Phase 2 adds recruiter and independent candidate practice modes, one shared Gemini interview engine, local retrieval, and six-question interviews. Phase 3 adds optional microphone answers with local faster-whisper transcription and browser-native question speech. The Phase 1 setup remains usable without an API key. Starting or answering an interview requires a backend Gemini key. Phase 4 adds local browser-side integrity observations. Phase 5 adds evidence-backed recruiter and practice reports. Authentication and automatic hiring/rejection decisions are not implemented.

## Prerequisites

- Python 3.10 or newer, with pip.
- Node.js 22 or newer, with npm.
- Two terminal windows. Run the commands below from the repository workspace (`prototype`).

## 1. Start the backend (Windows PowerShell)

```powershell
cd interview-bot\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

If PowerShell blocks activation, allow scripts for this terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternatively, activation is optional; use the environment executables directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

If `python` is unavailable, try `py` for the environment creation command, or use your installed Python executable path.

- Backend: http://localhost:8000
- Health: http://localhost:8000/health (returns `{"status":"ok"}`)
- FastAPI Swagger: http://localhost:8000/docs

The database and tables are created automatically on application startup. SQLite always lives at `backend/interview_bot.db`, independent of the terminal working directory. Existing Phase 1 databases are upgraded in place by adding `mode` (default `recruiter`) and nullable `interview_plan_json`; existing records are preserved. Do not delete your database. See the Phase 2 configuration below before starting an AI interview.

## 2. Start the frontend (new PowerShell terminal)

```powershell
cd interview-bot\frontend
npm install
npm run dev
```

If PowerShell blocks `npm.ps1`, use `npm.cmd install` and `npm.cmd run dev` instead.

Open http://127.0.0.1:5173 in Edge or another browser. The frontend calls http://127.0.0.1:8000. The backend allows local HTTP origins (`localhost` and `127.0.0.1`) on any port so Vite and Live Server both work. Vite uses a strict port and will report an error if 5173 is already occupied.

### Using VS Code Live Server instead of Vite

Keep FastAPI running in the backend terminal. In a frontend terminal, start automatic builds:

```powershell
cd interview-bot\frontend
npm.cmd run live
```

Leave that terminal running. In VS Code, right-click `interview-bot/frontend/index.html` and select **Open with Live Server**. It automatically opens the compiled app in `dist/`, preserving any interview hash URL. Opening `dist/index.html` directly also works. With `prototype` opened as the workspace and Live Server using port 5500, the entry URL is http://127.0.0.1:5500/interview-bot/frontend/index.html. Use the URL Live Server provides if your workspace root or port differs.

The source entry is a Live Server launcher; Vite inserts and compiles the React entry during development/builds. A missing build shows setup instructions instead of a blank page. `npm.cmd run live` rebuilds after frontend edits; refresh after the terminal reports a completed build if Live Server has not refreshed automatically. For a one-time build, use `npm.cmd run build`. Relative asset paths support nested folders. API requests still go directly to FastAPI on port 8000; Live Server cannot run the Python backend.

If Edge cannot connect, check that the terminal server is still running and try the numeric `127.0.0.1` URL above. A build alone does not start a server. Restart FastAPI after changing CORS settings unless it was started with `--reload`.

## 3. Run checks

Backend (from `interview-bot/backend`, with its environment activated):

```powershell
python -m pytest -q
```

Tests use a separate temporary SQLite database per test, including application startup. They do not initialize or modify the development database.

Frontend production build (from `interview-bot/frontend`):

```powershell
npm run build
```

## 4. Manually verify Phase 1

1. Start both servers and visit http://localhost:8000/health.
2. Open http://127.0.0.1:5173, choose Recruiter, and confirm “AI Interview Setup” appears.
3. Submit the empty form; verify a clear job-title error appears.
4. Enter `Backend Developer` and a nonempty job description.
5. Type `Python` and press Enter. Type `FastAPI` and click Add. Add `SQL`, remove it with ×, then add it again.
6. Select a real text-based PDF or DOCX resume under 5 MB. Verify the selected filename appears. A document needs at least 20 letters/digits of extractable text.
7. Click Create Interview. Confirm “Interview Created”, the ID, job title, skills, filename, and extracted character count. Start Interview is now enabled for Phase 2.
8. Visit `http://localhost:8000/api/interviews/ID`, replacing `ID` with the returned number. Verify metadata is present and `resume_text` is absent.
9. Restart the backend and load that same metadata URL to verify persistence.
10. Click Create another interview and repeat with the other supported file format.
11. Try an unsupported file (choose All files in the file picker), a file larger than 5 MB, and a scanned/image-only PDF. Verify useful errors. With valid form inputs, stop the backend and submit to verify the connection error, then restart it.

## API and storage

- `GET /health`: health status.
- `POST /api/interviews`: multipart fields `job_title`, `job_description`, `required_skills` (JSON string array), and `resume` (PDF/DOCX, maximum 5 × 1024 × 1024 bytes). Returns HTTP 201 with ID, title, skills, filename, character count, and status.
- `GET /api/interviews/{id}`: metadata, including description and creation timestamp (UTC), without full resume text. Unknown IDs return 404.
- Validation errors use JSON `detail` messages. Invalid inputs return 422, unsupported/unreadable documents 400, oversized files 413, and failed writes 500.

Skills are stored as JSON text and returned as arrays. Original uploaded documents are not permanently saved; the request upload is temporary. Extracted resume text and job information remain in the local SQLite database. Do not commit that database. PDF parsing uses pypdf; DOCX parsing uses python-docx and includes paragraphs and table cells. Scanned documents are rejected; there is no OCR.

Document extraction is isolated in `backend/app/services/document_parser.py` for later integration. Creation does not infer candidate identity or skills from resumes; Phase 1's parsed information is the extracted character count.

## Phase 2 setup (Windows PowerShell)

From the workspace root, update the existing environment; do not recreate the project:

```powershell
cd interview-bot\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). Use an account/project with available free-tier quota; this app does not provision billing. Set these values in `backend/.env`:

```dotenv
GEMINI_API_KEY=your_actual_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Never put the key in React, a `VITE_` variable, screenshots, or committed files. `.env` is ignored. Existing environment variables take precedence over `.env`. Restart the backend after editing the file. The default model is documented by [Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite); model availability and quota depend on your project.

Optionally download/warm the embedding model before the demo (no Gemini quota):

```powershell
.\.venv\Scripts\python.exe -c "from app.services.rag_service import get_embedding_model; get_embedding_model(); print('Embedding model ready')"
```

The first load downloads `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face and needs internet access. It subsequently runs locally on CPU. Dependencies include PyTorch, so installation is larger than Phase 1. The model loads once per backend process; up to 32 interview embedding indexes are cached in memory and rebuilt after a restart. If Windows reports a PyTorch DLL error, use a normal PowerShell terminal outside an editor sandbox and install/update the [Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Restart Windows if the installer requests it. This machine's runtime was updated during implementation; the installer reported restart-required (3010), although PyTorch imported successfully afterward.

Start the backend (one process; do not use multiple workers for this prototype):

```powershell
.\.venv\Scripts\python.exe run.py
```

In another terminal, from the workspace root:

```powershell
cd interview-bot\frontend
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. Live Server remains supported using the build instructions above. Hash URLs such as `#interview/1` work in both servers and restore saved sessions after refresh. Keep FastAPI running for either frontend option.

## One real Gemini test — recruiter mode

Automated tests use fake AI services and fake embedding vectors, never Gemini quota. The following is a separate manual test with real Gemini and local MiniLM retrieval:

1. Create a synthetic DOCX in Word (or save it as a text-based PDF) containing: `Alex Sample. Backend developer. Built a Python and FastAPI inventory API with SQL transactions, validation, pagination, and integration tests. Improved reporting queries by adding indexes and checking query plans.`
2. Choose Recruiter. Job title: `Backend Developer`. Job description: `We need a developer who can build REST APIs using Python and FastAPI and work with relational databases.` Add `Python`, `FastAPI`, and `SQL` as skills. Upload the synthetic resume and create the interview.
3. Click Start Interview. The first load may take a few minutes if the embedding model is not cached. Verify a role/resume-relevant question, skill, question number, and difficulty from 1–5 appear.
4. Answer the actual question with a concrete example. For an API question, try: `I built the inventory endpoint with Pydantic request validation and a SQL transaction around stock updates. I used an atomic conditional update to prevent negative stock, returned a conflict when stock was insufficient, and tested concurrent requests plus transaction rollback. I added an index after checking the reporting query plan and measured latency before and after.`
5. Check for a plausible deeper/harder follow-up. Later give a vague answer such as `I am not sure; I just used the usual approach.` Check for clarification, simplification, or a topic change. Exact decisions are contextual, not hard-coded. Decisions can be inspected through `GET /api/interviews/ID/session` in Swagger; numerical scores stay out of the candidate UI/API response.
6. Answer all six questions. Confirm completion with no seventh question or hiring decision; the completion button opens the final report. Refresh the same URL to verify the transcript persists. Recruiter interviews should not show practice coaching.

## Manual test — candidate practice mode

1. Return home and choose Practice Interview.
2. Enter a target role, such as `Financial Analyst`, and upload a matching synthetic PDF/DOCX resume. Leave the optional job description and focus skills empty.
3. Create the practice interview. It opens the same shared interview screen and generates a plan from the role and resume.
4. Answer in the textarea. Verify a concise improvement hint appears after each response, with no detailed scores.
5. Continue to six answers and verify completion. Refresh to confirm saved progress. Optionally repeat with a JD and focus skills.

## Phase 2 API and implementation notes

- Creation adds multipart `mode=recruiter|practice`, defaulting to recruiter. Recruiter validation is unchanged. Practice requires only `job_title` and `resume`; description and skills default to empty.
- `POST /api/interviews/{id}/start` creates the plan and first turn. Repeating start returns the existing session without consuming more AI quota.
- `POST /api/interviews/{id}/answer` accepts `{"answer_text":"...","turn_number":1}`. `turn_number` is optional for simple API clients; the frontend always supplies it to reject stale retries. Answers must contain 1–20,000 nonblank characters.
- `GET /api/interviews/{id}/session` returns metadata, a plan summary, transcript, current turn, completion flag, and practice-only hints. It excludes resume text, internal prompts and scoring details.
- Answer, evaluation, and next question are committed atomically. On AI failure the current turn remains unanswered so it can be retried. The UI preserves the draft answer. If the response was lost after saving, use Reload / Retry Session to recover before submitting again.
- Questions are limited to six. Duplicate questions are rejected with one corrective AI retry. After two consecutive questions on a skill, a different planned skill is required unless clarifying; after three, switching is required whenever another skill exists.
- RAG uses source-labeled overlapping character chunks, local MiniLM embeddings and NumPy cosine similarity. Retrieval includes relevant resume, job description, skills and rubric chunks, rather than sending full source documents every turn. Short excerpts may naturally cover all of a short source.
- Gemini uses [Pydantic structured outputs](https://googleapis.github.io/python-genai/). Prompts ignore protected/personal traits, treat document/answer instructions as untrusted, and prohibit hiring decisions. Scores are provisional interview signals, not validated employability measurements.
- Relevant context and typed answers are sent to Gemini. Documents are not permanently uploaded/saved by the application. Extracted text, plans, answers and evaluations remain in the local SQLite file.
- Missing credentials and retrieval failures return controlled 503 errors; invalid AI responses return 502; quota limits return 429. No fake AI fallback is used. Technical logs omit keys, prompts and document contents.
- For this local prototype, mutation locks are process-local. Run one backend process; authentication, public hosting hardening, and multiple-worker coordination are outside this phase.

Run all tests from `backend` with `.\.venv\Scripts\python.exe -m pytest -q`. Run `npm.cmd run build` from `frontend` to validate and refresh the Live Server build. Phases 4 and 5 are documented below.

## Phase 3: microphone answers and spoken questions

### Update dependencies and preload Whisper before the demo

From the workspace root:

```powershell
cd interview-bot\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep your existing Gemini settings in `backend/.env` and optionally add:

```dotenv
WHISPER_MODEL=base.en
```

`base.en` is the default even when the setting is absent. It is intended for English interviews. Whisper always runs on CPU with `int8`; no GPU setup or paid speech API is needed. The implementation uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), which decodes audio through its PyAV dependency; a separate FFmpeg command-line install is not needed.

Download and verify the model **before the live demo**:

```powershell
.\.venv\Scripts\python.exe -m app.services.transcription_service
```

The first run downloads model files from Hugging Face and may take several minutes. Subsequent runs use the local model cache. This command verifies loading and populates the disk cache; each new backend process still loads its own model into memory once.

Start the backend:

```powershell
.\.venv\Scripts\python.exe run.py
```

In a second PowerShell terminal, warm the **running** backend and check readiness:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/transcription/preload
Invoke-RestMethod http://127.0.0.1:8000/api/transcription/status
```

Expected status: `ready`, model: `base.en`, device: `cpu`, compute type: `int8`. The status GET does not download or load the model. It can return `not_loaded`, `loading`, `ready`, or `error`. Preload is explicit; transcription also lazy-loads when necessary. Repeat preload after restarting/reloading the backend.

Start the frontend from the workspace root in another terminal:

```powershell
cd interview-bot\frontend
npm.cmd run dev
```

Open http://127.0.0.1:5173 in Chrome or Edge. For Live Server, use `npm.cmd run live` and open `frontend/index.html` as described above. If port 8000 is already occupied, stop the earlier backend with Ctrl+C before starting another instance.

### Manual voice test (practice, then recruiter)

1. Choose Practice Interview, supply a target role and synthetic resume, and create the interview. A question should appear.
2. Click **Speak Question** and verify you hear only the question. **Stop Speech** cancels playback. Auto-speak is on by default after explicitly starting through the UI; browser autoplay restrictions may still require a click. On a refreshed/direct session URL, click Speak Question or interact with the voice controls to enable speech for that visit.
3. Click **Start Recording**. Allow microphone access for this local site. The recording control requests audio; the separate Phase 4 monitor requests camera permission.
4. Say: `In my project I improved performance by caching frequently requested data.` Verify **Listening…** and an elapsed timer appear.
5. Click **Stop Recording**. The microphone is released and **Transcribing…** appears. At three minutes recording stops automatically. Maximum upload size is 15 MB.
6. Review the text in the answer box and edit any recognition errors. New recordings append text to an existing draft. Nothing is submitted automatically.
7. Click **Submit Answer**. The existing Phase 2 endpoint evaluates the text and generates the next question in one request; the UI says **Evaluating answer and generating the next question…**. Practice mode shows a concise improvement hint.
8. Verify the next question is spoken when allowed, or click Speak Question. Turn off Auto-speak to use manual playback only.
9. Type an answer without recording and submit it. Continue to six answers and verify completion.
10. Repeat one voice answer in a recruiter-created interview. Coaching must stay hidden in recruiter mode.
11. Test microphone denial, silence, cancelling recording, and leaving the interview while recording. Typed answers must remain available; the microphone must turn off. On a backend/transcription failure, the existing draft must remain intact.

Microphone capture requires a secure context such as HTTPS or local `localhost`/`127.0.0.1` URLs; plain HTTP on a LAN IP may be blocked. See [getUserMedia requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia). If permission is denied, enable it using the browser's site permissions or continue typing. Browser voices vary; the app chooses an available English voice and otherwise uses the browser default. No paid voice service is configured.

### Audio privacy and endpoints

- `POST /api/interviews/{id}/transcribe`: multipart `audio` file for an in-progress interview. Accepts WebM, Ogg, MP4/M4A, WAV, MP3 and common MIME variants. Returns `interview_id`, `text`, and `language`.
- Whisper is separate from the adaptive engine. Transcription does not save or evaluate an answer; the candidate reviews it and uses the existing `/answer` endpoint.
- Audio is kept only in request memory/temporary upload storage and a temporary decoding file, deleted on success and failure. No audio path or recording is saved in SQLite. Cancel aborts the browser request; already-running backend processing may finish, then cleans its temporary file.
- Recording controls prevent overlapping recordings and answer submission during recording/transcription. Browser speech stops before the microphone starts. Tracks stop at the end or on navigation/unmount.
- Missing microphone, unsupported browser APIs, speech playback failure, empty speech, invalid audio, upload limits, and Whisper errors have text fallbacks. Phase 4 monitoring is separate from audio; Phase 5 reports are documented below.

### Gemini error fixed during Phase 3

The earlier message about key/model access was caused by HTTP 400: the legacy SDK `response_schema` serialization sent `additional_properties`, which the endpoint rejected. Requests now use `response_json_schema` from the Pydantic schema, and responses are still validated with Pydantic. A real synthetic start-and-answer check succeeded. Authentication, missing-model, quota, and request-format errors now have distinct messages. Restart the backend to load this fix; your existing Gemini key does not need replacement for this schema error.

Automated tests use mocked transcription and do not download or run a real Whisper model or consume Gemini quota. Separately, a real `base.en` smoke check successfully transcribed a locally synthesized test sentence. Physical microphone recording and audible browser playback still require the manual browser check above.

## Phase 4: browser-side integrity observations

Run `npm.cmd install` in `frontend` once. The new dependency is `@mediapipe/tasks-vision` (1.0.1). `npm.cmd run dev`, `npm.cmd run build`, and `npm.cmd run live` prepare the local WASM runtime and download Google's Face Landmarker model on first use. This preparation requires internet once; subsequent runs reuse the model. Generated assets are ignored by Git and included in the build. Live Server uses the same local assets and relative URLs.

Restart FastAPI to create the new `integrity_events` table automatically. Existing interviews and answer scores are preserved. No new Python dependencies are required. Use one backend process.

Use Edge or Chrome on `localhost`/`127.0.0.1` (or HTTPS). When the interview opens, allow camera permission. A visible, mirrored preview and monitoring status appear. Face the camera normally for about two seconds to calibrate. Camera denial or tracking failure is displayed and does not block typed or spoken answers. Stop Camera releases the camera; Retry / Recalibrate requests it again. Completion and navigation release tracks and terminate the worker.

### Method, timing and limitations

MediaPipe Face Landmarker runs in a browser worker with `numFaces: 2`, sampled at about 5 fps. It computes normalized nose-to-eye/face ratios relative to an initial neutral baseline. This is a **head-orientation heuristic**, not accurate eye gaze, emotion recognition, identity recognition, or proof of misconduct. Looking with only the eyes is not measured. Glasses, lighting, occlusion, camera placement, head tilt, posture and calibration can cause false positives or missed observations.

Thresholds live in `frontend/src/services/integrityConfig.js`:

| Observation | Sustained condition |
| --- | --- |
| LOOKING_AWAY | Horizontal ratio change > 0.22 or vertical > 0.14, for 1.5 seconds |
| FACE_MISSING | Zero detected faces for 2 seconds |
| MULTIPLE_FACES | At least two faces for 1 second |
| MONITORING_UNAVAILABLE | Camera/model/tracking failure, hidden page, frame gap or manual camera stop |

Recovery must last 0.4 seconds. Brief movements are discarded; sustained episodes produce one event after recovery or monitoring stops. Multiple episodes receive per-type occurrence numbers. Gaps over 1.5 seconds interrupt observations rather than counting unobserved time. Unavailability records the onset with unknown duration. Initial orientation calibration uses ten stable single-face samples. Retry recalibrates. Times are relative to the first monitoring start for that interview in the current browser tab; reloads retain the anchor. Separate tabs have separate timing anchors and session identifiers.

**Integrity events do not automatically determine whether the candidate cheated.** They never alter technical scores, adaptive questions or practice coaching. Recruiter and practice modes use the same monitor. A compact Review observations panel supports explanations during or after the interview; full results are available through the Phase 5 results page.

For optional diagnostics, create `frontend/.env.local` containing `VITE_INTEGRITY_DEBUG=true`, then restart Vite or rebuild Live Server assets. Default is off. It displays face count, orientation score and raw state only. Never place a Gemini key in a frontend environment file.

### Storage and APIs

- `POST /api/interviews/{id}/integrity-events`: append validated event metadata. Optional client event IDs make upload retries idempotent.
- `GET /api/interviews/{id}/integrity-events`: chronological observations with per-type occurrence numbers.
- `PATCH /api/interviews/{id}/integrity-events/{event_id}/explanation`: accepts only `candidate_explanation` (up to 2,000 characters); empty/null removes the explanation. Observation fields cannot be edited through this endpoint. No event deletion endpoint exists.

The table stores interview ID, optional turn number, type, start/end/duration, occurrence number, limited metadata, optional explanation, creation timestamp and a retry ID. A turn is captured at event onset when available. Only metadata is sent to FastAPI. Raw webcam frames, images, landmarks and video are never uploaded or persisted by the application; transient frames remain in browser memory. No facial identity database exists. Pending event metadata is held in sessionStorage for retries and removed when saved. Closing the tab before upload may lose pending observations. The prototype has no authentication, so explanation editing is not an authenticated ownership boundary. Do not expose it publicly.

### Automated checks

```powershell
# From interview-bot/backend
.\.venv\Scripts\python.exe -m pytest -q
# From interview-bot/frontend
npm.cmd test
npm.cmd run build
```

Backend tests use temporary databases. Frontend state-machine tests need no camera. Physical camera behaviour, worker/browser compatibility, microphone coexistence and visual layout still require the following manual checks.

### Manual webcam test (repeat in recruiter and practice modes)

1. Start FastAPI and Vite, or the Live Server build watcher. Open an interview with a question. Allow camera access; verify preview, calibration and active status.
2. Face forward, blink, and briefly glance aside for less than 1.5 seconds. Verify no excessive events.
3. Turn your head sideways for over 1.5 seconds, then face forward for at least 0.4 seconds. Open Review observations: exactly one head-turned observation should appear. Repeat and verify occurrence #2.
4. Leave the camera view for over 2 seconds and return. Verify one FACE_MISSING event with duration. Bring a second person into frame for over 1 second, then have them leave; verify one MULTIPLE_FACES event.
5. Add an explanation and save it. Reload and verify it persists alongside the unchanged type, time, duration and occurrence. Test an empty explanation to clear it.
6. Deny camera permission on another session, or click Stop Camera. Verify a clear unavailable status and one corresponding onset event. Typed/voice answers must still work. Restore permission and click Retry / Recalibrate.
7. Hide the tab and return. Verify monitoring resumes, the hidden interval is not counted as looking away, and unavailable status is recorded.
8. Record/transcribe an answer and use Speak Question while monitoring. Verify UI responsiveness and normal answer submission. Complete all six questions; verify camera indicator turns off. Verify leaving the page also releases it.
9. Stop FastAPI briefly, trigger an observation, then restart it and click Retry uploads. Verify one saved observation, with no duplicate from retries.
10. Repeat using Live Server at `frontend/index.html`. In DevTools Network verify event requests contain metadata only, with no image/video/landmark payload. Check model/WASM files load from the local frontend origin.

Session-start recovery: reloading while preparation is running now waits automatically for the saved session (HTTP 202), instead of displaying a conflict. Duplicate starts in one page share a promise. After three minutes of busy responses, a retry message is shown; actual AI/network failures remain visible. Run one FastAPI process as documented above.

## Phase 5: final results and evidence trails

### Architecture and flows

The same six-question `InterviewEngine` serves both modes. FastAPI stores resumes as extracted text, interview turns, evaluations and reports in SQLite. Local MiniLM embeddings and NumPy retrieve context; Gemini produces structured questions and concise report explanations. Browser speech synthesis and local faster-whisper support voice. MediaPipe runs separately in a browser worker. Integrity events never enter Gemini report context or skill aggregation.

**Recruiter:** Home -> Recruiter -> resume + role + JD + skills -> six adaptive questions -> View Candidate Report. Results include summary, Candidate Evidence Map, resume claims, adaptation, integrity timeline and transcript. Home -> Saved interviews reopens recent sessions and reports.

**Practice:** Home -> Practice Interview -> resume + target role -> the same engine, with optional coaching -> View Practice Feedback. Results emphasize strengths, improvement areas, exercises and before/after teaching evidence. No hiring suitability recommendation is generated.

### Changed-condition challenge and practice coaching

The shared engine can choose `CHANGE_CONSTRAINT` once: a substantive, testable approach with specificity and depth at least 3/5 may be challenged by changing one assumption. The next turn stores `CHANGE_CONSTRAINT`, its changed condition and parent turn ID. The UI and question speech include the condition. Report comparisons use the original and revised answers directly, plus a concise interpretation. There is no adaptability score. Older interviews without this turn show �not assessed.� The action is conditional, not forced.

Practice-only `TEACH_AND_RETRY` requires a named conceptual gap and depth at most 2/5, not merely a short answer. It creates one `TEACH_NEW_CHALLENGE` turn, a brief teaching note and a different application question linked to the original turn. Recruiter mode rejects this action. Reports describe observed improvement or lack of improvement without a learning-ability score. Special turns count toward the existing six-question limit. Duplicate questions and repeated special actions are rejected; after three consecutive questions on one skill, the engine switches skills where possible.

### Candidate Evidence Map

For each selected, planned or assessed skill, code averages the four existing rubric dimensions (relevance, specificity, depth and evidence), then averages assessed turns equally. The five segments use these prototype bands:

| Mean rubric signal | Visual level | Label |
| --- | --- | --- |
| No valid stored assessment | 0 | Not assessed |
| Below 1 | 1 | Limited evidence |
| 1 to below 2.5 | 2 | Limited evidence |
| 2.5 to below 4 | 3 | Moderate |
| 4 to below 4.5 | 4 | Strong |
| 4.5 to 5 | 5 | Strong |

These are heuristic summaries, not validated probabilities or guarantees of ability. Gemini cannot set the levels. Expand Why? for an explanation and remaining gap; question buttons jump to the actual transcript. Unassessed skills retain an explicit not-assessed label even if the model attempts to add evidence. Stored evaluations, their provisional nature and question coverage limit the report.

### Resume claim -> interview evidence -> remaining gap

Gemini extracts up to five professional claims, targeting three to five when the resume supports them. Claims must occur in the resume and name an allowed skill; unsupported extractions are rejected. Prompts exclude personal/protected attributes, irrelevant hobbies and identity details. MiniLM compares claim embeddings with answer chunks and retrieves at most two turns above a conservative cosine threshold of 0.25. This threshold is only a retrieval heuristic, not a truth or quality measure. Gemini interprets relevant explanations using only retrieved turn references.

Statuses are Supported by explanation, Needs clarification, and Not assessed. The interview cannot independently verify external factual claims. Numeric similarity is never converted into a skill score or displayed as a truth probability. Model explanations still require human inspection; source references establish traceability, not a guarantee that generated prose is correct.

### Persistence, timeline and failure handling

SQLite upgrades add nullable `final_report_json` and `report_generated_at` to interviews and `turn_type` (default NORMAL), `changed_condition`, `parent_turn_id`, `teaching_note` to turns. No database deletion is required.

- `POST /api/interviews/{id}/finalize`: completed interviews only; generate and persist a report, or reuse the existing one. Concurrent generation returns 202 and the frontend waits. Mutation locks require a single backend process.
- `GET /api/interviews/{id}/report`: return the stored report; 404 before generation.
- `GET /api/interviews`: latest 50 local interviews, without resume text or report contents.
- Existing session and integrity APIs remain independently available if report generation fails. Retry does not discard answers. Failed generation can consume quota again on retry; successful reports are cached and never regenerated automatically.

The timeline displays actual stored events, onset/end when known, duration, occurrence, question and candidate explanation. It refreshes independently of the cached report so later explanations appear. Practice calls this Interview Behaviour Feedback. It has no guilt score, emotion/identity interpretation or effect on skill evidence. Unknown camera durations stay unknown.

### Environment and exact start commands

Backend `.env` (copy `.env.example` if absent):

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
WHISPER_MODEL=base.en
```

Frontend optional `.env.local`: `VITE_INTEGRITY_DEBUG=false`. No other environment variables are required. Gemini keys belong only in backend `.env`. The example file now contains a placeholder; if a real key was previously saved/shared in `.env.example`, rotate it in Google AI Studio. This does not require enabling billing. Use a Gemini project with available free-tier quota; the app adds no paid services.

From the workspace root, PowerShell terminal 1:

```powershell
cd interview-bot\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Stop an existing backend with Ctrl+C before starting another. For development add `--reload`; avoid reloading during a demo. Database updates happen on startup.

Terminal 2, from the workspace root:

```powershell
cd interview-bot\frontend
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. For Live Server, replace the final command with `npm.cmd run live` and open `frontend/index.html` using Live Server. The backend must remain running. Hard-refresh Edge after updating compiled files. No new Phase 5 runtime dependencies were added.

Before presenting, warm Whisper using `POST http://127.0.0.1:8000/api/transcription/preload`, verify `/health`, and warm MiniLM using the earlier preload command. Model downloads and cold starts are outside the short presentation timing.

### Final 3�5 minute demo (after preloading)

1. Use a synthetic resume with �Improved API response time by 40% through database and caching optimizations.� Create Backend Developer with Python, FastAPI, SQL and System Design.
2. Answer a personalized question with the measured optimization approach: repeated queries, indexing, caching and before/after latency. Use one short recorded answer, review its transcription, and listen to a spoken question.
3. If a changed-condition question appears, point out its highlighted condition and give a reasoned alternative. This feature is conditional; a weak or unsuitable answer will not force it.
4. Turn your head away long enough to create an observation, return to the camera, then add an explanation. Finish the remaining questions with concise, substantive answers.
5. Open Candidate Report. Expand Why?, jump to a question, inspect the claim evidence and remaining gap, compare original/revised reasoning, and show the separate integrity timeline.
6. Reopen Results to demonstrate report caching. Show a previously completed **real synthetic practice session** with Teach -> New Challenge and improvement feedback if available; do not seed fake results into the demo database.

Timing depends on model/network latency and answer length. A complete live voice session can exceed five minutes; preloading models and keeping answers concise makes the short demo feasible. A saved genuine interview can demonstrate report exploration if free-tier quota or the network fails.

### DEMO CHECKLIST

- [ ] Gemini works
- [ ] Whisper model preloaded
- [ ] microphone works
- [ ] TTS works
- [ ] webcam works
- [ ] MediaPipe loads
- [ ] synthetic resume ready
- [ ] changed-condition challenge tested
- [ ] integrity event tested
- [ ] report generation tested
- [ ] fallback text input works

### Verification and remaining manual checks

Run `.\.venv\Scripts\python.exe -m pytest -q` in backend and `npm.cmd test` plus `npm.cmd run build` in frontend. Automated tests mock Gemini/embeddings, consume no API quota, and use temporary databases. They cover both six-question flows, action limits, mode separation, report caching/failure, source-reference rejection, deterministic levels, claim retrieval, legacy upgrades, JSX transcript/evidence/timeline rendering and earlier phases.

For final acceptance, perform the demo in Edge in both modes; confirm camera/microphone cleanup after navigation and completion, speaker playback, results refresh, explanation visibility and Live Server paths. These physical-device checks cannot be established by unit tests. No automatic hire/reject decisions, protected-trait scoring, or webcam inference of honesty, emotion or personality are implemented. This local unauthenticated prototype is not intended for public hosting.

Phase 5 verification: 101 backend tests and 17 frontend tests passed; production build passed. A headless Edge check using a temporary test database and mocked AI verified recruiter and practice result rendering, evidence expansion, claims/adaptation, transcript navigation and result reload. Test data was not stored in the development database. Live Gemini report quality and physical microphone/speaker/webcam acceptance remain manual checks.

Live Server reload protection: workspace settings now ignore backend/database, environment, test and verification file changes. Stop and start VS Code Live Server once to load the settings. This prevents a saved answer or integrity observation from triggering a full-page reload. Frontend build changes still refresh the page; avoid editing frontend code during the live interview.
