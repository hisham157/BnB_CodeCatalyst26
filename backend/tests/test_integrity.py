import pytest
from sqlalchemy import inspect

from app.models import Interview, InterviewTurn
from tests.test_interviews import client, create


def active(client, mode="recruiter"):
    interview_id = create(client, mode=mode).json()["id"]
    with client.test_sessions() as db:
        db.get(Interview, interview_id).status = "in_progress"
        db.add(InterviewTurn(interview_id=interview_id, turn_number=1, question="Professional example?", skill="Communication", difficulty=2))
        db.commit()
    return interview_id


def event(**overrides):
    return {"event_type": "LOOKING_AWAY", "started_at_seconds": 10, "ended_at_seconds": 13,
            "duration_seconds": 3, "turn_number": 1,
            "metadata": {"orientation_method": "normalized_landmark_ratios"}, **overrides}


@pytest.mark.parametrize("mode", ["recruiter", "practice"])
@pytest.mark.parametrize("kind", ["LOOKING_AWAY", "FACE_MISSING", "MULTIPLE_FACES", "MONITORING_UNAVAILABLE"])
def test_create_observation(client, mode, kind):
    interview_id = active(client, mode)
    response = client.post(f"/api/interviews/{interview_id}/integrity-events", json=event(event_type=kind))
    assert response.status_code == 201
    assert response.json()["event_type"] == kind
    assert response.json()["occurrence_number"] == 1
    assert response.json()["interview_id"] == interview_id
    with client.test_sessions() as db:
        interview = db.get(Interview, interview_id)
        assert interview.turns[0].evaluation_json is None
        assert interview.turns[0].difficulty == 2
        assert interview.status == "in_progress"


@pytest.mark.parametrize("changes", [
    {"event_type": "SUSPICIOUS"}, {"started_at_seconds": -1},
    {"ended_at_seconds": 9}, {"duration_seconds": 9}, {"turn_number": 2},
    {"metadata": {"image": "forbidden"}}, {"candidate_explanation": "not allowed at creation"},
])
def test_invalid_events(client, changes):
    interview_id = active(client)
    assert client.post(f"/api/interviews/{interview_id}/integrity-events", json=event(**changes)).status_code == 422


def test_chronology_occurrences_and_retry_idempotency(client):
    base = f"/api/interviews/{active(client)}/integrity-events"
    first = client.post(base, json=event(client_event_id="retry-safe")).json()
    assert client.post(base, json=event(client_event_id="retry-safe")).json() == first
    second = client.post(base, json=event(started_at_seconds=2, ended_at_seconds=5)).json()
    assert second["occurrence_number"] == 2
    other_type = client.post(base, json=event(event_type="FACE_MISSING")).json()
    assert other_type["occurrence_number"] == 1
    assert [item["id"] for item in client.get(base).json()] == [second["id"], first["id"], other_type["id"]]


def test_explanation_is_the_only_editable_field(client):
    interview_id = active(client)
    base = f"/api/interviews/{interview_id}/integrity-events"
    original = client.post(base, json=event()).json()
    url = f"{base}/{original['id']}/explanation"
    changed = client.patch(url, json={"explanation": "I checked the permitted notes."})
    assert changed.status_code == 200
    assert changed.json() == {**original, "candidate_explanation": "I checked the permitted notes."}
    assert client.patch(url, json={"explanation": "text", "event_type": "FACE_MISSING"}).status_code == 422
    assert client.patch(url, json={"explanation": ""}).json()["candidate_explanation"] is None
    assert client.patch(url, json={"explanation": None}).json()["candidate_explanation"] is None
    assert client.delete(f"{base}/{original['id']}").status_code in (404, 405)
    other = active(client)
    assert client.patch(f"/api/interviews/{other}/integrity-events/{original['id']}/explanation", json={"explanation": "wrong interview"}).status_code == 404


def test_unavailable_onset_and_patch_cors(client):
    interview_id = active(client)
    result = client.post(f"/api/interviews/{interview_id}/integrity-events", json={"event_type": "MONITORING_UNAVAILABLE", "started_at_seconds": 0, "metadata": {"reason": "CAMERA_PERMISSION_DENIED"}})
    assert result.status_code == 201
    assert result.json()["duration_seconds"] is None
    response = client.options(f"/api/interviews/{interview_id}/integrity-events/1/explanation", headers={"Origin": "http://127.0.0.1:5500", "Access-Control-Request-Method": "PATCH"})
    assert response.status_code == 200


def test_schema_created_without_dropping_existing_data(client):
    interview_id = create(client).json()["id"]
    with client.test_sessions() as db:
        assert "integrity_events" in inspect(db.bind).get_table_names()
        assert db.get(Interview, interview_id).resume_text
    assert client.get("/api/interviews/999/integrity-events").status_code == 404
