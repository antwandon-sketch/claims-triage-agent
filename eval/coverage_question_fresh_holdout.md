# coverage_question: fresh synthetic holdout test (independent of golden_dataset.json)

Produced 2026-07-31. **Step 1 result:** `golden_dataset.json` still has exactly
9 `coverage_question` cases (`case_08, 09, 10, 20, 31, 32, 33, 34, 35`) - no
new ones exist, so this file builds 8 new synthetic cases instead, written
without reading `eval/coverage_question_manual_trace.md` or re-reading the
existing 9 cases' wording this session, to keep them a genuinely independent
check rather than paraphrases of known cases.

For each case: realistic email text, an independent human-judgment label
(reasoned holistically, without running any function or boolean framework),
then a separate boolean extraction and the tree-derived function's output,
compared against the independent label.

**Function under test** (from the earlier session's `coverage_question_tree_fit.py`,
mechanically derived from a decision tree fit on the 9 golden cases):

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

---

## Case A - pure feature-existence lookup

**Subject:** Does my renters policy cover identity theft?

**Body:** "Hi, does my renters policy include any identity theft protection
or restoration services? Policy number RN-58820."

**Independent label (reasoned first, no function run):** No incident has
occurred, nothing is in dispute, and the question is answerable directly
from the policy's list of included coverages/endorsements - a textbook
generic feature question. Safe for a confident, general, non-binding
auto-reply. → **auto_reply**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | False | No loss/accident/damage/theft/injury described |
| has_policy_or_claim_number | True | RN-58820 given |
| has_liability_or_dispute_signal | False | No fault/dispute/denial language |
| has_underwriting_or_nonstandard_use_signal | False | No business/non-standard-use signal |
| asks_feature_existence_only | True | Pure "does my policy include X" lookup |
| cause_investigated_and_unresolved | False | No damage/loss to investigate |

**Function output:** `auto_reply`
**Result: MATCH**

---

## Case B - "would this apply to my situation" eligibility question

**Subject:** Coverage for stuff in a storage pod during our move

**Body:** "We're in the middle of moving and have a POD storage container
sitting in our driveway for the week with most of our furniture in it.
Would that be covered under our homeowners policy if anything happened to
it? Policy HO-40112."

**Independent label (reasoned first):** No loss has happened yet, but this
isn't a pure feature lookup either - off-premises/temporary-location
property coverage typically has specific conditions and sub-limits (how
long property can be away from the residence, whether a POD counts as "on
premises"). Answering confidently requires checking those specifics against
their actual situation, which shouldn't be auto-replied with a definitive
answer. → **request_more_info**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | False | No loss/accident/damage/theft/injury has occurred - "if anything happened" is conditional/future, same shape as case_08's hypothetical framing |
| has_policy_or_claim_number | True | HO-40112 given |
| has_liability_or_dispute_signal | False | No fault/dispute language |
| has_underwriting_or_nonstandard_use_signal | False | Temporary off-premises storage isn't a business activity or lasting risk-profile change |
| asks_feature_existence_only | False | Requires evaluating whether *this* situation (a POD, in the driveway, for a week) qualifies under off-premises coverage terms - not a pure existence lookup |
| cause_investigated_and_unresolved | False | No damage has occurred, nothing to investigate |

**Function output:** `request_more_info`
**Result: MATCH**

---

## Case C - cause investigated, still unresolved

**Subject:** Kitchen outlets - electrician can't find the cause

**Body:** "Our kitchen outlets keep tripping the breaker and we had an
electrician come look at it, but even after checking things out he
couldn't figure out what's causing it. Would fixing this be covered under
our policy? HO-77341."

**Independent label (reasoned first):** An electrician actively
investigated and still couldn't determine the cause. Electrical-issue
coverage often hinges on whether the cause is sudden/accidental (covered)
vs. wear-and-tear/faulty pre-existing wiring (usually excluded) - genuinely
unresolved even after real investigation, needs a human to sort out.
→ **escalate_human**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | True | Ongoing electrical issue is a real, present problem |
| has_policy_or_claim_number | True | HO-77341 given |
| has_liability_or_dispute_signal | False | No fault/dispute language |
| has_underwriting_or_nonstandard_use_signal | False | Not a business/non-standard-use question |
| asks_feature_existence_only | False | Not a feature lookup |
| cause_investigated_and_unresolved | True | Electrician actively inspected; cause still unknown afterward |

**Function output:** `escalate_human`
**Result: MATCH**

---

## Case D - cause just noticed, not yet investigated

**Subject:** Small crack in the basement wall

**Body:** "I noticed a small crack in our basement wall today, haven't had
a chance to look into it any further yet. If it turns out to be something,
would that even be covered? Policy HO-90287."

**Independent label (reasoned first):** Customer explicitly hasn't
investigated yet - just noticed something today. No evidence this is a
significant or unresolved-after-investigation issue; safe to gather basic
details first rather than escalate for something that might turn out to be
nothing. → **request_more_info**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | True | A crack is a real, observed thing, even if minor |
| has_policy_or_claim_number | True | HO-90287 given |
| has_liability_or_dispute_signal | False | No fault/dispute language |
| has_underwriting_or_nonstandard_use_signal | False | No business/non-standard-use signal |
| asks_feature_existence_only | False | Not a feature lookup |
| cause_investigated_and_unresolved | False | Explicitly "haven't had a chance to look into it further yet" - just noticed |

**Function output:** `request_more_info`
**Result: MATCH**

---

## Case E - business/non-standard use

**Subject:** Using my garage as a pottery studio

**Body:** "I've started using my detached garage as a small pottery
studio, I fire pieces in a kiln a few times a week. Does my homeowners
policy cover that space and the equipment, or do I need something
separate? Policy HO-63410."

**Independent label (reasoned first):** A business activity plus a kiln
(a real fire-risk change) is a change in risk profile a standard
homeowners policy likely wasn't written for. Needs underwriting review, not
a generic answer. → **escalate_human**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | False | Ongoing activity, no loss/accident/damage/theft/injury |
| has_policy_or_claim_number | True | HO-63410 given |
| has_liability_or_dispute_signal | False | No fault/dispute language |
| has_underwriting_or_nonstandard_use_signal | True | Business activity + kiln = textbook non-standard use / risk-profile change |
| asks_feature_existence_only | True (moot) | Surface phrasing ("or do I need something separate") reads existence-style, but irrelevant - the function checks `has_underwriting_or_nonstandard_use_signal` first and escalates before this field is ever consulted |
| cause_investigated_and_unresolved | False | No damage/loss involved |

**Function output:** `escalate_human`
**Result: MATCH**

---

## Case F - clear liability/dispute

**Subject:** Delivery driver slipped on our steps

**Body:** "A delivery driver slipped on our icy front steps last week and
says he's seeing a doctor for his back. Is something like that covered
under our homeowners policy? HO-11029."

**Independent label (reasoned first):** Textbook third-party liability
exposure - injury to a non-household member on the property, medical
treatment already involved. Needs a human, not an automated answer.
→ **escalate_human**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | True | A slip-and-fall last week is a real, already-occurred event |
| has_policy_or_claim_number | True | HO-11029 given |
| has_liability_or_dispute_signal | True | Third-party injury, doctor visit already involved - clearest possible liability signal |
| has_underwriting_or_nonstandard_use_signal | False | Not a business/non-standard-use question |
| asks_feature_existence_only | False (moot) | Liability branch fires first regardless |
| cause_investigated_and_unresolved | False | Cause (icy steps, slip) isn't in question |

**Function output:** `escalate_human`
**Result: MATCH**

---

## Case G - missing policy number entirely

**Subject:** Tree falling on neighbor's fence

**Body:** "If my tree fell on my neighbor's fence during a storm, does
homeowners insurance typically cover that kind of thing? I don't have my
policy number on hand right now, sorry."

**Independent label (reasoned first):** No event has happened yet
(hypothetical "if"), and critically, no policy or claim number is provided
at all. Regardless of anything else, missing identifying info means this
can't be answered confidently yet - need that first.
→ **request_more_info**

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | False | Purely hypothetical ("if my tree fell"), no event has occurred |
| has_policy_or_claim_number | False | Explicitly "I don't have my policy number on hand right now" |
| has_liability_or_dispute_signal | False | No active dispute - hypothetical, no third party involved yet |
| has_underwriting_or_nonstandard_use_signal | False | No business/non-standard-use signal |
| asks_feature_existence_only | True (moot) | "Typically cover" reads existence-style, but doesn't matter - missing policy number resolves this either way (the function's inner `not has_policy_or_claim_number` check under the feature-existence branch returns the same answer as the outer one) |
| cause_investigated_and_unresolved | False | No damage/loss to investigate |

**Function output:** `request_more_info`
**Result: MATCH**

---

## Case H - deliberately ambiguous/hard case

**Subject:** Laptop stolen from my car

**Body:** "My laptop was stolen out of my car last weekend outside a
restaurant. Does my renters policy typically cover personal property
stolen from a vehicle, and is there a special limit for electronics?
Policy RN-33192."

**Independent label (reasoned first, holistically):** Genuinely hard call.
The theft already happened (real, specific, past event) - unlike Case A's
pure hypothetical framing, this isn't just a feature question in spirit.
And "is there a special limit for electronics" is asking for a number that
varies policy-to-policy and could materially affect what the customer does
next (e.g., whether it's even worth filing a claim). Giving a wrong or
overly generic answer here has real consequences, so I'd rather this get a
human/policy-specific check than a confident auto-reply. → **request_more_info**
(acknowledging a reasonable person could argue for `auto_reply` with a
generic "yes, subject to your policy's limits" answer instead - this is the
deliberately close one.)

**Boolean extraction:**
| Field | Value | Why |
|---|---|---|
| references_specific_incident | True | A theft that already happened, not hypothetical |
| has_policy_or_claim_number | True | RN-33192 given |
| has_liability_or_dispute_signal | False | No fault/dispute/denial language |
| has_underwriting_or_nonstandard_use_signal | False | No business/non-standard-use signal |
| asks_feature_existence_only | **True, but genuinely ambiguous** | Best-faith read: both sub-questions ("is off-premises vehicle theft covered" and "what's the electronics limit") are, in principle, statable directly from policy language without evaluating contested facts about the theft itself - closer to a (two-part) lookup than to case_08/Case B's scenario-eligibility shape. But this is a real judgment call, not a clean one - see below. |
| cause_investigated_and_unresolved | False | The theft itself isn't in question - no unclear cause |

**Function output (using the `True` extraction above):** `auto_reply`
**Result: MISMATCH** against the independent label (`request_more_info`)

**This mismatch is the most useful result in this file, not a failure to
smooth over.** It hinges entirely on how `asks_feature_existence_only` gets
read for a case that mixes a real specific incident with feature-existence-
style phrasing ("typically cover," "is there a special limit"). Under the
*alternate* reading - `asks_feature_existence_only = False`, on the
argument that answering "would coverage really apply and at what amount"
for *their specific* stolen laptop is eligibility-dependent, not a pure
lookup - the function outputs `request_more_info`, which *would* match. The
honest conclusion: this field's definition doesn't yet cleanly resolve
cases where a real incident is described using generic/typical-coverage
phrasing rather than "would MY situation qualify" phrasing. That's a real
gap the other 8 (less deliberately adversarial) cases didn't surface.

---

## Summary

| Case | Independent label | Function output | Result |
|---|---|---|---|
| A - feature lookup | auto_reply | auto_reply | MATCH |
| B - eligibility, tied to real situation | request_more_info | request_more_info | MATCH |
| C - cause investigated, unresolved | escalate_human | escalate_human | MATCH |
| D - cause just noticed | request_more_info | request_more_info | MATCH |
| E - business/non-standard use | escalate_human | escalate_human | MATCH |
| F - clear liability | escalate_human | escalate_human | MATCH |
| G - missing policy number | request_more_info | request_more_info | MATCH |
| H - ambiguous (theft + generic phrasing) | request_more_info | auto_reply | **MISMATCH** |

**7 of 8 match. 1 of 8 (Case H, the deliberately hard case) mismatches**, and
the mismatch traces to a genuine, specific gap: `asks_feature_existence_only`
doesn't have a clean answer when a real, already-occurred incident is
described using generic/"typically covers" phrasing rather than "would MY
situation qualify" phrasing. This is a materially different (and arguably
better-targeted) failure than anything found in the golden-dataset trace,
precisely because these 8 cases were never looked at while the fields were
being designed - this is the first genuinely clean signal this session has
had on whether the design generalizes, as opposed to fitting the 9 cases (5
of them holdout) it was built against.
