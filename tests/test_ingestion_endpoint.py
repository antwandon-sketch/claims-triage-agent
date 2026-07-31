import json


def _post(client, payload, api_key="test-secret"):
    headers = {"X-API-Key": api_key} if api_key is not None else {}
    return client.post("/inbound-email", data=json.dumps(payload), content_type="application/json", headers=headers)


def test_health_check(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_rejects_missing_api_key(client, mock_db, mock_classifier):
    resp = _post(client, {"from": "a@example.com", "subject": "Hi", "text": "Hello"}, api_key=None)
    assert resp.status_code == 401


def test_rejects_wrong_api_key(client, mock_db, mock_classifier):
    resp = _post(client, {"from": "a@example.com", "subject": "Hi", "text": "Hello"}, api_key="wrong-secret")
    assert resp.status_code == 401


def test_rejects_non_json_body(client, mock_db, mock_classifier):
    resp = client.post("/inbound-email", data="not json", headers={"X-API-Key": "test-secret"})
    assert resp.status_code == 400


def test_rejects_missing_body_text(client, mock_db, mock_classifier):
    resp = _post(client, {"from": "a@example.com", "subject": "Hi", "text": ""})
    assert resp.status_code == 400


def test_rejects_placeholder_sender(client, mock_db, mock_classifier):
    resp = _post(client, {"from": "unknown", "subject": "Hi", "text": "Water everywhere, help!"})
    assert resp.status_code == 400


def test_happy_path_returns_decision(client, mock_db, mock_classifier):
    resp = _post(
        client,
        {
            "from": "jordan.ruiz@example.com",
            "subject": "Burst pipe!!",
            "text": "A pipe burst in my kitchen and there's water everywhere, policy PA-10293.",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()

    assert body["decision"]["category"] == "new_claim"
    assert body["decision"]["urgency"] == "high"
    assert body["decision"]["suggested_action"] == "escalate_human"
    assert "decision_id" in body
    assert "raw_email_id" in body

    # Confirms the endpoint actually persisted both the raw email and the
    # decision, rather than only returning a response.
    mock_db["save_raw_email"].assert_called_once()
    mock_db["save_decision"].assert_called_once()
    mock_classifier.assert_called_once()
