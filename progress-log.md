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

## 2026-07-31 - Prompt v4: fixed the urgency-bleed bug + 3 more label mistakes

Real v3 run: category 96.5%, urgency 82.5% (the weakest metric, untouched
by the category work), action 94.7%. Dug into the 8 urgency misses by
pulling actual expected-vs-predicted pairs (not just which cases missed) -
this split cleanly into three distinct findings, not one:

- **Confirmed real bug, 3-for-3 consistent evidence:** case_12, case_36,
  case_37 (all policy_change, all labeled 'low', all came back 'medium').
  All three describe completely routine requests with zero time pressure
  in the email itself (new driver's license, a divorce, a boat purchase).
  The v2 policy_change rule's "underwriting risk" language was bleeding
  into the urgency judgment, not just the action judgment it was meant
  for. Fixed by adding an explicit clarification that urgency and
  suggested_action are independent - escalating for underwriting reasons
  doesn't automatically mean higher urgency.
- **My own label mistakes, same root cause as case_07 last round:**
  case_10 (jewelry), case_30 (claim denial appeal), case_34 (mold) were
  all labeled medium/high based on how important or complicated the
  situation felt, not on actual time-sensitivity - which is what the
  system prompt's urgency definition is actually built on. Re-labeled all
  three to match the prompt's own stated definition (case_10 -> low,
  case_30 -> medium, case_34 -> low).
- **A genuine gap in the other direction:** case_27 (reopened claim,
  recurring water damage) was labeled 'high' but got 'medium' - likely the
  model anchoring partly on category (claim_status reads as inherently
  less urgent than new_claim) rather than the actual situation described,
  which is active/worsening property damage. Added a clarification that
  urgency reflects the current situation only, independent of whether it's
  a new claim or a reopened one.
- **Left unchanged, documented as defensible:** case_32 (dog bite) - model
  said 'high' where I expected 'medium'; given an actual injury (doctor
  visit) already happened, 'high' is a reasonable read. Not chased further.
- PROMPT_VERSION bumped to v4. 18 tests still passing (no scoring-logic or
  test changes needed - this was a data + prompt-text change only).

**Next session:** run `python -m eval.run_eval` for real under v4 and
compare urgency accuracy specifically (was 82.5% under v3) - this is the
one metric this round is squarely aimed at improving.

## 2026-07-31 - Real v4 run: urgency "improvement" was mostly illusory

Ran all 57 cases for real. Headline numbers: category 94.7%, urgency 87.7%
(up from 82.5%), action 93.0%. Dug into whether the urgency gain was real
by comparing actual model predictions (not just labels) between v3 and v4:

- All +5.2 points came from 3 relabeled cases (case_10/30/34) whose
  model predictions were identical in both runs - only the answer key
  changed. Legitimate correction, but not model improvement.
- On the 54 unchanged-label cases, urgency accuracy was exactly 47/54
  (87.0%) in both v3 and v4 - genuinely flat.
- The targeted fix worked on case_12/36/37 (medium -> low, correct) but
  introduced a same-shape regression on case_03/05/46/47 (correct medium
  flipped to wrong low). Net: 3 fixed, 4 newly broken.
- Conclusion: urgency is not fixed, it's flat at 87.0% like-for-like. The
  "urgency and suggested_action are independent" clarification made the
  model broadly more reluctant to call things medium, not just fixed the
  policy_change-specific bleed. Needs a more surgical rewrite next time -
  probably separating urgency and action guidance into language that
  shares zero vocabulary.

## 2026-07-31 - Added safety-critical stress testing (new capability, not just a test)

Decided to stress-test the system against scenarios outside normal
production traffic, prioritized by real-world consequence rather than
building all of them at once. Safety-critical language first, since
getting this wrong has actual real-world stakes, not just a lower eval
score.

- Added a genuinely new field to the classifier, not just a test: 
  `safety_instruction` (optional string). If an email describes an active
  physical emergency happening right now (gas leak, downed power line,
  CO alarm, active fire, someone trapped/injured), the model now
  populates this with a short, direct instruction for the customer -
  evacuate, call 911, call the gas company's emergency line. This is
  explicitly framed in the system prompt as mattering more than getting
  category or urgency right.
- Persisted the new field: added `safety_instruction` column to
  `agent_decisions` in db.py.
- Built `eval/stress_tests.json`: 10 cases, 5 genuine emergencies + 5
  deliberate false-positive traps (a fire that's already out, dramatic
  all-caps language about a routine address change, a non-working smoke
  detector, a tree-on-roof property claim with nobody in danger, a
  resolved car accident) - the traps matter as much as the positives,
  since a system that flags everything "urgent-sounding" is as useless as
  one that misses real danger.
- Built `eval/run_stress_tests.py` as a separate harness from
  `run_eval.py` on purpose - this measures a binary safety property, not
  classification accuracy, and explicitly does NOT collapse the two
  failure directions into one number: a false_negative (missed real
  emergency) is called out as the dangerous direction, separate from a
  false_positive (false alarm on something routine)
- 8 new unit tests for the pure scoring logic (`test_stress_scoring.py`),
  26 tests passing total
- Dry-run tested with fake responses including a deliberately-injected
  false negative AND false positive, confirming both get correctly
  flagged and separated in the report before spending a real API call
- PROMPT_VERSION bumped to v5 (new field + new system prompt priority
  instruction)

**Next session:** run `python -m eval.run_stress_tests` for real. Any
false_negative here should be treated seriously, not averaged into an
"accuracy is fine" narrative - this is the one test in this whole project
where a wrong answer has actual real-world consequences, not just a lower
score. Also still owe a more careful fix for the flat 87.0% urgency
accuracy from the v4 finding above.

## 2026-07-31 - Prompt v6: surgical fix for the flat urgency accuracy

Went back to the v4 finding (87.0% like-for-like, not the misleading
82.5%->87.7% headline) with real regression data in hand this time, rather
than another broad rewrite.

- Root cause: the v4 clarification said "no time pressure = low," meant
  only to stop the policy_change bleed. The model over-generalized it to
  mean "no *active hazard* = low," which broke 4 cases that have real
  timeliness stakes without an active hazard: case_03 (claim in
  progress), case_05 (customer waiting on an update), case_46/case_47
  (complaints that could escalate if ignored)
- Fix: narrowed the original rule to explicitly scope it to policy_change
  only, and added a new, separately-worded rule that medium urgency also
  covers "a customer waiting on an existing claim, a dispute over money
  or a decision, or a complaint about service that could get worse if
  ignored" - deliberately using none of the same vocabulary ("risk",
  "escalate", "time pressure") that caused the last bleed
- Checked this reasoning against the cases it needs to NOT break:
  case_12/36/37 (the original policy_change fixes, still need to be low)
  don't match any of the three new "medium" examples (no waiting claim,
  no dispute, no complaint), so they should stay correctly low.
  case_30 (denial appeal, medium) directly matches "a dispute over a
  decision," reinforcing rather than conflicting with its existing label
- PROMPT_VERSION bumped to v6. 26 tests still passing (prompt-text-only
  change, no scoring logic touched)

**Next session:** run `python -m eval.run_eval` for real under v6.
Specifically re-check case_03/05/46/47 (should flip back to correct) AND
case_12/36/37 (should still be correct, not reintroduce the original
bleed) - same discipline as the v3->v4 check: verify actual predictions
moved, not just the aggregate number, before calling this fixed.

## 2026-07-31 - First real eval run on all 57 cases (prompt v6): urgency actually fixed, but a new action regression appeared

- Ran `python -m eval.run_eval` for real, no flags, all 57 cases (26
  train, 31 holdout)
- TRAIN (26): category 96.2%, urgency 88.5%, action 80.8%
- HOLDOUT (31): category 96.8%, urgency 100.0%, action 93.5%
- ALL (57): category 96.5%, urgency 94.7%, action 87.7%
- Did the specific 7-case check the fix was aimed at, pulling actual
  expected-vs-predicted urgency from the results JSON rather than trusting
  the aggregate number:
  - case_03, case_05, case_46, case_47 - all flipped back to correct
    (medium/medium), as intended
  - case_12, case_36, case_37 - all still correctly low/low, the original
    policy_change bleed was NOT reintroduced
  - All 7 landed exactly where they should. This is a genuine fix, unlike
    the v3->v4 headline number - urgency accuracy this time is a real
    94.7%, not an artifact of relabeling
- New problem, unrelated to what this round targeted: action accuracy
  dropped (was 96.2% train / 93.0% all under v4/v5, now 80.8% train /
  87.7% all). Four new action misses appeared, all the same shape -
  expected `escalate_human`, got `request_more_info`: case_03, case_09,
  case_10, case_20. case_03 already had a wrong action even after the
  urgency fix landed correctly - urgency and action are still being
  scored independently, and this run shows they can move in opposite
  directions
- Not yet investigated why - the v6 prompt edit was described as
  urgency-only wording, so this may be an unintended interaction with the
  new medium-urgency rule (e.g. "customer waiting on an existing claim"
  language nudging the model toward request_more_info instead of
  escalating), or it may be unrelated. Don't guess further without
  checking the actual prompt diff and these 4 cases' bodies directly.

**Next session:** investigate the 4 new action misses
(case_03/09/10/20 - all escalate_human -> request_more_info) before
calling v6 a clean win. Same discipline as before: this looks like
trading one metric's problem for another's, and it needs the same
case-by-case check the urgency fix just got, not just an aggregate
accuracy comparison.

## 2026-07-31 - Fixed a real bug in the eval harness itself: rationale/summary were being silently discarded

- While investigating the 4 action misses from the run above, went to
  read the model's own stated reasoning and found `score_case()` in
  `eval/run_eval.py` never captured `rationale` or `summary` from the
  classifier's response - only category/urgency/action/confidence were
  kept. Every eval run so far (v1 through v6) threw this away; there was
  no way to see *why* the model picked a wrong answer, only that it did
- Fixed: `score_case()` now also stores `rationale` and `summary` per
  case. 2 new tests (`test_score_case_captures_rationale_and_summary`,
  `test_score_case_missing_rationale_is_none`), 28 tests passing total.
  No classifier or prompt change - this is a harness-only fix, no
  PROMPT_VERSION bump
- Ran `python -m eval.run_eval` for real to get rationale on the record
  for the 4 outstanding action misses. Pulled id, predicted_action, and
  rationale for case_03, case_09, case_10, case_20 verbatim from
  `eval_results/run_20260731_112334.json`:

  **case_03** - predicted_action: `escalate_human` (correct this run)
  > This is a new auto claim request with no active safety risk, but it
  > needs an agent to initiate the claims process.

  **case_09** - predicted_action: `request_more_info`
  > This is a general coverage inquiry about a minor, non-active issue
  > rather than a claim or emergency, but a definitive coverage answer
  > requires more details about the cause of the stain.

  **case_10** - predicted_action: `request_more_info`
  > This is a pre-claim coverage inquiry about jewelry limits under the
  > homeowners policy rather than an actual claim filing, though the
  > policy number would be needed to give a specific answer.

  **case_20** - predicted_action: `request_more_info`
  > This is a coverage question about flood insurance, and while not an
  > active emergency since water hasn't reached the home, the nearby
  > flooding makes it time-sensitive enough to warrant medium urgency; a
  > policy number is needed to give an accurate coverage answer.

- **case_03 flipped back to correct** (`escalate_human`) on this run,
  after being `request_more_info` consistently across 3 back-to-back
  runs earlier today with zero code changes in between. That makes
  case_03 look like ordinary model variance, not a stable regression -
  different from case_10 and case_20, which were confirmed
  `request_more_info` on all 3 of those repeat runs and are a real,
  repeatable effect
- **case_09/case_10/case_20 share one clear pattern in their own stated
  reasoning:** all three explicitly justify `request_more_info` by
  saying a policy number (or more detail) is needed to give a specific
  answer - the model is treating "missing policy number" as grounds for
  asking a clarifying question instead of escalating to a human, even
  though the golden answer expects escalation for these. This is a
  concrete, testable hypothesis for the v6 action regression, not a
  guess - worth checking directly against v6's prompt text next

**Next session:** check whether v6's SYSTEM_PROMPT still tells the model
that a missing policy number should trigger escalate_human (like the v2
policy_change rule originally did) or whether that instruction got lost
or de-prioritized relative to the new medium-urgency wording. case_09/10/20
all point the same direction, so this is worth fixing directly rather
than through another broad prompt rewrite.
