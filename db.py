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
