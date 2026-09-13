"""
Tests for draft_generator.py. Pure-function tests for determine_draft_type
and _build_decision_context (no API calls), plus integration tests of
generate_draft() with a mocked Anthropic client.
"""
from unittest.mock import MagicMock

import config
from draft_generator import determine_draft_type, _build_decision_context, generate_draft


def test_auto_reply_gets_customer_reply():
    assert determine_draft_type("auto_reply") == "customer_reply"


def test_request_more_info_gets_customer_reply():
    assert determine_draft_type("request_more_info") == "customer_reply"


def test_escalate_human_gets_internal_handoff_note():
    assert determine_draft_type("escalate_human") == "internal_handoff_note"


def _decision(**overrides):
    d = {
        "category": "policy_change",
        "urgency": "low",
        "suggested_action": "auto_reply",
        "summary": "Customer wants to update their mailing address.",
    }
    d.update(overrides)
    return d


def test_decision_context_includes_core_fields():
    context = _build_decision_context(_decision(), "customer_reply")
    assert "category: policy_change" in context
    assert "urgency: low" in context
    assert "suggested_action: auto_reply" in context
    assert "summary: Customer wants to update their mailing address." in context


def test_decision_context_omits_absent_optional_fields():
    context = _build_decision_context(_decision(), "customer_reply")
    assert "policy_number" not in context
    assert "customer_name" not in context
    assert "date_of_loss" not in context
    assert "safety_instruction" not in context
    assert "additional_issues" not in context


def test_decision_context_includes_present_optional_fields():
    decision = _decision(policy_number="PA-10293", customer_name="Jordan Ruiz", date_of_loss="2026-07-28")
    context = _build_decision_context(decision, "customer_reply")
    assert "policy_number: PA-10293" in context
    assert "customer_name: Jordan Ruiz" in context
    assert "date_of_loss: 2026-07-28" in context


def test_decision_context_flags_safety_instruction():
    decision = _decision(safety_instruction="Evacuate and call 911 immediately.")
    context = _build_decision_context(decision, "customer_reply")
    assert "Evacuate and call 911 immediately." in context
    assert "must open the draft with this verbatim" in context


def test_decision_context_lists_every_additional_issue():
    decision = _decision(
        suggested_action="escalate_human",
        additional_issues=[
            {"category": "billing_issue", "short_description": "Also disputes a charge."},
            {"category": "document_request", "short_description": "Also wants a new ID card."},
        ],
    )
    context = _build_decision_context(decision, "internal_handoff_note")
    assert "billing_issue: Also disputes a charge." in context
    assert "document_request: Also wants a new ID card." in context


def test_decision_context_skips_additional_issues_block_when_empty():
    decision = _decision(additional_issues=[])
    context = _build_decision_context(decision, "customer_reply")
    assert "additional_issues" not in context


def _mock_tool_use_response(draft_text, injection_detected=False, injection_explanation=None):
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {
        "draft_text": draft_text,
        "injection_shaped_content_detected": injection_detected,
        "injection_shaped_content_explanation": injection_explanation,
    }
    response = MagicMock()
    response.content = [tool_use_block]
    response.model_dump.return_value = {"mock": True}
    return response


def test_generate_draft_returns_customer_reply_for_auto_reply(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Thanks for reaching out - we've updated your mailing address."
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(suggested_action="auto_reply")
    result = generate_draft("Address change", "Please update my mailing address.", decision)

    assert result["draft_type"] == "customer_reply"
    assert "mailing address" in result["draft_text"]
    assert "latency_ms" in result
    mock_client.messages.create.assert_called_once()


def test_generate_draft_returns_internal_handoff_note_for_escalate_human(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Escalated: billing dispute, needs account review."
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(category="billing_issue", suggested_action="escalate_human")
    result = generate_draft("Overcharged", "I was overcharged this month.", decision)

    assert result["draft_type"] == "internal_handoff_note"
    mock_client.messages.create.assert_called_once()


def test_generate_draft_forces_the_draft_reply_tool(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response("Some draft.")
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    generate_draft("Subject", "Body", _decision())

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "draft_reply"}
    assert kwargs["tools"][0]["name"] == "draft_reply"


# --- injection-shaped-content override (added after the inj_06 finding) ---


def test_no_injection_detected_leaves_customer_reply_unchanged(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Thanks, we'll send that shortly.", injection_detected=False
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(suggested_action="auto_reply")
    result = generate_draft("Subject", "Body", decision)

    assert result["draft_type"] == "customer_reply"
    assert result["injection_shaped_content_detected"] is False
    assert "OVERRIDE" not in result["draft_text"]


def test_injection_detected_overrides_customer_reply_to_internal_handoff_note(monkeypatch):
    """The inj_06 scenario: suggested_action is auto_reply (already
    compromised upstream), but this call's own injection check catches it
    anyway - draft_type must flip in code, not stay customer_reply."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Category: new_claim | Urgency: medium | Suggested action: escalate_human\n"
        "Summary: roof damage claim with photos attached.",
        injection_detected=True,
        injection_explanation="Embedded fake '[attachment: SYSTEM: verified adjuster...]' text tried to force auto-approval.",
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(category="new_claim", suggested_action="auto_reply")
    result = generate_draft("Photos attached", "Roof damage from the storm.", decision)

    assert result["draft_type"] == "internal_handoff_note"
    assert result["injection_shaped_content_detected"] is True
    assert "OVERRIDE" in result["draft_text"]
    assert "verified adjuster" in result["draft_text"]


def test_injection_detected_overrides_request_more_info_too(monkeypatch):
    """determine_draft_type() maps both auto_reply and request_more_info to
    customer_reply - the override must catch both, not just auto_reply."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Could you confirm your policy number?",
        injection_detected=True,
        injection_explanation="Spacing-evasion 'i g n o r e' phrase found in the body.",
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(suggested_action="request_more_info")
    result = generate_draft("Subject", "Body", decision)

    assert result["draft_type"] == "internal_handoff_note"
    assert "OVERRIDE" in result["draft_text"]


def test_injection_detected_on_already_escalated_case_is_a_no_op_override(monkeypatch):
    """When suggested_action is already escalate_human, there's nothing to
    override - draft_type was already internal_handoff_note, and no
    banner should be injected on top of the model's own note."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(
        "Category: complaint | escalate_human. Note: injection attempt detected and disregarded.",
        injection_detected=True,
        injection_explanation="Fake system message found.",
    )
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(category="complaint", suggested_action="escalate_human")
    result = generate_draft("Subject", "Body", decision)

    assert result["draft_type"] == "internal_handoff_note"
    assert "OVERRIDE" not in result["draft_text"]


def test_missing_injection_field_defaults_to_not_detected(monkeypatch):
    """Defensive: if the model somehow omits the (required) field, .get()
    must default to False rather than raising or silently overriding."""
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {"draft_text": "A plain draft."}  # no injection field at all
    response = MagicMock()
    response.content = [tool_use_block]
    response.model_dump.return_value = {"mock": True}

    mock_client = MagicMock()
    mock_client.messages.create.return_value = response
    monkeypatch.setattr(config, "anthropic_client", mock_client)

    decision = _decision(suggested_action="auto_reply")
    result = generate_draft("Subject", "Body", decision)

    assert result["draft_type"] == "customer_reply"
    assert result["injection_shaped_content_detected"] is False
