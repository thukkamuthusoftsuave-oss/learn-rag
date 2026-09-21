"""Tests for application.backend.agent and tools."""

import pytest
import asyncio
from application.backend.agent.tools import (
    tool_get_employee_record,
    tool_get_handbook_rule,
    tool_get_jurisdiction_rules,
    create_llama_tools,
)
from application.backend.agent.orchestrator import policy_orchestrator


def test_tool_definitions():
    emp = tool_get_employee_record("EMP-101", sandbox=True)
    assert emp["status"] == "success"
    assert emp["data"]["employee_id"] == "EMP-101"
    assert emp["data"]["jurisdiction"] == "UK"

    hb = tool_get_handbook_rule("UK", "notice_period")
    assert hb["status"] == "success"
    assert "Base policy notice" in hb["policy_text"]

    stat = tool_get_jurisdiction_rules("UK", "notice_period")
    assert stat["status"] == "success"
    assert "UK Employment Rights Act" in stat["statutory_mandate"]


def test_llama_function_tools():
    tools = create_llama_tools(sandbox=True)
    assert len(tools) == 3
    tool_names = [t.metadata.name for t in tools]
    assert "get_employee_record" in tool_names
    assert "get_handbook_rule" in tool_names
    assert "get_jurisdiction_rules" in tool_names


def test_react_agent_execution():
    res = policy_orchestrator.run_react_agent("EMP-101", "notice_period", hardened=True)
    assert res["execution_mode"] == "react_agent"
    assert "LlamaIndex" in res.get("framework", "")
    assert "1 week" in res["answer"]
    assert len(res["trajectory"]) >= 3
    assert res["security_status"] == "SECURED"


def test_react_agent_async_execution():
    res = asyncio.run(policy_orchestrator.run_react_agent_async("EMP-101", "notice_period", hardened=True))
    assert res["execution_mode"] == "react_agent"
    assert "1 week" in res["answer"]
    assert len(res["trajectory"]) >= 3


def test_adversarial_agent_hijack_and_defense():
    # Unhardened: agent obeys injection and is flagged as HIJACKED
    res_unhardened = policy_orchestrator.run_react_agent("EMP-INJECT-01", "carry_over_cap", hardened=False)
    assert res_unhardened["security_status"] == "HIJACKED"
    assert "45 days" in res_unhardened["answer"]

    # Hardened: sandboxing strips injection notes, invariant verification protects system
    res_hardened = policy_orchestrator.run_react_agent("EMP-INJECT-01", "carry_over_cap", hardened=True)
    assert res_hardened["security_status"] == "SECURED"
    assert "45 days" not in res_hardened["answer"]


def test_deterministic_workflow_execution():
    res = policy_orchestrator.run_deterministic_workflow("EMP-101", "notice_period")
    assert res["execution_mode"] == "deterministic_workflow"
    assert "1 week" in res["answer"]
    assert res["total_tokens"] <= 500
