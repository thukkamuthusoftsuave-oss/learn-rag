"""Automated test suite for Week 7 HR Policy Agent and Fixed Workflow.

Validates:
1. Third tool design (single job, typed enum parameters, non-overlapping descriptions).
2. Four budgets enforcement in the agent loop (max iterations, max tokens, max cost, wall-clock).
3. Fixed workflow implementation (identical task, same tools, same contract, no loop).
4. Ten entitlement questions evaluation race and `race.csv` generation.
5. Bonus challenge memory persistence across process restart and sliding window buffer.
"""

import json
from pathlib import Path

import pytest

from policy_rag.agent.budgets import BudgetTracker, BudgetExceededError
from policy_rag.agent.dataset import BENCHMARK_QUESTIONS
from policy_rag.agent.enums import JurisdictionEnum, PolicyTopicEnum
from policy_rag.agent.loop import HRAgent
from policy_rag.agent.memory import ConversationMemory, PersistentFactStore
from policy_rag.agent.race import run_race
from policy_rag.agent.tools import (
    TOOL_DEFINITIONS,
    get_employee_record,
    get_handbook_rule,
    get_jurisdiction_rules,
)
from policy_rag.agent.workflow import FixedWorkflow


# --- 1. Tool Design & Non-Overlapping Descriptions Tests ---------------------

def test_third_tool_single_job_and_enums():
    """Validates that the third tool requires JurisdictionEnum and performs a single job."""
    # UK Notice Period statutory rule lookup
    res = get_jurisdiction_rules(JurisdictionEnum.UK, PolicyTopicEnum.NOTICE_PERIOD)
    assert res["status"] == "success"
    assert res["jurisdiction"] == "UK"
    assert "statutory_rules" in res
    assert "Employment Rights Act" in res["statutory_rules"]["statutory_reference"]

    # Parameter enum validation in tool schema
    tool_3_schema = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_jurisdiction_rules")
    params = tool_3_schema["function"]["parameters"]["properties"]
    assert "jurisdiction" in params
    assert "topic" in params
    assert params["jurisdiction"]["enum"] == [j.value for j in JurisdictionEnum]
    assert params["topic"]["enum"] == [t.value for t in PolicyTopicEnum]


def test_tool_descriptions_zero_overlap():
    """Validates that tool descriptions explicitly partition duties without overlap."""
    t1 = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_employee_record")
    t2 = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_handbook_rule")
    t3 = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_jurisdiction_rules")

    d1 = t1["function"]["description"]
    d2 = t2["function"]["description"]
    d3 = t3["function"]["description"]

    # Tool 1 explicitly disclaims handbook rules and statutory laws
    assert "NOT return company handbook policies or statutory labor laws" in d1
    # Tool 2 explicitly disclaims employee records and statutory labor regulations
    assert "NOT return individual employee records or local statutory labor regulations" in d2
    # Tool 3 explicitly disclaims company handbook rules and employee records
    assert "NOT retrieve company handbook rules or employee records" in d3


# --- 2. All Four Budgets Enforcement Tests -----------------------------------

def test_budget_enforcement_max_iterations():
    """Validates that max_iterations stops the loop cleanly without spinning."""
    agent = HRAgent(verbose=False)
    res = agent.run("What is the notice period for EMP-101 in the UK?", max_iterations=1)
    assert res["status"] == "budget_exceeded"
    assert res["termination_reason"] == "budget_exceeded"
    assert "max_iterations" in res["answer"]
    assert res["laps"] == 1


def test_budget_enforcement_max_tokens():
    """Validates that max_tokens stops the loop cleanly."""
    agent = HRAgent(verbose=False)
    res = agent.run("What is the notice period for EMP-101 in the UK?", max_tokens=400)
    assert res["status"] == "budget_exceeded"
    assert res["termination_reason"] == "budget_exceeded"
    assert "max_tokens" in res["answer"]


def test_budget_enforcement_max_cost():
    """Validates that max_cost stops the loop cleanly."""
    agent = HRAgent(verbose=False)
    res = agent.run("What is the notice period for EMP-101 in the UK?", max_cost=0.00005)
    assert res["status"] == "budget_exceeded"
    assert res["termination_reason"] == "budget_exceeded"
    assert "max_cost" in res["answer"]


def test_budget_enforcement_wall_clock():
    """Validates that wall_clock time limit stops the loop cleanly."""
    agent = HRAgent(verbose=False)
    res = agent.run("What is the notice period for EMP-101 in the UK?", max_time_seconds=0.005)
    assert res["status"] == "budget_exceeded"
    assert res["termination_reason"] == "budget_exceeded"
    assert "wall_clock" in res["answer"]


# --- 3. Fixed Workflow Implementation & Contract Tests -----------------------

def test_fixed_workflow_output_contract():
    """Validates that FixedWorkflow returns the exact same envelope contract without a loop."""
    wf = FixedWorkflow(verbose=False)
    res = wf.run("What is the notice period for EMP-101 in the UK?")
    assert res["status"] == "success"
    assert res["laps"] == 1  # No loop
    assert len(res["steps"]) == 4  # 4 explicit steps
    assert "Alice Smith" in res["answer"]
    assert "1 week" in res["answer"]
    assert res["total_tokens"] > 0
    assert res["total_cost"] > 0.0
    assert res["latency_ms"] > 0.0


# --- 4. Race Benchmark & Ten Questions Verification --------------------------

def test_ten_benchmark_questions_structure():
    """Validates dataset has 10 questions and at least 3 tenure/jurisdiction branching cases."""
    assert len(BENCHMARK_QUESTIONS) == 10
    branching_count = sum(1 for q in BENCHMARK_QUESTIONS if q.is_branching)
    assert branching_count >= 3, f"Expected >= 3 branching questions, got {branching_count}"


def test_race_execution_and_csv_generation(tmp_path):
    """Executes the race benchmark and verifies generated race.csv."""
    test_csv = tmp_path / "test_race.csv"
    metrics = run_race(output_csv_path=str(test_csv), verbose=False)

    assert "Agent" in metrics
    assert "Workflow" in metrics
    assert metrics["Agent"]["pass_rate_pct"] == 100.0
    assert metrics["Workflow"]["pass_rate_pct"] == 100.0
    # Workflow uses fewer tokens and is faster
    assert metrics["Workflow"]["total_tokens"] < metrics["Agent"]["total_tokens"]
    assert metrics["Workflow"]["p50_latency_ms"] < metrics["Agent"]["p50_latency_ms"]

    assert test_csv.exists()
    content = test_csv.read_text(encoding="utf-8")
    assert "SUMMARY METRICS" in content
    assert "Agent" in content
    assert "Workflow" in content


# --- 5. Bonus Challenge: Persistence & Sliding Window Tests ------------------

def test_bonus_persistence_across_restart(tmp_path):
    """Validates that employee jurisdiction survives a simulated process restart."""
    mem_file = tmp_path / "test_memory.json"
    store1 = PersistentFactStore(filepath=mem_file)
    store1.set_fact("EMP-105_jurisdiction", "US")

    # Simulate process restart by destroying store1 and creating fresh store2
    del store1
    store2 = PersistentFactStore(filepath=mem_file)
    assert store2.get_fact("EMP-105_jurisdiction") == "US"


def test_bonus_sliding_window_memory():
    """Validates that sliding window summarizes turns beyond the active window."""
    mem = ConversationMemory(window_size=3)
    for i in range(1, 10):
        mem.add_turn(f"User query turn {i} regarding carry-over cap", f"Assistant answer turn {i}")

    # Active verbatim window should not exceed window_size * 2 messages
    assert len(mem.turns) <= 6
    # Executive summary must contain compressed earlier context
    assert len(mem.summary) > 0
    assert "Earlier topics" in mem.summary
