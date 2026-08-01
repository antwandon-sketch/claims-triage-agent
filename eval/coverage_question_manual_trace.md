# coverage_question extract-then-decide: manual trace vs. golden dataset

Standalone scratch doc, not wired into the eval pipeline (`run_eval.py` does not
read this file). Produced 2026-07-31 to validate a proposed deterministic
scoring function against all 9 real `coverage_question` golden cases before any
`classifier.py` changes, per PROJECT.md's "Immediate next step."

## Function under test

```python
def score_coverage_question(
    references_specific_incident: bool,
    has_policy_or_claim_number: bool,
    has_liability_or_dispute_signal: bool,
    has_underwriting_or_nonstandard_use_signal: bool,
) -> str:
    if not has_policy_or_claim_number:
        return "request_more_info"
    if has_liability_or_dispute_signal:
        return "escalate_human"
    if has_underwriting_or_nonstandard_use_signal:
        return "escalate_human"
    if references_specific_incident:
        return "escalate_human"
    return "auto_reply"
```

## Result summary

**6 of 9 MATCH. 3 of 9 MISMATCH (case_08, case_09, case_31) — and all three
share the identical root cause**, not three separate problems: once
`has_policy_or_claim_number` is `True`, the function can only return
`auto_reply` or `escalate_human` — there is no path back to
`request_more_info`. But 3 of the 9 real golden cases (all `coverage_question`
questions with a policy number provided, no liability/underwriting signal, but
still not answerable without checking specific policy details) are labeled
`request_more_info`. The function's structure has no branch for "we have
enough identifying info, but the scenario-specific coverage question still
needs a human/adjuster to actually answer" — which is exactly what the
existing v7 auto_reply guardrail was written to require ("must never state
definitively that something is or isn't covered... even for scenarios that
seem simple or standard").

---

## case_08

**Paraphrase:** Customer asks whether their policy would cover a rental car
while their car is being repaired after an accident, framed as wanting to
know ahead of time, before they'd actually need it. Policy number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | **False** | The email is explicitly framed as anticipatory ("just want to know before I need it") rather than reporting an accident that has happened - conditional/hypothetical framing, not a specific triggering event being reported. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | False | No fault, dispute, denial, or contested-outcome language. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business or non-standard property/use language. |

**Function output:** `auto_reply`
**Golden label:** `request_more_info`
**Result: MISMATCH**

**Why they disagree:** With a policy number present and no other flag tripped,
the function falls through to `auto_reply`. But under `references_specific_incident=True`
(the other plausible reading - see ambiguity flag below), it would instead
fall to `escalate_human` via the last `if` - neither branch reaches
`request_more_info`, because that's structurally unreachable once
`has_policy_or_claim_number=True`.

**Ambiguity flag: YES.** `references_specific_incident` is genuinely
ambiguous here - "if my car is in the shop after an accident" can be read
either as a pure hypothetical (my reading, `False`) or as pointing to an
accident that has actually happened and is presently being dealt with
(`True`). Notably, **this ambiguity doesn't matter for the mismatch** - both
readings produce a wrong answer (`auto_reply` vs. `escalate_human`), neither
of which is `request_more_info`. This is a function-structure gap, not
(only) an extraction-judgment problem.

---

## case_09

**Paraphrase:** Customer noticed a small stain on their bedroom ceiling, isn't
sure it's even worth mentioning, and asks whether something like that would
be covered before deciding whether to do anything about it. Policy number
given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | **True** | An actual, currently-present stain exists and is being described - a real (if minor) instance of possible damage, not a purely hypothetical question. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | False | "Not sure if it's worth mentioning" is uncertainty about relevance, not a fault/liability dispute or contested outcome. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business or non-standard use signal. |

**Function output:** `escalate_human`
**Golden label:** `request_more_info`
**Result: MISMATCH**

**Why they disagree:** `references_specific_incident=True` routes straight to
`escalate_human` via the last `if` branch. The golden label reflects the
carve-out logic established in v7/v8/v9 (a customer simply not yet knowing
what caused something they just noticed is not, by itself, grounds to
escalate - gather basic details first). That carve-out has no representation
anywhere in this 4-field design; the function has no way to distinguish "a
real but minor, not-yet-investigated thing was noticed" from "a real,
significant, already-investigated incident."

**Ambiguity flag: YES.** `references_specific_incident` is borderline - a
faint, possibly-irrelevant ceiling stain is a much weaker "incident" than
case_31's chip or case_34's mold, but the field's definition ("a particular
loss, accident, damage, theft, injury") doesn't have a severity threshold. If
judged `False` instead, the function falls to `auto_reply` - still a
mismatch against `request_more_info`. Same underlying gap as case_08: no path
to `request_more_info` once a policy number is present.

---

## case_10

**Paraphrase:** Customer's ring went missing sometime in the past week; they
aren't sure if it was stolen or simply lost, and ask - before filing anything
- whether jewelry is covered under their homeowners policy and what the limit
is. No policy number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | True | A ring going missing is a specific, real, already-occurred event. |
| `has_policy_or_claim_number` | **False** | No policy number anywhere in the email. |
| `has_liability_or_dispute_signal` | True | "Not positive if it was stolen or I just lost it" is the field's own stated worked example of this signal. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business/non-standard-use language. |

**Function output:** `request_more_info` (short-circuited by the missing
policy number, before any other field is even consulted)
**Golden label:** `request_more_info`
**Result: MATCH**

**Ambiguity flag: no.** `has_policy_or_claim_number` is unambiguously `False`
- no number of any kind appears anywhere in the email. Clean match, and
notably the correct answer here didn't actually depend on resolving whether
"not positive if stolen or lost" counts as a liability/dispute signal, since
the missing-policy-number branch fires first and short-circuits the rest of
the function. (This is worth flagging on its own: this case appeared to
validate `has_liability_or_dispute_signal`'s definition, but the function's
branch order means that field was never actually exercised for this case.)

---

## case_20

**Paraphrase:** Customer is nervous because flooding is happening a few
streets away (not yet at their house) and asks whether their homeowners
policy covers flood damage or whether they'd need separate coverage. No
policy number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | False | Flooding is nearby but hasn't reached their property - anticipatory, not a loss that's happened to them. |
| `has_policy_or_claim_number` | **False** | No policy number given. |
| `has_liability_or_dispute_signal` | False | No fault/dispute language. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business/non-standard-use language. |

**Function output:** `request_more_info` (short-circuited by missing policy
number)
**Golden label:** `request_more_info`
**Result: MATCH**

**Ambiguity flag: no.** Missing-policy-number is clear-cut. Clean match.

---

## case_31

**Paraphrase:** Customer has a small chip in their windshield and asks
whether their policy covers a no-deductible repair, referencing that "some
places advertise" that. Policy number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | **True** | "I have a small chip in my windshield" is present-tense, concrete, real damage - not hypothetical, unlike case_08. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | False | No fault/dispute/denial language. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business/non-standard-use language. |

**Function output:** `escalate_human`
**Golden label:** `request_more_info`
**Result: MISMATCH**

**Why they disagree:** Same structural gap as case_08/case_09 - policy number
present, no liability or underwriting signal, but `references_specific_incident=True`
routes to `escalate_human` when the golden answer needs `request_more_info`
(acknowledge and gather/point to policy specifics, per the auto_reply
guardrail, without a human needing to get involved for something this
routine).

**Ambiguity flag: no** - unlike case_08 and case_09, `references_specific_incident`
is clearly and unambiguously `True` here (concrete, present-tense, unhedged
damage). This is the cleanest evidence that the mismatch is a genuine
function-logic gap, not an artifact of fuzzy boolean extraction: even the
least-ambiguous of the three mismatched cases still comes out wrong.

---

## case_32

**Paraphrase:** Customer's dog bit a neighbor's child in their yard
yesterday; nothing has been filed yet, but a doctor visit was mentioned, and
they ask whether this is covered under their homeowners policy. Policy
number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | True | A dog bite yesterday is a specific, real, already-occurred event. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | **True** | Injury to a third party with a doctor visit already involved is squarely a liability-exposure scenario - the clearest possible match to this field's intent. |
| `has_underwriting_or_nonstandard_use_signal` | False | Not a business/non-standard-use question. |

**Function output:** `escalate_human`
**Golden label:** `escalate_human`
**Result: MATCH**

**Ambiguity flag: no.** `has_liability_or_dispute_signal` is unambiguous
here - this is the clearest liability case in the dataset. Clean match.

---

## case_33

**Paraphrase:** Customer has been running a candle-selling business out of
their garage for a few months and asks whether their homeowners policy
covers that activity or whether they need something separate. Policy number
given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | False | No loss, accident, damage, theft, or injury - an ongoing activity/status question, not an incident. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | False | No fault/dispute/denial language. |
| `has_underwriting_or_nonstandard_use_signal` | **True** | Textbook match - a business activity conducted from the insured property, exactly what this field is defined to capture. |

**Function output:** `escalate_human`
**Golden label:** `escalate_human`
**Result: MATCH**

**Ambiguity flag: no.** This is the case the 4th field
(`has_underwriting_or_nonstandard_use_signal`) was specifically added to
handle - clean, unambiguous match. Confirms the 4-field design closes the gap
the original 3-field version had for exactly this case.

---

## case_34

**Paraphrase:** Customer found mold behind bathroom tile during a renovation
and isn't sure what caused it; asks whether that would be covered. Policy
number given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | True | Mold discovered during renovation is a real, specific, already-occurred issue. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | **True*** | See ambiguity flag - judged `True` for consistency with case_10's worked example, but this is a genuinely close call. |
| `has_underwriting_or_nonstandard_use_signal` | False | Not a business/non-standard-use scenario - it's property damage. |

**Function output:** `escalate_human` (reached via the liability branch under
the `True` reading; **also reached via the `references_specific_incident`
branch even under the alternate `False` reading** - see below)
**Golden label:** `escalate_human`
**Result: MATCH** (under either reading of the ambiguous field)

**Ambiguity flag: YES**, but does not change the outcome. "Not sure what
caused it" is structurally identical phrasing to case_10's "not positive if
it was stolen or I just lost it" (which the field definition explicitly
marks `True`) and to case_09's "not sure if it's worth mentioning" (which I
judged `False`). The field definition ("dispute over fault, liability, a
denial, or a contested coverage outcome") doesn't cleanly cover "cause of
damage is unknown" as a category distinct from an active fault/liability
dispute - this is the same ambiguity flagged for case_09, applied to a case
where it happens not to matter, because `references_specific_incident=True`
independently routes to the same correct answer via a different branch. This
won't always be true for future cases with an unclear cause but no
independent reason to escalate - worth resolving the definition either way
before this goes further, even though it's not a live mismatch today.

---

## case_35

**Paraphrase:** Customer asks a quick, generic question about whether their
auto policy includes roadside assistance or towing coverage. Policy number
given.

| Field | Value | Rationale |
|---|---|---|
| `references_specific_incident` | False | No loss, accident, damage, theft, or injury - a pure feature-existence lookup ("does my policy come with X"), the clearest generic case in the dataset. |
| `has_policy_or_claim_number` | **True** | Policy number given explicitly. |
| `has_liability_or_dispute_signal` | False | No fault/dispute language. |
| `has_underwriting_or_nonstandard_use_signal` | False | No business/non-standard-use language. |

**Function output:** `auto_reply`
**Golden label:** `auto_reply`
**Result: MATCH**

**Ambiguity flag: no.** Every field is unambiguous. This is the clean
`auto_reply` reference case the whole design is meant to isolate.

---

## Cross-case pattern (not a per-case note, worth surfacing on its own)

`has_liability_or_dispute_signal`'s given definition folds together two
things that behaved differently across these 9 cases:

1. **Active liability/fault exposure toward a third party** (case_32 - dog
   bite, doctor visit) - unambiguous, clearly `True`.
2. **Uncertain/unknown cause of a loss to the policyholder's own property**
   (case_09's stain, case_10's missing ring, case_34's mold) - all phrased
   almost identically ("not sure...", "not positive if... or...", "not sure
   what caused it"), but the *correct* golden answer differs: case_09 wants
   `request_more_info`, case_10 wants `request_more_info` (via the missing-
   policy-number path, coincidentally sidestepping this field entirely), and
   case_34 wants `escalate_human`. Treating all "uncertain cause" phrasing as
   one boolean can't produce three different correct answers from
   structurally similar input - this needs either a distinguishing signal in
   the field itself (e.g., "already actively investigated and still
   unresolved" vs. "just noticed, not yet looked into") or a fifth field
   dedicated to unclear-cause-of-loss, separate from third-party liability
   exposure.

---

## Round 2: fresh boolean extraction + collision check (no decision function yet)

Independent re-pass, per instruction: raw case text re-read directly from
`golden_dataset.json` (not the paraphrases above), 4 booleans extracted fresh
for all 9 cases, **no decision function applied or proposed at this stage** -
table and collision check only.

**Note on `has_liability_or_dispute_signal`:** this round's field definition
is narrower than the one used above - "dispute over fault, liability, a
denial, or a contested coverage outcome (fault between two parties, 'they
said it's not covered,' an active disagreement)." It no longer anchors to
case_10's phrase as a worked example. Read strictly and independently, "not
positive if it was stolen or I just lost it" (case_10) and "not sure what
caused it" (case_34) are uncertainty about the facts of a loss, not an active
two-party dispute, denial, or contested outcome - so both are judged `False`
this round, a change from the `True` judgment given to them above. This
recalibration is what surfaces the collisions below; it was not visible under
the looser reading.

### Table

| case_id | `references_specific_incident` | `has_policy_or_claim_number` | `has_liability_or_dispute_signal` | `has_underwriting_or_nonstandard_use_signal` | golden `suggested_action` |
|---|---|---|---|---|---|
| case_08 | False - hypothetical/anticipatory framing ("just want to know before I need it"), not reporting an event that happened | True - "Policy AU-24417" | False - no fault/dispute/denial language | False - no business/non-standard-use language | request_more_info |
| case_09 | True - an actual, currently-present stain is being described, even if minor | True - "Policy HO-61830" | False - "not sure if it's worth mentioning" is uncertainty about relevance, not a fault/dispute/denial | False - no business/non-standard-use language | request_more_info |
| case_10 | True - a ring going missing is a specific, real, already-occurred event | False - no policy or claim number anywhere in the email | False - "not positive if stolen or lost" is uncertainty about the facts of the loss, not a two-party dispute, denial, or contested outcome | False - no business/non-standard-use language | request_more_info |
| case_20 | False - flooding is nearby but hasn't reached their property; anticipatory, not a loss that's happened to them | False - no policy number given | False - no fault/dispute language | False - no business/non-standard-use language | request_more_info |
| case_31 | True - "I have a small chip in my windshield" is present-tense, concrete, real damage | True - "policy AU-40118" | False - no fault/dispute/denial language | False - no business/non-standard-use language | request_more_info |
| case_32 | True - a dog bite yesterday is a specific, real, already-occurred event | True - "HO-90213" | True - injury to a third party with a doctor visit already mentioned is squarely a liability-exposure scenario | False - not a business/non-standard-use question | escalate_human |
| case_33 | False - no loss/accident/damage/theft/injury; an ongoing activity/status question, not an incident | True - "HO-33987" | False - no fault/dispute/denial language | True - a business activity conducted from the insured property is exactly what this field is defined to capture | escalate_human |
| case_34 | True - mold discovered during renovation is a real, specific, already-occurred issue | True - "HO-51204" | False - "not sure what caused it" is uncertainty about the facts, not a two-party dispute, denial, or contested outcome | False - it's property damage, not a business/non-standard-use scenario | escalate_human |
| case_35 | False - a pure feature-existence lookup ("does my policy come with X"), no loss/accident/damage/theft/injury | True - "AU-77120" | False - no fault/dispute language | False - no business/non-standard-use language | auto_reply |

### Collision check

Grouped all 9 cases by their exact 4-boolean tuple. **Two collisions found** -
in both cases, cases with an *identical* boolean signature need *different*
golden actions, which means these 4 fields alone cannot deterministically
separate them. No decision function can resolve a case where two rows have
the same inputs and different correct outputs - the fields themselves are
underspecified for these pairs/groups.

**Collision 1: `(references_specific_incident=False, has_policy_or_claim_number=True, has_liability_or_dispute_signal=False, has_underwriting_or_nonstandard_use_signal=False)`**
- case_08 → `request_more_info`
- case_35 → `auto_reply`

Both cases are judged as *not* referencing a specific incident, both have a
policy number, and neither has a liability or underwriting signal - yet
case_08 needs a human-reviewable answer and case_35 is safe for a fully
automated one. The actual difference between them (case_08 is a
scenario-specific "would MY situation be covered" question that happens to be
phrased hypothetically; case_35 is a generic "does this add-on exist"
lookup) isn't captured by any of the 4 fields once `references_specific_incident`
comes out `False` for both. Either case_08's `references_specific_incident`
judgment is wrong (arguably it should be `True` despite the hypothetical
framing, since it's still anchored to *their* rental-car scenario, not a
generic feature question), or a 5th field is needed to distinguish
"scenario-specific hypothetical" from "generic feature lookup."

**Collision 2: `(references_specific_incident=True, has_policy_or_claim_number=True, has_liability_or_dispute_signal=False, has_underwriting_or_nonstandard_use_signal=False)`**
- case_09 → `request_more_info`
- case_31 → `request_more_info`
- case_34 → `escalate_human`

case_09 and case_31 agree with each other on this tuple (both correctly want
`request_more_info`), but case_34 shares the exact same 4-boolean signature
and needs `escalate_human` instead. This is the same underlying gap flagged
in the Round 1 "cross-case pattern" note, now expressed as a hard collision
rather than a soft ambiguity: nothing in these 4 fields distinguishes "real
damage/incident with an unclear cause that's fine to just gather more detail
on" (case_09's minor ceiling stain, case_31's windshield chip - though note
case_31 doesn't even have an unclear-cause element, it's just a routine
repair question) from "real damage with an unclear cause that needs an
adjuster" (case_34's mold, found during renovation, cause still unresolved).
A field capturing something like "cause investigated and still unresolved"
vs. "just noticed, no investigation" - the same carve-out concept from the
v7/v8/v9 prompt-text era - looks necessary to break this tie.

**Not proposing a fix or decision function per instruction - collision
reporting only.**

---

## Round 3: resolving the two collisions - what's actually different, and two new fields

Read the raw email text of case_08, case_09, case_31, case_34, and case_35
directly from `golden_dataset.json` again for this pass. For each collision
group, identified the specific distinction a human adjuster would recognize
that the current 4 booleans don't capture, and proposed one new boolean field
per collision. **No decision function written. Full 9-case table not
re-run yet** - only confirming the new fields separate their target pairs, as
instructed.

### Collision 1 (case_08 vs. case_35): existence-lookup vs. eligibility-determination

case_35 ("does my auto policy come with roadside assistance or towing
coverage") is a pure yes/no fact about whether an add-on exists on the
policy - answerable directly from the declarations page, no judgment
involved. case_08 ("does my policy cover a rental car while it's being
repaired" after "an accident") looks similar on the surface, but rental car
reimbursement is a *conditional* coverage - whether it applies typically
depends on the underlying loss being a covered peril, whether the customer
carries comprehensive/collision, and per-day/total limits. Fully answering it
requires evaluating whether *this* scenario would qualify, not just
confirming the line-item exists on the policy. That's the real distinction:
"does X exist on my policy" (case_35) vs. "would my situation actually
trigger X" (case_08) - a difference a human adjuster recognizes immediately
but that "no incident referenced" alone doesn't capture, since case_08 was
judged `references_specific_incident=False` for the same reason (hypothetical
framing) that made it look identical to case_35.

**Proposed field: `asks_feature_existence_only`**

*Definition:* True if the question can be answered by confirming whether a
specific coverage or add-on is present on the policy at all (a yes/no lookup
against the declarations page), with no need to evaluate whether a
particular situation would qualify or trigger it. False if answering
requires judging whether a specific (even hypothetical/future) scenario
would meet the coverage's conditions or limits.

| Case | Value | Why |
|---|---|---|
| case_08 | **False** | Answering requires evaluating whether "car in shop after an accident" would qualify under rental-reimbursement conditions (covered peril? comp/collision carried? limits?) - not just confirming the feature exists. |
| case_35 | **True** | Purely "does this add-on exist" - no scenario to evaluate, no conditions to check. |

Confirmed: this field separates case_08 (`False`) from case_35 (`True`).

### Collision 2 (case_09/case_31 vs. case_34): cause investigated-and-unresolved vs. simply not yet looked into

case_31's cause isn't even in question - a windshield chip is unambiguous,
undisputed damage; the missing piece is policy-specific glass-coverage
detail, nothing about the cause. case_09's cause is unknown, but the
customer explicitly hasn't investigated it - "not wet or growing that I can
tell" is a passive glance, nothing examined. case_34 is different in kind:
the mold was found *during a renovation* - the wall/tile was already opened
and actively examined as part of that work - and even with that inspection
already done, the cause still can't be determined. This is the "disputed or
unresolved even after investigation" pattern the v7/v8/v9 prompt-text era
carve-out existed to separate from "just noticed, hasn't looked into it yet"
- and it's exactly what's missing from the current 4 fields, which treat all
three cases' "not sure what caused/happened" language identically.

**Proposed field: `cause_investigated_and_unresolved`**

*Definition:* True if the email indicates the cause of the damage/loss has
already been actively examined (e.g., discovered or inspected during a
renovation, repair, or investigation) and still cannot be determined. False
if the cause is clear/undisputed, or unknown only because the customer
hasn't investigated further yet (a passive, just-noticed observation).

| Case | Value | Why |
|---|---|---|
| case_09 | **False** | Cause unknown, but explicitly not yet investigated ("not wet or growing that I can tell"). |
| case_31 | **False** | Cause isn't in question at all - the damage itself (a chip) is unambiguous. |
| case_34 | **True** | Cause unknown *despite* active investigation - discovered during a renovation, i.e., already examined. |

Confirmed: this field separates case_34 (`True`) from case_09/case_31 (both
`False`).

### One field or two?

**Two separate fields are required - cross-tested and confirmed neither
field resolves the other collision:**

- `asks_feature_existence_only` on case_09/case_31/case_34: all three are
  `False` (none are feature-existence lookups - all describe real, present
  damage and ask whether it's covered). Does not discriminate within
  collision 2 at all.
- `cause_investigated_and_unresolved` on case_08/case_35: both `False`
  (neither involves an unclear cause of damage in the first place - case_08
  is about scenario eligibility, case_35 is a pure feature lookup). Does not
  discriminate within collision 1 at all.

The two collisions are genuinely different problems - one is about whether a
question needs eligibility judgment vs. a simple fact lookup, the other is
about whether an unclear cause has already been investigated. Both fields
are needed; neither substitutes for the other.

**Still not writing a decision function, and not re-running the full 9-case
table with these 2 new fields added - that's the next step, not this one.**

---

## Round 4: full 9-case re-trace with all 6 fields - collision check

Re-extracted `asks_feature_existence_only` and `cause_investigated_and_unresolved`
for all 9 cases (not just the 5 involved in the two collisions), combined with
the original 4 fields, and re-ran the collision check across the full set.

### Full table

| case_id | ref_incident | policy/claim # | liability/dispute | underwriting/nonstandard | feature_existence_only | cause_investigated_unresolved | golden action |
|---|---|---|---|---|---|---|---|
| case_08 | False | True | False | False | **False** | False | request_more_info |
| case_09 | True | True | False | False | False | False | request_more_info |
| case_10 | True | False | False | False | False (borderline - see note) | False (borderline - see note) | request_more_info |
| case_20 | False | False | False | False | **True** | False | request_more_info |
| case_31 | True | True | False | False | False | False | request_more_info |
| case_32 | True | True | True | False | False | False | escalate_human |
| case_33 | False | True | False | True | **True** | False | escalate_human |
| case_34 | True | True | False | False | False | **True** | escalate_human |
| case_35 | False | True | False | False | **True** | False | auto_reply |

**Two borderline calls on case_10, flagged honestly rather than smoothed
over:**
- `asks_feature_existence_only`: the phrasing ("is jewelry even covered...
  and is there a limit?") reads similarly to case_35's/case_20's
  existence-style questions, but standard homeowners jewelry coverage
  typically depends on cause (theft is usually covered, simple loss/
  "mysterious disappearance" is often excluded or needs a separate rider) -
  so whether coverage actually applies here substantively depends on
  resolving "stolen vs. lost," the same eligibility-dependent shape as
  case_08. Judged `False` on substance over surface phrasing, but this is a
  closer call than case_08 or case_35.
- `cause_investigated_and_unresolved`: "not positive if it was stolen or I
  just lost it somewhere" is uncertainty about what happened, but unlike
  case_34's "found during a renovation," nothing in the email indicates an
  active investigation already took place - it reads as passive uncertainty,
  closer to case_09's shape. Judged `False`, but the line between "actively
  investigated" and "thought about it and still doesn't know" is not as
  sharp for a missing/possibly-stolen item as it is for structural damage
  found mid-renovation.

Neither borderline call changes case_10's outcome either way - it's already
uniquely resolved by `has_policy_or_claim_number=False` regardless of how
the other fields land, the same as in every prior round.

### Collision check

Grouped all 9 cases by the full 6-boolean tuple.

**No collisions found.** case_09 and case_31 still share an identical
6-field tuple `(True, True, False, False, False, False)`, but now correctly
agree on the same golden label (`request_more_info` for both) - two cases
sharing a signature and agreeing is not a collision, only two cases sharing
a signature and *disagreeing* is. Both of Round 3's collisions are resolved:

- case_08 `(False, True, False, False, False, False)` → request_more_info
  vs. case_35 `(False, True, False, False, True, False)` → auto_reply -
  now distinguished by `asks_feature_existence_only`.
- case_34 `(True, True, False, False, False, True)` → escalate_human vs.
  case_09/case_31 `(True, True, False, False, False, False)` →
  request_more_info - now distinguished by `cause_investigated_and_unresolved`.

All 9 real coverage_question golden cases are now uniquely and correctly
separated by the 6-field vector. This is the first point in tonight's
investigation (v7 reword, v8 revert, v9 rewrite, and now this extract-then-
decide design) where the full golden set resolves cleanly with zero
unresolved conflicts - on paper. **Still not a decision function, and still
not tested against the real model's actual extraction judgment** - every
prior round this session (v8, v9) that looked clean on paper failed once
run for real. That gap - manual trace vs. real API behavior - is the next
thing to close, not proof this is done.

---

## Round 5: train/holdout check + decision function derived from data (not hand-written)

### Train/holdout check - flagged explicitly, per instruction

Checked `eval/golden_dataset.json`'s `split` field for all 9 coverage_question
cases directly:

| case_id | split |
|---|---|
| case_08 | train |
| case_09 | train |
| case_10 | train |
| case_20 | train |
| case_31 | **holdout** |
| case_32 | **holdout** |
| case_33 | **holdout** |
| case_34 | **holdout** |
| case_35 | **holdout** |

**5 of the 9 cases used in this whole investigation are holdout, not
train: case_31, case_32, case_33, case_34, case_35.** Both collisions
resolved in Round 3 were built directly from holdout-case wording -
`asks_feature_existence_only` was reverse-engineered specifically to
separate case_08 (train) from case_35 (holdout), using case_35's exact
phrasing; `cause_investigated_and_unresolved` was reverse-engineered
specifically from case_34's (holdout) exact wording ("found during a
renovation"). Per this project's own train/holdout discipline
(established across the v2-v9 prompt-text era: "the moment a specific
holdout case's content drives a change, it's effectively become a train
case"), that discipline has been broken in this design exercise -
case_31/33/34/35's specific wording has directly shaped the field
definitions and, by extension, the decision function below. Any accuracy
this design eventually shows on the current holdout set can't be treated
as a clean, unbiased measurement - the holdout set has been looked at and
designed against. This doesn't mean the design work is wrong, but it does
mean a genuinely fair read on generalization will require either new
holdout cases these fields were never looked at, or treating this design's
current holdout performance as informative-but-optimistic, not a real
holdout number.

### Decision function derived from a fitted decision tree, not hand-written

Wrote a scratch script (`coverage_question_tree_fit.py`, session
scratchpad, not part of the tracked repo - same convention as
`case32_ablation.py`) that:
1. Fits `sklearn.tree.DecisionTreeClassifier` on the 6 boolean fields (the
   original 4 + `asks_feature_existence_only` +
   `cause_investigated_and_unresolved`) against the 3-class golden label,
   for all 9 coverage_question cases.
2. Exports the fitted tree as `export_text` rules.
3. Mechanically walks the fitted tree's actual node structure to generate
   a Python function - no hand-written if/else branches anywhere in this
   step.
4. Verifies the generated function against both the tree's own
   predictions and the golden labels directly, as two independent checks.

**Exported tree (`export_text`):**

```
|--- has_liability_or_dispute_signal <= 0.50
|   |--- cause_investigated_and_unresolved <= 0.50
|   |   |--- has_underwriting_or_nonstandard_use_signal <= 0.50
|   |   |   |--- asks_feature_existence_only <= 0.50
|   |   |   |   |--- class: request_more_info
|   |   |   |--- asks_feature_existence_only >  0.50
|   |   |   |   |--- has_policy_or_claim_number <= 0.50
|   |   |   |   |   |--- class: request_more_info
|   |   |   |   |--- has_policy_or_claim_number >  0.50
|   |   |   |   |   |--- class: auto_reply
|   |   |--- has_underwriting_or_nonstandard_use_signal >  0.50
|   |   |   |--- class: escalate_human
|   |--- cause_investigated_and_unresolved >  0.50
|   |   |--- class: escalate_human
|--- has_liability_or_dispute_signal >  0.50
|   |--- class: escalate_human
```

**Plain English:**
1. Liability/dispute signal present → `escalate_human`
2. Else, cause investigated and still unresolved → `escalate_human`
3. Else, underwriting/non-standard-use signal present → `escalate_human`
4. Else, if it's *not* a pure feature-existence question → `request_more_info`
5. Else (it *is* a pure feature-existence question): no policy/claim
   number → `request_more_info`; has a policy/claim number → `auto_reply`

**Generated Python function** (mechanically transcribed from the fitted
tree, not hand-written):

```python
def score_coverage_question(
    references_specific_incident: bool,
    has_policy_or_claim_number: bool,
    has_liability_or_dispute_signal: bool,
    has_underwriting_or_nonstandard_use_signal: bool,
    asks_feature_existence_only: bool,
    cause_investigated_and_unresolved: bool,
) -> str:
    if not has_liability_or_dispute_signal:
        if not cause_investigated_and_unresolved:
            if not has_underwriting_or_nonstandard_use_signal:
                if not asks_feature_existence_only:
                    return "request_more_info"
                else:
                    if not has_policy_or_claim_number:
                        return "request_more_info"
                    else:
                        return "auto_reply"
            else:
                return "escalate_human"
        else:
            return "escalate_human"
    else:
        return "escalate_human"
```

**Verification: PASSED.** Generated function matches the tree's own
predictions on all 9 cases, and matches all 9 golden labels directly -
two independent checks, both green. Expected, since Round 4 already
confirmed zero collisions across this 6-field vector, meaning some
separating tree was guaranteed to exist; this only confirms sklearn found
one and that the mechanical transcription didn't introduce an error.

**Notable artifact: `references_specific_incident` does not appear
anywhere in the fitted tree.** With only 9 data points, the tree found a
shorter path to perfect separation that doesn't need this field at all -
the other 5 fields alone fully separate all 9 cases. This is a small-
sample artifact, not evidence the field is actually redundant in general;
a 10th case could easily require it. Flagging so it isn't mistaken for a
validated finding.

### Caveats, stated plainly rather than treated as resolved

1. **This tree is fit on 9 examples and is only guaranteed correct on
   those 9.** A decision tree with enough splits can always achieve 100%
   training accuracy on a small dataset with no label noise (which is
   exactly what Round 4 confirmed: zero collisions means zero label
   noise for these 6 features) - that is a statement about this specific
   9-point dataset, not a statement about how well the tree generalizes
   to a coverage_question email it hasn't seen.
2. **Not yet tested against real model-extracted booleans.** Every
   boolean value used to fit this tree was manually traced by hand
   against raw email text - none of them came from actually asking the
   model to extract `references_specific_incident`,
   `has_policy_or_claim_number`, etc. from these emails. Every prior
   design this session that looked clean on paper (v8's ablation, v9's
   manual trace) failed once tested against real model output. That is
   the next gap to close, not something this round proves is fine.
3. **The train/holdout violation above** means even a future clean
   result on this specific 9-case set would be an optimistic, not a fair,
   read on generalization, since 5 of the 9 cases' wording directly
   shaped the fields being tested.

**Still no classifier.py changes. Still not treating this as final.**

---

## Round 6: override rule to fix Case H, verified against both sets (not retrained)

The fresh independent holdout test (`eval/coverage_question_fresh_holdout.md`)
scored 7/8, with Case H's mismatch traced to `asks_feature_existence_only`
being genuinely ambiguous when a real, already-occurred incident is
described using generic "does my policy typically cover X" phrasing rather
than "would MY situation qualify" phrasing.

**Proposed fix:** an override rule sitting in front of the existing
tree-derived function (the tree itself is untouched, not retrained or
refit): whenever `references_specific_incident` is `True`, force
`asks_feature_existence_only` to `False` before calling the function.
Reasoning: if a real incident already happened, answering can never be a
pure feature-existence lookup, regardless of how generically the question
happens to be phrased - the incident itself means a specific situation
needs evaluating, not just a policy-terms lookup.

```python
def score_coverage_question_with_override(
    references_specific_incident: bool,
    has_policy_or_claim_number: bool,
    has_liability_or_dispute_signal: bool,
    has_underwriting_or_nonstandard_use_signal: bool,
    asks_feature_existence_only: bool,
    cause_investigated_and_unresolved: bool,
) -> str:
    if references_specific_incident:
        asks_feature_existence_only = False  # override applied here
    return score_coverage_question(  # the existing tree-derived function, unmodified
        references_specific_incident,
        has_policy_or_claim_number,
        has_liability_or_dispute_signal,
        has_underwriting_or_nonstandard_use_signal,
        asks_feature_existence_only,
        cause_investigated_and_unresolved,
    )
```

### Verified against all 9 golden cases - not assumed

Ran a scratch script (`coverage_question_override_check.py`, session
scratchpad) that computes both the pre-override and post-override output
for every case and reports whether anything changed, rather than trusting
the "none currently have both fields True" claim on inspection alone.

| case_id | expected | before override | after override | changed? |
|---|---|---|---|---|
| case_08 | request_more_info | request_more_info | request_more_info | no |
| case_09 | request_more_info | request_more_info | request_more_info | no |
| case_10 | request_more_info | request_more_info | request_more_info | no |
| case_20 | request_more_info | request_more_info | request_more_info | no |
| case_31 | request_more_info | request_more_info | request_more_info | no |
| case_32 | escalate_human | escalate_human | escalate_human | no |
| case_33 | escalate_human | escalate_human | escalate_human | no |
| case_34 | escalate_human | escalate_human | escalate_human | no |
| case_35 | auto_reply | auto_reply | auto_reply | no |

**9/9 match, both before and after. 0 cases changed, 0 previously-matching
cases broke.** Confirmed programmatically (not assumed): none of the 9
golden cases have `references_specific_incident=True` and
`asks_feature_existence_only=True` simultaneously, so the override is a
true no-op on this set - it only ever fires on `Case H` from the fresh
holdout set.

### Verified against all 8 fresh holdout cases

| case | expected | before override | after override | changed? |
|---|---|---|---|---|
| Case A | auto_reply | auto_reply | auto_reply | no |
| Case B | request_more_info | request_more_info | request_more_info | no |
| Case C | escalate_human | escalate_human | escalate_human | no |
| Case D | request_more_info | request_more_info | request_more_info | no |
| Case E | escalate_human | escalate_human | escalate_human | no |
| Case F | escalate_human | escalate_human | escalate_human | no |
| Case G | request_more_info | request_more_info | request_more_info | no |
| **Case H** | request_more_info | auto_reply | **request_more_info** | **yes** |

**8/8 match with the override applied (up from 7/8).** Case H flips from
`auto_reply` to `request_more_info` and now matches its independent label.
The other 7 cases are unaffected - confirmed, not assumed.

### Final tally

| Set | Before override | After override |
|---|---|---|
| Golden 9 | 9/9 | **9/9** |
| Fresh holdout 8 | 7/8 | **8/8** |

### Caveats, unchanged from Round 5 and still not resolved by this

1. This is still a design validated entirely by hand-traced booleans, not
   real model-extracted ones - the override fixes a specific extraction
   ambiguity identified by manual reasoning, but hasn't been checked
   against what the model would actually output for
   `asks_feature_existence_only` on a case like Case H.
2. The train/holdout violation flagged in Round 5 still stands for the
   golden 9 (5 of 9 are holdout, and two of the six fields were built
   directly from holdout-case wording). The fresh holdout 8 cases are
   clean of that specific problem (built without looking at any existing
   case wording), but they're now a small set (n=8) that's been iterated
   on once already (the override was added specifically because of Case
   H) - a genuinely fresh, never-before-seen third batch would be the
   next real check, not a substitute for testing this against the actual
   model.
3. **Still no classifier.py changes. Still not treating this as final.**
