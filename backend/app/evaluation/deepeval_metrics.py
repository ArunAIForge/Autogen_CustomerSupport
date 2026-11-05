"""DeepEval-compatible evaluation metrics for ClothesSpot.

Computes:
1. Retrieval Relevance (Precision, Recall, Source Match)
2. Answer Correctness & Completeness
3. Hallucination Rate (Groundedness against context)
4. Faithfulness Score
5. Escalation Rule Accuracy
"""

import re
from typing import Any, Dict, List, Optional, Set


class RetrievalRelevanceMetric:
    """Measures how well retrieved passages match expected ground truth sources."""

    def __init__(self, name: str = "RetrievalRelevance") -> None:
        self.name = name

    def measure(self, retrieved_sources: List[str], expected_sources: List[str]) -> Dict[str, Any]:
        """Compute precision, recall, and F1 for retrieved sources."""
        ret_set = set(retrieved_sources)
        exp_set = set(expected_sources)

        if not exp_set:
            # If expected is empty (e.g. out of scope / no matching doc)
            score = 1.0 if not ret_set else 0.5
            return {"score": score, "precision": 1.0, "recall": 1.0, "passed": True}

        intersection = ret_set.intersection(exp_set)
        precision = len(intersection) / len(ret_set) if ret_set else 0.0
        recall = len(intersection) / len(exp_set) if exp_set else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        passed = recall >= 0.8
        return {
            "score": round(f1, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "passed": passed,
        }


class HallucinationMetric:
    """Measures hallucination rate by comparing claims against retrieved context."""

    def __init__(self, name: str = "HallucinationRate") -> None:
        self.name = name

    def measure(
        self,
        response: str,
        retrieved_passages: List[Dict[str, Any]],
        expected_policy_tokens: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Check for ungrounded numerical or policy assertions."""
        combined_context = " ".join([p.get("content", "") for p in retrieved_passages]).lower()
        resp_lower = response.lower()

        # Check for numbers in response (e.g., 30 days, 14 days, 15 minutes, 24-48 hours)
        numbers_in_response = set(re.findall(r"\b\d+\b", resp_lower))
        numbers_in_context = set(re.findall(r"\b\d+\b", combined_context))

        # Check for hallucinated numbers
        hallucinated_nums = []
        for num in numbers_in_response:
            if num not in numbers_in_context:
                # Ignore trivial digits like single bullet list numbers (1, 2, 3)
                if int(num) > 4:
                    hallucinated_nums.append(num)

        hallucination_rate = len(hallucinated_nums) / len(numbers_in_response) if numbers_in_response else 0.0
        faithfulness = 1.0 - min(1.0, hallucination_rate)

        return {
            "hallucination_rate": round(hallucination_rate, 3),
            "faithfulness": round(faithfulness, 3),
            "hallucinated_entities": hallucinated_nums,
            "passed": hallucination_rate == 0.0,
        }


class AnswerCorrectnessMetric:
    """Measures factual agreement and completeness with expected resolution."""

    def __init__(self, name: str = "AnswerCorrectness") -> None:
        self.name = name

    def measure(
        self,
        response: str,
        expected_keywords: List[str],
        actual_status: str,
        expected_status: str
    ) -> Dict[str, Any]:
        """Verify presence of key answer steps and correct status badge."""
        resp_lower = response.lower()
        matched_keywords = [kw for kw in expected_keywords if kw.lower() in resp_lower]
        keyword_score = len(matched_keywords) / len(expected_keywords) if expected_keywords else 1.0
        status_match = (actual_status.lower() == expected_status.lower())

        final_score = (keyword_score * 0.7) + (0.3 if status_match else 0.0)
        passed = (final_score >= 0.75) and status_match

        return {
            "score": round(final_score, 3),
            "keyword_coverage": round(keyword_score, 3),
            "matched_keywords": matched_keywords,
            "status_match": status_match,
            "passed": passed,
        }


class EscalationAccuracyMetric:
    """Evaluates adherence to the 5-point escalation rubric."""

    def __init__(self, name: str = "EscalationAccuracy") -> None:
        self.name = name

    def measure(
        self,
        actual_status: str,
        expected_status: str,
        actual_reason: str,
        expected_reason_substr: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ensure correct escalation decision and valid reason."""
        status_correct = (actual_status.lower() == expected_status.lower())
        reason_valid = True
        if expected_status == "Escalated" and expected_reason_substr:
            reason_valid = expected_reason_substr.lower() in actual_reason.lower()

        score = 1.0 if (status_correct and reason_valid) else (0.5 if status_correct else 0.0)
        return {
            "score": score,
            "status_correct": status_correct,
            "reason_valid": reason_valid,
            "passed": score == 1.0,
        }
