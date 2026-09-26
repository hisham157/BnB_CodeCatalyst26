from types import SimpleNamespace

import numpy as np

from app.services.rag_service import RagService, chunk_text


class KeywordEmbeddings:
    def __init__(self):
        self.calls = 0

    def encode(self, texts, **kwargs):
        self.calls += 1
        return np.array([[text.lower().count(word) for word in ("finance", "marketing", "python")] for text in texts], dtype=float)


def test_retrieves_relevant_source_chunks_and_caches():
    model = KeywordEmbeddings()
    rag = RagService(model)
    interview = SimpleNamespace(
        id=1, resume_text="marketing " * 100 + "finance " * 120,
        job_description="Finance analyst budgeting", required_skills='["Finance"]',
    )
    results = rag.retrieve(interview, "finance", top_k=4)
    assert {chunk["source"] for chunk in results} == {"RESUME", "JOB_DESCRIPTION", "SKILLS", "INTERVIEW_RUBRIC"}
    resume = next(chunk for chunk in results if chunk["source"] == "RESUME")
    assert resume["text"].count("finance") > resume["text"].count("marketing")
    assert model.calls == 2
    rag.retrieve(interview, "marketing")
    assert model.calls == 3  # Only the new query is encoded.
    interview.resume_text = "python " * 120
    assert "python" in rag.retrieve(interview, "python")[0]["text"]
    assert model.calls == 5


def test_chunk_overlap_and_empty_text():
    parts = chunk_text("abcdefghijklmnopqrstuvwxyz", size=10, overlap=2)
    assert parts[0][-2:] == parts[1][:2]
    assert all(len(part) <= 10 for part in parts)
    assert chunk_text("   ") == []
