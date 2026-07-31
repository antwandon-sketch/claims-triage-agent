# Claims Triage Agent — AI Systems

**Master context doc.** Say "read PROJECT.md" at the start of a new thread
to get full context immediately. For the detailed, chronological build
history (useful for understanding *why* a decision was made, not just
what the current state is), see `progress-log.md`.

Last updated: 2026-07-31

---

## The Project

**Purpose:** A second AI-agent portfolio piece, deliberately different
from the `ai-consulting-lab` HVAC voice agent - that one demonstrates
real-time voice + booking automation; this one demonstrates **evals and
observability**, targeting AI Engineer / Forward Deployed Engineer roles.

**What it does:** Reads inbound insurance-agency policyholder email,
classifies it (category, urgency, key fields, suggested action) using
Claude with forced structured output, and logs every decision for
measurement - the classification core, not yet a full send-and-close-loop
system (see "What's not built yet" below).

**Repo:** `github.com/antwandon-sketch/claims-triage-agent` (own top-level
repo, deliberately kept separate from `ai-consulting-lab` rather than
nested in its `agents/` folder - a hiring manager should be able to open
this repo and immediately understand it's a distinct piece of work).

**Possible future use:** A friend's manager at a Farmers Insurance
affiliate in Kyle, TX was pitched informally ~2 months ago and may be
interested. Deliberately not reaching out until the build is solid -
this is a portfolio piece first, a pitch second.

---

## Current State

| Thing | Status |
|---|---|
| Ingestion endpoint | `POST /inbound-email` - Flask, live-tested end to end against Neon + real Claude API |
| Classifier | Claude Sonnet 5, forced structured output via tool use, **PROMPT_VERSION v6** |
| Categories | 9: new_claim, claim_status, coverage_question, policy_change, billing_issue, sales_lead, complaint, document_request, other (expanded from an original 5 after v3 - see progress-log for why) |
| Golden dataset | 57 hand-labeled cases (`eval/golden_dataset.json`), split 26 train / 31 holdout |
| Latest full eval | Category ~96.5%, urgency ~94.7%, action ~93.0% on ALL (see progress-log.md's most recent entry for the exact current numbers - they get re-measured every prompt version) |
| Safety-critical stress test | Separate harness (`eval/run_stress_tests.py`), 10 cases (5 real emergencies + 5 false-positive traps). Last real run: 10/10, zero false negatives |
| `safety_instruction` field | New classifier output field - populated only for active physical danger (gas leak, downed power line, CO alarm, active fire, someone trapped/injured), persisted to `agent_decisions.safety_instruction` |
| `eval_runs` table | Tracks accuracy history across prompt versions in Postgres |
| Database | Neon Postgres - separate database from ai-consulting-lab |
| Tests | 28 passing (`pytest -v`) |

**What's not built yet:** the system decides and logs, it doesn't act.
No reply is actually sent for any action (`auto_reply`, `escalate_human`,
`request_more_info`) - there's no outbound send capability yet, and no way
to thread a customer's follow-up reply back to the original case. This is
deliberate, sequenced work for a later phase, the same shape as the HVAC
project's SMS-confirmation gap - get the classification core solid and
measured first.

**Stress-test categories not yet built:** multi-issue emails (two asks in
one email), exaggerated/manipulative urgency language, prompt injection
inside the email body, garbled/low-signal input. Safety-critical was built
first (highest real-world consequence); these four are next, in no fixed
order.

---

## Stack

- **Language/runtime:** Python 3.12, Flask
- **LLM:** Anthropic API, `claude-sonnet-5` (defaults to high reasoning
  effort on the API already - no `effort` parameter needed or set)
- **Relational DB:** Neon (serverless Postgres, free tier) - `db.py`
  handles `init_db()`, `save_raw_email()`, `save_decision()`,
  `list_decisions()`, `save_eval_run()`, `list_eval_runs()`
- **Testing:** pytest - `tests/conftest.py` mocks DB and classifier calls
  entirely, so the suite runs with no real credentials and no API cost
- **Version control:** GitHub (own repo, private)

---

## Repo Structure

```
claims-triage-agent/
├── README.md                 ← public-facing setup/usage docs
├── PROJECT.md                 ← this file
├── progress-log.md            ← detailed, chronological session log
├── app.py                     ← Flask entry point
├── config.py                  ← env vars + shared Anthropic client
├── db.py                      ← Neon persistence (emails, decisions, eval_runs)
├── classifier.py               ← SYSTEM_PROMPT + tool schema (PROMPT_VERSION v6)
├── routes/
│   └── ingestion.py            ← POST /inbound-email
├── eval/
│   ├── golden_dataset.json     ← 57 cases, train/holdout split
│   ├── run_eval.py             ← accuracy harness (--split all/train/holdout)
│   ├── stress_tests.json       ← safety-critical, 10 cases
│   └── run_stress_tests.py     ← safety stress harness (separate from accuracy)
├── tests/
│   ├── conftest.py
│   ├── test_ingestion_endpoint.py
│   ├── test_eval_scoring.py
│   └── test_stress_scoring.py
├── sample_emails/               ← manual curl-testing payloads
├── eval_results/                ← gitignored run outputs
└── .env                         ← gitignored, real credentials
```

---

## Conventions and Hard-Won Lessons (this project specifically)

- **PORT=5002** in `.env` - 5000 is macOS AirPlay, 5001 is the HVAC
  project. Both can run at once without conflict.
- **Never paste real `.env` contents anywhere outside the terminal** -
  not into chat, not into a commit, not into a screenshot. A real
  incident on 2026-07-31 required rotating all three credentials
  (Anthropic key, Neon password, app secret) after a terminal-output
  copy-paste exposed them in chat.
- **Always check actual expected-vs-predicted values, not just the
  aggregate accuracy number, before calling a fix successful.** Caught a
  real illusory improvement this way (v3->v4's headline urgency gain was
  entirely from relabeling, not model improvement - the like-for-like
  score was flat).
- **When a fix seems to break something else, check for repeatability**
  (re-run 2-3 times with no code changes) before assuming it's a real,
  stable effect versus ordinary model variance. This distinguished a real
  regression (case_10/case_20, stable across 3 repeats) from a false
  alarm (case_03, which flipped back to correct on its own).
- **`rationale` and `summary` are captured in eval_results now** - this
  was a real gap (every run through v6 silently discarded them). Read the
  model's actual stated reasoning before theorizing about why a case is
  failing, rather than guessing from the outside.
- **Many "regressions" turn out to be wrong answer-key labels, not real
  model problems.** Several rounds this session found the golden dataset's
  expected label didn't actually match the system prompt's own stated
  definitions - sanity-check the label against the prompt before assuming
  the model is wrong.
- **Train/holdout discipline:** only look at holdout's aggregate score,
  never individual case wording, when deciding on a prompt edit - the
  moment a specific holdout case's content drives a change, it's
  effectively become a train case.
- **Progress-log.md is the authoritative history, live on the user's
  machine.** When it needs a new entry, give Claude Code the exact text to
  append - never ship a full-file zip of it, which risks overwriting
  entries added directly on the real machine with a stale copy.
- **Sonnet vs. Opus:** deliberately staying on Sonnet 5. The kinds of
  mistakes found so far (urgency bleeding from adjacent instructions,
  answer-key errors) are prompt-clarity problems, not reasoning-depth
  problems - a more expensive model reading the same ambiguous wording is
  just as likely to inherit the same issue.

---

## Note for New Thread Sessions

Say "read PROJECT.md" - it has full context on the product, stack, and
current state. For the specific reasoning behind any past decision (why a
prompt version changed, why a case got relabeled, exact historical
accuracy numbers), see `progress-log.md`.
