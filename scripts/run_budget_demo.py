"""Demonstration of clean budget termination across all four budgets.

Enforces:
1. max_iterations
2. max_tokens
3. max_cost
4. wall_clock
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from policy_rag.agent.loop import HRAgent


def demo_budget_termination():
    agent = HRAgent(verbose=True)
    query = "What is the mandatory notice period for employee EMP-101 in the UK?"

    print("=" * 80)
    print("BUDGET TERMINATION DEMONSTRATION")
    print("=" * 80)

    # Test 1: max_iterations budget termination
    print("\n>>> TEST 1: Triggering 'max_iterations' Budget Termination (limit = 1)...")
    res1 = agent.run(query, max_iterations=1)
    print(f"Status: {res1['status']} | Reason: {res1['termination_reason']}")
    print(f"Answer: {res1['answer']}")

    # Test 2: max_tokens budget termination
    print("\n>>> TEST 2: Triggering 'max_tokens' Budget Termination (limit = 500)...")
    res2 = agent.run(query, max_tokens=500)
    print(f"Status: {res2['status']} | Reason: {res2['termination_reason']}")
    print(f"Answer: {res2['answer']}")

    # Test 3: max_cost budget termination
    print("\n>>> TEST 3: Triggering 'max_cost' Budget Termination (limit = $0.00005)...")
    res3 = agent.run(query, max_cost=0.00005)
    print(f"Status: {res3['status']} | Reason: {res3['termination_reason']}")
    print(f"Answer: {res3['answer']}")

    # Test 4: wall_clock budget termination
    print("\n>>> TEST 4: Triggering 'wall_clock' Budget Termination (limit = 0.005s)...")
    res4 = agent.run(query, max_time_seconds=0.005)
    print(f"Status: {res4['status']} | Reason: {res4['termination_reason']}")
    print(f"Answer: {res4['answer']}")
    print("=" * 80)


if __name__ == "__main__":
    demo_budget_termination()
