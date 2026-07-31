"""
Stress test harness for safety-critical behavior. Separate from run_eval.py
on purpose: that harness measures classification accuracy (category,
urgency, action) against a labeled dataset. This one measures a narrower,
higher-stakes binary property - did the model correctly recognize an
active physical emergency and populate safety_instruction, and did it
correctly stay silent when there wasn't one?

The two failure directions are NOT equally bad:
  - false_negative: a real emergency didn't get a safety instruction. This
    is the dangerous direction - worth treating as a near-blocking issue.
  - false_positive: a routine or already-resolved situation got a safety
    instruction anyway. Annoying (undermines trust in real ones over
    time) but not dangerous the way a false_negative is.
The report below always calls these out separately rather than folding
them into one "accuracy" number, since collapsing them would hide which
direction any failure is in.

Usage:
    python -m eval.run_stress_tests
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import classify_email  # noqa: E402

STRESS_TESTS_PATH = os.path.join(os.path.dirname(__file__), "stress_tests.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_results")


def load_stress_tests(path=STRESS_TESTS_PATH):
    with open(path) as f:
        return json.load(f)


def score_stress_case(case, predicted_decision):
    """
    Pure function - no side effects, easy to unit test. A safety_instruction
    is considered "present" if it's a non-empty string.
    """
    raw_value = predicted_decision.get("safety_instruction")
    actual_present = bool(raw_value and str(raw_value).strip())
    expected_present = case["expected_safety_instruction"]

    if expected_present and not actual_present:
        miss_type = "false_negative"
    elif actual_present and not expected_present:
        miss_type = "false_positive"
    else:
        miss_type = None

    return {
        "id": case["id"],
        "expected_safety_instruction": expected_present,
        "actual_safety_instruction_present": actual_present,
        "safety_instruction_text": raw_value,
        "correct": miss_type is None,
        "miss_type": miss_type,
    }


def aggregate_stress_scores(case_scores):
    """Pure function - no side effects."""
    total = len(case_scores)
    if total == 0:
        raise ValueError("No stress test cases to score.")

    correct = sum(1 for c in case_scores if c["correct"])
    false_negatives = [c["id"] for c in case_scores if c["miss_type"] == "false_negative"]
    false_positives = [c["id"] for c in case_scores if c["miss_type"] == "false_positive"]

    return {
        "total_cases": total,
        "accuracy": round(correct / total, 4),
        "false_negatives": false_negatives,
        "false_positives": false_positives,
    }


def print_report(summary, case_scores):
    print(f"\n{'=' * 60}")
    print(f"SAFETY-CRITICAL STRESS TEST - {summary['total_cases']} cases")
    print(f"{'=' * 60}")
    print(f"Accuracy: {summary['accuracy'] * 100:.1f}%")

    if summary["false_negatives"]:
        print(f"\n!!! FALSE NEGATIVES ({len(summary['false_negatives'])}) - real emergencies that got NO safety instruction:")
        for cid in summary["false_negatives"]:
            print(f"  {cid}: expected a safety instruction, got none")
        print("  These are the dangerous misses - treat as a near-blocking issue, not a metric to average away.")
    else:
        print("\nNo false negatives - every real emergency got a safety instruction.")

    if summary["false_positives"]:
        print(f"\nFalse positives ({len(summary['false_positives'])}) - non-emergencies that got a safety instruction anyway:")
        for cid in summary["false_positives"]:
            case = next(c for c in case_scores if c["id"] == cid)
            print(f"  {cid}: {case['safety_instruction_text']!r}")
        print("  Less dangerous than a false negative, but worth fixing - crying wolf erodes trust in real alerts.")
    else:
        print("No false positives - nothing non-hazardous triggered a safety instruction.")

    print(f"\n{'-' * 60}")
    print("All cases:")
    for c in case_scores:
        status = "OK" if c["correct"] else f"MISS ({c['miss_type']})"
        print(f"  {c['id']}: expected={c['expected_safety_instruction']}, got={c['actual_safety_instruction_present']} - {status}")
    print()


def main():
    stress_tests = load_stress_tests()
    case_scores = []

    print(f"Running {len(stress_tests)} safety-critical stress test cases...")
    for i, case in enumerate(stress_tests, start=1):
        print(f"  [{i}/{len(stress_tests)}] {case['id']}...", end=" ", flush=True)
        result = classify_email(case["subject"], case["body"])
        score = score_stress_case(case, result["decision"])
        case_scores.append(score)
        print("OK" if score["correct"] else f"MISS ({score['miss_type']})")

    summary = aggregate_stress_scores(case_scores)
    print_report(summary, case_scores)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"stress_safety_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "cases": case_scores}, f, indent=2)
    print(f"Detailed results written to {out_path}")


if __name__ == "__main__":
    main()
