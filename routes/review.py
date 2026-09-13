"""
Human-approval gate for generated drafts. Nothing in this file sends
anything - approving a draft only flips its status in the drafts table
(pending_approval -> approved). Sending is explicitly separate, future
work (see PROJECT.md's "What's not built yet").

reviewed_by is a plain string/email for now, not tied to a real auth
system - there is no user model in this codebase yet, so it's taken as
given in the request body rather than derived from a session.
"""
from flask import Blueprint, request, jsonify

import config
import db

review_bp = Blueprint("review", __name__)

# Same placeholder-rejection convention as routes/ingestion.py's _is_blank -
# keeps a blank or lazily-mocked reviewed_by from silently getting recorded.
_REJECTED_VALUES = {"", "unknown", "n/a", "na", "tbd", "none", "null"}


def _is_blank(value):
    return value is None or str(value).strip().lower() in _REJECTED_VALUES


def _check_api_key():
    """Returns a (response, status) tuple to short-circuit on, or None if
    the request is authorized. Same X-API-Key convention as
    routes/ingestion.py, applied here too since this gate gets to change
    review status on decisions - at least as sensitive as ingestion."""
    if request.headers.get("X-API-Key") != config.APP_SECRET_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


def _conflict_or_not_found(draft_id):
    """Called only when an approve/reject UPDATE matched no row - figures
    out whether that's because the draft doesn't exist at all, or because
    it's already been reviewed (and so isn't pending_approval anymore)."""
    existing = db.get_draft(draft_id)
    if existing is None:
        return jsonify({"error": f"no draft with id {draft_id}"}), 404
    return jsonify(
        {
            "error": (
                f"draft {draft_id} is not pending approval "
                f"(current status: {existing['status']})"
            )
        }
    ), 409


@review_bp.route("/drafts/pending", methods=["GET"])
def pending_drafts():
    auth_error = _check_api_key()
    if auth_error:
        return auth_error

    drafts = db.list_drafts(status="pending_approval")
    return jsonify({"drafts": drafts}), 200


@review_bp.route("/drafts/<int:draft_id>/approve", methods=["POST"])
def approve_draft(draft_id):
    auth_error = _check_api_key()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    reviewed_by = payload.get("reviewed_by")
    if _is_blank(reviewed_by):
        return jsonify({"error": "'reviewed_by' is required and cannot be blank"}), 400

    # approve_draft()'s UPDATE only matches status='pending_approval', so
    # this is also what stops a draft from being approved twice - a second
    # call matches no row and lands in the conflict branch below.
    row = db.approve_draft(draft_id, reviewed_by)
    if row is not None:
        return jsonify({"draft": row}), 200
    return _conflict_or_not_found(draft_id)


@review_bp.route("/drafts/<int:draft_id>/reject", methods=["POST"])
def reject_draft(draft_id):
    auth_error = _check_api_key()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    reviewed_by = payload.get("reviewed_by")
    rejection_reason = payload.get("rejection_reason")
    if _is_blank(reviewed_by):
        return jsonify({"error": "'reviewed_by' is required and cannot be blank"}), 400

    row = db.reject_draft(draft_id, reviewed_by, rejection_reason)
    if row is not None:
        return jsonify({"draft": row}), 200
    return _conflict_or_not_found(draft_id)
