"""
Tests for the eval harness's scoring logic. These test score_case() and
aggregate_scores() directly with fixed inputs - no API calls, no database,
no golden_dataset.json even needed. That's deliberate: the scoring math
should be trustworthy on its own, independent of whether the classifier
itself is doing well or badly that day.
"""
from eval.run_eval import score_case, aggregate_scores, filter_by_split


def _case(id="c1", category="new_claim", urgency="high", action="escalate_human", split="train"):
    return {
        "id": id,
        "split": split,
        "expected_category": category,
        "expected_urgency": urgency,
        "expected_suggested_action": action,
    }


def _decision(category="new_claim", urgency="high", action="escalate_human", confidence=0.9):
    return {"category": category, "urgency": urgency, "suggested_action": action, "confidence": confidence}


def test_score_case_all_correct():
    result = score_case(_case(), _decision())
    assert result["category_correct"] is True
    assert result["urgency_correct"] is True
    assert result["action_correct"] is True
    assert result["split"] == "train"


def test_score_case_captures_rationale_and_summary():
    """The v6 investigation found rationale/summary were being discarded -
    this is the regression test making sure they stay captured going
    forward."""
    decision = _decision()
    decision["rationale"] = "Missing policy number, need it to assess confidently."
    decision["summary"] = "Customer asking about jewelry coverage."
    result = score_case(_case(), decision)
    assert result["rationale"] == "Missing policy number, need it to assess confidently."
    assert result["summary"] == "Customer asking about jewelry coverage."


def test_score_case_missing_rationale_is_none():
    result = score_case(_case(), {"category": "new_claim", "urgency": "high", "suggested_action": "escalate_human"})
    assert result["rationale"] is None
    assert result["summary"] is None


def test_score_case_wrong_category():
    result = score_case(_case(category="new_claim"), _decision(category="coverage_question"))
    assert result["category_correct"] is False
    assert result["predicted_category"] == "coverage_question"
    assert result["expected_category"] == "new_claim"


def test_score_case_wrong_urgency_only():
    result = score_case(_case(urgency="high"), _decision(urgency="medium"))
    assert result["urgency_correct"] is False
    assert result["category_correct"] is True
    assert result["action_correct"] is True


def test_score_case_missing_field_in_prediction():
    """A malformed/incomplete prediction should score as incorrect, not crash."""
    result = score_case(_case(), {"category": "new_claim"})
    assert result["category_correct"] is True
    assert result["urgency_correct"] is False
    assert result["action_correct"] is False


def test_aggregate_scores_perfect_run():
    scores = [score_case(_case(id=f"c{i}"), _decision()) for i in range(5)]
    summary = aggregate_scores(scores)
    assert summary["total_cases"] == 5
    assert summary["category_accuracy"] == 1.0
    assert summary["urgency_accuracy"] == 1.0
    assert summary["action_accuracy"] == 1.0


def test_aggregate_scores_computes_accuracy_fraction():
    scores = [
        score_case(_case(id="c1", category="new_claim"), _decision(category="new_claim")),
        score_case(_case(id="c2", category="new_claim"), _decision(category="coverage_question")),
    ]
    summary = aggregate_scores(scores)
    assert summary["total_cases"] == 2
    assert summary["category_accuracy"] == 0.5


def test_aggregate_scores_confusion_matrix_tracks_mismatches():
    scores = [
        score_case(_case(id="c1", category="new_claim"), _decision(category="coverage_question")),
        score_case(_case(id="c2", category="new_claim"), _decision(category="coverage_question")),
        score_case(_case(id="c3", category="new_claim"), _decision(category="new_claim")),
    ]
    summary = aggregate_scores(scores)
    matrix = summary["confusion_matrix"]["new_claim"]
    assert matrix["coverage_question"] == 2
    assert matrix["new_claim"] == 1


def test_aggregate_scores_empty_list_raises():
    try:
        aggregate_scores([])
        assert False, "expected a ValueError for an empty case list"
    except ValueError:
        pass


def test_filter_by_split_all_returns_everything():
    cases = [_case(id="c1", split="train"), _case(id="c2", split="holdout")]
    assert filter_by_split(cases, "all") == cases


def test_filter_by_split_train_only():
    cases = [_case(id="c1", split="train"), _case(id="c2", split="holdout")]
    result = filter_by_split(cases, "train")
    assert [c["id"] for c in result] == ["c1"]


def test_filter_by_split_holdout_only():
    cases = [_case(id="c1", split="train"), _case(id="c2", split="holdout")]
    result = filter_by_split(cases, "holdout")
    assert [c["id"] for c in result] == ["c2"]
