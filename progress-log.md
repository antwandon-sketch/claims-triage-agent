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

## 2026-07-31 - Prompt v2: fixed real answer-key mistakes, action accuracy 75% -> 90%

- Added policy_change escalation rule to SYSTEM_PROMPT: anything affecting
  underwriting risk or premium (adding/removing a driver, cancellations,
  newly insured property) escalates to a human; routine administrative
  changes can auto_reply
- Fixed 3 golden-dataset mistakes found by the v1 run: case_07's expected
  urgency was 'high' but conflicted with the system prompt's own
  definition of high urgency (safety/property risk) - changed to 'medium';
  case_08 and case_09 were missing policy numbers, likely why the model
  asked for more info instead of answering directly
- Result: category 100% (unchanged), urgency 90% (unchanged, different
  case), action 75% -> 90%
- Known accepted edge cases, not chased further: case_03 and case_09 still
  prefer request_more_info over escalate_human even with a policy number
  present - defensible model behavior, not a data problem
- Side effect worth remembering: the same prompt edit that fixed case_12's
  action introduced a new urgency miss on the same case (low -> medium) -
  a reminder that prompt changes can shift outputs you weren't targeting,
  which is exactly why the eval always re-runs the whole set, not just the
  case you were fixing

## 2026-07-31 - Grew golden dataset to 45 cases, added train/holdout split

- Added 25 new hand-labeled cases (case_21 through case_45), 5 per
  category, covering angles not in the original 20: injury claims, claims
  with no active leak, claim reopens, liability questions, home-business
  coverage, removing (not just adding) a driver, adding a non-auto asset
  (boat), billing errors, and more
- Reason: the original 20 have now been looked at and tuned against twice
  (v1 and v2) - continuing to measure "accuracy" against the same cases
  the prompt was tuned on risks overfitting (the score goes up because the
  prompt is increasingly tailored to those specific emails, not because it
  actually generalizes better)
- Tagged every case with `split: train` (the original 20) or
  `split: holdout` (the new 25). Rule going forward: only ever look at the
  holdout set's aggregate score, never its individual misses, when
  deciding how to edit the prompt - the moment a holdout case's specific
  wording drives a prompt change, it has effectively become a train case
- `eval/run_eval.py` now takes `--split {all,train,holdout}` and, when run
  with `all` (the default), prints three reports: TRAIN, HOLDOUT, and ALL
- Added `filter_by_split()` as a pure, unit-tested function (3 new tests)
- Dry-run tested the full split-aware report with fake responses,
  including a deliberately-injected holdout-only miss, to confirm the
  three-way breakdown actually reports correctly before spending a real
  API call
- 18 tests passing total

**Next session:** run `python -m eval.run_eval` for real against all 45
cases. Expect train accuracy to still look strong (already tuned for);
the holdout numbers are the first genuinely unseen read on how well this
generalizes, and are the ones worth taking seriously if pitching this to a
real agency.

## 2026-07-31 - Prompt v3: expanded category schema, 45 -> 57 cases

The first real all-45 run surfaced a train/holdout gap (category 100% ->
76%) driven almost entirely by the catch-all `other` bucket - `other` was
absorbing genuinely different kinds of requests (complaints, sales leads,
document requests, billing issues) that a real agency would want routed to
different people, not lumped into one bucket a human has to manually sort.

- Split `other` into 4 new top-level categories: `billing_issue`,
  `sales_lead`, `complaint`, `document_request`. Kept a slimmed-down
  `other` for genuine leftovers (job applications, general non-policy
  questions, unsubscribes).
- Boundary decided on principle, not by reverse-engineering the specific
  holdout cases that were confused: policy_change = changes what's
  actually written on the policy (including name/address/phone
  corrections, matching existing precedent); document_request = produces
  a document FROM the policy without changing anything; billing_issue =
  payment/premium problems; complaint = dissatisfaction with service
  (distinct from disputing a claim's outcome, which stays claim_status);
  sales_lead = prospective customer, always escalate_human since only a
  licensed producer can quote.
- Recategorized the 5 existing cases that had been sitting in `other`
  (case_15 -> complaint, case_18 -> sales_lead, case_41 -> policy_change,
  case_42 -> document_request, case_45 -> billing_issue) rather than
  inventing new ones for them, since real examples already existed
- Added 12 new cases (3 each for the 4 new categories) so every category
  now has real coverage in both train and holdout, not just 1 example
  sitting in a single split
- Dataset grew from 45 to 57 cases: 26 train / 31 holdout across all 9
  categories
- `new_claim`, `claim_status`, `coverage_question` were untouched -
  they weren't part of the confusion, no reason to rework them
- Dry-run tested the new 9-category schema with fake responses, including
  a deliberately-injected billing_issue/policy_change mix-up, to confirm
  the confusion matrix correctly reports pairings involving the new
  categories before spending a real API call
- 18 tests still passing (schema/category names aren't hardcoded into the
  scoring logic, so no test changes were needed)

**Next session:** run `python -m eval.run_eval` for real against all 57
cases under prompt v3. This is the first true test of the new category
boundaries - expect some rough edges in the new categories on first run,
same as v1 did for the original 5.

## 2026-07-31 - First real eval run on all 57 cases (prompt v3)

- Ran `python -m eval.run_eval` for real against the live Neon DB and
  Claude API, no flags, all 57 cases (26 train, 31 holdout)
- TRAIN (26 cases): category 96.2%, urgency 84.6%, action 96.2%
- HOLDOUT (31 cases): category 96.8%, urgency 80.7%, action 93.5%
- ALL (57 cases combined): category 96.5%, urgency 82.5%, action 94.7%
- The v2 train/holdout category gap (100% -> 76%) is gone: train and
  holdout category accuracy are now within 0.6 points of each other
  (96.2% vs 96.8%), which is the result the 9-category split was meant to
  produce - the old `other` catch-all was the thing that wasn't
  generalizing, not the original 5 categories
- Urgency is now the weakest metric on both splits (84.6% train, 80.7%
  holdout) and wasn't touched by the v3 category work - still the same
  low/medium/high edge cases from v1/v2 (case_10, case_12, case_27,
  case_30, case_34, case_36, case_37), plus one new one (case_32)
- Only one category miss anywhere in this run: case_53 [train] -
  `document_request` predicted as `policy_change`. This is a real
  boundary case for the new schema (the case likely involves a document
  tied to a policy change) rather than a train/holdout generalization
  problem, since it's a train case
- Two action misses: case_06 [train] (auto_reply expected, got
  request_more_info) and case_44 [holdout] (auto_reply expected, got
  escalate_human) - both isolated, no pattern across categories
- Per the standing rule: not editing the prompt off the back of holdout
  misses (case_27/28/30/32/34/36/37/44) - case_53's document_request
  miss is a train case and fair game if a future session wants to
  tighten that boundary
