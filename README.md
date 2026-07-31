# Claims Triage Agent

An email-based AI agent that reads inbound policyholder emails to an
independent insurance agency, classifies them (category, urgency, key
facts), and either drafts a response, requests missing information, or
escalates to a human - logging every decision for later evaluation.

Built as a companion portfolio project to a voice AI agent for home services
missed-call recovery. That project demonstrates real-time voice + booking
automation; this one demonstrates **evals and observability**: every
decision the agent makes is logged, and a labeled test set (a "golden
dataset") is used to measure classification accuracy over time as the
prompt is iterated on.

## Status

**Phase 1 (this commit):** ingestion endpoint, Claude classifier, decision
logging to Postgres. Working end to end against mocked dependencies in the
test suite.

**Coming next:**
- Phase 2 - richer observability logging (already mostly in place: latency,
  prompt version, raw model response are all captured from the start)
- Phase 3 - golden dataset + eval harness + accuracy tracking over prompt
  versions
- Phase 4 - a small dashboard over `agent_decisions` and eval history

## Stack

- Flask - `/inbound-email` webhook endpoint (the same shape a service like
  SendGrid Inbound Parse or Mailgun Routes would call in production)
- Claude (`claude-sonnet-5`) - forced structured output via tool use, so the
  response is always valid JSON, never free-form text
- Postgres (Neon) - `raw_emails` and `agent_decisions` tables
- pytest - endpoint tests run against mocked DB and mocked Claude calls, so
  the suite never needs real credentials or spends real API tokens

## Setup

```bash
python3 -m venv triage-env
source triage-env/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# fill in .env with real values - never commit this file
```

## Running locally

```bash
python app.py
```

## Testing

```bash
pytest
```

## Manually testing the endpoint

```bash
curl -X POST http://localhost:5002/inbound-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <value from your .env>" \
  -d @sample_emails/01_urgent_new_claim.json
```
