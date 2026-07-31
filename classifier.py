"""
The reasoning step: hands an email to Claude and gets back a structured
decision - never free-form text. Same idea as the booking flow's function
calling in the HVAC project, just a different schema.

We force the model to use the classify_email tool (tool_choice) so the
response is always valid JSON matching CLASSIFY_EMAIL_TOOL, never a stray
paragraph we'd have to parse with regex.
"""
import time

import config

CLASSIFY_EMAIL_TOOL = {
    "name": "classify_email",
    "description": (
        "Classify an inbound email to an insurance agency and extract the "
        "key facts needed to route and respond to it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "new_claim", "claim_status", "coverage_question", "policy_change",
                    "billing_issue", "sales_lead", "complaint", "document_request", "other",
                ],
                "description": "The single best-fitting category for this email.",
            },
            "urgency": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": (
                    "high = active emergency or immediate safety/property risk, "
                    "medium = time-sensitive but not an emergency, "
                    "low = routine question or administrative request."
                ),
            },
            "policy_number": {
                "type": "string",
                "description": "Policy number if mentioned, otherwise omit.",
            },
            "customer_name": {
                "type": "string",
                "description": "Sender's name if it can be determined, otherwise omit.",
            },
            "date_of_loss": {
                "type": "string",
                "description": "Date the incident occurred, if this is claim-related and a date is given.",
            },
            "summary": {
                "type": "string",
                "description": "One or two sentence plain-language summary of what the customer needs.",
            },
            "suggested_action": {
                "type": "string",
                "enum": ["auto_reply", "escalate_human", "request_more_info"],
                "description": (
                    "auto_reply = a confident, routine answer can be drafted automatically; "
                    "escalate_human = needs an agent's judgment or is high-stakes; "
                    "request_more_info = the email is missing details needed to act on it."
                ),
            },
            "confidence": {
                "type": "number",
                "description": "Self-reported confidence in this classification, from 0.0 to 1.0.",
            },
            "rationale": {
                "type": "string",
                "description": "One sentence explaining why this category/urgency/action were chosen.",
            },
            "safety_instruction": {
                "type": "string",
                "description": (
                    "ONLY populate this if the email describes an active, immediate "
                    "physical danger happening right now - a gas leak, a downed power "
                    "line, a carbon monoxide alarm, an active fire, someone trapped or "
                    "injured needing help right now. Give one short, direct instruction "
                    "for what the customer should do immediately (evacuate, call 911, "
                    "call the gas company's emergency line). Omit this field entirely "
                    "for anything else, including already-resolved incidents, routine "
                    "claims, and urgent-sounding but non-hazardous requests."
                ),
            },
        },
        "required": ["category", "urgency", "summary", "suggested_action", "confidence", "rationale"],
    },
}

SYSTEM_PROMPT = (
    "You triage inbound email for an independent insurance agency. Read the "
    "email and call classify_email with your assessment. Never invent a "
    "policy number, name, or date that isn't in the email - omit the field "
    "instead of guessing. When urgency is ambiguous, prefer the lower-risk "
    "reading only if there is no plausible safety or property-damage concern.\n\n"
    "Category definitions, since several are easy to confuse:\n"
    "- policy_change: the request changes something actually written on the "
    "policy - coverage limits, drivers, insured property, address, phone "
    "number, or correcting a misspelled name on the policy. Escalate to a "
    "human anything that affects underwriting risk or premium (adding or "
    "removing a driver, canceling a policy, adding a newly insured property "
    "or vehicle). Routine administrative changes (address/phone/name "
    "corrections, dwelling coverage increases with no new risk information) "
    "can be handled with auto_reply.\n"
    "- document_request: the customer wants a document produced or reissued "
    "FROM the policy, without changing anything on it - a certificate of "
    "insurance, an ID card, a copy of the declarations page. A simple resend "
    "of something the customer should already have can be auto_reply; "
    "anything naming a third party (a landlord, lienholder) or requiring "
    "verification should escalate_human.\n"
    "- billing_issue: a payment, premium, or billing-account problem "
    "(overcharge, failed autopay, payment plan questions). These almost "
    "always need a human to actually investigate or correct, so default to "
    "escalate_human unless it's a simple factual billing question with no "
    "problem to fix.\n"
    "- complaint: dissatisfaction with service itself (unresponsive staff, "
    "rude interaction) rather than disputing a specific claim decision - a "
    "dispute over a claim's outcome is claim_status, not complaint. Almost "
    "always escalate_human - auto-replying to a complaint tends to make "
    "things worse, not better.\n"
    "- sales_lead: a prospective customer, not an existing policyholder "
    "matter. Always escalate_human - only a licensed producer can actually "
    "quote or bind coverage.\n"
    "- other: genuinely doesn't fit any category above - general questions "
    "unrelated to a specific policy, unsubscribe requests, job inquiries, "
    "and similar.\n\n"
    "A few urgency clarifications, since it's easy to let category or "
    "action bleed into this judgment:\n"
    "- Urgency and suggested_action are independent. A policy_change that "
    "needs a human for underwriting reasons (adding/removing a driver, a "
    "newly insured asset) is not automatically higher urgency just because "
    "it escalates - if the email itself describes no time pressure, rate "
    "it low urgency even though the action is escalate_human.\n"
    "- Urgency reflects the current state of the situation only, not "
    "whether this is a brand-new claim or an existing one being reopened "
    "or followed up on. Active or worsening property damage is high "
    "urgency whether it was just discovered or is a recurrence of a "
    "previous claim.\n\n"
    "Before anything else, check for active physical danger: if the email "
    "describes a gas leak, a downed power line, a carbon monoxide alarm, "
    "an active fire, or someone trapped or injured right now, populate "
    "safety_instruction with a short, direct instruction the customer "
    "should follow immediately. This matters more than getting category "
    "or urgency exactly right. Do not populate it for anything else - "
    "an already-resolved incident, a routine claim, or dramatic-sounding "
    "language with no actual physical hazard. False alarms undermine "
    "trust in the real ones, so only use this for genuine, active danger."
)


def classify_email(subject: str, body: str) -> dict:
    """
    Returns a dict with keys:
      decision       - the parsed structured output (category, urgency, etc.)
      latency_ms      - how long the API call took
      raw_response    - the full API response, for logging/observability
      prompt_version  - which prompt version produced this (from config)
      model_name      - which model produced this (from config)

    Takes subject separately from body (rather than body alone, as Phase 1
    originally did) because subject lines often carry real signal - "URGENT"
    or "Re: still no response" changes the read on urgency even when the
    body text alone looks routine.
    """
    email_text = f"Subject: {subject or '(no subject)'}\n\n{body}"

    start = time.time()
    response = config.anthropic_client.messages.create(
        model=config.MODEL_NAME,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[CLASSIFY_EMAIL_TOOL],
        tool_choice={"type": "tool", "name": "classify_email"},
        messages=[{"role": "user", "content": email_text}],
    )
    latency_ms = int((time.time() - start) * 1000)

    tool_use_block = next(block for block in response.content if block.type == "tool_use")
    decision = tool_use_block.input

    return {
        "decision": decision,
        "latency_ms": latency_ms,
        "raw_response": response.model_dump(),
        "prompt_version": config.PROMPT_VERSION,
        "model_name": config.MODEL_NAME,
    }
