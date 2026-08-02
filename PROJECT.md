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
| Classifier | Claude Sonnet 5, forced structured output via tool use, **PROMPT_VERSION v7 still the confirmed-shipped version; v11 built, fully validated, and staged for review as of 2026-08-01 - NOT committed yet, uncommitted in the working tree pending explicit go-ahead** (v8/v9 built and reverted 2026-07-31; v10's extract-then-decide architecture solved coverage_question but introduced a root-caused billing_issue regression, not shipped; v11 = v10 unchanged except the coverage_question bullet's self-referential narrative text removed, which fixed the regression - see progress-log.md's v10 and v11 entries) |
| Categories | 9: new_claim, claim_status, coverage_question, policy_change, billing_issue, sales_lead, complaint, document_request, other (expanded from an original 5 after v3 - see progress-log for why) |
| Golden dataset | 57 hand-labeled cases (`eval/golden_dataset.json`), split 26 train / 31 holdout |
| Latest full eval (v11, staged) | Category 96.5-98.2%, urgency 89.5-91.2%, action 96.5-98.2% across 3 runs - matches or exceeds v7's 96.5/93.0/96.5 baseline on category and action; urgency within already-established normal variance. See progress-log.md's v11 entry for per-run detail and the one new residual finding (case_54, urgency-only, no action/routing impact). |
| Stress test suite | `eval/run_stress_tests.py`, 28 cases across 4 categories (10 safety-critical + 6 prompt-injection + 6 urgency-manipulation + 6 multi-issue, the last added 2026-08-01). Safety-critical: 10/10 clean under v7/v10/v11, zero false negatives. Prompt-injection: 2/6 clean under v7 and v10 (confirmed identical via stash A/B, pre-existing), 3/6 clean under v11. Urgency-manipulation: 4/6 clean - a stated deadline, real or invented, pulls urgency up past what the content warrants in 2 of 6 cases; category/action stay correct. Multi-issue (v11, first real run): 5/6 clean on the primary-issue read - the one miss (mi_01) turned out to be an urgency judgment call unrelated to the trap it was designed to test, not evidence the fake second ask caused confusion. More importantly: **3 of 6 cases (mi_04, mi_05, mi_06) surfaced a real architectural gap, not a scoring miss** - each bundles a second, genuinely separate issue (a coverage question, a document need, a status check) into one flowing paragraph, and even though the primary-issue classification was correct in all 3, `classify_email`'s schema has exactly one category/urgency/action per email, so the second issue is silently dropped every time regardless of what the model does right. See the Open Threads section below. Full case-by-case detail in `eval/stress_tests.json` and the timestamped run in `eval_results/`. |
| `safety_instruction` field | New classifier output field - populated only for active physical danger (gas leak, downed power line, CO alarm, active fire, someone trapped/injured), persisted to `agent_decisions.safety_instruction` |
| `eval_runs` table | Tracks accuracy history across prompt versions in Postgres |
| Database | Neon Postgres - separate database from ai-consulting-lab |
| Tests | 33 passing (`pytest -v`) |

**What's not built yet:** the system decides and logs, it doesn't act.
No reply is actually sent for any action (`auto_reply`, `escalate_human`,
`request_more_info`) - there's no outbound send capability yet, and no way
to thread a customer's follow-up reply back to the original case. This is
deliberate, sequenced work for a later phase, the same shape as the HVAC
project's SMS-confirmation gap - get the classification core solid and
measured first.

**Stress-test categories not yet built:** garbled/low-signal input only.
Safety-critical, prompt injection, exaggerated/manipulative urgency
language, and (as of 2026-08-01) multi-issue emails are all built now -
see the Current State table above for real results on each.

**Resolved this session:** v10's case_56 (billing_issue) regression was
root-caused across five diagnostic rounds - schema-size isolation,
prompt-bullet isolation, a full 4x2x10 factorial, a time-drift-controlled
interleaved test, and finally a targeted narrative-text-only isolation -
to the coverage_question bullet's self-referential "three prior
attempts... each fixed one case while breaking another" narrative text,
not the schema growth and not the operational extract-then-decide
instructions themselves. Removing only that narrative (v11) restored
case_56 to 0 misses across 3 full-suite runs, matching v7's clean
behavior, while coverage_question's own fix (0 action misses,
consistent across v10 and v11) was fully preserved. Full history in
progress-log.md's five case_56 diagnostic entries plus the v11
implementation entry, all dated 2026-08-01.

**New, low-severity open item found during v11's validation:** case_54
(document_request) misses urgency (expected low, got medium) in all 3
v11 full-suite runs and a majority of isolated re-checks - confirmed
via stash A/B that this case is clean under both true v7 and v10 (never
a regression before v11). Category and suggested_action (escalate_human)
are correct every time, so the case still reaches a human either way -
this changes queue priority, not the outcome. Not root-caused this
round (discovered only in v11's full-suite re-run, outside the
targeted case_55/case_56 diagnostic scope); worth its own investigation
in a future prompt version, not currently judged a blocker given the
operational impact.

**Still open, unrelated to any of this session's changes:** the
prompt-injection stress suite (`eval/run_stress_tests.py`) has never
passed cleanly - 2/6 under v7 and v10 (confirmed identical via
stash A/B), 3/6 under v11 (a mild improvement, likely ordinary
variance on one borderline case rather than anything v11-caused, since
that case doesn't touch coverage_question at all). Needs its own
investigation whenever it's prioritized; out of scope for all of this
session's rounds.

---

## Open Threads

- **v11 is committed and pushed - confirmed shipped.** (This line was
  stale as of an earlier draft of this doc, which still described it as
  staged/awaiting go-ahead; corrected 2026-08-01.)
- Root-cause case_54's urgency miss as a follow-up - low priority given
  the action/category are unaffected, but worth understanding given
  this project's history of coverage_question-adjacent edits leaking
  into unrelated categories (case_25/v8, case_04+case_05/v9, case_56/v10,
  possibly case_54/v11 - pattern not yet confirmed for this one).
- Separately, investigate the prompt-injection stress-test gap (2-3/6
  clean across v7/v10/v11) - not caused by any of this session's work,
  but a real, pre-existing weakness worth its own pass.
- **New: multi-issue emails expose a real architectural gap, not a
  prompt-tunable miss.** `classify_email`'s schema outputs exactly one
  category/urgency/action per email. 3 of the 6 multi_issue stress cases
  (mi_04, mi_05, mi_06) bundle two genuinely separate, substantive asks
  into a single paragraph with no "also"/list marker - a billing
  question folded into a coverage question, a policy_change folded into
  a document need, a service complaint folded into a claim_status check.
  In all 3, the model correctly classified the primary issue - but the
  secondary issue has nowhere to go in the current output schema and is
  silently dropped every time, independent of whether the primary read
  is right. This needs a design decision (e.g. an `additional_issues`
  list in the schema, or a boolean flag plus a follow-up pass) before
  the agent could be trusted with genuinely multi-part customer email in
  production - not something a prompt edit alone can fix. Not addressed
  this round (out of scope - this task was stress-test coverage only).
- Once the agent build is complete, create a portfolio-style PDF
  summarizing the build process (evals, debugging, and observability
  narrative) for job-search/interview use.

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
- **Never commit or push without an explicit go-ahead in the same turn,
  even after a long back-and-forth resolving a data question** - resolving
  the analysis is not the same as approval to ship it. This was violated
  once on 2026-07-31 (commit ed91197).
- **A coverage_question prompt fix that traces cleanly by hand and passes
  on its targeted cases can still fail under full regression** - confirmed
  twice (v8, v9). Never trust a fix until it's cleared a full 3x
  regression run against cases outside the ones it was designed for.
- **When a classification boundary keeps reappearing after multiple
  independent wording rewrites** (v7's reword, v8's revert, v9's rewrite -
  three different texts, same failure shape: fix the targeted case,
  destabilize others nearby), the fix needs to be architectural - separate
  the LLM's fact-extraction (a narrow, well-scoped judgment) from the
  final decision logic (deterministic code), rather than another
  prompt-text iteration. Research established prompt-engineering/LLM-
  reliability patterns for this class of problem before proposing another
  manual wording edit.

---

## Note for New Thread Sessions

Say "read PROJECT.md" - it has full context on the product, stack, and
current state. For the specific reasoning behind any past decision (why a
prompt version changed, why a case got relabeled, exact historical
accuracy numbers), see `progress-log.md`.
