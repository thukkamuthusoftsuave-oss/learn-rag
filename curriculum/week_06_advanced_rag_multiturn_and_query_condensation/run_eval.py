"""Week 6 Evaluation: Multi-Turn Query Condensation & Citation Check.

Demonstrates conversational follow-up rewriting into standalone search queries
and verifies citation grounding.
"""

from session_manager import ChatSession
from condensation_engine import condense_followup_query
from citation_synthesizer import verify_citations


def run_multiturn_demo():
    print("=== Week 6: Multi-Turn Chat & Query Condensation Demo ===\n")

    session = ChatSession()

    # Turn 1
    turn1_user = "What is the carry-over cap for a regular employee in the US?"
    turn1_assistant = "Regular employees in the US have a carry-over cap of 10 days. [[HR-207 Section 4.2]]"
    session.add_turn(turn1_user, turn1_assistant, metadata={"region": "US"})
    print(f"Turn 1 User     : '{turn1_user}'")
    print(f"Turn 1 Assistant: '{turn1_assistant}'")

    # Turn 2: Ambiguous Follow-Up
    turn2_user = "What about the UK?"
    print(f"\nTurn 2 User     : '{turn2_user}' (ambiguous follow-up)")

    # Condensation
    condensed_q = condense_followup_query(turn2_user, session.get_history())
    print(f"-> Condensed Query for Retriever: '{condensed_q}'")

    # Verify citation grounding
    fake_retrieved = [
        {"section": "HR-207 Section 4.2", "filename": "addendum_UK.txt", "text": "UK Carry-over cap: 8 days."}
    ]
    turn2_assistant = "In the UK, regular employees receive an 8-day carry-over cap. [[HR-207 Section 4.2]]"
    valid, errors = verify_citations(turn2_assistant, fake_retrieved)
    print(f"\nCitation Grounding Check: {'PASSED' if valid else 'FAILED'}")
    if not valid:
        print(f"  Errors: {errors}")


if __name__ == "__main__":
    run_multiturn_demo()
