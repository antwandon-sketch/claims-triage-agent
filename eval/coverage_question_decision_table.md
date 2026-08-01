# coverage_question: exhaustive 64-combination decision table

Produced 2026-08-01. Standalone design-validation doc, not wired into
`classifier.py` or any pipeline file - same convention as the other
`coverage_question_*.md` scratch docs and `coverage_question_full_table.py`
(session scratchpad, not part of the tracked repo).

**Purpose:** every prior round (the manual trace, the fresh holdout set, the
sklearn tree, the model-extraction tests) only ever validated the design
against 9 golden + 8 fresh = 17 real cases. A `DecisionTreeClassifier` fit
on 9 points is, by construction, only *guaranteed* correct on those 9
points - it says nothing about the other 55 combinations of the 6 boolean
fields it was never shown. This document reasons through **all 64**
combinations from the field *definitions alone*, independent of any
specific email's wording, and derives a decision function directly from
that reasoning instead of from a tree fit to a small sample.

## The 6 fields (definitions as currently finalized, Round 2 of `coverage_question_model_extraction_test.md`)

- **`references_specific_incident`** (`ref`): True if the email describes
  or points to a specific triggering event (a particular loss, accident,
  damage, theft, injury) that has *already occurred*, rather than a
  general/hypothetical question about coverage terms.
- **`has_policy_or_claim_number`** (`pol`): True if the email includes an
  explicit policy or claim number, or an unambiguous reference to one.
- **`has_liability_or_dispute_signal`** (`liab`): True if the email
  describes potential liability exposure to a third party - a
  non-household person was injured, or their property was damaged - even
  if nothing has been filed and no dispute has started yet. Also True for
  active dispute/denial/contested-outcome language.
- **`has_underwriting_or_nonstandard_use_signal`** (`uw`): True if the
  email describes a business activity, non-standard use of the property,
  or other change in risk profile the policy wasn't written for - as
  opposed to a claim about something that already happened.
- **`asks_feature_existence_only`** (`exist`): True if the question can be
  answered by confirming whether a coverage/add-on is present on the
  policy at all (a yes/no lookup), with no need to evaluate whether a
  particular situation would qualify. False if answering requires judging
  whether a specific (even hypothetical) scenario would meet the
  coverage's conditions or limits.
- **`cause_investigated_and_unresolved`** (`cause`): True if the cause of
  the damage/loss has already been actively examined and still can't be
  determined. False if the cause is clear, or unknown only because nobody
  has investigated yet.

## Step 1-2: definitional dependencies, N/A rows, and ambiguous rows

Before enumerating, three logical relationships fall directly out of the
definitions above - reasoned once here, then applied mechanically to all
64 rows (via a small script, to avoid hand-computation errors across 64
rows):

**N/A (logically impossible): `cause=True` requires `ref=True`.**
`cause_investigated_and_unresolved` presumes an actual loss/damage whose
cause was examined. There is no such thing as "actively investigated an
unresolved cause" of damage that never happened. **Every row with
`ref=False, cause=True` is marked N/A**, regardless of the other 4 fields
- `2^4 = 16` rows.

**Ambiguous (a): `liab=True, ref=False`.** `has_liability_or_dispute_signal`'s
definition ("a person *was* injured, or their property *was* damaged")
presumes something real happened. The definition doesn't explicitly forbid
a dispute forming over a purely hypothetical scenario, so this isn't
strictly impossible, but it's a real gap - **this is the abstract, general
form of the Case G regression** found empirically in
`coverage_question_model_extraction_test.md` (a hypothetical "if my tree
fell on my neighbor's fence" read as live liability exposure once the
field was broadened). Flagged rather than forced. The decision still
defaults to `escalate_human` for these rows - liability exposure is never
safe to silently downgrade even if the *extraction* that produced it is
questionable - but the flag makes clear this reflects a definitional gap,
not confidence. `8` rows (`pol, uw, exist` free, `cause` forced `False`
since `ref=False`).

**Ambiguous (b): no incident, not a pure lookup, no escalate signal.**
`ref=False, exist=False, liab=False, uw=False` (regardless of `pol`,
`cause` forced `False`) describes a genuinely vague question - not
anchored to a specific incident, and not phrased as a "does X exist"
lookup either (e.g., a broad "how does insurance generally handle mold"
educational question with no named feature and no specific scenario).
None of the 6 fields cleanly capture "vague general question, no named
feature, no incident." Defaults to `request_more_info` (ask what
specifically they mean) as the safer of the two plausible answers, but
this is a real, if narrow, design gap. `2` rows.

No other combinations were found to be impossible or contradictory on
inspection - e.g., `liab=True` and `uw=True` together (an injury connected
to a home business) is unusual but perfectly sensible, not flagged.

## Step 3: the derived priority-order rule

Reasoning from the definitions alone, independent of the tree fit in
`coverage_question_manual_trace.md`:

1. **`liab` → `escalate_human`**, unconditionally. Liability exposure is
   never safe to auto-resolve or silently defer, regardless of what else
   is or isn't known.
2. **`cause` → `escalate_human`** (only reachable with `ref=True`, per the
   N/A rule above). A cause that resisted real investigation needs a human,
   not a guess.
3. **`uw` → `escalate_human`**, unconditionally. A risk-profile change the
   policy wasn't written for needs underwriting judgment, not a template
   answer.
4. **`not pol` OR `ref` → `request_more_info`**. Two different reasons
   collapse to the same action: missing identifying info needs to be
   gathered before anything else can happen, *and*, independently, a real
   already-occurred incident is never answerable via a pure
   existence-lookup regardless of whether a policy number is present (this
   is exactly what the Round 6 override enforced as a separate
   pre-processing step - deriving from the full table makes that override
   **structurally unnecessary**, since checking `ref` before ever
   consulting `exist` achieves the identical effect without a bolt-on
   rule).
5. **`exist` → `auto_reply`**. What's left at this point: no incident, a
   policy number is present (or the question doesn't need one), no
   liability/underwriting/unresolved-cause signal, and it's a pure
   feature-existence lookup - safe for a general, non-binding answer.
6. **Else → `request_more_info`** (ambiguous category (b) above - the
   residual vague-question gap).

## Step 4: the full 64-row table

Columns match the short names above (`ref, pol, liab, uw, exist, cause`),
each `0`/`1`. `status` is `NA` (impossible), `AMBIGUOUS` (flagged, resolved
by default rather than by clean derivation), or `CLEAN` (unambiguous given
the definitions).

| # | ref | pol | liab | uw | exist | cause | status | action |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | AMBIGUOUS | request_more_info |
| 2 | 0 | 0 | 0 | 0 | 0 | 1 | NA | — |
| 3 | 0 | 0 | 0 | 0 | 1 | 0 | CLEAN | request_more_info |
| 4 | 0 | 0 | 0 | 0 | 1 | 1 | NA | — |
| 5 | 0 | 0 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 6 | 0 | 0 | 0 | 1 | 0 | 1 | NA | — |
| 7 | 0 | 0 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 8 | 0 | 0 | 0 | 1 | 1 | 1 | NA | — |
| 9 | 0 | 0 | 1 | 0 | 0 | 0 | AMBIGUOUS | escalate_human |
| 10 | 0 | 0 | 1 | 0 | 0 | 1 | NA | — |
| 11 | 0 | 0 | 1 | 0 | 1 | 0 | AMBIGUOUS | escalate_human |
| 12 | 0 | 0 | 1 | 0 | 1 | 1 | NA | — |
| 13 | 0 | 0 | 1 | 1 | 0 | 0 | AMBIGUOUS | escalate_human |
| 14 | 0 | 0 | 1 | 1 | 0 | 1 | NA | — |
| 15 | 0 | 0 | 1 | 1 | 1 | 0 | AMBIGUOUS | escalate_human |
| 16 | 0 | 0 | 1 | 1 | 1 | 1 | NA | — |
| 17 | 0 | 1 | 0 | 0 | 0 | 0 | AMBIGUOUS | request_more_info |
| 18 | 0 | 1 | 0 | 0 | 0 | 1 | NA | — |
| 19 | 0 | 1 | 0 | 0 | 1 | 0 | CLEAN | auto_reply |
| 20 | 0 | 1 | 0 | 0 | 1 | 1 | NA | — |
| 21 | 0 | 1 | 0 | 1 | 0 | 0 | CLEAN | escalate_human |
| 22 | 0 | 1 | 0 | 1 | 0 | 1 | NA | — |
| 23 | 0 | 1 | 0 | 1 | 1 | 0 | CLEAN | escalate_human |
| 24 | 0 | 1 | 0 | 1 | 1 | 1 | NA | — |
| 25 | 0 | 1 | 1 | 0 | 0 | 0 | AMBIGUOUS | escalate_human |
| 26 | 0 | 1 | 1 | 0 | 0 | 1 | NA | — |
| 27 | 0 | 1 | 1 | 0 | 1 | 0 | AMBIGUOUS | escalate_human |
| 28 | 0 | 1 | 1 | 0 | 1 | 1 | NA | — |
| 29 | 0 | 1 | 1 | 1 | 0 | 0 | AMBIGUOUS | escalate_human |
| 30 | 0 | 1 | 1 | 1 | 0 | 1 | NA | — |
| 31 | 0 | 1 | 1 | 1 | 1 | 0 | AMBIGUOUS | escalate_human |
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

**Totals: 16 NA, 10 AMBIGUOUS, 38 CLEAN.** (Generated and counted
programmatically, `coverage_question_full_table.py`, not hand-tallied.)

Rows 41-64 (`ref=1, liab=1`, i.e. any real incident with a liability
signal) are all `escalate_human` regardless of the other 4 fields, which
looks repetitive in the table but is the correct, honest reflection of the
priority rule - `liab=True` dominates everything else by design (step 1),
so 16 of the 64 rows are "clean" for the same one-line reason. Not
collapsed into a single summary row here because the instruction asked for
all 64 enumerated explicitly.

## Step 4 (cross-check): all 17 known cases against the new table

| case | combo (ref,pol,liab,uw,exist,cause) | table action | expected | match |
|---|---|---|---|---|
| case_08 | (0,1,0,0,0,0) | request_more_info | request_more_info | MATCH |
| case_09 | (1,1,0,0,0,0) | request_more_info | request_more_info | MATCH |
| case_10 | (1,0,0,0,0,0) | request_more_info | request_more_info | MATCH |
| case_20 | (0,0,0,0,1,0) | request_more_info | request_more_info | MATCH |
| case_31 | (1,1,0,0,0,0) | request_more_info | request_more_info | MATCH |
| case_32 | (1,1,1,0,0,0) | escalate_human | escalate_human | MATCH |
| case_33 | (0,1,0,1,1,0) | escalate_human | escalate_human | MATCH |
| case_34 | (1,1,0,0,0,1) | escalate_human | escalate_human | MATCH |
| case_35 | (0,1,0,0,1,0) | auto_reply | auto_reply | MATCH |
| Case A | (0,1,0,0,1,0) | auto_reply | auto_reply | MATCH |
| Case B | (0,1,0,0,0,0) | request_more_info | request_more_info | MATCH |
| Case C | (1,1,0,0,0,1) | escalate_human | escalate_human | MATCH |
| Case D | (1,1,0,0,0,0) | request_more_info | request_more_info | MATCH |
| Case E | (0,1,0,1,1,0) | escalate_human | escalate_human | MATCH |
| Case F | (1,1,1,0,0,0) | escalate_human | escalate_human | MATCH |
| Case G | (0,0,0,0,1,0) | request_more_info | request_more_info | MATCH |
| Case H | (1,1,0,0,1,0) | request_more_info | request_more_info | MATCH |

**17/17 match**, using each case's known-correct hand-traced boolean
vector (not the raw, sometimes-imperfect real-model-extracted values from
`coverage_question_model_extraction_test.md`). Two notes worth surfacing,
not burying:

- **case_08 and Case B both land in flagged AMBIGUOUS category (a)/(b)
  territory** (`ref=0, exist=0`, no escalate signal) - the table's default
  (`request_more_info`) happens to match their golden labels, but this
  confirms these two real cases sit exactly on the design gap flagged
  above, not just in the abstract.
- **Case G**, using its *correct* hand-traced vector (`liab=False`),
  matches cleanly. The Round 2 regression documented in
  `coverage_question_model_extraction_test.md` was a real-model
  *extraction* error (the broadened liability field reading a hypothetical
  "if my tree fell" as live exposure) - not a flaw in the decision logic
  itself. This table's ambiguous-category-(a) flag formalizes exactly that
  risk in the abstract, which is why it was flagged as a real design gap
  rather than dismissed as a one-off.

## Step 5: the decision function, derived from the table

```python
def score_coverage_question_from_table(
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

Verified programmatically (`coverage_question_full_table.py`) to reproduce
the table's `action` column exactly on all 48 non-N/A rows, and to match
all 17 known cases (table above).

## Relationship to the previous (tree-derived) function

Worth stating plainly rather than treating this as a from-scratch
replacement: **this function is logically equivalent to the Round 5/6
sklearn-tree-plus-override combination** from
`coverage_question_manual_trace.md`, checked by hand across every reachable
combination of `(ref, pol, exist)` with the escalate-triggering fields held
false. The Round 6 override (force `exist=False` whenever `ref=True`,
applied as a separate pre-processing step before calling the tree) turns
out to be **exactly what step 4 of this function does structurally**, by
checking `ref` before ever consulting `exist` - the override becomes
redundant once derived this way, not because it was wrong, but because a
cleaner branch order makes it unnecessary as a bolt-on.

This convergence is a genuinely reassuring result, not a wasted exercise:
a tree fit on 9 hand-picked points and a function derived from reasoning
about all 64 combinations landed on the *same* decision logic. That's
real evidence the underlying structure is sound - but it's evidence about
the **CLEAN and NA rows**, not about the 10 **AMBIGUOUS** rows, which
neither the tree (never saw them) nor this table (flagged, didn't resolve
them cleanly) can claim to have settled.

## Caveats, stated plainly rather than treated as resolved

1. **10 of 64 rows (15.6%) are flagged ambiguous, not resolved.** Every one
   defaults to the safer of two plausible actions (`escalate_human` for
   liability-shaped ambiguity, `request_more_info` for the vague-question
   gap), which is a defensible engineering choice, but it is a choice, not
   a derivation. A future case landing in one of these 10 combinations is
   exactly as likely to be mishandled as case_08 or Case G were.
2. **This is still reasoning from definitions, not from real model
   extraction of all 64 combinations.** Only 17 of the 64 combinations
   have ever been checked against what Claude actually extracts for a real
   email; the other 47 (including all 10 ambiguous ones and most of the 38
   clean ones) are untested against real model behavior.
3. **The two flagged ambiguous categories are exactly where the two real
   regressions in `coverage_question_model_extraction_test.md` (case_08's
   original miss, and the Case G/Case B fallout from broadening
   `has_liability_or_dispute_signal`) actually occurred** - not a
   coincidence. The abstract exercise and the empirical testing are
   converging on the same weak points, which is a good sign the right
   things are being flagged, not a claim that they're fixed.
4. **Still no classifier.py changes. Still not treating this as final.**

---

## Round 2: resolving the 10 ambiguous rows with definitive reasoning

### Correction to the task premise, flagged rather than silently worked around

The request for this round stated "case_08 currently falls in [Category
A]." **Checked directly against this document's own cross-check table
(above): it doesn't.** case_08's hand-traced vector is `(ref=0, pol=1,
liab=0, uw=0, exist=0, cause=0)` - `liab=0`, not `1`, which fails Category
A's defining condition (`liab=True, ref=False`) outright. case_08 is
actually in **Category B** (`ref=0, exist=0, liab=0, uw=0` - "no field
fires at all"), alongside Case B (the fresh-holdout case). This document's
own prior summary used imprecise "(a)/(b)" shorthand when describing
case_08, which is the likely source of the mix-up. **No currently-known
case (of the 17) tests Category A at all** - every case with `liab=True`
also has `ref=True` (case_32, Case F). Category A's resolution below is
therefore reasoned entirely from first principles, with no real case to
validate or refute it against - stated plainly, not glossed over.

### Category A: does escalation require an actual incident?

**Question:** should `has_liability_or_dispute_signal=True` alone trigger
`escalate_human`, or should escalation require `references_specific_incident=True`
too (i.e., liability language about something that hasn't actually
happened yet doesn't count)?

**What a real Category A email looks like**, since none of the 17 cases
supply an example: something like "My dog has been getting territorial
near the fence gate lately - if he ever bit someone, would that be
covered?" or "If a delivery driver ever slipped on our front steps in
winter, are we covered?" - a *preventive*, not-yet-happened liability
worry, as opposed to case_32/Case F's already-occurred injuries.

**Reasoning:**
- `auto_reply` is ruled out regardless of how this question resolves - the
  general auto_reply guardrail ("must never make or imply a coverage or
  liability determination") applies exactly as much to a hypothetical
  liability question as a real one. The actual choice is between
  `escalate_human` and `request_more_info`.
- Unlike case_08 (hypothetical, but about a routine, low-stakes
  reimbursement question), a liability question - even framed
  preventively - describes a scenario where a third party's injury or
  property damage is the subject. The downside of an automated system
  getting this wrong (or even just deferring without flagging it as
  worth a person's attention) is asymmetric: liability exposure can carry
  real dollar and legal consequences that a missed rental-car
  reimbursement simply doesn't.
- A preventive liability question is also exactly the kind of signal a
  real agency has a business reason to want a human to see promptly - it
  can inform underwriting (an aggressive dog, a hazardous walkway) or
  prompt a proactive conversation about additional coverage (umbrella
  liability), not just react to a claim. That's a materially different
  value case than "gather a policy number and move on."
- Requiring `references_specific_incident=True` before escalating would
  mean the system silently treats a customer's own stated liability worry
  as routine informational request_more_info territory, which
  under-weights exactly the kind of question this project's own
  established safety-first principle (see `safety_instruction`: "this
  matters more than getting category or urgency exactly right") says
  should be over-, not under-, escalated.

**Resolved: Category A → `escalate_human`, unconditionally on `liab=True`.
`references_specific_incident` is not a requirement for escalation on
liability grounds - already-occurred and merely-anticipated liability
exposure are treated the same.** This is the same action the earlier
default already produced; what changes is that it's now a reasoned,
definitive answer instead of a "safer default" placeholder - and, per the
correction above, it has never actually been checked against a real case,
which is the honest caveat to carry forward rather than treat this as
proven.

### Category B: default, or a 7th field?

**Question:** does the vague/unanchored "no field fires" case need a 7th
boolean to distinguish sub-cases, or is a flat `request_more_info` default
correct?

**Both real cases in this category resolve identically and correctly under
the flat default:**
- case_08 (hypothetical rental-car eligibility, tied to a real personal
  circumstance - "if my car is in the shop") → `request_more_info` ✓
- Case B (hypothetical POD-storage coverage, tied to a real personal
  circumstance - a POD actually sitting in the driveway right now) →
  `request_more_info` ✓

**Considered, and explicitly rejected, one theoretical sub-distinction:** a
genuinely generic, no-personal-anchor educational question ("how does
homeowners insurance typically handle water damage, just curious") is
conceptually different from case_08/Case B (both are hypothetical
questions anchored to a real, current, personal situation) - a purely
educational question might arguably be safe for a general `auto_reply`
rather than `request_more_info`, since there's no personal scenario to get
wrong. This is a plausible distinction, but:
1. **No real case tests it.** Both known Category B members are the
   "anchored to a real personal situation" kind, and both are correctly
   handled by the flat default.
2. Splitting this out would mean adding a field (and doubling the
   completeness space, see below) to handle a case that has not been
   shown to exist in practice - the exact premature-abstraction pattern
   this project has explicitly avoided elsewhere (see PROJECT.md's
   Conventions: no half-finished implementations, no designing for
   hypothetical future requirements over demonstrated need).
3. If a real case surfaces later that's genuinely this generic and gets
   mishandled by `request_more_info`, that's the point at which a 7th
   field (or a redefinition of `asks_feature_existence_only` to also cover
   generic educational questions, not just named-feature lookups) should
   be considered - with real evidence driving the design, not speculation.

**Resolved: Category B → `request_more_info`, flat default, no 7th field
added.** Noted as an open watch-item (generic educational questions with
no personal anchor and no named feature) for a future round if real
evidence surfaces, not built preemptively.

### Step 3: updated table status for the 10 previously-ambiguous rows

All 10 rows keep the **same action** they defaulted to before (`escalate_human`
for the 8 Category A rows, `request_more_info` for the 2 Category B rows) -
what changes is the status, from `AMBIGUOUS` (resolved by a stated-safer
default) to `CLEAN` (resolved by definitive first-principles reasoning,
recorded above). Table rows 9, 11, 13, 15, 25, 27, 29, 31 (Category A) and
rows 1, 17 (Category B), referencing the numbering in the Step 4 table
above, are updated accordingly:

| # | ref | pol | liab | uw | exist | cause | status (was) | status (now) | action |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | AMBIGUOUS | **RESOLVED** | request_more_info |
| 9 | 0 | 0 | 1 | 0 | 0 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 11 | 0 | 0 | 1 | 0 | 1 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 13 | 0 | 0 | 1 | 1 | 0 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 15 | 0 | 0 | 1 | 1 | 1 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 17 | 0 | 1 | 0 | 0 | 0 | 0 | AMBIGUOUS | **RESOLVED** | request_more_info |
| 25 | 0 | 1 | 1 | 0 | 0 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 27 | 0 | 1 | 1 | 0 | 1 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 29 | 0 | 1 | 1 | 1 | 0 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |
| 31 | 0 | 1 | 1 | 1 | 1 | 0 | AMBIGUOUS | **RESOLVED** | escalate_human |

**Updated totals: 16 NA, 0 AMBIGUOUS, 48 CLEAN/RESOLVED.** Every reachable
combination of the 6 fields now has a definitive, reasoned answer. The
decision function in Step 5 above is unchanged (its logic already produced
these actions as defaults; no code change was needed, only the reasoning
behind two branches moved from "safer placeholder" to "derived").

### Step 4: re-verification of all 17 known cases

Re-ran the verification script with the finalized (non-default) reasoning
applied - since no action values changed, this is confirmatory, not a new
result, but it was actually executed, not assumed:

```
case_08  (0,1,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
case_09  (1,1,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
case_10  (1,0,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
case_20  (0,0,0,0,1,0) -> request_more_info  expected=request_more_info  MATCH
case_31  (1,1,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
case_32  (1,1,1,0,0,0) -> escalate_human     expected=escalate_human     MATCH
case_33  (0,1,0,1,1,0) -> escalate_human     expected=escalate_human     MATCH
case_34  (1,1,0,0,0,1) -> escalate_human     expected=escalate_human     MATCH
case_35  (0,1,0,0,1,0) -> auto_reply         expected=auto_reply         MATCH
Case A   (0,1,0,0,1,0) -> auto_reply         expected=auto_reply         MATCH
Case B   (0,1,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
Case C   (1,1,0,0,0,1) -> escalate_human     expected=escalate_human     MATCH
Case D   (1,1,0,0,0,0) -> request_more_info  expected=request_more_info  MATCH
Case E   (0,1,0,1,1,0) -> escalate_human     expected=escalate_human     MATCH
Case F   (1,1,1,0,0,0) -> escalate_human     expected=escalate_human     MATCH
Case G   (0,0,0,0,1,0) -> request_more_info  expected=request_more_info  MATCH
Case H   (1,1,0,0,1,0) -> request_more_info  expected=request_more_info  MATCH

ALL MATCH: True
```

**17/17.**

### Step 5: no 7th field added - completeness space stays at 64, not reopened

Category B was resolved with a flat default rather than a new field, so
**the completeness space remains `2^6 = 64`**, fully enumerated and now
fully resolved (16 NA + 48 CLEAN, 0 AMBIGUOUS). No re-run of a larger
`2^7 = 128` exercise is needed *for this round* - flagged explicitly per
instruction, in case this reads ambiguously: **this is a statement that no
7th field exists, not a claim that 128 combinations have been silently
checked.** If a 7th field is added in a future round (e.g., if the
generic-educational-question watch-item above turns out to be real), the
64-row table becomes incomplete the moment that happens and the same
exhaustive-enumeration exercise would need to be redone at 128 rows before
trusting it again - this document's completeness claim is scoped strictly
to the current 6 fields.

### Caveats, carried forward

1. **Category A's resolution is unvalidated against any real case** - it's
   principled reasoning, not evidence. The first real Category A case this
   design encounters (in manual tracing, synthetic testing, or real model
   extraction) is the actual test of whether "escalate hypothetical
   liability unconditionally" is correct or over-cautious.
2. **Category B's rejected 7th-field idea (generic educational questions)
   remains a real, if unconfirmed, watch-item** - not built, not
   dismissed, just not yet justified by evidence.
3. Everything else flagged in this document's earlier caveats (real-model
   extraction only tested on 17 of 64 combinations, `classifier.py`
   untouched, nothing here treated as final) still applies unchanged.
