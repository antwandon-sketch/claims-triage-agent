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

**Since Phase 3 (prompt v3-v11):**
- Prompt versions v3 through v6 shipped: category schema expanded 5 -> 9,
  urgency-bleed bug fixed in the `policy_change` rule, `safety_instruction`
  field + safety-critical stress harness added, and a surgical urgency fix
  in v6, then v7 added written definitions for the 3 previously-undefined
  categories plus a general auto_reply coverage-determination guardrail.
- Golden dataset grown from 20 to 57 hand-labeled cases, split 26 train /
  31 holdout.
- **v8 and v9 (reverted, never shipped):** two attempts to fix a specific
  `coverage_question` urgency/action instability by rewording the
  category's prompt text in prose. Each fix traced cleanly by hand and
  passed initial spot checks, but a full 3x regression run showed the
  same failure shape both times: it fixed the targeted case and
  destabilized a different one nearby (v8: case_31/case_25; v9:
  case_04/case_05/case_10). Neither shipped - see progress-log.md's v8
  and v9 entries.
- **v10 (built, reverted before shipping):** rather than a third prose
  rewrite, `coverage_question`'s `auto_reply` / `request_more_info` /
  `escalate_human` boundary was redesigned as extract-then-decide - the
  model only extracts 6 independently-defined boolean facts about the
  email (does it reference a specific incident, is there a liability
  signal, etc.), and a plain deterministic Python function computes the
  action from those booleans, no LLM judgment call involved. This fully
  solved the category's own instability (0 action misses across 3
  full-suite runs). But matched git-stash A/B testing surfaced a real,
  reproducible regression in an unrelated category - one `billing_issue`
  case dropped from 100% reliable under v7 to roughly 60-80% reliable
  under v10, depending on sample. Not shipped pending root cause.
- **v11 (current, shipped):** five rounds of controlled testing -
  isolating the schema change, isolating the prompt-text change, a full
  4x2x10 factorial across both variables, a time-drift-controlled
  interleaved run, and a targeted isolation of one specific sentence -
  traced the v10 regression to a self-referential "three prior attempts
  each fixed one case while breaking another" narrative the v10 prompt
  text used to explain itself to the model. That sentence, not the
  schema and not the actual extraction/decision logic, was destabilizing
  the unrelated case. Removing only that sentence (keeping every
  operational instruction, field description, and worked example
  unchanged) fixed it: the previously-unreliable case is back to 0
  misses across 3 full-suite runs, matching v7. Full investigation
  across all five diagnostic rounds is in progress-log.md.
- Latest full eval (v11, 3 runs): category 96.5-98.2%, urgency
  89.5-91.2%, action 96.5-98.2% (v7 baseline for comparison: 96.5%
  category, 93.0% urgency, 96.5% action). Category and action match or
  exceed the baseline in every run; the urgency dip is within the
  case-level variance already documented for a couple of known cases,
  not a new issue.
- One known, low-severity open item: one `document_request` case
  (case_54) intermittently gets urgency wrong (flagged medium instead of
  low) under v11 - confirmed via stash A/B that this is new relative to
  v7. Category and the actual routing decision (`escalate_human`) are
  correct every time, so the email still reaches a human either way;
  this only affects queue priority, not the outcome. Not yet root-caused
  - flagged as a follow-up, not a blocker.
- Safety-critical stress harness (separate from the accuracy eval):
  10/10, zero false negatives - holds across v7, v10, and v11.
- Prompt-injection stress harness (6 cases): 3/6 clean under v11 (up
  from a 2/6 baseline confirmed identical under both v7 and v10 via
  stash A/B - a pre-existing gap, not caused by any prompt version
  tested so far). No false negatives on the safety-critical set; the
  injection failures are the model following instructions embedded in
  email bodies for 2-3 of the 6 adversarial cases. Not yet root-caused -
  a real, separately-tracked open item (see progress-log.md).

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

The golden dataset is 57 cases across 9 categories (`new_claim`,
`claim_status`, `coverage_question`, `policy_change`, `billing_issue`,
`sales_lead`, `complaint`, `document_request`, `other`), split into 26
`train` (cases the prompt has been tuned against) and 31 `holdout` (cases
only ever checked for score, never used to guide a prompt edit).

```bash
python -m eval.run_eval                  # runs everything, reports train/holdout/all
python -m eval.run_eval --split train    # just the cases you tune against
python -m eval.run_eval --split holdout  # just the cases you don't
```

This makes real API calls (a few cents total for the full set), prints an
accuracy report and confusion matrix for each view, saves the run's summary
to `eval_runs` in Postgres, and writes a detailed per-case breakdown to
`eval_results/`.

## Running the safety-critical stress test

Separate from the accuracy harness above - this tests a narrower, binary
safety property: does the classifier correctly recognize an active
physical emergency (gas leak, downed power line, CO alarm, active fire,
someone trapped/injured) and populate `safety_instruction`, and does it
correctly stay silent on routine or already-resolved situations (including
deliberately dramatic-sounding but non-hazardous emails)?

```bash
python -m eval.run_stress_tests
```

A **false negative** (a real emergency with no safety instruction) is
treated as the dangerous failure direction and called out separately from
a **false positive** (a routine case that got a safety instruction
anyway) - the two aren't equally bad, so the report never collapses them
into one accuracy number.

## Manually testing the endpoint

```bash
curl -X POST http://localhost:5002/inbound-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <value from your .env>" \
  -d @sample_emails/01_urgent_new_claim.json
```
