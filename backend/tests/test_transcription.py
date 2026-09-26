from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.models import Interview
from app.services.transcription_service import TranscriptionError, TranscriptionService, get_transcription_service
from tests.test_interviews import client, create


class FakeTranscription:
    def __init__(self):
        self.text = " I improved performance by caching data. "
        self.failure = False
        self.calls = 0
        self.loaded = False

    def transcribe(self, data, suffix):
        self.calls += 1
        if self.failure:
            raise TranscriptionError("We couldn't transcribe that recording. Try recording again or type your answer.")
        return {"text": self.text, "language": "en"}

    def load(self):
        self.loaded = True

    def status(self):
        return {"status": "ready" if self.loaded else "not_loaded", "model": "base.en"}


@pytest.fixture
def voice_client(client):
    service = FakeTranscription()
    client.app.dependency_overrides[get_transcription_service] = lambda: service
    return client, service


def active_interview(client, mode="practice"):
    interview_id = create(client, mode=mode).json()["id"]
    with client.test_sessions() as db:
        db.get(Interview, interview_id).status = "in_progress"
        db.commit()
    return interview_id


def upload(client, interview_id, data=b"test audio", mime="audio/webm;codecs=opus"):
    return client.post(f"/api/interviews/{interview_id}/transcribe", files={"audio": ("answer.webm", data, mime)})


@pytest.mark.parametrize("mode", ["practice", "recruiter"])
def test_transcription_returns_text_without_saving_answer(voice_client, mode):
    client, service = voice_client
    interview_id = active_interview(client, mode)
    response = upload(client, interview_id)
    assert response.status_code == 200
    assert response.json() == {"interview_id": interview_id, "text": "I improved performance by caching data.", "language": "en"}
    with client.test_sessions() as db:
        assert db.get(Interview, interview_id).turns == []


@pytest.mark.parametrize("mime", ["text/plain", "application/pdf", "image/png"])
def test_unsupported_file(voice_client, mime):
    client, service = voice_client
    assert upload(client, active_interview(client), mime=mime).status_code == 415
    assert service.calls == 0


@pytest.mark.parametrize("mime", ["audio/ogg", "audio/mp4", "audio/wav", "audio/webm;codecs=opus"])
def test_audio_variants(voice_client, mime):
    client, _ = voice_client
    assert upload(client, active_interview(client), mime=mime).status_code == 200


def test_empty_and_oversized_upload(voice_client):
    client, service = voice_client
    interview_id = active_interview(client)
    assert upload(client, interview_id, data=b"").status_code == 400
    assert upload(client, interview_id, data=b"x" * (15 * 1024 * 1024 + 1)).status_code == 413
    assert service.calls == 0


def test_empty_transcript_and_whisper_failure(voice_client):
    client, service = voice_client
    interview_id = active_interview(client)
    service.text = " ... "
    response = upload(client, interview_id)
    assert response.status_code == 422
    assert "No clear speech" in response.json()["detail"]
    service.failure = True
    assert upload(client, interview_id).status_code == 503


def test_unknown_or_inactive_interview(voice_client):
    client, service = voice_client
    assert upload(client, 999).status_code == 404
    interview_id = create(client).json()["id"]
    assert upload(client, interview_id).status_code == 409
    assert service.calls == 0


def test_status_does_not_load_and_preload_is_explicit(voice_client):
    client, service = voice_client
    assert client.get("/api/transcription/status").json()["status"] == "not_loaded"
    assert not service.loaded
    assert client.post("/api/transcription/preload").json()["status"] == "ready"


@pytest.mark.parametrize("failure", [None, "decode", "inference", "empty", "too_long"])
def test_temporary_audio_deleted_even_on_failure(monkeypatch, failure):
    from faster_whisper import audio
    paths = []

    def decode(path, sampling_rate):
        paths.append(Path(path))
        assert paths[-1].read_bytes() == b"test audio"
        if failure == "decode":
            raise ValueError("invalid file")
        return np.zeros(16000 * 181 if failure == "too_long" else 16000, dtype=np.float32)

    class Model:
        def transcribe(self, data, **kwargs):
            assert kwargs["vad_filter"] is True
            if failure == "inference":
                raise RuntimeError("inference failed")
            segments = [] if failure == "empty" else [SimpleNamespace(text=" Hello  world ")]
            return iter(segments), SimpleNamespace(language="en")

    monkeypatch.setattr(audio, "decode_audio", decode)
    service = TranscriptionService()
    service._model = Model()
    if failure:
        with pytest.raises(TranscriptionError):
            service.transcribe(b"test audio", ".webm")
    else:
        assert service.transcribe(b"test audio", ".webm")["text"] == "Hello world"
    assert paths and all(not path.exists() and not path.parent.exists() for path in paths)
    assert not service._transcribe_lock.locked()
