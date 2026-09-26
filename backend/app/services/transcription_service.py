"""Local speech recognition only; interview decisions stay in interview_engine."""
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

logger = logging.getLogger(__name__)
NO_SPEECH = "No clear speech was detected. Please record your answer again or type your answer."


class TranscriptionError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


class TranscriptionService:
    def __init__(self):
        self._model = None
        self._model_name = None
        self._load_lock = Lock()
        self._transcribe_lock = Lock()
        self._state = "not_loaded"

    def status(self):
        return {"status": self._state, "model": self._model_name or os.getenv("WHISPER_MODEL", "base.en"), "device": "cpu", "compute_type": "int8"}

    def load(self):
        with self._load_lock:
            if self._model is None:
                self._state = "loading"
                try:
                    from faster_whisper import WhisperModel
                    name = os.getenv("WHISPER_MODEL", "base.en").strip() or "base.en"
                    self._model = WhisperModel(name, device="cpu", compute_type="int8")
                    self._model_name = name
                    self._state = "ready"
                    logger.info("Local Whisper model ready on CPU (int8).")
                except Exception as exc:
                    self._state = "error"
                    logger.warning("Whisper initialization failed: %s", type(exc).__name__)
                    raise TranscriptionError("Whisper could not load. Check its installation/model download, or continue by typing.") from None
            return self._model

    def transcribe(self, audio_bytes, suffix):
        if not self._transcribe_lock.acquire(blocking=False):
            raise TranscriptionError("Another recording is being transcribed. Please try again shortly.", 409)
        try:
            model = self.load()
            # Close the file before decoding on Windows; delete it even on failure.
            with TemporaryDirectory(prefix="interview-audio-") as directory:
                path = Path(directory) / f"recording{suffix}"
                path.write_bytes(audio_bytes)
                try:
                    from faster_whisper.audio import decode_audio
                    audio = decode_audio(str(path), sampling_rate=16000)
                except Exception as exc:
                    logger.warning("Audio decoding failed: %s", type(exc).__name__)
                    raise TranscriptionError("Could not read this audio recording. Record again or type your answer.", 400) from None
                if len(audio) == 0:
                    raise TranscriptionError(NO_SPEECH, 422)
                if len(audio) > 16000 * 180:
                    raise TranscriptionError("Recordings must be three minutes or shorter.", 413)
                segments, info = model.transcribe(
                    audio, beam_size=1, vad_filter=True,
                    condition_on_previous_text=False,
                )
                text = " ".join(" ".join(segment.text.split()) for segment in segments).strip()
                if not any(character.isalnum() for character in text):
                    raise TranscriptionError(NO_SPEECH, 422)
                return {"text": text, "language": getattr(info, "language", None)}
        except TranscriptionError:
            raise
        except Exception as exc:
            logger.warning("Whisper transcription failed: %s", type(exc).__name__)
            raise TranscriptionError("We couldn't transcribe that recording. Try recording again or type your answer.") from None
        finally:
            self._transcribe_lock.release()


transcription_service = TranscriptionService()


def get_transcription_service():
    return transcription_service


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    transcription_service.load()
    print(transcription_service.status())
