"""Single Entry Point for Week 12 Capstone: Policy Answer Desk.
Runs end-to-end interactive CLI, automated evaluation suite, or serves as a standalone runner.
"""

import asyncio
import argparse
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from curriculum.week_12_capstone.capstone_agent import capstone_agent
from curriculum.week_12_capstone.run_capstone_eval import run_full_eval_suite


async def run_single_query(query: str, employee_id: str):
    print("\n" + "=" * 70)
    print(f"  POLICY ANSWER DESK - INQUIRY RUNNER")
    print(f"  Employee ID: {employee_id}")
    print(f"  Query:       {query}")
    print("=" * 70 + "\n")

    res = await capstone_agent.answer_policy_query(query=query, employee_id=employee_id)

    print(f"Status:   {res['status']}")
    print(f"Trace ID: {res['trace_id']}")
    print(f"Latency:  {res['latency_ms']} ms | Tokens: {res.get('tokens_used', 'N/A')} | Cost: ${res.get('cost_usd', 0.0):.6f}\n")

    if res.get("resolved_profile"):
        prof = res["resolved_profile"]
        print(f"Resolved HR Profile: {prof.get('name')} | Entity: {prof.get('entity')} | Grade: {prof.get('grade')}")

    print("\nAnswer Output:")
    print("-" * 70)
    print(res["answer"])
    print("-" * 70)

    if res.get("citations"):
        print("\nCitations:")
        for c in res["citations"]:
            print(f"  • {c}")

    if res.get("escalated"):
        print(f"\n[!] Escalation Ticket Created: {res.get('ticket_id')}")

    print("\n" + "=" * 70 + "\n")


async def run_interactive():
    print("=" * 70)
    print("  WELCOME TO POLICY ANSWER DESK (WEEK 12 CAPSTONE)")
    print("  Available test employees: EMP-IND-301, EMP-UK-601, EMP-IND-102, EMP-UK-304, EMP-IND-701")
    print("  Type 'exit' to quit, 'eval' to run the 30-case integration eval suite.")
    print("=" * 70 + "\n")

    current_emp = "EMP-IND-301"

    while True:
        try:
            print(f"[Current Employee: {current_emp}]")
            query = input("Ask a policy question (or switch employee with 'emp <ID>'): ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting Policy Answer Desk. Goodbye!")
                break
            if query.lower() == "eval":
                await run_full_eval_suite()
                continue
            if query.lower().startswith("emp "):
                current_emp = query.split()[1].strip().upper()
                print(f"Switched active employee to: {current_emp}\n")
                continue

            await run_single_query(query, current_emp)

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break


def main():
    parser = argparse.ArgumentParser(description="Policy Answer Desk - Capstone Entry Point")
    parser.add_argument("--query", "-q", type=str, help="Policy question to evaluate")
    parser.add_argument("--employee", "-e", type=str, default="EMP-IND-301", help="Employee ID (e.g. EMP-IND-301, EMP-UK-601)")
    parser.add_argument("--eval", action="store_true", help="Run the full 30-case evaluation suite")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive policy inquiry CLI")

    args = parser.parse_args()

    if args.eval:
        asyncio.run(run_full_eval_suite())
    elif args.query:
        asyncio.run(run_single_query(args.query, args.employee))
    elif args.interactive or len(sys.argv) == 1:
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
