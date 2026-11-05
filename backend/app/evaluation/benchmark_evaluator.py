"""Local benchmark evaluation runner for the ClothesSpot customer support workflow.

Executes all 6 required specification complaints plus 2 custom benchmark test cases,
computing local metrics (retrieval relevance, answer correctness, hallucination rate,
escalation accuracy).
"""

from typing import Any, Dict, List
from backend.app.agents.team import AutoGenSupportTeam
from backend.app.retrieval.kb_manager import get_kb_manager
from backend.app.evaluation.deepeval_metrics import (
    RetrievalRelevanceMetric,
    HallucinationMetric,
    AnswerCorrectnessMetric,
    EscalationAccuracyMetric,
)


BENCHMARK_TEST_CASES = [
    {
        "id": 1,
        "complaint": "Where is my order? It was supposed to arrive yesterday.",
        "customer_name": "Alex",
        "order_id": "ORD-1001",
        "expected_category": "Shipping",
        "expected_sources": ["shipping_policy.md"],
        "expected_status": "Resolved",
        "expected_keywords": ["shipping_policy.md", "tracking", "24 to 48", "courier"],
        "expected_reason_substr": None,
    },
    {
        "id": 2,
        "complaint": "I want to return the shoes I bought last week. How do I get a refund?",
        "customer_name": "Priya",
        "order_id": "ORD-2002",
        "expected_category": "Refund",
        "expected_sources": ["refund_policy.md"],
        "expected_status": "Resolved",
        "expected_keywords": ["refund_policy.md", "30", "return", "prepaid", "5 to 7"],
        "expected_reason_substr": None,
    },
    {
        "id": 3,
        "complaint": "I forgot my password and can't log in.",
        "customer_name": "Sam",
        "order_id": "N/A",
        "expected_category": "Account",
        "expected_sources": ["account_and_login.md"],
        "expected_status": "Resolved",
        "expected_keywords": ["account_and_login.md", "forgot password", "reset link", "15 minutes"],
        "expected_reason_substr": None,
    },
    {
        "id": 4,
        "complaint": "The blender I received is broken. Can I get a replacement?",
        "customer_name": "Jordan",
        "order_id": "ORD-4004",
        "expected_category": "Product",
        "expected_sources": ["product_faq.md"],
        "expected_status": "Resolved",
        "expected_keywords": ["product_faq.md", "replacement", "14 days", "photo", "24 to 48"],
        "expected_reason_substr": None,
    },
    {
        "id": 5,
        "complaint": "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer.",
        "customer_name": "Marcus",
        "order_id": "ORD-5005",
        "expected_category": "Billing",
        "expected_sources": ["billing_and_payments.md"],
        "expected_status": "Escalated",
        "expected_keywords": ["billing_and_payments.md", "charges", "escalated"],
        "expected_reason_substr": "urgency",
    },
    {
        "id": 6,
        "complaint": "Do you sell gift cards for a company of 500 employees with custom branding?",
        "customer_name": "Elena",
        "order_id": "N/A",
        "expected_category": "Product",
        "expected_sources": ["product_faq.md"],
        "expected_status": "Escalated",
        "expected_keywords": ["gift cards", "escalated", "corporate"],
        "expected_reason_substr": "No matching document",
    },
    {
        "id": 7,
        "complaint": "My promotional code SUMMER25 gives an invalid promo code error during checkout.",
        "customer_name": "David",
        "order_id": "N/A",
        "expected_category": "Product",
        "expected_sources": ["product_faq.md"],
        "expected_status": "Resolved",
        "expected_keywords": ["product_faq.md", "promo", "voucher"],
        "expected_reason_substr": None,
    },
    {
        "id": 8,
        "complaint": "Someone hacked into my account from a strange location and ordered items using my saved card!",
        "customer_name": "Sarah",
        "order_id": "ORD-8008",
        "expected_category": "Billing",
        "expected_sources": ["billing_and_payments.md"],
        "expected_status": "Escalated",
        "expected_keywords": ["escalated", "freeze", "fraud"],
        "expected_reason_substr": "fraud",
    },
]


class BenchmarkEvaluator:
    """Runs end-to-end evaluation and aggregates quality scores."""

    def __init__(self) -> None:
        self.team = AutoGenSupportTeam()
        self.kb_manager = get_kb_manager()
        self.retrieval_metric = RetrievalRelevanceMetric()
        self.hallucination_metric = HallucinationMetric()
        self.correctness_metric = AnswerCorrectnessMetric()
        self.escalation_metric = EscalationAccuracyMetric()

    def run_eval(self) -> Dict[str, Any]:
        """Execute all test cases and return scorecard."""
        results: List[Dict[str, Any]] = []

        total_retrieval_score = 0.0
        total_hallucination_rate = 0.0
        total_faithfulness = 0.0
        total_correctness = 0.0
        total_escalation_acc = 0.0
        total_cases = len(BENCHMARK_TEST_CASES)

        for case in BENCHMARK_TEST_CASES:
            case_id = case["id"]
            complaint = case["complaint"]
            cust_name = case["customer_name"]
            order_id = case["order_id"]

            # Process through team
            resp = self.team.run_complaint_workflow(
                raw_complaint=complaint,
                customer_name=cust_name,
                order_id=order_id,
            )

            # Retrieve full KB context for this query
            kb_res = self.kb_manager.search_kb(complaint, category=resp.category, top_k=3)
            passages = kb_res.get("passages", [])

            # Evaluate metrics
            ret_eval = self.retrieval_metric.measure(resp.kb_sources, case["expected_sources"])
            halluc_eval = self.hallucination_metric.measure(resp.response, passages)
            corr_eval = self.correctness_metric.measure(
                resp.response,
                case["expected_keywords"],
                resp.status,
                case["expected_status"],
            )
            esc_eval = self.escalation_metric.measure(
                resp.status,
                case["expected_status"],
                resp.escalation_reason or "",
                case.get("expected_reason_substr"),
            )

            total_retrieval_score += ret_eval["score"]
            total_hallucination_rate += halluc_eval["hallucination_rate"]
            total_faithfulness += halluc_eval["faithfulness"]
            total_correctness += corr_eval["score"]
            total_escalation_acc += esc_eval["score"]

            case_result = {
                "case_id": case_id,
                "complaint": complaint,
                "category": resp.category,
                "urgency": resp.urgency,
                "sentiment": resp.sentiment,
                "actual_status": resp.status,
                "expected_status": case["expected_status"],
                "status_match": resp.status == case["expected_status"],
                "retrieval_score": ret_eval["score"],
                "hallucination_rate": halluc_eval["hallucination_rate"],
                "faithfulness": halluc_eval["faithfulness"],
                "correctness": corr_eval["score"],
                "escalation_acc": esc_eval["score"],
                "sources": resp.kb_sources,
                "response_preview": resp.response[:120] + "...",
            }
            results.append(case_result)

        avg_retrieval = round(total_retrieval_score / total_cases, 3)
        avg_hallucination = round(total_hallucination_rate / total_cases, 3)
        avg_faithfulness = round(total_faithfulness / total_cases, 3)
        avg_correctness = round(total_correctness / total_cases, 3)
        avg_escalation = round(total_escalation_acc / total_cases, 3)

        return {
            "total_cases": total_cases,
            "avg_retrieval_relevance": avg_retrieval,
            "avg_hallucination_rate": avg_hallucination,
            "avg_faithfulness": avg_faithfulness,
            "avg_answer_correctness": avg_correctness,
            "avg_escalation_accuracy": avg_escalation,
            "case_results": results,
            "all_status_passed": all(r["status_match"] for r in results),
        }
