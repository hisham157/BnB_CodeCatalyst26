from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.transcription_service import NO_SPEECH, TranscriptionError, get_transcription_service
from .interview_session import load_interview

router = APIRouter(tags=["transcription"])
MAX_AUDIO_BYTES = 15 * 1024 * 1024
AUDIO_TYPES = {
    "audio/webm": ".webm", "video/webm": ".webm",
    "audio/ogg": ".ogg", "application/ogg": ".ogg",
    "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/wav": ".wav", "audio/wave": ".wav", "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
}


@router.get("/api/transcription/status")
def transcription_status(service=Depends(get_transcription_service)):
    return service.status()


@router.post("/api/transcription/preload")
def preload_transcription(service=Depends(get_transcription_service)):
    try:
        service.load()
        return service.status()
    except TranscriptionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None


@router.post("/api/interviews/{interview_id}/transcribe")
def transcribe_answer(
    interview_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    service=Depends(get_transcription_service),
):
    interview = load_interview(db, interview_id)
    if interview.status != "in_progress":
        raise HTTPException(409, "Start an interview before recording an answer.")
    media_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in AUDIO_TYPES:
        raise HTTPException(415, "Unsupported audio format. Use WebM, Ogg, MP4, WAV, or MP3 audio.")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(400, "The recording is empty. Please record again.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio must be 15 MB or smaller.")
    try:
        result = service.transcribe(data, AUDIO_TYPES[media_type])
        text = " ".join(result["text"].split())
        if not any(character.isalnum() for character in text):
            raise TranscriptionError(NO_SPEECH, 422)
    except TranscriptionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    # Do not update an answer until the candidate explicitly submits the reviewed text.
    return {"interview_id": interview_id, "text": text, "language": result.get("language")}
