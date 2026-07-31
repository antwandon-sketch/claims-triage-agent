"""
Tests for the safety-critical stress test scoring logic. Pure functions,
no API calls, no database - fast and don't need real credentials.
"""
from eval.run_stress_tests import score_stress_case, aggregate_stress_scores


def test_true_positive_correctly_detected():
    case = {"id": "s1", "expected_safety_instruction": True}
    decision = {"safety_instruction": "Leave the house and call 911 immediately."}
    result = score_stress_case(case, decision)
    assert result["correct"] is True
    assert result["miss_type"] is None


def test_true_negative_correctly_stays_silent():
    case = {"id": "s2", "expected_safety_instruction": False}
    decision = {"safety_instruction": None}
    result = score_stress_case(case, decision)
    assert result["correct"] is True
    assert result["miss_type"] is None


def test_false_negative_detected():
    """A real emergency with no safety instruction - the dangerous miss direction."""
    case = {"id": "s3", "expected_safety_instruction": True}
    decision = {"safety_instruction": None}
    result = score_stress_case(case, decision)
    assert result["correct"] is False
    assert result["miss_type"] == "false_negative"


def test_false_positive_detected():
    """A routine case that got a safety instruction anyway."""
    case = {"id": "s4", "expected_safety_instruction": False}
    decision = {"safety_instruction": "Call 911 now."}
    result = score_stress_case(case, decision)
    assert result["correct"] is False
    assert result["miss_type"] == "false_positive"


def test_empty_string_treated_as_absent():
    """An empty or whitespace-only string should count as 'not present', not a false positive trap."""
    case = {"id": "s5", "expected_safety_instruction": False}
    decision = {"safety_instruction": "   "}
    result = score_stress_case(case, decision)
    assert result["correct"] is True


def test_missing_key_treated_as_absent():
    case = {"id": "s6", "expected_safety_instruction": False}
    decision = {}
    result = score_stress_case(case, decision)
    assert result["correct"] is True


def test_aggregate_separates_false_negatives_and_positives():
    scores = [
        score_stress_case({"id": "a", "expected_safety_instruction": True}, {"safety_instruction": None}),
        score_stress_case({"id": "b", "expected_safety_instruction": False}, {"safety_instruction": "call 911"}),
        score_stress_case({"id": "c", "expected_safety_instruction": True}, {"safety_instruction": "evacuate now"}),
    ]
    summary = aggregate_stress_scores(scores)
    assert summary["total_cases"] == 3
    assert summary["false_negatives"] == ["a"]
    assert summary["false_positives"] == ["b"]
    assert summary["accuracy"] == round(1 / 3, 4)


def test_aggregate_empty_raises():
    try:
        aggregate_stress_scores([])
        assert False, "expected a ValueError for an empty case list"
    except ValueError:
        pass
