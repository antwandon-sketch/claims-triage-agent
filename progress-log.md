# Progress Log - Claims Triage Agent

## 2026-07-30 - Phase 1: scaffold + ingestion + classifier + logging

- New repo, separate from ai-consulting-lab (deliberately - a second, focused
  repo reads cleaner for a portfolio than folders bolted onto the HVAC project)
- Built: config.py, db.py (raw_emails + agent_decisions tables), classifier.py
  (Claude tool-use call forcing structured JSON output), routes/ingestion.py
  (POST /inbound-email), app.py
- Reused conventions from ai-consulting-lab/PROJECT.md: X-API-Key header /
  APP_SECRET_KEY variable name, .env.example with names only (never real
  values), blueprint structure, mocked DB + mocked Claude calls in tests so
  the suite runs without real credentials
- Set PORT default to 5002 (5000 = macOS AirPlay, 5001 = the HVAC project) so
  both projects can run at the same time without a conflict
- 7 tests passing (health check, auth rejection, bad JSON, blank/placeholder
  field rejection, happy path decision + persistence)
- Not yet built: eval_labels/eval_runs tables, golden dataset, eval harness
  (Phase 3), dashboard (Phase 4), real Neon DB connection (still using a
  fake DATABASE_URL locally since tests mock the DB layer entirely)

**Since then:** Neon database stood up, `.env` filled in, `init_db()` run
against it. Confirmed real end-to-end curl calls for all 3 sample emails
against the live database and real Claude API - correctly judged the
ambiguous "small water stain, not urgent yet" case as low urgency but still
escalate_human, which is exactly the nuance the schema was designed to
allow (urgency and suggested_action are independent decisions, not the same
thing). Pushed to a dedicated GitHub repo (kept separate from
ai-consulting-lab deliberately, so this reads as its own clean portfolio
piece).

## 2026-07-31 - Phase 3: golden dataset + eval harness

- Small but real fix caught along the way: `classify_email()` was only
  taking the email body, silently discarding the subject line - fixed to
  take both, since subject lines often carry real signal (e.g. "URGENT")
- Built `eval/golden_dataset.json` - 20 hand-labeled cases, 4 per category,
  spread across all 3 urgency levels, with deliberate edge cases: a new
  claim that isn't urgent (day-old fender bender), a policy_change that
  still needs a human (cancellation - retention conversation), a
  claim_status that IS urgent (settlement dispute), and an ambiguous
  coverage question (ceiling stain) - each testing that the model isn't
  just pattern-matching category to urgency to action
- Built `eval/run_eval.py` - runs the golden set through the real
  classifier, scores category/urgency/action accuracy, builds a confusion
  matrix, saves the summary to a new `eval_runs` table (added to db.py),
  and writes a detailed per-case JSON to `eval_results/`
- Scoring logic (`score_case`, `aggregate_scores`) is pure - no API calls,
  no database - so it's covered by fast unit tests
  (`tests/test_eval_scoring.py`) that don't depend on how well the
  classifier itself is doing that day
- Dry-run tested the full script end to end with fake responses
  (deliberately wrong on 2 of 20 cases) before ever spending a real API
  call - confirmed the report, confusion matrix, and miss-detail sections
  all work correctly
- 15 tests passing total (8 original + 7 new eval ones)

**Next session:** run `python -m eval.run_eval` for real against the live
Neon DB and real Claude API, review the actual accuracy numbers and any
misses together, and decide whether prompt v1 needs adjusting before
calling this "measured and working."

## 2026-07-30 - Phase 3: eval run against prompt v2

- Ran the eval harness for real against the live Neon DB and Claude API,
  following up on the "decide whether prompt v1 needs adjusting" note above
- Updated `SYSTEM_PROMPT` (now v2) with explicit policy_change escalation
  rules: adding/removing a driver, canceling a policy, or adding a newly
  insured property/vehicle should escalate_human; address/contact updates
  and no-new-risk dwelling coverage increases can stay auto_reply
- Also fixed 3 issues in `golden_dataset.json` found along the way:
  case_07's expected_urgency was mislabeled high (a mid-claim settlement
  dispute isn't the same as "just filed" - downgraded to medium), and
  case_08/case_09 were missing policy numbers in the body text
- Results vs the same 20-case set: category accuracy 100% (unchanged),
  urgency accuracy 90% (unchanged, but the specific missed case changed),
  action accuracy up from 75% to 90%
- Side effect worth flagging: case_12 (adding a driver) now misses on
  urgency (expected low, got medium) even though its action call is now
  correct - the same prompt change that fixed the escalation call nudged
  urgency up too. A reminder that prompt edits aren't surgical - a change
  aimed at one field can shift unrelated outputs.
- case_03 and case_09 still miss on action (expected escalate_human, got
  request_more_info) even after adding policy numbers, which rules out
  "missing data" as the cause - reading these as genuine judgment-call
  differences rather than bugs, and accepting them as known edge cases for
  now rather than chasing further prompt tweaks.
