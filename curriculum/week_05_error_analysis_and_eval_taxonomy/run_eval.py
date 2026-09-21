"""Week 5 Evaluation: Error Taxonomy Ranking & Prediction Card.

Analyzes a set of simulated production traces, ranks failure modes by impact,
and generates an actionable prediction card.
"""

from error_taxonomy import rank_issues_by_impact
from prediction_card import generate_prediction_card


def run_error_analysis_demo():
    print("=== Week 5: Error Analysis & Evaluation Taxonomy Demo ===\n")

    # Sample traces reflecting realistic production telemetry
    sample_traces = [
        {"query": "What is the notice period for 1.5 years in UK?", "label": "CORRECT"},
        {"query": "Who is eligible for sabbatical in EMEA?", "label": "CORRECT"},
        {"query": "What defines continuous service in US?", "label": "CORRECT"},
        {"query": "What is maternity leave in EMEA?", "label": "CORRECT_REFUSAL"},
        {"query": "What is the carry-over cap for a senior in US?", "label": "RETRIEVAL_FAILURE"},
        {"query": "What does Section 4.7 say about part-time hours?", "label": "RETRIEVAL_FAILURE"},
        {"query": "What is the carry-over cap for LATAM regular?", "label": "RETRIEVAL_FAILURE"},
        {"query": "After 10 years what sabbatical do I get?", "label": "GENERATION_FAILURE"},
    ]

    print(f"Ingested {len(sample_traces)} production traces for analysis.")
    ranked_issues = rank_issues_by_impact(sample_traces)

    print("\n--- Error Taxonomy Impact Ranking (Frequency × Severity) ---")
    for item in ranked_issues:
        print(f"[{item['label']}] Count={item['count']} | Severity={item['severity']} | Impact Score={item['impact_score']}")

    card = generate_prediction_card(ranked_issues)
    print(card)


if __name__ == "__main__":
    run_error_analysis_demo()
