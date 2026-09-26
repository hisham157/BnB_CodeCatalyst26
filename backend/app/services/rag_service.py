from collections import OrderedDict
from hashlib import sha256
import logging
from pathlib import Path
from threading import RLock

import numpy as np

from .gemini_service import AIServiceError

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
logger = logging.getLogger(__name__)
_model = None
_model_lock = RLock()


def get_embedding_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME, device="cpu")
        return _model


def chunk_text(text, size=600, overlap=80):
    if size <= overlap or overlap < 0:
        raise ValueError("Chunk size must exceed nonnegative overlap.")
    text = " ".join(text.split())
    return [text[start:start + size] for start in range(0, len(text), size - overlap)]


class RagService:
    def __init__(self, model=None):
        self.model = model
        self.cache = OrderedDict()
        self.lock = RLock()

    def encode(self, texts):
        with _model_lock:
            model = self.model if self.model is not None else get_embedding_model()
            vectors = np.asarray(model.encode(texts, convert_to_numpy=True), dtype=np.float32)
        return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)

    def retrieve(self, interview, query, top_k=6):
        sources = {
            "RESUME": interview.resume_text,
            "JOB_DESCRIPTION": interview.job_description,
            "SKILLS": interview.required_skills if interview.required_skills != "[]" else "",
            "INTERVIEW_RUBRIC": (Path(__file__).resolve().parents[1] / "data/interview_rubric.txt").read_text(encoding="utf-8"),
        }
        fingerprint = sha256(str(sources).encode()).hexdigest()
        key = (interview.id, fingerprint)
        try:
            with self.lock:
                if key not in self.cache:
                    chunks = [{"source": source, "text": part} for source, text in sources.items() for part in chunk_text(text)]
                    self.cache[key] = (chunks, self.encode([chunk["text"] for chunk in chunks]))
                    if len(self.cache) > 32:
                        self.cache.popitem(last=False)
                self.cache.move_to_end(key)
                chunks, vectors = self.cache[key]
            scores = vectors @ self.encode([query])[0]
            ranked = np.argsort(-scores).tolist()
            # Preserve source coverage, then fill remaining slots by similarity.
            selected = []
            for source in sources:
                match = next((index for index in ranked if chunks[index]["source"] == source), None)
                if match is not None and len(selected) < top_k:
                    selected.append(match)
            selected.extend(index for index in ranked if index not in selected)
            return [chunks[index] for index in selected[:top_k]]
        except Exception as exc:
            logger.warning("Local embedding/retrieval failure: %s", type(exc).__name__)
            raise AIServiceError("Local resume retrieval is unavailable. Check the embedding model installation/download and retry.") from exc
