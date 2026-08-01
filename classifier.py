"""
The reasoning step: hands an email to Claude and gets back a structured
decision - never free-form text. Same idea as the booking flow's function
calling in the HVAC project, just a different schema.

We force the model to use the classify_email tool (tool_choice) so the
response is always valid JSON matching CLASSIFY_EMAIL_TOOL, never a stray
paragraph we'd have to parse with regex.

PROMPT_VERSION v11: the coverage_question bullet's self-referential
"three prior attempts... each fixed one case while breaking another"
narrative (added in v10) was root-caused as the driver of a real
billing_issue regression (case_56) via a controlled, interleaved,
time-drift-ruled-out experiment - see progress-log.md's 2026-08-01
entries. Removed; every operational instruction in the bullet (field
names, worked-examples reference, override note) is unchanged from v10.
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
            "references_specific_incident": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True if the email describes or points to "
                    "a specific triggering event (a particular loss, accident, damage, "
                    "theft, injury) that has already occurred, rather than a general/ "
                    "hypothetical question about coverage terms."
                ),
            },
            "has_policy_or_claim_number": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True if the email includes an explicit "
                    "policy or claim number, or an unambiguous reference to one."
                ),
            },
            "has_liability_or_dispute_signal": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True if EITHER: (1) the email describes a "
                    "third-party injury or property-damage incident that has ALREADY "
                    "occurred or is currently happening, connected to the policyholder "
                    "(e.g., on their property, or caused by their pet, vehicle, or "
                    "actions) - even if nothing has been filed and no dispute has "
                    "started yet; OR (2) the email explicitly frames a hypothetical, "
                    "not-yet-happened scenario using liability/fault/responsibility "
                    "language - asking whether the policyholder would be \"liable,\" "
                    "\"responsible,\" \"at fault,\" or similar, for a potential future "
                    "third-party injury or damage. Also True for language suggesting an "
                    "active dispute over fault, a denial, or a contested coverage "
                    "outcome (\"they said it's not covered,\" an active disagreement). "
                    "False for a hypothetical, not-yet-happened scenario phrased as a "
                    "GENERIC coverage question, without explicit liability/fault/"
                    "responsibility language - even if it mentions a third party's "
                    "property. Worked examples: \"my dog keeps lunging at the fence, if "
                    "he ever got loose and bit someone, would we be LIABLE for that\" is "
                    "True - hypothetical, but explicitly asks about liability/fault for "
                    "a potential future third-party injury. \"if a tree in our yard ever "
                    "fell on the neighbor's shed, does homeowners insurance TYPICALLY "
                    "cover that kind of thing\" is False - hypothetical, mentions a "
                    "third party's property, but is a generic \"does my policy cover "
                    "this type of peril\" question, not an explicit liability/fault "
                    "question."
                ),
            },
            "has_underwriting_or_nonstandard_use_signal": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True if the email describes an ONGOING "
                    "business activity, a commercial use of the property, or another "
                    "LASTING change in risk profile the policy wasn't written for (e.g., "
                    "running a business from home, renting out a room, keeping "
                    "livestock) - a risk the insurer would need to know about and "
                    "potentially underwrite separately. False for routine, TEMPORARY "
                    "personal circumstances, even if physically unusual-sounding - "
                    "these don't change the property's risk profile or require "
                    "separate underwriting. Worked examples: \"I run a dog-boarding "
                    "business out of my basement\" is True (ongoing commercial "
                    "activity). \"We have a storage pod parked in the driveway for a "
                    "few days during a home move\" is False (temporary, routine, just "
                    "an ordinary moving-related inconvenience)."
                ),
            },
            "asks_feature_existence_only": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True ONLY if the question has NO personal "
                    "or situational anchor at all - it could be asked by any "
                    "policyholder regardless of their specific circumstances, "
                    "answerable with one generic yes/no fact about the policy (a lookup "
                    "against the declarations page). False if the question is tied to "
                    "ANY specific real, hypothetical, or ongoing personal scenario - a "
                    "particular business, a particular pet/property/person, a "
                    "particular item, a particular past or possible future event - EVEN "
                    "IF the question is phrased generically using words like "
                    "\"typically\" or asks \"or do I need something separate\" - that "
                    "kind of generic-sounding phrasing does NOT override a real "
                    "personal anchor. Worked examples: \"does my policy include "
                    "roadside assistance\" is True - no personal scenario at all. \"I "
                    "run a candle business out of my garage, does my policy cover that, "
                    "or do I need something separate?\" is False - despite the "
                    "generic-sounding framing, it's tied to their specific real "
                    "business. \"If my tree fell on my neighbor's fence, does "
                    "homeowners insurance typically cover that kind of thing?\" is "
                    "False - anchored to their specific tree and neighbor, "
                    "\"typically\" doesn't make it a pure lookup. Hypothetical/"
                    "conditional phrasing (\"if X happened, would Y be included\") is "
                    "also NOT a pure lookup on its own. One more example, same "
                    "principle: \"does my policy include rental reimbursement\" is True "
                    "(pure lookup); \"If my car needs repairs after a covered accident, "
                    "would a rental be included\" is False - still requires evaluating "
                    "whether that future scenario would meet the coverage's conditions "
                    "(covered peril? comp/collision requirement? per-day/total limits?)."
                ),
            },
            "cause_investigated_and_unresolved": {
                "type": "boolean",
                "description": (
                    "ONLY relevant when category is coverage_question - omit entirely "
                    "for any other category. True if the email indicates the cause of "
                    "the damage/loss has already been actively examined (e.g., "
                    "discovered or inspected during a renovation, repair, or "
                    "investigation) and still cannot be determined. False if the cause "
                    "is clear/undisputed, or unknown only because the customer hasn't "
                    "investigated further yet (a passive, just-noticed observation)."
                ),
            },
        },
        "required": ["category", "urgency", "summary", "suggested_action", "confidence", "rationale"],
    },
}


def score_coverage_question(
    references_specific_incident: bool,
    has_policy_or_claim_number: bool,
    has_liability_or_dispute_signal: bool,
    has_underwriting_or_nonstandard_use_signal: bool,
    asks_feature_existence_only: bool,
    cause_investigated_and_unresolved: bool,
) -> str:
    """
    Deterministic suggested_action for coverage_question emails, derived
    from exhaustive reasoning over all 64 combinations of these 6 booleans
    (see eval/coverage_question_FINAL_DESIGN.md) - not another prose
    judgment call for the model to make. Three prior prompt-only attempts
    at this category's action boundary (v7's reword, v8's revert, v9's
    rewrite) each fixed a targeted case while destabilizing another; this
    replaces that single LLM judgment with narrow LLM fact-extraction (the
    6 booleans above) feeding this plain decision logic instead. v10
    shipped this but introduced a billing_issue regression via unrelated
    prompt text explaining this history to the model; v11 keeps this
    function and the 6 fields, only removing that explanatory text.
    """
    if has_liability_or_dispute_signal:
        return "escalate_human"
    if cause_investigated_and_unresolved:
        return "escalate_human"
    if has_underwriting_or_nonstandard_use_signal:
        return "escalate_human"
    if (not has_policy_or_claim_number) or references_specific_incident:
        return "request_more_info"
    if asks_feature_existence_only:
        return "auto_reply"
    return "request_more_info"

SYSTEM_PROMPT = (
    "You triage inbound email for an independent insurance agency. Read the "
    "email and call classify_email with your assessment. Never invent a "
    "policy number, name, or date that isn't in the email - omit the field "
    "instead of guessing. When urgency is ambiguous, prefer the lower-risk "
    "reading only if there is no plausible safety or property-damage concern.\n\n"
    "Category definitions, since several are easy to confuse:\n"
    "- new_claim: the customer is reporting a loss or incident for the "
    "first time and has no existing claim number - a fire, accident, "
    "theft, or storm/weather damage, whether just discovered, still "
    "active, or already resolved. Always escalate_human; initiating a "
    "claim requires an adjuster's judgment regardless of urgency.\n"
    "- claim_status: the customer references an existing claim number and "
    "is following up on it - checking status, submitting requested "
    "documents, disputing an outcome, or reporting the loss has recurred. "
    "A simple no-rush status check or document submission can be "
    "auto_reply; disputes, denials, payment delays, and reopened/"
    "recurring damage need escalate_human.\n"
    "- coverage_question: the customer is asking, before any claim is "
    "filed, whether their policy would cover a specific scenario. "
    "Populate the 6 fields references_specific_incident, has_policy_or_claim_number, "
    "has_liability_or_dispute_signal, "
    "has_underwriting_or_nonstandard_use_signal, "
    "asks_feature_existence_only, and cause_investigated_and_unresolved "
    "as accurately as you can (see each field's own description for its "
    "exact definition and worked examples) - suggested_action for this "
    "category is computed deterministically from those 6 fields "
    "downstream, not decided by you. Still provide some suggested_action "
    "value to satisfy the schema, but it will be overridden and doesn't "
    "need to be precise.\n"
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
    "A general rule for auto_reply, regardless of category: auto_reply "
    "must never make or imply a coverage or liability determination - "
    "confirming or denying that a loss is covered, promising a "
    "settlement amount, or interpreting policy language authoritatively. "
    "If a determination is genuinely needed, use request_more_info or "
    "escalate_human instead.\n\n"
    "A few urgency clarifications, since it's easy to let category or "
    "action bleed into this judgment:\n"
    "- For policy_change requests specifically: needing a human for "
    "underwriting reasons (adding/removing a driver, a newly insured "
    "asset) does not by itself raise urgency. Rate these low unless the "
    "email itself also describes something time-sensitive.\n"
    "- Medium urgency isn't limited to active hazards - it also covers "
    "situations where a delay has real consequences even with no property "
    "or safety risk: a customer waiting on an existing claim, a dispute "
    "over money or a decision, or a complaint about service that could "
    "get worse if ignored. Reserve low urgency for requests where the "
    "timing genuinely doesn't matter - routine administrative changes, "
    "document requests, and general questions with no dependency on when "
    "they're handled.\n"
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

    if decision.get("category") == "coverage_question":
        decision["suggested_action"] = score_coverage_question(
            bool(decision.get("references_specific_incident", False)),
            bool(decision.get("has_policy_or_claim_number", False)),
            bool(decision.get("has_liability_or_dispute_signal", False)),
            bool(decision.get("has_underwriting_or_nonstandard_use_signal", False)),
            bool(decision.get("asks_feature_existence_only", False)),
            bool(decision.get("cause_investigated_and_unresolved", False)),
        )

    return {
        "decision": decision,
        "latency_ms": latency_ms,
        "raw_response": response.model_dump(),
        "prompt_version": config.PROMPT_VERSION,
        "model_name": config.MODEL_NAME,
    }
