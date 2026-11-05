"""ClothesSpot Test Runner.

Executes all unit, integration, and DeepEval benchmark tests using Python's
built-in test framework.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bootstrap  # noqa: F401

from backend.tests.test_agents import (
    test_customer_query_agent_classification,
    test_knowledge_base_agent_grounding,
    test_resolution_agent_policy_compliance,
    test_log_agent_escalation_rules,
)
from backend.tests.test_retrieval import (
    test_bm25_retrieval,
    test_vector_similarity_search,
    test_query_expansion,
    test_kb_manager_comprehensive,
)
from backend.tests.test_guardrails import (
    test_prompt_injection_detection,
    test_pii_credit_card_redaction,
    test_output_guardrails_leakage,
)
from backend.tests.test_escalation import (
    test_escalation_point_1_high_urgency,
    test_escalation_point_2_angry_customer,
    test_escalation_point_3_no_matching_document,
    test_escalation_point_4_legal_threat_and_payment_dispute,
    test_escalation_point_5_low_confidence_or_b2b_custom,
    test_ticket_logging_columns,
)
from backend.tests.test_api import (
    test_api_health,
    test_api_dashboard_pages,
    test_api_process_complaint_resolved,
    test_api_process_complaint_escalated,
    test_api_request_validation,
    test_api_tickets_and_download,
    test_api_analytics,
    test_api_search,
    test_api_search_validation,
    test_api_frontend_cors,
    test_ticket_log_migrates_legacy_csv,
)
from backend.tests.test_deepeval_benchmarks import test_full_deepeval_benchmarks


TEST_FUNCTIONS = [
    # Agents
    ("test_customer_query_agent_classification", test_customer_query_agent_classification),
    ("test_knowledge_base_agent_grounding", test_knowledge_base_agent_grounding),
    ("test_resolution_agent_policy_compliance", test_resolution_agent_policy_compliance),
    ("test_log_agent_escalation_rules", test_log_agent_escalation_rules),
    # Retrieval
    ("test_bm25_retrieval", test_bm25_retrieval),
    ("test_vector_similarity_search", test_vector_similarity_search),
    ("test_query_expansion", test_query_expansion),
    ("test_kb_manager_comprehensive", test_kb_manager_comprehensive),
    # Guardrails
    ("test_prompt_injection_detection", test_prompt_injection_detection),
    ("test_pii_credit_card_redaction", test_pii_credit_card_redaction),
    ("test_output_guardrails_leakage", test_output_guardrails_leakage),
    # Escalation
    ("test_escalation_point_1_high_urgency", test_escalation_point_1_high_urgency),
    ("test_escalation_point_2_angry_customer", test_escalation_point_2_angry_customer),
    ("test_escalation_point_3_no_matching_document", test_escalation_point_3_no_matching_document),
    ("test_escalation_point_4_legal_threat_and_payment_dispute", test_escalation_point_4_legal_threat_and_payment_dispute),
    ("test_escalation_point_5_low_confidence_or_b2b_custom", test_escalation_point_5_low_confidence_or_b2b_custom),
    ("test_ticket_logging_columns", test_ticket_logging_columns),
    # API
    ("test_api_health", test_api_health),
    ("test_api_dashboard_pages", test_api_dashboard_pages),
    ("test_api_process_complaint_resolved", test_api_process_complaint_resolved),
    ("test_api_process_complaint_escalated", test_api_process_complaint_escalated),
    ("test_api_request_validation", test_api_request_validation),
    ("test_api_tickets_and_download", test_api_tickets_and_download),
    ("test_api_analytics", test_api_analytics),
    ("test_api_search", test_api_search),
    ("test_api_search_validation", test_api_search_validation),
    ("test_api_frontend_cors", test_api_frontend_cors),
    ("test_ticket_log_migrates_legacy_csv", test_ticket_log_migrates_legacy_csv),
    # DeepEval Benchmarks
    ("test_full_deepeval_benchmarks", test_full_deepeval_benchmarks),
]


def main():
    print("=" * 70)
    print("ClothesSpot Automated Test Suite Execution")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    for name, func in TEST_FUNCTIONS:
        try:
            func()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}")
            errors.append((name, str(e)))
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_FUNCTIONS)} tests.")
    if failed == 0:
        print("ALL TESTS PASSED SUCCESSFULLY")
    else:
        print("Some tests encountered errors:")
        for name, err in errors:
            print(f"   - {name}: {err}")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
