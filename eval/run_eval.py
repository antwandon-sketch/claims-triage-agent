"""
The eval harness. Run this any time you change the classifier prompt to see
whether accuracy actually went up or down, instead of just eyeballing a few
test emails.

Usage:
    python -m eval.run_eval

What it does:
    1. Loads eval/golden_dataset.json (the hand-labeled answer key)
    2. Sends each case's subject+body through the real classify_email()
       function - this makes real Claude API calls and costs a small
       amount of real money (20 cases, short prompts - a few cents total)
    3. Compares each prediction to the expected label
    4. Prints a readable accuracy report + confusion matrix to the terminal
    5. Saves the run's summary scores to the eval_runs table in Postgres,
       so you can track accuracy across prompt versions over time
    6. Writes a detailed per-case breakdown to eval_results/<timestamp>.json
       so you can actually read through every case, not just the summary

The scoring functions (score_case, aggregate_scores) are pure - no API
calls, no database - so they're covered by fast unit tests in
tests/test_eval_scoring.py that run without any real credentials.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import db  # noqa: E402
from classifier import classify_email  # noqa: E402

GOLDEN_DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_results")


def load_golden_dataset(path=GOLDEN_DATASET_PATH):
    with open(path) as f:
        return json.load(f)


def score_case(case, predicted_decision):
    """
    Compares one case's expected labels against what the classifier actually
    predicted. Pure function - no side effects - so it's easy to unit test.
    """
    return {
        "id": case["id"],
        "expected_category": case["expected_category"],
        "predicted_category": predicted_decision.get("category"),
        "category_correct": predicted_decision.get("category") == case["expected_category"],
        "expected_urgency": case["expected_urgency"],
        "predicted_urgency": predicted_decision.get("urgency"),
        "urgency_correct": predicted_decision.get("urgency") == case["expected_urgency"],
        "expected_action": case["expected_suggested_action"],
        "predicted_action": predicted_decision.get("suggested_action"),
        "action_correct": predicted_decision.get("suggested_action") == case["expected_suggested_action"],
        "confidence": predicted_decision.get("confidence"),
    }


def aggregate_scores(case_scores):
    """
    Turns a list of per-case score dicts into summary accuracy percentages
    plus a confusion matrix for category (which categories get mistaken for
    which). Pure function - no side effects.
    """
    total = len(case_scores)
    if total == 0:
        raise ValueError("No cases to score.")

    category_correct = sum(1 for c in case_scores if c["category_correct"])
    urgency_correct = sum(1 for c in case_scores if c["urgency_correct"])
    action_correct = sum(1 for c in case_scores if c["action_correct"])

    confusion_matrix = defaultdict(lambda: defaultdict(int))
    for c in case_scores:
        confusion_matrix[c["expected_category"]][c["predicted_category"]] += 1

    return {
        "total_cases": total,
        "category_accuracy": round(category_correct / total, 4),
        "urgency_accuracy": round(urgency_correct / total, 4),
        "action_accuracy": round(action_correct / total, 4),
        "confusion_matrix": {k: dict(v) for k, v in confusion_matrix.items()},
    }


def print_report(summary, case_scores):
    print(f"\n{'=' * 60}")
    print(f"EVAL RUN - {summary['total_cases']} cases")
    print(f"{'=' * 60}")
    print(f"Category accuracy:  {summary['category_accuracy'] * 100:.1f}%")
    print(f"Urgency accuracy:   {summary['urgency_accuracy'] * 100:.1f}%")
    print(f"Action accuracy:    {summary['action_accuracy'] * 100:.1f}%")

    print(f"\n{'-' * 60}")
    print("Confusion matrix (category) - rows = expected, columns = predicted")
    print(f"{'-' * 60}")
    categories = sorted(summary["confusion_matrix"].keys())
    for expected_cat in categories:
        row = summary["confusion_matrix"][expected_cat]
        row_str = ", ".join(f"{pred}={count}" for pred, count in row.items())
        print(f"  {expected_cat:20s} -> {row_str}")

    misses = [c for c in case_scores if not (c["category_correct"] and c["urgency_correct"] and c["action_correct"])]
    if misses:
        print(f"\n{'-' * 60}")
        print(f"Cases with at least one wrong field ({len(misses)}):")
        print(f"{'-' * 60}")
        for c in misses:
            print(f"  {c['id']}:")
            if not c["category_correct"]:
                print(f"    category: expected {c['expected_category']!r}, got {c['predicted_category']!r}")
            if not c["urgency_correct"]:
                print(f"    urgency:  expected {c['expected_urgency']!r}, got {c['predicted_urgency']!r}")
            if not c["action_correct"]:
                print(f"    action:   expected {c['expected_action']!r}, got {c['predicted_action']!r}")
    else:
        print("\nAll cases matched on category, urgency, and action.")
    print()


def main():
    golden_set = load_golden_dataset()
    case_scores = []

    print(f"Running {len(golden_set)} cases against {config.MODEL_NAME} (prompt {config.PROMPT_VERSION})...")
    for i, case in enumerate(golden_set, start=1):
        print(f"  [{i}/{len(golden_set)}] {case['id']}...", end=" ", flush=True)
        result = classify_email(case["subject"], case["body"])
        score = score_case(case, result["decision"])
        score["latency_ms"] = result["latency_ms"]
        case_scores.append(score)
        ok = score["category_correct"] and score["urgency_correct"] and score["action_correct"]
        print("OK" if ok else "MISS")

    summary = aggregate_scores(case_scores)
    print_report(summary, case_scores)

    run_id = db.save_eval_run(
        prompt_version=config.PROMPT_VERSION,
        model_name=config.MODEL_NAME,
        total_cases=summary["total_cases"],
        category_accuracy=summary["category_accuracy"],
        urgency_accuracy=summary["urgency_accuracy"],
        action_accuracy=summary["action_accuracy"],
        confusion_matrix=summary["confusion_matrix"],
    )
    print(f"Saved as eval_runs.id = {run_id}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"run_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "cases": case_scores}, f, indent=2)
    print(f"Detailed per-case results written to {out_path}")


if __name__ == "__main__":
    main()
