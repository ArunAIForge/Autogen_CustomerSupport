"""DeepEval automated evaluation suite verifying all benchmark complaints."""

try:
    import pytest
except ImportError:
    pytest = None
import bootstrap  # noqa: F401
from backend.app.evaluation.benchmark_evaluator import BenchmarkEvaluator


def test_full_deepeval_benchmarks():
    evaluator = BenchmarkEvaluator()
    report = evaluator.run_eval()

    assert report["total_cases"] == 8
    assert report["all_status_passed"] is True, "All 8 benchmark cases must match expected status"
    assert report["avg_escalation_accuracy"] == 1.0, "Escalation decisions must be 100% accurate"
    assert report["avg_answer_correctness"] >= 0.90, "Answer correctness must be at least 90%"
    assert report["avg_faithfulness"] >= 0.90, "Faithfulness must be at least 90%"
    assert report["avg_hallucination_rate"] <= 0.05, "Hallucination rate must be below 5%"
