"""
The ingestion endpoint. In production this is the URL you'd hand to an
inbound-email service (SendGrid Inbound Parse, Mailgun Routes) so real email
gets POSTed here as JSON. For now it's fed by curl / sample_emails/*.json
while the agent is being built and evaluated.

A "blueprint" here is just Flask's term for a self-contained group of routes
that gets registered onto the main app in app.py - same pattern as
dispatch.py / billing.py in the HVAC project.
"""
from flask import Blueprint, request, jsonify

import config
import db
from classifier import classify_email

ingestion_bp = Blueprint("ingestion", __name__)

# Placeholder values the API refuses to accept for required fields - keeps a
# blank or lazily-mocked payload from silently creating garbage rows.
_REJECTED_VALUES = {"", "unknown", "n/a", "na", "tbd", "none", "null"}


def _is_blank(value):
    return value is None or str(value).strip().lower() in _REJECTED_VALUES


@ingestion_bp.route("/inbound-email", methods=["POST"])
def inbound_email():
    if request.headers.get("X-API-Key") != config.APP_SECRET_KEY:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400

    sender_email = payload.get("from")
    subject = payload.get("subject")
    body = payload.get("text")

    if _is_blank(sender_email) or _is_blank(body):
        return jsonify({"error": "'from' and 'text' are required and cannot be blank"}), 400

    raw_email_id = db.save_raw_email(
        sender_email=sender_email,
        subject=subject,
        body=body,
        raw_payload=payload,
    )

    result = classify_email(subject, body)

    decision_id = db.save_decision(
        raw_email_id=raw_email_id,
        decision=result["decision"],
        prompt_version=result["prompt_version"],
        model_name=result["model_name"],
        latency_ms=result["latency_ms"],
        raw_model_response=result["raw_response"],
    )

    return jsonify(
        {
            "raw_email_id": raw_email_id,
            "decision_id": decision_id,
            "decision": result["decision"],
            "latency_ms": result["latency_ms"],
        }
    ), 201
