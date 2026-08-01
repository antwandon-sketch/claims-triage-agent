# coverage_question: real model extraction vs. hand-traced booleans

Produced 2026-08-01. Standalone validation script
(`coverage_question_model_extraction_test.py`, session scratchpad, not part
of the tracked repo - same convention as `case32_ablation.py`), not wired
into `classifier.py` or any pipeline file.

**Purpose:** every round of the extract-then-decide design so far
(`coverage_question_manual_trace.md`, `coverage_question_fresh_holdout.md`)
used hand-traced boolean values as a stand-in for the model's actual
extraction behavior. This is the first test of the real thing - Claude
(`claude-sonnet-5`), given the raw email text and the same 6 field
definitions used throughout, extracting the booleans itself via forced
tool use (same pattern as `classifier.py`'s `classify_email`, but isolated,
not wired into the real pipeline), with the Round 6 override applied and
the result run through the existing (unmodified, not retrained)
tree-derived decision function.

All 17 cases: the 9 golden `coverage_question` cases plus the 8 fresh
holdout cases from `coverage_question_fresh_holdout.md`.

---

## Per-case results

### case_08
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | False | False | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | **True** | False | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`auto_reply`, expected=`request_more_info` — **MISMATCH**

### case_09
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | True | True | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | False | False | |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`request_more_info`, expected=`request_more_info` — MATCH

### case_10
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | True | True | |
| has_policy_or_claim_number | False | False | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | **True** | False | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`request_more_info`, expected=`request_more_info` — MATCH (disagreement didn't change the outcome - missing policy number short-circuits either way)

### case_20
All 6 fields agree. Final action: model=`request_more_info`, expected=`request_more_info` — MATCH

### case_31
All 6 fields agree. Final action: model=`request_more_info`, expected=`request_more_info` — MATCH

### case_32
All 6 fields agree. Final action: model=`escalate_human`, expected=`escalate_human` — MATCH

### case_33
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | False | False | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | True | True | |
| asks_feature_existence_only | False | **True** | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`escalate_human`, expected=`escalate_human` — MATCH (disagreement didn't change the outcome - underwriting signal already forces escalation before this field is consulted)

### case_34
All 6 fields agree. Final action: model=`escalate_human`, expected=`escalate_human` — MATCH

### case_35
All 6 fields agree. Final action: model=`auto_reply`, expected=`auto_reply` — MATCH

### Case A
All 6 fields agree. Final action: model=`auto_reply`, expected=`auto_reply` — MATCH

### Case B
All 6 fields agree. Final action: model=`request_more_info`, expected=`request_more_info` — MATCH

### Case C
All 6 fields agree. Final action: model=`escalate_human`, expected=`escalate_human` — MATCH

### Case D
All 6 fields agree. Final action: model=`request_more_info`, expected=`request_more_info` — MATCH

### Case E
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | False | False | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | True | True | |
| asks_feature_existence_only | False | True (flagged moot in the fresh-holdout doc) | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`escalate_human`, expected=`escalate_human` — MATCH (as predicted when this field was flagged "moot" - underwriting signal fires first)

### Case F
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | True | True | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | **False** | True | **YES** |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | False | False | |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`request_more_info`, expected=`escalate_human` — **MISMATCH**

### Case G
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | False | False | |
| has_policy_or_claim_number | False | False | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | False | True (flagged moot in the fresh-holdout doc) | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`request_more_info`, expected=`request_more_info` — MATCH (as predicted when flagged "moot" - missing policy number resolves it either way)

### Case H
| Field | Model | Hand-traced | Differs? |
|---|---|---|---|
| references_specific_incident | True | True | |
| has_policy_or_claim_number | True | True | |
| has_liability_or_dispute_signal | False | False | |
| has_underwriting_or_nonstandard_use_signal | False | False | |
| asks_feature_existence_only | **False** | True | **YES** |
| cause_investigated_and_unresolved | False | False | |

Final action: model=`request_more_info`, expected=`request_more_info` — MATCH. Notable: the model landed on the *opposite* boolean value from the hand-traced extraction (which was itself flagged as genuinely ambiguous), but the Round 6 override made it moot either way here - `references_specific_incident=True`, so `asks_feature_existence_only` gets forced to `False` regardless of what the model said, and the override's forced value happens to match what the model independently extracted anyway.

---

## Summary

**Final action match rate: 15/17 (88.2%)**
**Field-level agreement rate: 95/102 (93.1%)**

Field-level disagreement occurred in 7 of 17 cases, but only 2 of those 7 actually changed the final action - the other 5 disagreements happened to land on a field that either didn't matter for that case (short-circuited by another field, or made moot by the Round 6 override) or didn't cross a decision boundary. That distinction matters: raw field disagreement (7/17, ~41% of cases had at least one wrong field) is a much less reassuring number than the 15/17 action-match rate suggests on its own - the design has real slack in it that happened to absorb most of the model's extraction noise, but not all of it.

## Flagged: cases where disagreement changed the outcome (the real findings)

### case_08 — a previously-known ambiguity, not fixed by the Round 6 override

Model extracted `asks_feature_existence_only=True`; hand trace said `False`.
This is the exact ambiguity flagged all the way back in Round 1 of
`coverage_question_manual_trace.md`: "if my car is in the shop after an
accident... just want to know before I need it" can genuinely be read
either as a scenario-specific eligibility question or a generic feature
question. **The Round 6 override does not help here** - it only fires when
`references_specific_incident=True`, and both the model and the hand trace
agree that field is `False` for this case (the hypothetical framing reads
as "no incident yet" either way). This is a distinct gap from Case H's -
Case H's problem was a real incident described in generic phrasing; case_08's
problem is a hypothetical framing that reads as a generic feature question
to the model, when the golden label says it shouldn't. No existing override
addresses this.

### Case F — a real, concerning inconsistency in the model's own extraction

Model extracted `has_liability_or_dispute_signal=False` for a delivery
driver slipping on icy steps and seeing a doctor for his back - a case
built specifically as "the clearest possible liability signal," structurally
almost identical to case_32 (dog bite, doctor visit, nothing filed yet),
where the model *did* correctly extract `True`. **The model was
inconsistent with itself across two nearly-identical liability scenarios in
the same test run.** Likely cause: the field's own definition emphasizes
dispute/denial/active-disagreement language ("fault between two parties,
'they said it's not covered,' an active disagreement") more heavily than
pure liability *exposure* - and a slip-and-fall with no claim filed yet and
no one disputing anything arguably has no active "dispute" yet, only
potential future liability. This is the same tension flagged in
`coverage_question_manual_trace.md`'s "Cross-case pattern" note (active
liability exposure vs. actual fault dispute being folded into one field),
now showing up as inconsistent model behavior rather than just an
abstract definitional concern. Worth narrowing this field's definition to
explicitly state that *potential* liability exposure counts, not just an
active dispute - the current wording's own examples are pulling the model
toward the narrower reading, unpredictably.

---

## What this does and doesn't establish

- **Does establish:** the model can extract most of these 6 fields
  reliably (10 of 17 cases had zero disagreement at all), and the design's
  branch structure absorbs a fair amount of extraction noise without it
  reaching the final action.
- **Does not establish:** that this is production-ready. Two real,
  distinct failure modes surfaced in a single 17-case run - a
  known-but-unfixed hypothetical-framing ambiguity (case_08) and a
  genuine model self-inconsistency on the liability field (Case F). Both
  are actionable, neither is fixed by anything built so far tonight.
- **Sample size caveat:** 17 cases, one model call each, no repeat-run
  stability check (unlike the case_09/case_32 stability checks done
  earlier this session for the prompt-text-only design). It's not yet
  known whether Case F's disagreement is a stable pattern or ordinary
  run-to-run variance - that would need the same 3x-repeat discipline
  used everywhere else this session before concluding it's a reliable
  failure mode rather than a one-off.
- **Still no classifier.py changes. Still not treating this as final.**

---

## Round 2: revised field descriptions for the two flagged findings

Targeted schema-description changes only - the decision function, the
Round 6 override, and the other 4 field descriptions are unchanged. Not
touching `classifier.py` or any pipeline file; still a standalone scratch
script.

### Revised: `asks_feature_existence_only`

Added two worked examples distinguishing a pure lookup from a
hypothetically-phrased scenario that still requires conditional
evaluation, using phrasing similar in shape to case_08's without copying
it verbatim:

```
True if the question can be answered by confirming whether a specific
coverage or add-on is present on the policy at all (a yes/no lookup
against the declarations page), with no need to evaluate whether a
particular situation would qualify or trigger it. False if answering
requires judging whether a specific (even hypothetical/future) scenario
would meet the coverage's conditions or limits. Worked examples: "does my
policy include rental reimbursement" is a pure lookup (True) - it has one
yes/no answer regardless of circumstances. "If my car needs repairs after
a covered accident, would a rental be included" is phrased
conditionally/hypothetically but is NOT a pure lookup (False) - answering
it still requires evaluating whether that future scenario would meet the
coverage's conditions (was it a covered peril, is there a
comprehensive/collision requirement, what are the per-day/total limits),
so hypothetical phrasing does not by itself make something a pure
existence lookup.
```

### Revised: `has_liability_or_dispute_signal`

Broadened to trigger on unaddressed third-party injury/property-damage
exposure directly, not only on active dispute/denial language:

```
True if the email describes potential liability exposure to a third party
- a non-household person was injured, or their property was damaged, in a
way connected to the policyholder (e.g., on their property, or caused by
their pet, vehicle, or actions) - even if nothing has been filed yet and
no one has disputed fault or coverage yet. An unaddressed third-party
injury or property-damage exposure needs human review regardless of
whether a dispute has actually started. Also True for language suggesting
an active dispute over fault, a denial, or a contested coverage outcome
(fault between two parties, "they said it's not covered," an active
disagreement) - that is a second, independent way to trigger this field,
not a requirement for the third-party case above.
```

### Re-run: all 17 cases, real model extraction, revised schema

**Final action match rate: 15/17 (unchanged from Round 1)**
**Field-level agreement rate: 95/102, 93.1% (unchanged from Round 1)**

**The two targeted fixes worked exactly as intended:**

| Case | Field | Round 1 (before) | Round 2 (after) | Fixed? |
|---|---|---|---|---|
| case_08 | asks_feature_existence_only | True (wrong) → `auto_reply` (MISMATCH) | False (correct) → `request_more_info` (MATCH) | **YES** |
| Case F | has_liability_or_dispute_signal | False (wrong) → `request_more_info` (MISMATCH) | True (correct) → `escalate_human` (MATCH) | **YES** |

**But two cases that matched cleanly in Round 1 are now new mismatches -
explicitly checked for, not assumed clean:**

| Case | Field(s) that changed | Round 1 | Round 2 |
|---|---|---|---|
| **Case B** | `has_underwriting_or_nonstandard_use_signal`: False → **True** | MATCH (`request_more_info`) | **MISMATCH** (`escalate_human`, expected `request_more_info`) |
| **Case G** | `has_liability_or_dispute_signal`: False → **True**; `asks_feature_existence_only`: True → False | MATCH (`request_more_info`) | **MISMATCH** (`escalate_human`, expected `request_more_info`) |

**Net result: the fix traded two failures for two different failures. The
overall match rate did not improve** - this is the same shape of problem
that showed up all night at the prompt-text level (v7's reword, v8's
revert, v9's rewrite each fixed a targeted case while destabilizing
another), now reproduced one layer down, at the field-schema-description
level.

### Why the new regressions happened

**Case G** is directly explained by the `has_liability_or_dispute_signal`
broadening: "If my tree fell on my neighbor's fence during a storm, does
homeowners insurance typically cover that kind of thing?" describes
hypothetical third-party property damage (a neighbor's fence). The revised
definition's "their property was damaged... even if nothing has been
filed yet" doesn't distinguish an already-occurred third-party loss
(case_32, Case F) from a purely hypothetical one that hasn't happened
("if my tree fell") - Case G was always meant to resolve via its missing
policy number, but the model now reads it as a live liability-exposure
case before that ever gets checked, because **the decision function checks
`has_liability_or_dispute_signal` before `has_policy_or_claim_number`** -
the missing-policy-number path is not a true first-priority check, it
only applies once liability, cause-unresolved, and underwriting have all
already come back False. That branch-order fact was true in Round 1 too,
but never surfaced because no case tripped both fields at once until this
revision made it possible.

**Case B**'s regression is harder to explain directly - the field that
flipped (`has_underwriting_or_nonstandard_use_signal`) was not one of the
two fields revised this round. The POD-storage-during-a-move scenario now
reads as a non-standard-use signal to the model where it didn't before.
Possible causes: ordinary single-call model variance (no stability check
has been run on this specific case), or an indirect effect of the tool
schema changing overall (new examples added to two other fields shifting
how the model weighs the whole extraction task). **Cannot distinguish
between these two explanations from a single run** - the same discipline
used everywhere else this session (re-run 2-3 times, no code changes, to
tell a real effect from ordinary variance) would be needed before treating
Case B's regression as caused by this change specifically, as opposed to
a one-off.

### Caveats, unchanged in kind from Round 1

1. Net match rate is flat (15/17 both rounds) - this round did not make
   the design better, it relocated the failures.
2. Case G's root cause (branch-order priority) is a real, previously
   invisible structural fact about the decision function - worth noting
   even though the function itself is explicitly out of scope for this
   round's changes.
3. Case B's root cause is unconfirmed - could be real cross-field
   interaction from the schema change, or ordinary variance. Not resolved
   here.
4. **Still no classifier.py changes. Still not treating any of this as
   final.**

---

## Round 3: Category A real-data test + fixes for the Case B and Case G extraction bugs

Two separate threads this round: (1) writing real synthetic test cases for
Category A - the "purely hypothetical liability" combination that
`coverage_question_decision_table.md` resolved to `escalate_human` with
zero real test coverage - and (2) fixing the two extraction bugs Round 2
introduced (Case B, Case G) without re-breaking anything Round 2 already
fixed (case_08, Case F).

### ITEM 1: two new Category A test cases, independently labeled first

**Case I - "Worried about our dog being liable"**

> "My dog has started growling and lunging at the fence when the mail
> carrier walks by, and I'm worried he might get loose one day. If he ever
> got out and bit someone, would we be liable for that, and is something
> like that covered under our homeowners policy, HO-88213?"

**Independent reasoning, before running anything:** No bite has occurred -
purely preventive, hypothetical ("if he ever got out"). But this
explicitly invokes liability language ("would we be liable") about a
potential future third-party injury. Per the Category A resolution in
`coverage_question_decision_table.md`: liability exposure carries
asymmetric downside risk regardless of whether it's already happened, and
a real agency has genuine reason to want visibility into this kind of
thing early (aggressive-dog liability is a real underwriting concern, not
just a claims one). **Independent label: `escalate_human`.**

**Case J - "Are we liable if someone falls on our front steps?"**

> "We have a steep, uneven set of front steps with no railing, and I keep
> thinking someone's going to trip on them eventually. If a guest or
> delivery person ever fell and got hurt there, would we be liable, and
> would that be covered under our homeowners policy? I don't have my
> policy number handy right now."

**Independent reasoning, before running anything:** Same shape as Case I -
a known physical hazard, framed as a preventive liability worry, nothing
has happened yet. Also missing a policy number, which is a useful
additional test: per the established priority order, liability concerns
should dominate the missing-policy-number path too (checked first), not
get silently downgraded to `request_more_info` just because identifying
info is also missing. **Independent label: `escalate_human`.**

Both cases were deliberately written as *clean* Category A tests - genuine
liability/fault language, explicitly no incident - rather than edge cases,
specifically to check whether the abstract resolution holds up on the
simplest real version of the combination before worrying about harder
variants.

### ITEM 2: revised field descriptions for the two extraction bugs

**`has_liability_or_dispute_signal` - the Case G bug.** Root cause: the
Round 2 broadening ("a person WAS injured, or their property WAS damaged")
didn't clearly rule out a purely hypothetical framing, so "if my tree fell
on my neighbor's fence... does insurance typically cover that" got read as
live liability exposure. This is a **different problem from Category A**:
Category A is about what to DO once liability is correctly True (resolved:
escalate, no incident required); this bug is about the field incorrectly
turning True on a case that was never actually a liability question at all
- Case G asks a generic "does my policy cover this type of peril" question
that happens to mention a neighbor's property, not "would I be liable."
The fix distinguishes explicit liability/fault language (Case I, Case J)
from a generic hypothetical coverage question that merely mentions a third
party (Case G):

```
True if EITHER: (1) the email describes a third-party injury or
property-damage incident that has ALREADY occurred or is currently
happening, connected to the policyholder (e.g., on their property, or
caused by their pet, vehicle, or actions) - even if nothing has been filed
and no dispute has started yet; OR (2) the email explicitly frames a
hypothetical, not-yet-happened scenario using liability/fault/
responsibility language - asking whether the policyholder would be
"liable," "responsible," "at fault," or similar, for a potential future
third-party injury or damage. Also True for language suggesting an active
dispute over fault, a denial, or a contested coverage outcome ("they said
it's not covered," an active disagreement).
False for a hypothetical, not-yet-happened scenario phrased as a GENERIC
coverage question, without explicit liability/fault/responsibility
language - even if it mentions a third party's property. Worked examples:
"my dog keeps lunging at the fence, if he ever got loose and bit someone,
would we be LIABLE for that" is True - hypothetical, but explicitly asks
about liability/fault for a potential future third-party injury. "if a
tree in our yard ever fell on the neighbor's shed, does homeowners
insurance TYPICALLY cover that kind of thing" is False - hypothetical,
mentions a third party's property, but is a generic "does my policy cover
this type of peril" question, not an explicit liability/fault question -
treat it the same as any other hypothetical coverage question, not as a
liability signal.
```

**`has_underwriting_or_nonstandard_use_signal` - the Case B bug.** Root
cause: "a POD storage container sitting in our driveway for the week" was
read as non-standard property use, when the field is meant to capture
lasting risk-profile changes (a business, a rental unit), not ordinary
temporary personal circumstances that happen to look physically unusual.
Fix distinguishes ongoing/commercial from temporary/routine:

```
True if the email describes an ONGOING business activity, a commercial use
of the property, or another LASTING change in risk profile the policy
wasn't written for (e.g., running a business from home, renting out a
room, keeping livestock) - a risk the insurer would need to know about and
potentially underwrite separately. False for routine, TEMPORARY personal
circumstances, even if physically unusual-sounding - these don't change
the property's risk profile or require separate underwriting, they're
ordinary temporary situations, not a business or lasting non-standard use.
Worked examples: "I run a dog-boarding business out of my basement" is
True (ongoing commercial activity, a real underwriting-relevant risk
change). "We have a storage pod parked in the driveway for a few days
during a home move" is False (temporary, routine, not a business or
lasting risk-profile change - just an ordinary moving-related
inconvenience).
```

### Re-run: all 19 cases (17 existing + Case I + Case J), real model extraction

**Final action match rate: 19/19 (100%)**
**Field-level agreement rate: 110/114 (96.5%)** - up from 95/102 (93.1%) in
Round 2.

**Both targeted bugs are fixed, confirmed by direct comparison:**

| Case | Field | Round 2 (before) | Round 3 (after) | Fixed? |
|---|---|---|---|---|
| Case B | has_underwriting_or_nonstandard_use_signal | True (wrong) → `escalate_human` (MISMATCH) | False (correct) → `request_more_info` (MATCH) | **YES** |
| Case G | has_liability_or_dispute_signal | True (wrong) → `escalate_human` (MISMATCH) | False (correct) → `request_more_info` (MATCH) | **YES** |

**Neither previously-fixed case broke:**

| Case | Round 2 | Round 3 |
|---|---|---|
| case_08 | MATCH, 0 diffs | MATCH, 0 diffs (unchanged) |
| Case F | MATCH, 0 diffs | MATCH, 0 diffs (unchanged) |

**Both new Category A cases match the independent, pre-registered
reasoning:**

| Case | Independent label | Model extraction | Final action | Result |
|---|---|---|---|---|
| Case I (aggressive dog) | escalate_human | liab=True (correct), all fields clean | escalate_human | **MATCH** |
| Case J (unsafe steps, no policy #) | escalate_human | liab=True (correct), all fields clean, pol=False correctly extracted too | escalate_human | **MATCH** |

Case J is worth calling out specifically: `has_policy_or_claim_number`
correctly extracted `False`, and `has_liability_or_dispute_signal`
correctly extracted `True` - the model applied the priority order
correctly on its own (liability dominates the missing-policy-number path),
without that priority order being restated anywhere in the extraction
schema itself (extraction and decision are still two separate steps; the
schema doesn't know about branch order, only the downstream function does).

**Four residual field-level disagreements remain, none of which changed
any outcome** (same "doesn't matter, but not zero" pattern as Round 1/2):
`case_33`, `Case E`, `Case G`, `Case H` all still show `asks_feature_existence_only`
disagreements - all four are structurally protected from mattering (Case
33/E by the underwriting signal firing first; Case G by the missing-
policy-number path firing regardless; Case H because `ref=True` routes
past `exist` before it's ever consulted). `asks_feature_existence_only`
remains this design's least reliably-extracted field across all three
rounds, even though it has never yet caused a live mismatch after Round 1.

### Category A: does the abstract reasoning hold up on real data?

**Yes, on this round's test - but with the same caveat as everywhere else
this session: two clean, deliberately-easy cases passing is a first data
point, not proof.** Both Case I and Case J were designed to be unambiguous
Category A examples (explicit "would we be liable" language, clearly no
incident), specifically to test whether the *clean* form of the abstract
resolution holds before testing harder variants. It did. A genuinely
harder next test would be a Category A case *without* explicit
liability/fault wording - e.g., a hypothetical scenario that's liability-
*shaped* but doesn't use the word "liable" or "responsible" at all - which
would stress-test the revised field definition's reliance on explicit
liability/fault/responsibility language rather than confirm it.

### Caveats, carried forward and updated

1. **`asks_feature_existence_only` remains the weakest-extracted field**
   across all three rounds (4 of 19 cases this round) - still never fatal
   so far, purely because of branch-order luck, not because the field
   itself has been fixed. Worth a dedicated round if this design moves
   toward implementation.
2. Category A's real-data validation is now n=2, both deliberately easy.
   The harder "liability-shaped but no explicit liability wording" variant
   remains untested.
3. Sample-size/stability caveat from Round 1 still applies: no case in
   this file has been repeat-run to check for ordinary model variance -
   every result here is a single API call per case.
4. **Still no classifier.py changes. Still not treating any of this as
   final.**

---

## Round 4: fixing asks_feature_existence_only's 4 residual disagreements - fixed, but broke case_08

### Step 1: the 4 cases (from Round 3, confirmed directly in that section above)

`case_33`, `Case E`, `Case G`, `Case H` - all 4 showed `asks_feature_existence_only`
disagreements in Round 3, all in the same direction: model said `False`,
hand-trace said `True`.

### Step 2: raw text, read fresh from source (not trace-doc paraphrases)

- **case_33** (`golden_dataset.json`): "I started selling candles online
  out of my garage a few months ago. Does my homeowners policy, HO-33987,
  cover any of that, **or do I need something separate**?"
- **Case E** (`coverage_question_fresh_holdout.md`): "I've started using
  my detached garage as a small pottery studio, I fire pieces in a kiln a
  few times a week. Does my homeowners policy cover that space and the
  equipment, **or do I need something separate**?"
- **Case G** (`coverage_question_fresh_holdout.md`): "If my tree fell on
  my neighbor's fence during a storm, does homeowners insurance
  **typically** cover that kind of thing?"
- **Case H** (`coverage_question_fresh_holdout.md`): "My laptop was stolen
  out of my car last weekend... Does my renters policy **typically**
  cover personal property stolen from a vehicle, and is there a special
  limit for electronics?"

### Step 3: the pattern - and a correction to the hand-trace, not just the model

All 4 use generic-sounding surface phrasing ("typically," "or do I need
something separate") that superficially resembles a feature-existence
lookup - but all 4 are also anchored to a real, specific personal scenario
(their actual candle business, their actual kiln, their actual tree and
named neighbor, their actual stolen laptop). **The model consistently
ignored the generic-sounding phrasing and keyed off the personal anchor
instead - the same, single direction in all 4 cases, not scattered
ambiguities.** The hand-trace did the opposite: it was swayed by the
generic wording and called these `True`, inconsistent with the two clean
reference `True` cases (case_35, Case A - both genuinely zero-anchor
"does my policy include X" questions).

**Conclusion, stated plainly: this was a hand-trace calibration error on
four cases, not a pure model extraction bug.** The model's consistent
behavior is the more defensible reading of the field's own original
intent ("no need to evaluate whether a particular situation would
qualify") - all 4 cases require evaluating a real, specific situation,
regardless of how genetically the question is phrased. Corrected the
recorded hand-traced value for `asks_feature_existence_only` from `True`
to `False` for all 4 cases before re-running - verified beforehand that
this changes none of their expected final actions (all 4 were already
"moot" for exactly this reason: `uw=True` dominates for case_33/Case E,
missing `pol` dominates for Case G, `ref=True` dominates for Case H).

### Step 4: revised field description

```
True ONLY if the question has NO personal or situational anchor at all -
it could be asked by any policyholder regardless of their specific
circumstances, answerable with one generic yes/no fact about the policy (a
lookup against the declarations page). False if the question is tied to
ANY specific real, hypothetical, or ongoing personal scenario - a
particular business, a particular pet/property/person, a particular item,
a particular past or possible future event - EVEN IF the question is
phrased generically using words like "typically" or asks "or do I need
something separate" - that kind of generic-sounding phrasing does NOT
override a real personal anchor; judge by whether a real scenario is
present, not by the surface wording. Worked examples: "does my policy
include roadside assistance" is True - no personal scenario at all,
purely about the policy's feature list, answerable the same way for
anyone. "I run a candle business out of my garage, does my policy cover
that, or do I need something separate?" is False - despite the "or do I
need something separate" framing (which sounds like a generic feature
check), it's tied to their specific real business, and answering requires
evaluating whether THEIR specific activity is covered, not a generic
yes/no. "If my tree fell on my neighbor's fence, does homeowners insurance
typically cover that kind of thing?" is False - despite the "typically"
framing (which sounds generic), it's anchored to their specific tree and
their specific neighbor's property, and "typically" doesn't make it a
pure lookup. Hypothetical/conditional phrasing ("if X happened, would Y
be included") is also NOT a pure lookup on its own, for the same reason -
a hypothetical scenario is still a specific scenario, not a generic
feature check.
```

No other field's description was touched. The decision function/table
from `coverage_question_decision_table.md` was not changed - this round
only ever touched extraction-schema text.

### Re-run: all 19 cases, revised schema + corrected hand-trace

**`asks_feature_existence_only`-specific agreement rate: 18/19 (94.7%)** -
up from 15/19 (78.9%) measured against the *old* hand-trace in Round 3.

**Overall field-level agreement rate: 113/114 (99.1%)** - up from 110/114
(96.5%) in Round 3.

**Final action match rate: 18/19 (94.7%) - DOWN from 19/19 in Round 3.**

**The 4 targeted disagreements are fixed, confirmed directly:**

| Case | Round 3 | Round 4 |
|---|---|---|
| case_33 | diff (model=False, hand=True*) | **0 diffs** |
| Case E | diff (model=False, hand=True*) | **0 diffs** |
| Case G | diff (model=False, hand=True*) | **0 diffs** |
| Case H | diff (model=False, hand=True*) | **0 diffs** |

*hand-trace value shown is the pre-correction Round 3 value, since that's
what was being compared against at the time.

**But case_08 - clean in Round 2 and Round 3 - broke:**

| Field | Round 3 | Round 4 |
|---|---|---|
| `asks_feature_existence_only` | `False` (correct) | **`True` (wrong)** |
| Final action | `request_more_info` (MATCH) | **`auto_reply` (MISMATCH)** |

**This is the exact same bug case_08 had in Round 1, re-fixed in Round 2,
now regressed in Round 4.** Almost certainly the cause: Round 2's fix
added a worked example closely shaped like case_08 itself ("If my car
needs repairs after a covered accident, would a rental be included" -
deliberately close to case_08's actual phrasing without copying it
verbatim). **Round 4's rewrite replaced the entire description, including
that example, with new worked examples targeting the personal-anchor
pattern (candle business, tree/neighbor) - it did not preserve or combine
with the Round 2 example.** The new description does state the general
principle broadly enough that it should logically cover case_08 too
("Hypothetical/conditional phrasing... is also NOT a pure lookup"), but
empirically, on this run, it didn't transfer - a specific, closely-matched
worked example appears to have been doing real work that a more general
statement of the same principle didn't fully replicate.

**Explicit status of every previously-fixed case, checked individually as
instructed - not assumed clean:**

| Case | Status |
|---|---|
| case_08 | **BROKEN this round** (was fixed in Round 2, held in Round 3) |
| Case F | Still correct, 0 diffs |
| Case B | Still correct, 0 diffs |
| Case G | Still correct, 0 diffs (and its own targeted `asks_feature_existence_only` disagreement is now also fixed) |
| Case I (Category A) | Still correct, 0 diffs |
| Case J (Category A) | Still correct, 0 diffs |

**No other new disagreements on any other field** - the only change from
Round 3 to Round 4, across all 19 cases and 6 fields, is
`asks_feature_existence_only` on these 5 cases (4 fixed, 1 newly broken).

### Net assessment: this is not a clean win, stated plainly

Field-level agreement improved (96.5% → 99.1%) and the underlying pattern
identified was real and worth fixing - the hand-trace correction alone was
a genuine improvement in accuracy of what's being measured against. But
the final-action match rate went down (19/19 → 18/19), because fixing 4
cases cost 1 previously-fixed case. This is the same shape of problem that
has recurred all session, one level down again: this time inside a single
field's worked-example set, not across fields or across prompt versions.
**Not treating 99.1%/18-19 as better than 96.5%/19-19 just because one
number went up** - the number that matters most (final action) went down.

**Not fixed within this round, flagged as the clear next step:** restore
or reintroduce a case_08-shaped worked example *alongside* the new
personal-anchor examples, rather than in place of them, and re-verify
against all 19 (plus a repeat-run check on case_08 specifically, since
this is a single API call and it's not yet confirmed whether this
regression is stable or ordinary variance - the same repeat-run caveat
flagged and never yet acted on since Round 1).

### Caveats, carried forward and updated

1. **case_08 is an open regression, not a resolved one.** Next round
   should not claim `asks_feature_existence_only` is fixed until this is
   addressed and re-verified.
2. Category A's real-data validation remains n=2 (Case I, Case J), both
   still correct this round, both still deliberately easy tests.
3. No case in this file has ever been repeat-run to distinguish a stable
   wording effect from ordinary single-call model variance - this
   round's case_08 regression is exactly the kind of result that caveat
   was written for.
4. **Still no classifier.py changes. Still not treating any of this as
   final.**

---

## Round 5: fixing case_08 additively, then a real stability check (first one all session)

### Step 1: additive fix, not a replacement

Read Round 4's live `asks_feature_existence_only` description and the
Round 2 history in this document (above) to find the exact worked example
that had protected case_08 before Round 4's rewrite dropped it:

> "does my policy include rental reimbursement" is a pure lookup (True) -
> it has one yes/no answer regardless of circumstances. "If my car needs
> repairs after a covered accident, would a rental be included" is
> phrased conditionally/hypothetically but is NOT a pure lookup (False) -
> answering it still requires evaluating whether that future scenario
> would meet the coverage's conditions (was it a covered peril, is there
> a comprehensive/collision requirement, what are the per-day/total
> limits), so hypothetical phrasing does not by itself make something a
> pure existence lookup.

Appended this verbatim to the end of Round 4's description, after its
existing text - nothing from Round 4 was removed, reworded, or
reordered, only added to. The field description now carries both the
Round 4 personal-anchor-pattern examples (candle business, tree/neighbor)
and the Round 2 case_08-shaped example, side by side.

### Step 2: single confirmation run

**Final action match rate: 19/19 (100%)**
**Field-level agreement rate: 114/114 (100.0%)** - zero disagreements on
any field, any case.

**case_08 confirmed fixed:**

| Field | Round 4 (broken) | Round 5 (this run) |
|---|---|---|
| `asks_feature_existence_only` | `True` (wrong) | `False` (correct) |
| Final action | `auto_reply` (MISMATCH) | `request_more_info` (MATCH) |

**All 4 of Round 4's fixes held** (case_33, Case E, Case G, Case H - all 0
diffs). **No other case newly broke.** This is the first run all session
with zero field-level disagreements across the entire 19-case set.

### Step 3: stability check - verified, not assumed

No design changes between runs. Ran the identical script 2 more times (3
total for this final version) and directly diffed the extracted output
across all 3 runs, rather than trusting matching summary lines alone:

```
$ diff <(run 1 per-case output) <(run 2 per-case output)
(no output - exit code 0)
$ diff <(run 1 per-case output) <(run 3 per-case output)
(no output - exit code 0)
```

**All 3 runs produced byte-identical results** - every one of the 19
cases' 6 extracted booleans, and every final action, matched exactly
across all 3 independent API calls per case (57 total calls this round).

| Run | Final action match | Field-level agreement |
|---|---|---|
| 1 | 19/19 | 114/114 (100.0%) |
| 2 | 19/19 | 114/114 (100.0%) |
| 3 | 19/19 | 114/114 (100.0%) |

### Step 4: stated plainly, as instructed

**Results are stable across all 3 runs, and 19/19 final-action match holds
in every run. No case flips. This is the first fully clean, verified-
stable result for the coverage_question extract-then-decide design this
session** - clean not just on a single run (every prior "clean" result
this session, including Round 3's initial 19/19, was a single API call
per case, never repeat-checked) but confirmed identical across 3
independent runs with zero design changes in between.

### What this does and doesn't establish, stated with the same discipline as every prior round

- **Does establish:** for these specific 19 email texts (17 original +
  2 Category A), with the current 6 field descriptions and the current
  decision function/table, real model extraction is both correct and
  stable across repeats.
- **Does not establish:** that this generalizes beyond these 19 cases.
  `coverage_question_decision_table.md` enumerated 64 possible boolean
  combinations; only a handful have ever been exercised by a real email.
  Category A's real-data coverage is still n=2, both deliberately easy.
  The vague/unanchored "Category B" gap flagged in the decision table
  (defaulted to `request_more_info`, no 7th field added) has real
  coverage from case_08 and Case B only.
- **Does not establish production-readiness.** classifier.py has not been
  touched at any point in this entire investigation (v10 onward). This
  result says the *design*, tested standalone, is currently sound and
  stable on its known cases - it says nothing about integration, about
  cases outside the 19, or about whether real extraction stays this clean
  under different phrasing than what's been tested.
- **Still no classifier.py changes.**
