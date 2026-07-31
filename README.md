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

**Phase 1:** ingestion endpoint, Claude classifier, decision logging to
Postgres. Confirmed working end to end against a live database and the
real Claude API.

**Phase 2:** folded into Phase 1 from the start - every decision already
logs latency, prompt version, model name, and the full raw model response.

**Phase 3 (this commit):** a 20-case hand-labeled golden dataset
(`eval/golden_dataset.json`) and an eval harness (`eval/run_eval.py`) that
runs the classifier against it, reports category/urgency/action accuracy
plus a confusion matrix, and saves each run's scores to the `eval_runs`
table so accuracy can be tracked across prompt versions over time. The
scoring logic itself is unit tested (`tests/test_eval_scoring.py`) with
fixed inputs, independent of how the classifier is actually performing.

**Coming next:**
- Phase 4 - a small dashboard over `agent_decisions` and `eval_runs` history

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

## Running the eval harness

```bash
python -m eval.run_eval
```

This runs all 20 golden-dataset cases through the real classifier (real API
calls, small real cost), prints an accuracy report and confusion matrix,
saves the summary to `eval_runs` in Postgres, and writes a detailed
per-case breakdown to `eval_results/`.

## Manually testing the endpoint

```bash
curl -X POST http://localhost:5002/inbound-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <value from your .env>" \
  -d @sample_emails/01_urgent_new_claim.json
```
