"""
Tests for classifier.py's deterministic post-processing. Pure-function
tests for apply_additional_issues_override (no API calls), plus
integration tests of classify_email() with a mocked Anthropic client to
confirm ordering against score_coverage_question's override.

PROMPT_VERSION v12 closes the multi-issue architectural gap documented in
PROJECT.md's Open Threads (Case W/X style deferral, Option A).
"""
from unittest.mock import MagicMock

import config
from classifier import apply_additional_issues_override, classify_email


def _decision(action="auto_reply", additional_issues=None):
    d = {
        "category": "policy_change",
        "urgency": "low",
        "summary": "Customer wants to update their mailing address.",
        "suggested_action": action,
        "confidence": 0.9,
        "rationale": "Routine administrative change.",
    }
    if additional_issues is not None:
        d["additional_issues"] = additional_issues
    return d


def test_no_additional_issues_key_leaves_action_unchanged():
    decision = _decision(action="auto_reply")
    result = apply_additional_issues_override(decision)
    assert result["suggested_action"] == "auto_reply"


def test_empty_additional_issues_leaves_action_unchanged():
    decision = _decision(action="auto_reply", additional_issues=[])
    result = apply_additional_issues_override(decision)
    assert result["suggested_action"] == "auto_reply"


def test_one_additional_issue_forces_escalate_human():
    decision = _decision(
        action="auto_reply",
        additional_issues=[{"category": "billing_issue", "short_description": "Also asks about a late fee."}],
    )
    result = apply_additional_issues_override(decision)
    assert result["suggested_action"] == "escalate_human"


def test_multiple_additional_issues_force_escalate_human_and_are_preserved():
    issues = [
        {"category": "billing_issue", "short_description": "Also asks about a late fee."},
        {"category": "document_request", "short_description": "Also wants a new ID card."},
    ]
    decision = _decision(action="request_more_info", additional_issues=issues)
    result = apply_additional_issues_override(decision)
    assert result["suggested_action"] == "escalate_human"
    assert result["additional_issues"] == issues
    assert len(result["additional_issues"]) == 2


def test_override_replaces_an_already_escalated_action_without_error():
    decision = _decision(
        action="escalate_human",
        additional_issues=[{"category": "complaint", "short_description": "Also complains about hold times."}],
    )
    result = apply_additional_issues_override(decision)
    assert result["suggested_action"] == "escalate_human"


def _mock_tool_use_response(decision_input):
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = decision_input
    response = MagicMock()
    response.content = [tool_use_block]
    response.model_dump.return_value = {"mock": True}
    return response


def test_classify_email_applies_additional_issues_override_after_coverage_question(monkeypatch):
    """additional_issues must win even when the primary category is
    coverage_question and score_coverage_question would otherwise pick a
    different action - the override runs after, not before."""
    raw_decision = {
        "category": "coverage_question",
        "urgency": "low",
        "summary": "Asks if roadside assistance is included.",
        "suggested_action": "auto_reply",
        "confidence": 0.9,
        "rationale": "Pure feature-existence lookup.",
        "references_specific_incident": False,
        "has_policy_or_claim_number": True,
        "has_liability_or_dispute_signal": False,
        "has_underwriting_or_nonstandard_use_signal": False,
        "asks_feature_existence_only": True,
        "cause_investigated_and_unresolved": False,
        "additional_issues": [{"category": "billing_issue", "short_description": "Also disputes a charge."}],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(raw_decision)
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    result = classify_email("Quick question", "Does my policy include roadside assistance? Also, I was overcharged.")

    # Without additional_issues, score_coverage_question would return "auto_reply" here
    # (has_policy_or_claim_number=True, asks_feature_existence_only=True, no other flags).
    assert result["decision"]["suggested_action"] == "escalate_human"


def test_classify_email_no_additional_issues_matches_v11_behavior(monkeypatch):
    """Zero additional issues: behavior is unchanged from v11 - the model's
    (or score_coverage_question's) own action passes through untouched."""
    raw_decision = {
        "category": "document_request",
        "urgency": "low",
        "summary": "Wants a copy of the declarations page.",
        "suggested_action": "auto_reply",
        "confidence": 0.95,
        "rationale": "Simple resend of a document the customer should already have.",
        "additional_issues": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(raw_decision)
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    result = classify_email("Declarations page", "Can you send me a copy of my declarations page?")

    assert result["decision"]["suggested_action"] == "auto_reply"
