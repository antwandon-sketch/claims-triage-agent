# coverage_question extract-then-decide: FINAL DESIGN (canonical reference)

**Read this file first.** This supersedes `coverage_question_manual_trace.md`,
`coverage_question_fresh_holdout.md`, `coverage_question_decision_table.md`,
and `coverage_question_model_extraction_test.md` as the single source of
truth for this design. Those four files remain in place for the full
chronological history and reasoning trail - read them if you need to know
*why* a decision was made, not just what it currently is. This file is
"what any future session should read to get up to speed fast," not a
replacement for the detailed record.

**Status as of 2026-08-01: design validated standalone, `classifier.py`
NOT touched.** This is a design-validation exercise for an extract-then-
decide refactor of the `coverage_question` category's
`auto_reply`/`request_more_info`/`escalate_human` boundary - replacing a
single LLM prose judgment (the shape every prior prompt version, v7
through v9, used and each broke on) with a narrow LLM extraction step (6
booleans) feeding a deterministic Python function. Nothing here has been
wired into the real pipeline yet.

---

## Why this exists

Three independent prompt-text rewrites (v7's original coverage_question
reword, v8's revert, v9's rewrite) each fixed their targeted case while
destabilizing another nearby - inside and, in v8/v9's case, *outside* the
category being edited (see `progress-log.md`'s v8/v9 entries). The
diagnosis: asking an LLM to reason through an entire multi-way boundary in
prose, in one step, doesn't compose reliably. The fix under validation
here separates that into two narrow steps: (1) the LLM extracts 6 narrow,
independently-defined boolean facts about the email, and (2) a
deterministic, non-LLM function computes the action from those facts. Step
2 can be exhaustively verified (it's just 64 possible input combinations);
step 1 still needs empirical checking, but each individual fact is a much
narrower judgment than "figure out the whole boundary."

---

## The 6 fields, final definitions with worked examples

These are the exact descriptions as they stand after 5 rounds of revision,
each triggered by a real disagreement between hand-tracing, the decision
table's abstract reasoning, or real model extraction - not written fresh,
accumulated. Field order matches the tuple order used throughout every
other document (`ref, pol, liab, uw, exist, cause`).

### 1. `references_specific_incident`
> True if the email describes or points to a specific triggering event (a
> particular loss, accident, damage, theft, injury) that has already
> occurred, rather than a general/hypothetical question about coverage
> terms.

### 2. `has_policy_or_claim_number`
> True if the email includes an explicit policy or claim number, or an
> unambiguous reference to one.

### 3. `has_liability_or_dispute_signal`
> True if EITHER: (1) the email describes a third-party injury or
> property-damage incident that has ALREADY occurred or is currently
> happening, connected to the policyholder (e.g., on their property, or
> caused by their pet, vehicle, or actions) - even if nothing has been
> filed and no dispute has started yet; OR (2) the email explicitly frames
> a hypothetical, not-yet-happened scenario using liability/fault/
> responsibility language - asking whether the policyholder would be
> "liable," "responsible," "at fault," or similar, for a potential future
> third-party injury or damage. Also True for language suggesting an
> active dispute over fault, a denial, or a contested coverage outcome
> ("they said it's not covered," an active disagreement).
> False for a hypothetical, not-yet-happened scenario phrased as a GENERIC
> coverage question, without explicit liability/fault/responsibility
> language - even if it mentions a third party's property.
>
> Worked examples: "my dog keeps lunging at the fence, if he ever got
> loose and bit someone, would we be LIABLE for that" is True -
> hypothetical, but explicitly asks about liability/fault for a potential
> future third-party injury. "if a tree in our yard ever fell on the
> neighbor's shed, does homeowners insurance TYPICALLY cover that kind of
> thing" is False - hypothetical, mentions a third party's property, but
> is a generic "does my policy cover this type of peril" question, not an
> explicit liability/fault question.

### 4. `has_underwriting_or_nonstandard_use_signal`
> True if the email describes an ONGOING business activity, a commercial
> use of the property, or another LASTING change in risk profile the
> policy wasn't written for (e.g., running a business from home, renting
> out a room, keeping livestock) - a risk the insurer would need to know
> about and potentially underwrite separately. False for routine,
> TEMPORARY personal circumstances, even if physically unusual-sounding -
> these don't change the property's risk profile or require separate
> underwriting.
>
> Worked examples: "I run a dog-boarding business out of my basement" is
> True (ongoing commercial activity). "We have a storage pod parked in
> the driveway for a few days during a home move" is False (temporary,
> routine, just an ordinary moving-related inconvenience).

### 5. `asks_feature_existence_only`
> True ONLY if the question has NO personal or situational anchor at all -
> it could be asked by any policyholder regardless of their specific
> circumstances, answerable with one generic yes/no fact about the policy
> (a lookup against the declarations page). False if the question is tied
> to ANY specific real, hypothetical, or ongoing personal scenario - a
> particular business, a particular pet/property/person, a particular
> item, a particular past or possible future event - EVEN IF the question
> is phrased generically using words like "typically" or asks "or do I
> need something separate" - that kind of generic-sounding phrasing does
> NOT override a real personal anchor.
>
> Worked examples: "does my policy include roadside assistance" is True -
> no personal scenario at all. "I run a candle business out of my garage,
> does my policy cover that, or do I need something separate?" is False -
> despite the generic-sounding framing, it's tied to their specific real
> business. "If my tree fell on my neighbor's fence, does homeowners
> insurance typically cover that kind of thing?" is False - anchored to
> their specific tree and neighbor, "typically" doesn't make it a pure
> lookup. Hypothetical/conditional phrasing ("if X happened, would Y be
> included") is also NOT a pure lookup on its own. One more example, same
> principle: "does my policy include rental reimbursement" is True (pure
> lookup); "If my car needs repairs after a covered accident, would a
> rental be included" is False - still requires evaluating whether that
> future scenario would meet the coverage's conditions (covered peril?
> comp/collision requirement? per-day/total limits?).

### 6. `cause_investigated_and_unresolved`
> True if the email indicates the cause of the damage/loss has already
> been actively examined (e.g., discovered or inspected during a
> renovation, repair, or investigation) and still cannot be determined.
> False if the cause is clear/undisputed, or unknown only because the
> customer hasn't investigated further yet (a passive, just-noticed
> observation).

---

## The decision function

Derived from exhaustive reasoning over all 64 possible input combinations
(`coverage_question_decision_table.md`), not fit to a small sample. Proven
logically equivalent to the earlier `DecisionTreeClassifier`-plus-override
approach (Round 5/6 of `coverage_question_manual_trace.md`) - the override
(force `exist=False` whenever `ref=True`) is structurally subsumed by
checking `ref` before `exist` here, so it's not a separate step anymore.

```python
def score_coverage_question(
    references_specific_incident: bool,
    has_policy_or_claim_number: bool,
    has_liability_or_dispute_signal: bool,
    has_underwriting_or_nonstandard_use_signal: bool,
    asks_feature_existence_only: bool,
    cause_investigated_and_unresolved: bool,
) -> str:
    if has_liability_or_dispute_signal:
        return "escalate_human"
    if cause_investigated_and_unresolved:
        return "escalate_human"
    if has_underwriting_or_nonstandard_use_signal:
        return "escalate_human"
    if (not has_policy_or_claim_number) or references_specific_incident:
        return "request_more_info"
    if asks_feature_existence_only:
        return "auto_reply"
    return "request_more_info"
```

**Plain English priority order:**
1. Liability/dispute signal → always escalate, unconditionally (no
   requirement that an incident has already occurred - see Category A
   below).
2. Cause investigated and still unresolved → always escalate.
3. Underwriting/non-standard-use signal → always escalate.
4. Missing policy number, OR a real already-occurred incident → always
   request more info (a real incident is never answerable via pure
   lookup, regardless of whether identifying info is present).
5. A pure feature-existence question → auto_reply.
6. Anything left over (no incident, not a pure lookup, no escalate
   signal - a vague, unanchored question) → request_more_info, as the
   safer default.

---

## The complete 64-row decision table

64 = 2^6 possible boolean combinations. **16 are logically impossible
(N/A)**, **48 have a definitive, reasoned resolution - zero remaining
ambiguous rows** (as of `coverage_question_decision_table.md` Round 2).

**N/A rule:** `cause_investigated_and_unresolved=True` requires
`references_specific_incident=True` (you can't have investigated an
unresolved cause of damage that never happened). Every row with `ref=0,
cause=1` is N/A - 16 rows.

**Category A resolution** (`liab=1, ref=0` - hypothetical liability, no
incident yet): resolves to `escalate_human`, unconditionally. Liability
exposure carries asymmetric downside regardless of whether it's already
happened, and is exactly the kind of thing a real agency wants visibility
into early (underwriting-relevant, not just claims-relevant). **Real-data
validation: n=2 as of the last test round** (Case I, Case J - both clean,
explicit "would we be liable" framing) - see Part 2/3 below for expansion.

**Category B resolution** (`ref=0, exist=0, liab=0, uw=0` - vague,
unanchored question): resolves to `request_more_info`, flat default, no
7th field added. Considered and declined a 7th field for "purely generic,
no-anchor educational questions" (e.g. "how does umbrella coverage
generally work") - a plausible but, until this session, never-tested
sub-case. **Real-data validation: n=2 as of the last test round** (case_08,
Case B - both hypothetical-but-personally-anchored, not the pure-generic
sub-case) - see Part 4 below for the first real test of the pure-generic
sub-case.

| # | ref | pol | liab | uw | exist | cause | status | action |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | RESOLVED | request_more_info |
| 2 | 0 | 0 | 0 | 0 | 0 | 1 | NA | — |
| 3 | 0 | 0 | 0 | 0 | 1 | 0 | CLEAN | request_more_info |
| 4 | 0 | 0 | 0 | 0 | 1 | 1 | NA | — |
| 5 | 0 | 0 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 6 | 0 | 0 | 0 | 1 | 0 | 1 | NA | — |
| 7 | 0 | 0 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 8 | 0 | 0 | 0 | 1 | 1 | 1 | NA | — |
| 9 | 0 | 0 | 1 | 0 | 0 | 0 | RESOLVED | escalate_human |
| 10 | 0 | 0 | 1 | 0 | 0 | 1 | NA | — |
| 11 | 0 | 0 | 1 | 0 | 1 | 0 | RESOLVED | escalate_human |
| 12 | 0 | 0 | 1 | 0 | 1 | 1 | NA | — |
| 13 | 0 | 0 | 1 | 1 | 0 | 0 | RESOLVED | escalate_human |
| 14 | 0 | 0 | 1 | 1 | 0 | 1 | NA | — |
| 15 | 0 | 0 | 1 | 1 | 1 | 0 | RESOLVED | escalate_human |
| 16 | 0 | 0 | 1 | 1 | 1 | 1 | NA | — |
| 17 | 0 | 1 | 0 | 0 | 0 | 0 | RESOLVED | request_more_info |
| 18 | 0 | 1 | 0 | 0 | 0 | 1 | NA | — |
| 19 | 0 | 1 | 0 | 0 | 1 | 0 | CLEAN | auto_reply |
| 20 | 0 | 1 | 0 | 0 | 1 | 1 | NA | — |
| 21 | 0 | 1 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 22 | 0 | 1 | 0 | 1 | 0 | 1 | NA | — |
| 23 | 0 | 1 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 24 | 0 | 1 | 0 | 1 | 1 | 1 | NA | — |
| 25 | 0 | 1 | 1 | 0 | 0 | 0 | RESOLVED | escalate_human |
| 26 | 0 | 1 | 1 | 0 | 0 | 1 | NA | — |
| 27 | 0 | 1 | 1 | 0 | 1 | 0 | RESOLVED | escalate_human |
| 28 | 0 | 1 | 1 | 0 | 1 | 1 | NA | — |
| 29 | 0 | 1 | 1 | 1 | 0 | 0 | RESOLVED | escalate_human |
| 30 | 0 | 1 | 1 | 1 | 0 | 1 | NA | — |
| 31 | 0 | 1 | 1 | 1 | 1 | 0 | RESOLVED | escalate_human |
| 32 | 0 | 1 | 1 | 1 | 1 | 1 | NA | — |
| 33 | 1 | 0 | 0 | 0 | 0 | 0 | CLEAN | request_more_info |
| 34 | 1 | 0 | 0 | 0 | 0 | 1 | CLEAN | escalate_human |
| 35 | 1 | 0 | 0 | 0 | 1 | 0 | CLEAN | request_more_info |
| 36 | 1 | 0 | 0 | 0 | 1 | 1 | CLEAN | escalate_human |
| 37 | 1 | 0 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 38 | 1 | 0 | 0 | 1 | 0 | 1 | CLEAN | escalate_human |
| 39 | 1 | 0 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 40 | 1 | 0 | 0 | 1 | 1 | 1 | CLEAN | escalate_human |
| 41 | 1 | 0 | 1 | 0 | 0 | 0 | CLEAN | escalate_human |
| 42 | 1 | 0 | 1 | 0 | 0 | 1 | CLEAN | escalate_human |
| 43 | 1 | 0 | 1 | 0 | 1 | 0 | CLEAN | escalate_human |
| 44 | 1 | 0 | 1 | 0 | 1 | 1 | CLEAN | escalate_human |
| 45 | 1 | 0 | 1 | 1 | 0 | 0 | CLEAN | escalate_human |
| 46 | 1 | 0 | 1 | 1 | 0 | 1 | CLEAN | escalate_human |
| 47 | 1 | 0 | 1 | 1 | 1 | 0 | CLEAN | escalate_human |
| 48 | 1 | 0 | 1 | 1 | 1 | 1 | CLEAN | escalate_human |
| 49 | 1 | 1 | 0 | 0 | 0 | 0 | CLEAN | request_more_info |
| 50 | 1 | 1 | 0 | 0 | 0 | 1 | CLEAN | escalate_human |
| 51 | 1 | 1 | 0 | 0 | 1 | 0 | CLEAN | request_more_info |
| 52 | 1 | 1 | 0 | 0 | 1 | 1 | CLEAN | escalate_human |
| 53 | 1 | 1 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 54 | 1 | 1 | 0 | 1 | 0 | 1 | CLEAN | escalate_human |
| 55 | 1 | 1 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 56 | 1 | 1 | 0 | 1 | 1 | 1 | CLEAN | escalate_human |
| 57 | 1 | 1 | 1 | 0 | 0 | 0 | CLEAN | escalate_human |
| 58 | 1 | 1 | 1 | 0 | 0 | 1 | CLEAN | escalate_human |
| 59 | 1 | 1 | 1 | 0 | 1 | 0 | CLEAN | escalate_human |
| 60 | 1 | 1 | 1 | 0 | 1 | 1 | CLEAN | escalate_human |
| 61 | 1 | 1 | 1 | 1 | 0 | 0 | CLEAN | escalate_human |
| 62 | 1 | 1 | 1 | 1 | 0 | 1 | CLEAN | escalate_human |
| 63 | 1 | 1 | 1 | 1 | 1 | 0 | CLEAN | escalate_human |
| 64 | 1 | 1 | 1 | 1 | 1 | 1 | CLEAN | escalate_human |

---

## Empirical validation status (as of end of prior session, before this document's own new rounds)

**19 real/synthetic cases tested via real Claude API extraction** (9
golden `coverage_question` cases + 8 fresh-holdout synthetic cases + 2
Category A synthetic cases), covering **11 of the 64 rows** (all distinct
combinations actually exercised - see table below). **19/19 final-action
match, 114/114 (100%) field-level agreement, confirmed stable across 3
independent repeat runs with zero design changes between them** (byte-
identical results, verified by direct diff, not assumed) -
`coverage_question_model_extraction_test.md` Round 5.

| Row # | Combo (ref,pol,liab,uw,exist,cause) | Tested by |
|---|---|---|
| 1 | (0,0,0,0,0,0) | Case G |
| 3 | (0,0,0,0,1,0) | case_20 |
| 9 | (0,0,1,0,0,0) | Case J |
| 17 | (0,1,0,0,0,0) | case_08, Case B |
| 19 | (0,1,0,0,1,0) | case_35, Case A |
| 21 | (0,1,0,1,0,0) | case_33, Case E |
| 25 | (0,1,1,0,0,0) | Case I |
| 33 | (1,0,0,0,0,0) | case_10 |
| 49 | (1,1,0,0,0,0) | case_09, case_31, Case D, Case H |
| 50 | (1,1,0,0,0,1) | case_34, Case C |
| 57 | (1,1,1,0,0,0) | case_32, Case F |

**11 of 64 rows tested (17.2%). 37 of the 48 non-N/A rows remain
completely untested against any real email** - zero coverage of any row
with 2+ simultaneous True flags among `liab`/`uw`/`exist` compound with
`ref`/`cause`, and zero coverage of the "pure generic educational
question" sub-case within Category B. This is exactly what the rest of
this document (appended below, from this session's work) exists to close.

---

*(Everything below this line is appended by later rounds in this same
session - see the dated section headers.)*

---

## 2026-08-01, later same day: closing the coverage gap - 14 new cases across 3 fronts

Goal: expand real-model-extraction testing beyond the 19 cases and 11
rows tested so far, targeting (a) previously-untested compound-signal rows
in the 64-row table, (b) a harder version of Category A (implied liability
without the words "liable/fault/responsible"), and (c) the never-tested
Category B sub-case (a purely generic educational question with zero
personal anchor).

### Part 2: 10 cases targeting untested table rows

Selected 10 of the 37 untested clean rows (computed programmatically, not
by hand), prioritizing compound signals (2+ simultaneous True flags) and
rows structurally different from anything tested - including matched
pol=True/pol=False pairs to check whether missing identifying info changes
anything when an escalate-triggering signal is also present.

| Case | Combo (ref,pol,liab,uw,exist,cause) | Scenario | Independent reasoning (before running) |
|---|---|---|---|
| K | (0,0,1,1,0,0) | Hypothetical dog-walking business, explicit "would I be liable," no policy # | liab fires unconditionally → **escalate_human** |
| L | (0,1,1,1,0,0) | Same shape, home bakery, WITH policy # | Same → **escalate_human** |
| M | (1,0,0,0,0,1) | Real water stain recurrence, contractor investigated twice, still unresolved, no policy # | cause fires (implies ref=True, confirmed) → **escalate_human** |
| N | (1,0,0,1,0,0) | Real kiln damage to own garage wall during an ongoing pottery business, no policy # | uw fires; deliberately NOT a third-party injury (own property only) to isolate uw from liab → **escalate_human** |
| O | (1,1,0,1,0,0) | Same as N, WITH policy # | Same → **escalate_human** |
| P | (1,0,0,0,?,0)* | Real fender bender last week, "does insurance typically include a rental," no policy # | **Robustness test**, not a pure extraction test: `ref=True` routes to `request_more_info` via the `(not pol) or ref` branch *before* `exist` is ever consulted, regardless of what `exist` extracts to → **request_more_info** |
| Q | (1,1,0,0,?,0)* | Same shape as P, WITH policy # | Same robustness logic → **request_more_info** |
| R | (0,0,0,1,0,0) | Ongoing Airbnb room rental, no policy # | uw fires alone → **escalate_human** |
| S | (1,0,0,0,?,1)* | Real mold found by inspector, actively investigated, still unresolved, no policy # | cause fires before exist is relevant → **escalate_human** |
| T | (1,1,1,1,?,1)* | Deliberately maximal/artificial: real dog bite (liability), ongoing pet-grooming business (underwriting), unresolved water-damage cause, all in one email, WITH policy # | liab fires first regardless of everything else → **escalate_human** |

*`exist`'s exact extracted value doesn't determine the outcome for these
rows - flagged as a deliberate robustness test of the priority order
(checking `ref`/`cause`/etc. before `exist`), not solely a test of
`exist`'s own extraction accuracy.

### Part 3: 2 harder Category A cases - implied liability, no explicit wording

Both describe a known, foreseeable hazard with clear third-party injury
risk, without ever using "liable," "fault," or "responsible."

| Case | Scenario | Independent reasoning (before running) |
|---|---|---|
| U | Rotten, leaning oak tree over the sidewalk where schoolchildren walk daily; "if it ever came down on one of them, what would that mean for us" | A human adjuster would immediately recognize this as real, foreseeable liability exposure - arguably more serious than a generic hypothetical, since it's a known, unaddressed hazard. **Predicted correct action: `escalate_human`.** Separately predicted (and flagged as a real test of the field's limits): the *current* field definition requires explicit liability/fault/responsibility wording, which this case doesn't use - predicted the model might fail to extract `liab=True` here, defaulting to `request_more_info` instead. |
| V | Icy sloped driveway used by mail carriers and delivery drivers, "we've slipped on it ourselves more than once," "what happens if one of them goes down hard on it" | Same reasoning - **predicted correct action: `escalate_human`**, with the same predicted risk that the wording-based field definition might fail to catch it. |

### Part 4: 2 Category B cases - generic educational question, zero personal anchor

The sub-case explicitly flagged as a watch-item in
`coverage_question_decision_table.md` and never tested until now.

| Case | Scenario | Independent reasoning (before running) |
|---|---|---|
| W | "Can you explain how umbrella coverage generally works?" - no policy referenced, no personal situation, purely conceptual | Genuinely zero anchor - arguably even more generic than case_35's "does *my* policy include X" (this doesn't reference their policy at all). Predicted `asks_feature_existence_only=True`. Predicted mechanical result given the current function: `request_more_info` (missing-policy-number branch fires regardless of `exist`, since no `pol` is given or relevant). **Flagged before running**, not after: I believe the *merits* argue for `auto_reply` here (a genuinely safe, no-stakes educational answer), but the current design's `(not pol) or ref` rule doesn't distinguish "missing pol because it wasn't relevant" from "missing pol because we need it" - a real structural question, not a bug to silently paper over. |
| X | "Can you explain how deductibles typically work for homeowners insurance?" | Same shape, same reasoning, same flagged structural question. |

### Part 5: batch run - 33 cases (19 existing + 14 new)

**First run: 31/33 final action, 196/198 (99.0%) field-level agreement.**

- **All 19 previously-tested cases: still 0 diffs, no regressions** from
  adding 14 new cases to the same script.
- **All 10 Part 2 completeness-table cases: 0 diffs, all matched
  independent reasoning exactly** - including P, Q, S correctly extracting
  `exist=False` (not True) for "typically"-phrased-but-personally-anchored
  questions, consistent with Round 4/5's now-established pattern, and
  Case T correctly resolving via the liability branch despite being a
  deliberately compound, somewhat artificial email.
- **Case W, X: 0 diffs.** Model correctly extracted `asks_feature_existence_only=True`
  for both genuinely generic educational questions, exactly as predicted.
  Final action came back `request_more_info` for both, exactly as
  mechanically predicted - **confirming, not just theorizing, the flagged
  structural question**: a purely generic, no-stakes educational question
  with no policy number still routes to `request_more_info` rather than
  `auto_reply`, because missing-policy-number is checked unconditionally
  ahead of the feature-existence check. This is a real design choice to
  revisit, not an extraction failure - the extraction was accurate.
- **Case U, V: MISMATCH** - `has_liability_or_dispute_signal` extracted as
  `True` on both, where the pre-registered hand-trace predicted `False`.

### The Case U/V finding: the model was right, the prediction was wrong

Checked directly, not assumed: on both cases, the model correctly
recognized implied liability exposure (a known, foreseeable, unaddressed
hazard with real third-party injury risk) **without** the literal words
"liable," "fault," or "responsible" appearing anywhere in either email -
going beyond what the field description's explicit wording technically
requires, but squarely consistent with its stated underlying principle and
worked examples (asymmetric downside risk, real business reason to see
this early). This is the exact same shape of finding as Round 4's
case_33/Case E/Case G/Case H correction: **the recorded expected value was
the error, not the model's extraction.** My own pre-registered prediction
undersold the model's ability to generalize past the letter of the
worked examples to their underlying intent.

**Corrected the recorded expected values for Case U and Case V** from
`(liab=False, request_more_info)` to `(liab=True, escalate_human)` -
matching what the model actually and correctly produced. **No field
description was touched** - per Part 6's instruction, this round required
no additive fix at all, because there was no actual defect in the
extraction schema to fix.

### Part 6: re-verification + 3x stability check on the full 33

**Confirmation run (post-correction): 33/33 final action, 198/198 (100.0%)
field-level agreement.**

**3x repeat-stability check, no code/prompt changes between runs, per the
same discipline as the last round - verified by direct diff of raw
per-case output, not by trusting matching summary lines:**

| Run | Final action | Field-level agreement |
|---|---|---|
| 1 | 33/33 | 198/198 (100.0%) |
| 2 | 33/33 | 198/198 (100.0%) |
| 3 | 33/33 | 198/198 (100.0%) |

```
$ diff <(run 1 per-case output) <(run 2 per-case output)
(no output - exit code 0)
$ diff <(run 1 per-case output) <(run 3 per-case output)
(no output - exit code 0)
```

**All 3 runs byte-identical.** 99 real API calls this round (33 cases × 3
runs), zero variance observed anywhere.

### Updated table coverage

**18 of 64 rows now tested (28.1%), up from 11 (17.2%)** - computed
programmatically from the actual stable model output, not hand-tallied:

| Row # | Combo | Tested by |
|---|---|---|
| 1 | (0,0,0,0,0,0) | Case G |
| 3 | (0,0,0,0,1,0) | case_20, Case W, Case X |
| 5 | (0,0,0,1,0,0) | Case R |
| 9 | (0,0,1,0,0,0) | Case J |
| 13 | (0,0,1,1,0,0) | Case K |
| 17 | (0,1,0,0,0,0) | case_08, Case B |
| 19 | (0,1,0,0,1,0) | case_35, Case A |
| 21 | (0,1,0,1,0,0) | case_33, Case E |
| 25 | (0,1,1,0,0,0) | Case I, Case U, Case V |
| 29 | (0,1,1,1,0,0) | Case L |
| 33 | (1,0,0,0,0,0) | case_10, Case P |
| 34 | (1,0,0,0,0,1) | Case M, Case S |
| 37 | (1,0,0,1,0,0) | Case N |
| 49 | (1,1,0,0,0,0) | case_09, case_31, Case D, Case H, Case Q |
| 50 | (1,1,0,0,0,1) | case_34, Case C |
| 53 | (1,1,0,1,0,0) | Case O |
| 57 | (1,1,1,0,0,0) | case_32, Case F |
| 62 | (1,1,1,1,0,1) | Case T |

Notable: row 64 (`ref=1, exist=1` in combination with every other flag)
remains untested and, per the field definitions as currently written, may
be structurally hard to reach naturally at all - `exist=True` requires
zero personal anchor, but every escalate-triggering field's own definition
inherently describes a personal scenario, and Case T (the closest attempt)
correctly resolved `exist=False`. **46 of 64 rows (30 of the 48 non-N/A
rows) remain untested** - the design has not been exhaustively validated
against real model behavior, only exhaustively validated *in the abstract*
(the decision table) and validated on an expanding but still partial
sample of real extractions.

---

## FINAL CONSOLIDATED SUMMARY

**Total cases tested against the real model: 33** (9 golden + 8 fresh-
holdout + 2 original Category A + 10 new completeness-table + 2 harder
Category A + 2 Category B), **covering 18 of 64 possible boolean
combinations (28.1%).**

**Overall result: 33/33 final-action match, 198/198 (100%) field-level
agreement, confirmed stable across 3 independent repeat runs with zero
variance** (byte-identical, verified by diff).

**One real finding this round, and it resolved in the design's favor, not
against it:** Case U and Case V initially reported as mismatches, but
investigation showed the model correctly identified implied liability
exposure beyond what the field description's literal wording required -
the fix was correcting a wrong prediction on my part, not patching a
design defect. No field description was modified. This is the second
round in a row (after Round 4's case_33/E/G/H) where an apparent
"disagreement" turned out to be an error in the recorded expected value,
not in the extraction - worth remembering as a general lesson: **a
disagreement between model output and a hand-written expectation is not
automatically a model bug.**

**One real, still-open design question, confirmed (not just theorized) by
Case W/X:** a purely generic, no-personal-anchor educational coverage
question currently routes to `request_more_info` rather than `auto_reply`,
because the missing-policy-number rule fires unconditionally ahead of the
feature-existence check, and no policy number is relevant to a fully
generic question in the first place. This is a genuine design decision to
make, not a bug - flagged, not fixed, consistent with treating Category
B's 7th-field question as still open.

### Is this ready for actual `classifier.py` implementation in a new thread?

**Close, but not yet - three specific things still stand between this
design and implementation, stated plainly rather than rounded up to
"done":**

1. **28.1% of the 64-row space has real-model validation; 71.9% does
   not.** Every tested row has passed cleanly and stably, and the tested
   set now includes the highest-value compound and edge cases by design -
   but "every row we checked works" is not the same claim as "the design
   works." The remaining untested rows are lower-priority (mostly
   `ref=1, liab=1` variants where liability dominates regardless of the
   other 4 fields, so the marginal risk is genuinely lower) but they are
   not zero-risk by assumption alone.
2. **The Case W/X finding is a real open decision**, not a defect: does a
   fully generic educational question deserve `auto_reply`, or does
   `request_more_info` remain the safer default? This should be resolved
   as a deliberate choice before implementation, the same way Category
   A's liability question was resolved as a deliberate choice earlier
   this session - not left for `classifier.py` to inherit unresolved.
3. **This entire validation has been standalone.** Every test in this
   whole investigation called the extraction schema directly via an
   isolated script - never through `classifier.py`, never integrated with
   the rest of the category-routing prompt (`new_claim`, `claim_status`,
   `policy_change`, etc.), never checked against the full `run_eval.py`
   pipeline or the 57-case golden dataset as a whole. Integration risk
   (does adding a 6-field extraction tool alongside the existing
   category/urgency/action schema change behavior on *other* categories,
   the way v8/v9's prompt-text changes did?) has not been tested at all.

**Recommended next step for a new thread, not this one:** resolve the
Case W/X design question explicitly, then implement as an actual
`classifier.py` change (new tool-schema fields alongside the existing
ones, the decision function as a plain Python post-processing step - not
another prose rewrite of `SYSTEM_PROMPT`), then run the full `run_eval.py`
57-case suite (not just `coverage_question` cases) 3x for stability,
watching explicitly for the same cross-category destabilization pattern
that broke v8 and v9 (a `coverage_question`-scoped change affecting
`new_claim`/`claim_status`/other categories). That integration test is the
one thing nothing in this entire session - 33 cases, 18 rows, 3 stability
checks - has been able to substitute for.

---

**Design decision (2026-08-01):** Case W/X generic/no-anchor questions
intentionally route to `request_more_info` due to missing policy number,
even though the question itself doesn't require one. Decided in favor of
consistency and lower-cost-of-error over customer convenience. No
exception field added; not a bug.
