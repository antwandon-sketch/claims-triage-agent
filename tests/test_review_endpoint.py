"""
Tests for the human-approval gate (routes/review.py). db.py is mocked
entirely, same approach as test_ingestion_endpoint.py - no real Postgres
needed, and no risk of an approve/reject test accidentally hitting a real
database.
"""
import json
from unittest.mock import MagicMock

import pytest


API_KEY = "test-secret"


def _headers(api_key=API_KEY):
    return {"X-API-Key": api_key} if api_key is not None else {}


def _pending_draft(draft_id=1):
    return {
        "id": draft_id,
        "agent_decision_id": 10,
        "draft_type": "customer_reply",
        "draft_text": "Thanks for reaching out...",
        "status": "pending_approval",
        "reviewed_at": None,
        "reviewed_by": None,
        "rejection_reason": None,
        "category": "document_request",
        "urgency": "low",
        "suggested_action": "auto_reply",
        "summary": "Wants a copy of the declarations page.",
        "sender_email": "a@example.com",
        "subject": "Declarations page",
        "body": "Can you send me a copy?",
    }


@pytest.fixture
def mock_review_db(monkeypatch):
    """Replaces db.list_drafts / db.get_draft / db.approve_draft /
    db.reject_draft as used by routes/review.py with mocks."""
    mocks = {
        "list_drafts": MagicMock(return_value=[]),
        "get_draft": MagicMock(return_value=None),
        "approve_draft": MagicMock(return_value=None),
        "reject_draft": MagicMock(return_value=None),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(f"routes.review.db.{name}", mock)
    return mocks


def test_pending_requires_api_key(client, mock_review_db):
    resp = client.get("/drafts/pending", headers=_headers(api_key=None))
    assert resp.status_code == 401


def test_pending_rejects_wrong_api_key(client, mock_review_db):
    resp = client.get("/drafts/pending", headers=_headers(api_key="wrong"))
    assert resp.status_code == 401


def test_pending_lists_only_pending_approval(client, mock_review_db):
    mock_review_db["list_drafts"].return_value = [_pending_draft()]

    resp = client.get("/drafts/pending", headers=_headers())

    assert resp.status_code == 200
    assert resp.get_json()["drafts"] == [_pending_draft()]
    # Confirms the filter was actually passed through, not just that
    # *a* list of drafts came back.
    mock_review_db["list_drafts"].assert_called_once_with(status="pending_approval")


def test_pending_empty_list(client, mock_review_db):
    resp = client.get("/drafts/pending", headers=_headers())
    assert resp.status_code == 200
    assert resp.get_json()["drafts"] == []


def _post(client, path, payload=None, api_key=API_KEY):
    return client.post(
        path,
        data=json.dumps(payload) if payload is not None else None,
        content_type="application/json",
        headers=_headers(api_key),
    )


def test_approve_requires_api_key(client, mock_review_db):
    resp = _post(client, "/drafts/1/approve", {"reviewed_by": "anthony@example.com"}, api_key=None)
    assert resp.status_code == 401


def test_approve_requires_reviewed_by(client, mock_review_db):
    resp = _post(client, "/drafts/1/approve", {})
    assert resp.status_code == 400
    mock_review_db["approve_draft"].assert_not_called()


def test_approve_rejects_blank_reviewed_by(client, mock_review_db):
    resp = _post(client, "/drafts/1/approve", {"reviewed_by": "  "})
    assert resp.status_code == 400


def test_approve_success(client, mock_review_db):
    approved = {**_pending_draft(), "status": "approved", "reviewed_by": "anthony@example.com", "reviewed_at": "2026-09-12T23:00:00"}
    mock_review_db["approve_draft"].return_value = approved

    resp = _post(client, "/drafts/1/approve", {"reviewed_by": "anthony@example.com"})

    assert resp.status_code == 200
    body = resp.get_json()["draft"]
    assert body["status"] == "approved"
    assert body["reviewed_by"] == "anthony@example.com"
    assert body["reviewed_at"] is not None
    mock_review_db["approve_draft"].assert_called_once_with(1, "anthony@example.com")


def test_approve_nonexistent_draft_is_404(client, mock_review_db):
    mock_review_db["approve_draft"].return_value = None
    mock_review_db["get_draft"].return_value = None

    resp = _post(client, "/drafts/999/approve", {"reviewed_by": "anthony@example.com"})

    assert resp.status_code == 404


def test_approve_twice_is_conflict_not_double_approved(client, mock_review_db):
    """A draft that's already approved can't be approved again - the mocked
    UPDATE matches no row (as the real WHERE status='pending_approval'
    clause would), and get_draft shows it's already approved."""
    mock_review_db["approve_draft"].return_value = None
    mock_review_db["get_draft"].return_value = {**_pending_draft(), "status": "approved"}

    resp = _post(client, "/drafts/1/approve", {"reviewed_by": "someone_else@example.com"})

    assert resp.status_code == 409
    assert "approved" in resp.get_json()["error"]


def test_approve_already_rejected_draft_is_conflict(client, mock_review_db):
    mock_review_db["approve_draft"].return_value = None
    mock_review_db["get_draft"].return_value = {**_pending_draft(), "status": "rejected"}

    resp = _post(client, "/drafts/1/approve", {"reviewed_by": "anthony@example.com"})

    assert resp.status_code == 409
    assert "rejected" in resp.get_json()["error"]


def test_reject_requires_reviewed_by(client, mock_review_db):
    resp = _post(client, "/drafts/1/reject", {"rejection_reason": "wrong tone"})
    assert resp.status_code == 400
    mock_review_db["reject_draft"].assert_not_called()


def test_reject_success_with_reason(client, mock_review_db):
    rejected = {
        **_pending_draft(),
        "status": "rejected",
        "reviewed_by": "anthony@example.com",
        "reviewed_at": "2026-09-12T23:00:00",
        "rejection_reason": "Tone is too informal for this customer.",
    }
    mock_review_db["reject_draft"].return_value = rejected

    resp = _post(
        client,
        "/drafts/1/reject",
        {"reviewed_by": "anthony@example.com", "rejection_reason": "Tone is too informal for this customer."},
    )

    assert resp.status_code == 200
    body = resp.get_json()["draft"]
    assert body["status"] == "rejected"
    assert body["reviewed_by"] == "anthony@example.com"
    assert body["rejection_reason"] == "Tone is too informal for this customer."
    mock_review_db["reject_draft"].assert_called_once_with(1, "anthony@example.com", "Tone is too informal for this customer.")


def test_reject_success_without_reason(client, mock_review_db):
    """rejection_reason is optional."""
    rejected = {**_pending_draft(), "status": "rejected", "reviewed_by": "anthony@example.com", "rejection_reason": None}
    mock_review_db["reject_draft"].return_value = rejected

    resp = _post(client, "/drafts/1/reject", {"reviewed_by": "anthony@example.com"})

    assert resp.status_code == 200
    mock_review_db["reject_draft"].assert_called_once_with(1, "anthony@example.com", None)


def test_reject_twice_is_conflict(client, mock_review_db):
    mock_review_db["reject_draft"].return_value = None
    mock_review_db["get_draft"].return_value = {**_pending_draft(), "status": "rejected"}

    resp = _post(client, "/drafts/1/reject", {"reviewed_by": "someone_else@example.com"})

    assert resp.status_code == 409


def test_reject_nonexistent_draft_is_404(client, mock_review_db):
    mock_review_db["reject_draft"].return_value = None
    mock_review_db["get_draft"].return_value = None

    resp = _post(client, "/drafts/999/reject", {"reviewed_by": "anthony@example.com"})

    assert resp.status_code == 404
