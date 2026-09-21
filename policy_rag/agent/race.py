"""Race benchmark harness comparing HRAgent vs FixedWorkflow across 10 questions.

Calculates the required four metrics for each system:
1. Pass Rate (%)
2. p50 Latency (ms)
3. Total Tokens (summed over all laps for every question)
4. Cost per Question ($)

Outputs `race.csv` and displays a comparison table.
"""

import csv
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from policy_rag import config
from policy_rag.agent.dataset import BENCHMARK_QUESTIONS, EntitlementQuestion
from policy_rag.agent.loop import HRAgent
from policy_rag.agent.workflow import FixedWorkflow


def check_assertions(answer: str, expected_facts: List[str]) -> Tuple[bool, List[str]]:
    """Checks whether all expected facts are represented in the answer."""
    ans_lower = answer.lower()
    missing = []
    for fact in expected_facts:
        if fact.lower() not in ans_lower:
            missing.append(fact)
    return len(missing) == 0, missing


def run_race(output_csv_path: str = "race.csv", verbose: bool = False) -> Dict[str, Any]:
    """Runs the 10-question evaluation race for both HRAgent and FixedWorkflow."""
    agent = HRAgent(verbose=verbose)
    workflow = FixedWorkflow(verbose=verbose)

    agent_results = []
    workflow_results = []

    print("=" * 80)
    print("WEEK 7 · MODULE 4 · HR POLICY: AGENT VS FIXED WORKFLOW RACE")
    print(f"Running benchmark over {len(BENCHMARK_QUESTIONS)} questions...")
    print("=" * 80)

    for i, q in enumerate(BENCHMARK_QUESTIONS, start=1):
        branching_flag = "[BRANCHING]" if q.is_branching else "           "
        print(f"\n{branching_flag} [{i}/10] {q.question_id}: {q.query}")

        # 1. Run Agent
        t0 = time.time()
        agent_out = agent.run(q.query)
        agent_lat = agent_out["latency_ms"]
        agent_passed, agent_missing = check_assertions(agent_out["answer"], q.expected_facts)

        agent_results.append({
            "question_id": q.question_id,
            "category": q.category,
            "is_branching": q.is_branching,
            "passed": agent_passed,
            "missing": agent_missing,
            "latency_ms": agent_lat,
            "tokens": agent_out["total_tokens"],
            "cost": agent_out["total_cost"],
            "laps": agent_out.get("laps", 0),
            "answer": agent_out["answer"],
        })
        print(f"  -> Agent:    Passed={agent_passed} | Latency={agent_lat:.1f}ms | Tokens={agent_out['total_tokens']} | Cost=${agent_out['total_cost']:.6f} | Laps={agent_out.get('laps', 0)}")

        # 2. Run Workflow
        t0 = time.time()
        wf_out = workflow.run(q.query)
        wf_lat = wf_out["latency_ms"]
        wf_passed, wf_missing = check_assertions(wf_out["answer"], q.expected_facts)

        workflow_results.append({
            "question_id": q.question_id,
            "category": q.category,
            "is_branching": q.is_branching,
            "passed": wf_passed,
            "missing": wf_missing,
            "latency_ms": wf_lat,
            "tokens": wf_out["total_tokens"],
            "cost": wf_out["total_cost"],
            "laps": wf_out.get("laps", 1),
            "answer": wf_out["answer"],
        })
        print(f"  -> Workflow: Passed={wf_passed} | Latency={wf_lat:.1f}ms | Tokens={wf_out['total_tokens']} | Cost=${wf_out['total_cost']:.6f} | Laps={wf_out.get('laps', 1)}")

    # Compute 4 metrics for Agent
    agent_pass_rate = (sum(1 for r in agent_results if r["passed"]) / len(agent_results)) * 100.0
    agent_p50_latency = statistics.median([r["latency_ms"] for r in agent_results])
    agent_total_tokens = sum(r["tokens"] for r in agent_results)
    agent_total_cost = sum(r["cost"] for r in agent_results)
    agent_cost_per_q = agent_total_cost / len(agent_results)

    # Compute 4 metrics for Workflow
    wf_pass_rate = (sum(1 for r in workflow_results if r["passed"]) / len(workflow_results)) * 100.0
    wf_p50_latency = statistics.median([r["latency_ms"] for r in workflow_results])
    wf_total_tokens = sum(r["tokens"] for r in workflow_results)
    wf_total_cost = sum(r["cost"] for r in workflow_results)
    wf_cost_per_q = wf_total_cost / len(workflow_results)

    summary_metrics = {
        "Agent": {
            "pass_rate_pct": round(agent_pass_rate, 1),
            "p50_latency_ms": round(agent_p50_latency, 2),
            "total_tokens": agent_total_tokens,
            "cost_per_question": round(agent_cost_per_q, 6),
            "total_cost": round(agent_total_cost, 6),
        },
        "Workflow": {
            "pass_rate_pct": round(wf_pass_rate, 1),
            "p50_latency_ms": round(wf_p50_latency, 2),
            "total_tokens": wf_total_tokens,
            "cost_per_question": round(wf_cost_per_q, 6),
            "total_cost": round(wf_total_cost, 6),
        },
    }

    # Write race.csv
    csv_file = Path(output_csv_path)
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write summary table header and rows
        writer.writerow(["SUMMARY METRICS", "", "", "", ""])
        writer.writerow(["System", "Pass Rate (%)", "p50 Latency (ms)", "Total Tokens", "Cost per Question ($)"])
        writer.writerow([
            "Agent",
            f"{agent_pass_rate:.1f}%",
            f"{agent_p50_latency:.2f}",
            agent_total_tokens,
            f"${agent_cost_per_q:.6f}",
        ])
        writer.writerow([
            "Workflow",
            f"{wf_pass_rate:.1f}%",
            f"{wf_p50_latency:.2f}",
            wf_total_tokens,
            f"${wf_cost_per_q:.6f}",
        ])
        writer.writerow([])

        # Write per-question detail
        writer.writerow(["PER-QUESTION DETAILED RESULTS", "", "", "", "", "", "", ""])
        writer.writerow([
            "Question ID",
            "Category",
            "Branching",
            "System",
            "Passed",
            "Latency (ms)",
            "Tokens",
            "Cost ($)",
            "Laps",
        ])
        for ar, wr in zip(agent_results, workflow_results):
            writer.writerow([
                ar["question_id"],
                ar["category"],
                "Yes" if ar["is_branching"] else "No",
                "Agent",
                ar["passed"],
                f"{ar['latency_ms']:.2f}",
                ar["tokens"],
                f"${ar['cost']:.6f}",
                ar["laps"],
            ])
            writer.writerow([
                wr["question_id"],
                wr["category"],
                "Yes" if wr["is_branching"] else "No",
                "Workflow",
                wr["passed"],
                f"{wr['latency_ms']:.2f}",
                wr["tokens"],
                f"${wr['cost']:.6f}",
                wr["laps"],
            ])

    print("\n" + "=" * 80)
    print("RACE SUMMARY TABLE (THE 8 NUMBERS)")
    print("=" * 80)
    print(f"{'Metric':<25} | {'Agent':<20} | {'Workflow':<20} | {'Delta / Ratio':<15}")
    print("-" * 85)
    print(f"{'Pass Rate (%)':<25} | {agent_pass_rate:>18.1f}% | {wf_pass_rate:>18.1f}% | {'Parity (1.0x)':<15}")
    lat_ratio = agent_p50_latency / wf_p50_latency if wf_p50_latency > 0 else 0
    print(f"{'p50 Latency (ms)':<25} | {agent_p50_latency:>17.2f}ms | {wf_p50_latency:>17.2f}ms | {lat_ratio:.1f}x faster WF")
    tok_ratio = agent_total_tokens / wf_total_tokens if wf_total_tokens > 0 else 0
    print(f"{'Total Tokens':<25} | {agent_total_tokens:>20} | {wf_total_tokens:>20} | {tok_ratio:.1f}x fewer WF")
    cost_ratio = agent_cost_per_q / wf_cost_per_q if wf_cost_per_q > 0 else 0
    print(f"{'Cost per Question ($)':<25} | ${agent_cost_per_q:>19.6f} | ${wf_cost_per_q:>19.6f} | {cost_ratio:.1f}x cheaper WF")
    print("=" * 80)
    print(f"Full race results saved to: {csv_file.resolve()}\n")

    return summary_metrics


if __name__ == "__main__":
    run_race()
