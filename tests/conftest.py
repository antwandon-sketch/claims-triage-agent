"""
Test fixtures. Mocks db.py and classifier.py entirely so the test suite
never needs a real DATABASE_URL or a real ANTHROPIC_API_KEY, and never
spends real API tokens just to run `pytest`. Same approach as
ai-consulting-lab/tests/conftest.py, which mocks the DB layer for /book.
"""
import sys
import os
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Config needs *some* value for these before app.py imports it, even though
# the real API/DB calls are mocked out below.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")

import app as app_module  # noqa: E402


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def mock_db(monkeypatch):
    """Replaces db.save_raw_email / db.save_decision with mocks that return
    predictable fake IDs instead of touching Postgres."""
    import db

    mock_save_raw_email = MagicMock(return_value=1)
    mock_save_decision = MagicMock(return_value=1)
    monkeypatch.setattr("routes.ingestion.db.save_raw_email", mock_save_raw_email)
    monkeypatch.setattr("routes.ingestion.db.save_decision", mock_save_decision)
    return {"save_raw_email": mock_save_raw_email, "save_decision": mock_save_decision}


@pytest.fixture
def mock_classifier(monkeypatch):
    """Replaces classify_email with a mock returning a canned decision,
    instead of making a real Anthropic API call."""
    fake_result = {
        "decision": {
            "category": "new_claim",
            "urgency": "high",
            "policy_number": "PA-10293",
            "customer_name": "Jordan Ruiz",
            "date_of_loss": "2026-07-28",
            "summary": "Customer reports a pipe burst causing water damage.",
            "suggested_action": "escalate_human",
            "confidence": 0.91,
            "rationale": "Active water damage is a safety/property risk requiring prompt handling.",
        },
        "latency_ms": 850,
        "raw_response": {"mock": True},
        "prompt_version": "v1",
        "model_name": "claude-sonnet-5",
    }
    mock = MagicMock(return_value=fake_result)
    monkeypatch.setattr("routes.ingestion.classify_email", mock)
    return mock
