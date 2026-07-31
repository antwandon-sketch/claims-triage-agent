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
                "enum": ["new_claim", "claim_status", "coverage_question", "policy_change", "other"],
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
        },
        "required": ["category", "urgency", "summary", "suggested_action", "confidence", "rationale"],
    },
}

SYSTEM_PROMPT = (
    "You triage inbound email for an independent insurance agency. Read the "
    "email and call classify_email with your assessment. Never invent a "
    "policy number, name, or date that isn't in the email - omit the field "
    "instead of guessing. When urgency is ambiguous, prefer the lower-risk "
    "reading only if there is no plausible safety or property-damage concern."
)


def classify_email(email_text: str) -> dict:
    """
    Returns a dict with keys:
      decision       - the parsed structured output (category, urgency, etc.)
      latency_ms      - how long the API call took
      raw_response    - the full API response, for logging/observability
      prompt_version  - which prompt version produced this (from config)
      model_name      - which model produced this (from config)
    """
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
