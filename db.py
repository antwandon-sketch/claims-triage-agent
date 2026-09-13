"""
Neon (Postgres) persistence layer.

Phase 1 tables:
  raw_emails       - the inbound email, as received
  agent_decisions  - what Claude decided about it, plus everything needed
                     for observability (prompt version, latency, raw response)

Phase 3 adds eval_runs (score history) here. The golden dataset itself
(eval/golden_dataset.json) deliberately lives as a version-controlled file,
not a table - that's the normal convention for eval test data, since you
want to review changes to your test cases the same way you'd review a diff
to any other test file, not by querying a database.

drafts (added alongside draft_generator.py): the draft text produced from
an agent_decisions row - a customer_reply or an internal_handoff_note (see
draft_generator.py's module docstring). This table only stores text for a
human to review; there is still no send capability anywhere in this
codebase.

drafts.status (added alongside routes/review.py, the human-approval gate):
pending_approval -> approved | rejected. Nothing in this codebase moves a
draft to a hypothetical future 'sent' status - that requires actual send
capability, which doesn't exist yet, so it's deliberately not part of the
status set below until it does.
"""
import json
import psycopg2
import psycopg2.extras

import config


def get_connection():
    return psycopg2.connect(config.DATABASE_URL)


def init_db():
    """Create tables if they don't already exist. Safe to run repeatedly."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_emails (
                    id SERIAL PRIMARY KEY,
                    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    sender_email TEXT NOT NULL,
                    subject TEXT,
                    body TEXT NOT NULL,
                    raw_payload JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_decisions (
                    id SERIAL PRIMARY KEY,
                    raw_email_id INTEGER NOT NULL REFERENCES raw_emails(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    category TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    policy_number TEXT,
                    customer_name TEXT,
                    date_of_loss TEXT,
                    summary TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    rationale TEXT,
                    safety_instruction TEXT,
                    prompt_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    latency_ms INTEGER,
                    raw_model_response JSONB
                );
                """
            )
            # CREATE TABLE IF NOT EXISTS above only helps on a brand-new
            # database - it's a no-op if agent_decisions already exists,
            # which it does on the live database from Phase 1. This ALTER
            # is what actually adds the new column to that existing table.
            # Safe to re-run - IF NOT EXISTS makes it a no-op afterward.
            cur.execute(
                "ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS safety_instruction TEXT;"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id SERIAL PRIMARY KEY,
                    run_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    prompt_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    total_cases INTEGER NOT NULL,
                    category_accuracy REAL NOT NULL,
                    urgency_accuracy REAL NOT NULL,
                    action_accuracy REAL NOT NULL,
                    confusion_matrix JSONB,
                    notes TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id SERIAL PRIMARY KEY,
                    agent_decision_id INTEGER NOT NULL REFERENCES agent_decisions(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    draft_type TEXT NOT NULL,
                    draft_text TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    latency_ms INTEGER,
                    raw_model_response JSONB,
                    status TEXT NOT NULL DEFAULT 'pending_approval'
                        CHECK (status IN ('pending_approval', 'approved', 'rejected')),
                    reviewed_at TIMESTAMP,
                    reviewed_by TEXT,
                    rejection_reason TEXT
                );
                """
            )
            # As with safety_instruction above: CREATE TABLE IF NOT EXISTS is
            # a no-op against a drafts table that already exists from before
            # the approval gate was added, so these ALTERs are what actually
            # backfill the new columns on a live database. Safe to re-run.
            cur.execute(
                "ALTER TABLE drafts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending_approval';"
            )
            cur.execute("ALTER TABLE drafts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;")
            cur.execute("ALTER TABLE drafts ADD COLUMN IF NOT EXISTS reviewed_by TEXT;")
            cur.execute("ALTER TABLE drafts ADD COLUMN IF NOT EXISTS rejection_reason TEXT;")
            # ADD COLUMN IF NOT EXISTS has no CHECK-constraint equivalent, so
            # the constraint from the CREATE TABLE above wouldn't exist on a
            # table that predates this change. This adds it separately,
            # tolerating "already exists" so re-running init_db() stays safe.
            cur.execute(
                """
                DO $$
                BEGIN
                    ALTER TABLE drafts ADD CONSTRAINT drafts_status_check
                        CHECK (status IN ('pending_approval', 'approved', 'rejected'));
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        conn.commit()


def save_raw_email(sender_email, subject, body, raw_payload):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_emails (sender_email, subject, body, raw_payload)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (sender_email, subject, body, json.dumps(raw_payload)),
            )
            raw_email_id = cur.fetchone()[0]
        conn.commit()
    return raw_email_id


def save_decision(raw_email_id, decision, prompt_version, model_name, latency_ms, raw_model_response):
    """
    decision: dict with keys category, urgency, policy_number, customer_name,
              date_of_loss, summary, suggested_action, confidence, rationale,
              safety_instruction (optional - only present for active physical
              danger cases)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_decisions (
                    raw_email_id, category, urgency, policy_number, customer_name,
                    date_of_loss, summary, suggested_action, confidence, rationale,
                    safety_instruction, prompt_version, model_name, latency_ms,
                    raw_model_response
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    raw_email_id,
                    decision["category"],
                    decision["urgency"],
                    decision.get("policy_number"),
                    decision.get("customer_name"),
                    decision.get("date_of_loss"),
                    decision["summary"],
                    decision["suggested_action"],
                    decision["confidence"],
                    decision.get("rationale"),
                    decision.get("safety_instruction"),
                    prompt_version,
                    model_name,
                    latency_ms,
                    json.dumps(raw_model_response),
                ),
            )
            decision_id = cur.fetchone()[0]
        conn.commit()
    return decision_id


def save_eval_run(prompt_version, model_name, total_cases, category_accuracy,
                   urgency_accuracy, action_accuracy, confusion_matrix, notes=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (
                    prompt_version, model_name, total_cases, category_accuracy,
                    urgency_accuracy, action_accuracy, confusion_matrix, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    prompt_version, model_name, total_cases, category_accuracy,
                    urgency_accuracy, action_accuracy, json.dumps(confusion_matrix), notes,
                ),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
    return run_id


def list_eval_runs(limit=20):
    """Most recent eval runs first - this is the accuracy-over-time history."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM eval_runs ORDER BY run_at DESC LIMIT %s;",
                (limit,),
            )
            return cur.fetchall()


def save_draft(agent_decision_id, draft_type, draft_text, prompt_version, model_name, latency_ms, raw_model_response):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO drafts (
                    agent_decision_id, draft_type, draft_text,
                    prompt_version, model_name, latency_ms, raw_model_response
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent_decision_id,
                    draft_type,
                    draft_text,
                    prompt_version,
                    model_name,
                    latency_ms,
                    json.dumps(raw_model_response),
                ),
            )
            draft_id = cur.fetchone()[0]
        conn.commit()
    return draft_id


def list_drafts(limit=50, status=None):
    """Most recent drafts first, joined back to the decision and original
    email so a reviewer has full context without a second lookup. Pass
    status (e.g. 'pending_approval') to filter to just that status;
    omit it to list drafts regardless of status."""
    query = """
        SELECT dr.*, d.category, d.urgency, d.suggested_action, d.summary,
               e.sender_email, e.subject, e.body
        FROM drafts dr
        JOIN agent_decisions d ON d.id = dr.agent_decision_id
        JOIN raw_emails e ON e.id = d.raw_email_id
    """
    params = []
    if status is not None:
        query += " WHERE dr.status = %s"
        params.append(status)
    query += " ORDER BY dr.created_at DESC LIMIT %s;"
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, tuple(params))
            return cur.fetchall()


def get_draft(draft_id):
    """A single draft by id, no joins - used by the approval endpoints to
    check whether a draft exists and what status it's currently in."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM drafts WHERE id = %s;", (draft_id,))
            return cur.fetchone()


def approve_draft(draft_id, reviewed_by):
    """
    Moves a draft from pending_approval to approved, stamping reviewed_at/
    reviewed_by. The WHERE clause requires status = 'pending_approval', so
    this is also what stops a draft from being approved twice (or approved
    after already being rejected) - the UPDATE simply matches no row and
    returns None. Callers that need to distinguish "no such draft" from
    "already reviewed" should call get_draft() first.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE drafts
                SET status = 'approved', reviewed_at = NOW(), reviewed_by = %s
                WHERE id = %s AND status = 'pending_approval'
                RETURNING *;
                """,
                (reviewed_by, draft_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def reject_draft(draft_id, reviewed_by, rejection_reason=None):
    """Same one-way-transition guarantee as approve_draft(): only succeeds
    from pending_approval, so a draft can't be rejected twice or rejected
    after already being approved."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE drafts
                SET status = 'rejected', reviewed_at = NOW(), reviewed_by = %s,
                    rejection_reason = %s
                WHERE id = %s AND status = 'pending_approval'
                RETURNING *;
                """,
                (reviewed_by, rejection_reason, draft_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def list_decisions(limit=50):
    """Most recent decisions first - used by the observability dashboard (Phase 4)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.*, e.sender_email, e.subject, e.body
                FROM agent_decisions d
                JOIN raw_emails e ON e.id = d.raw_email_id
                ORDER BY d.created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cur.fetchall()
