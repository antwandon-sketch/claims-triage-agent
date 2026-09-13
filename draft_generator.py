"""
Draft-generation: turns a classify_email() decision into draft text for a
human to review. No send capability exists yet (see PROJECT.md's "What's
not built yet") - this module only produces text and hands it back to the
caller to persist via db.save_draft(); nothing here calls an email API or
otherwise delivers anything.

draft_type is decided deterministically from suggested_action, not left to
the model - same pattern as classifier.py's apply_additional_issues_override()
and score_coverage_question(): a routing choice that doesn't need judgment
shouldn't be a prompt-following task.
  - auto_reply / request_more_info -> "customer_reply": customer-facing
    text, written to go out close to as-is once send capability exists.
  - escalate_human -> "internal_handoff_note": briefing text FOR the human
    agent, not the customer. Critically, this is where every entry in
    additional_issues gets explicitly named - the whole reason that field
    exists (v12, PROJECT.md Open Threads) is so a genuine second ask isn't
    silently dropped, and that guarantee is worthless if the note a human
    actually reads doesn't mention it.

Case W/X pattern (see eval/coverage_question_FINAL_DESIGN.md's 2026-08-01
design decision, and PROJECT.md's Open Threads note on the
additional_issues override): when there's a real choice between guessing
what the customer probably meant and asking/deferring instead, this
project consistently picks consistency and a low cost of error over
convenience. Draft text follows the same rule - a request_more_info draft
asks only for what's actually missing and never guesses at it; a
customer_reply never states or implies a coverage or liability
determination, regardless of category, mirroring classify_email's own
auto_reply guardrail.
"""
import time

import config

DRAFT_REPLY_TOOL = {
    "name": "draft_reply",
    "description": (
        "Write the draft text described in the system prompt - either a "
        "customer-facing reply or an internal handoff note for a human "
        "agent, depending on which one the prompt asked you to produce."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "draft_text": {
                "type": "string",
                "description": (
                    "The full draft text, plain prose (no markdown, no "
                    "subject line - subject is handled separately)."
                ),
            },
        },
        "required": ["draft_text"],
    },
}

SYSTEM_PROMPT = (
    "You write draft text for an independent insurance agency's inbound "
    "email triage system. Nothing you write is sent automatically - a "
    "human reviews every draft first. You will be told which of two kinds "
    "of draft to write for this email, based on a classification a "
    "separate step already produced:\n\n"
    "1. customer_reply - text meant to go to the customer directly, once "
    "a human has reviewed it. Written for suggested_action=auto_reply or "
    "request_more_info.\n"
    "2. internal_handoff_note - a short briefing FOR THE HUMAN AGENT who "
    "will handle this, not for the customer. Written for "
    "suggested_action=escalate_human.\n\n"
    "Hard rules that apply no matter which kind you're writing:\n"
    "- Never state or invent a specific fact that wasn't given to you - a "
    "claim status, a dollar amount, a date, a coverage determination. If "
    "the real answer isn't in what you were given, say a specific person "
    "or team will follow up with it - don't guess, and don't fill the gap "
    "with a plausible-sounding placeholder.\n"
    "- A customer_reply must never state or imply a coverage or liability "
    "determination - confirming or denying that a loss is covered, "
    "promising a settlement amount, or interpreting policy language "
    "authoritatively. That determination-avoidance rule applies "
    "regardless of category, the same guardrail classify_email itself "
    "uses for auto_reply.\n"
    "- If a safety_instruction was provided, it describes an active "
    "physical danger. Open the draft with that instruction verbatim, "
    "before anything else - do not soften, summarize, or bury it.\n"
    "- For request_more_info, ask only for the specific piece(s) of "
    "information actually missing. Do not guess what the customer "
    "probably meant instead of asking, even when a plausible guess "
    "exists - this project consistently prefers a low cost of error over "
    "saving the customer a round trip (the same design principle behind "
    "coverage_question's own action boundary).\n\n"
    "--- If writing a customer_reply, category-specific guidance: ---\n"
    "- new_claim: acknowledge the loss was reported, note an adjuster "
    "will be in touch, and do not promise or imply any outcome.\n"
    "- claim_status: acknowledge the status request. You do not have "
    "access to the actual claim system, so never state a specific status "
    "- say a specific person or team will provide the real update, "
    "referencing the claim number if one was given.\n"
    "- coverage_question: you're only writing a customer_reply for this "
    "category when it's a plain factual feature-existence question - "
    "answer only what was actually asked, and still never phrase it as a "
    "determination about this customer's own situation.\n"
    "- policy_change: acknowledge exactly what's being requested. If "
    "anything about it still needs review, say so plainly rather than "
    "implying it's already done.\n"
    "- document_request: confirm what document is being sent or what's "
    "needed before it can be.\n"
    "- billing_issue: acknowledge the billing question. Do not promise a "
    "credit, refund, or specific corrected amount.\n"
    "- other: a brief, plain acknowledgment appropriate to what was "
    "asked.\n"
    "(sales_lead and complaint always escalate_human, so they never reach "
    "this branch.)\n\n"
    "--- If writing an internal_handoff_note, instead: ---\n"
    "Write a short, factual briefing for the human agent who will handle "
    "this - not a message to the customer. Include: the category and "
    "urgency, a one-line summary of what the customer wants, why this "
    "needs a human (underwriting risk, a complaint, a sales inquiry, a "
    "billing dispute, etc. - whatever applies for this category), and any "
    "extracted fields you were given (policy number, customer name, date "
    "of loss). If you were given additional_issues, you MUST explicitly "
    "list every single one of them by category and description in its own "
    "line - this is not optional. A multi-issue email's second ask has "
    "nowhere else to surface once this note is written; dropping it here "
    "silently defeats the entire point of tracking it."
)


def determine_draft_type(suggested_action: str) -> str:
    """
    Deterministic, not model-decided - same philosophy as
    classifier.py's apply_additional_issues_override() and
    score_coverage_question(). escalate_human always gets an internal
    handoff note (a human is taking this over directly); auto_reply and
    request_more_info both get a customer-facing reply.
    """
    return "internal_handoff_note" if suggested_action == "escalate_human" else "customer_reply"


def _build_decision_context(decision: dict, draft_type: str) -> str:
    lines = [
        f"Write a: {draft_type}",
        f"category: {decision.get('category')}",
        f"urgency: {decision.get('urgency')}",
        f"suggested_action: {decision.get('suggested_action')}",
        f"summary: {decision.get('summary')}",
    ]
    for field in ("policy_number", "customer_name", "date_of_loss"):
        value = decision.get(field)
        if value:
            lines.append(f"{field}: {value}")

    safety_instruction = decision.get("safety_instruction")
    if safety_instruction:
        lines.append(f"safety_instruction (must open the draft with this verbatim): {safety_instruction}")

    additional_issues = decision.get("additional_issues") or []
    if additional_issues:
        lines.append("additional_issues (must each be explicitly listed in an internal_handoff_note):")
        for issue in additional_issues:
            lines.append(f"  - {issue.get('category')}: {issue.get('short_description')}")

    return "\n".join(lines)


def generate_draft(subject: str, body: str, decision: dict) -> dict:
    """
    Returns a dict with keys:
      draft_text     - the generated draft (customer_reply or
                        internal_handoff_note text)
      draft_type     - "customer_reply" or "internal_handoff_note"
      latency_ms     - how long the API call took
      raw_response   - the full API response, for logging/observability
      prompt_version - which prompt version produced this (from config)
      model_name     - which model produced this (from config)

    Takes the already-computed classify_email() decision rather than
    reclassifying - draft-generation is a separate step downstream of
    triage, not a replacement for it.
    """
    draft_type = determine_draft_type(decision.get("suggested_action"))
    email_text = f"Subject: {subject or '(no subject)'}\n\n{body}"
    decision_context = _build_decision_context(decision, draft_type)
    user_message = f"{decision_context}\n\n---\nOriginal customer email:\n{email_text}"

    start = time.time()
    response = config.anthropic_client.messages.create(
        model=config.MODEL_NAME,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[DRAFT_REPLY_TOOL],
        tool_choice={"type": "tool", "name": "draft_reply"},
        messages=[{"role": "user", "content": user_message}],
    )
    latency_ms = int((time.time() - start) * 1000)

    tool_use_block = next(block for block in response.content if block.type == "tool_use")
    draft_text = tool_use_block.input["draft_text"]

    return {
        "draft_text": draft_text,
        "draft_type": draft_type,
        "latency_ms": latency_ms,
        "raw_response": response.model_dump(),
        "prompt_version": config.PROMPT_VERSION,
        "model_name": config.MODEL_NAME,
    }
