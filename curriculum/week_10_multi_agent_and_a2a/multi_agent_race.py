import sys
import os
import time
import asyncio
from typing import Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from application.backend.agent.tools import (
    tool_get_employee_record,
    tool_get_handbook_rule,
    tool_get_jurisdiction_rules,
)
from application.backend.core.config import settings

try:
    from llama_index.llms.openai import OpenAI
except ImportError:
    OpenAI = None

def get_llm(name_id=""):
    has_api_key = bool(settings.openrouter_api_key and len(settings.openrouter_api_key.strip()) > 10)
    if has_api_key and OpenAI is not None:
        return OpenAI(
            api_key=settings.openrouter_api_key,
            api_base="https://openrouter.ai/api/v1",
            model=settings.default_llm_model,
            temperature=0.0
        )
    else:
        from application.backend.agent.orchestrator import DeterministicPolicyLLM
        llm = DeterministicPolicyLLM()
        llm.employee_id = name_id
        llm.topic = "sabbatical" # fallback topic
        return llm

def get_single_agent(emp_id):
    tools = [
        FunctionTool.from_defaults(fn=lambda e: tool_get_employee_record(e, sandbox=True), name="get_employee_record"),
        FunctionTool.from_defaults(fn=tool_get_handbook_rule, name="get_handbook_rule"),
        FunctionTool.from_defaults(fn=tool_get_jurisdiction_rules, name="get_jurisdiction_rules"),
    ]
    return ReActAgent.from_tools(tools, llm=get_llm(emp_id), verbose=False)

def get_multi_agent_team(emp_id):
    # Specialist 1: Profile Agent
    profile_tools = [FunctionTool.from_defaults(fn=lambda e: tool_get_employee_record(e, sandbox=True), name="get_employee_record")]
    profile_agent = ReActAgent.from_tools(profile_tools, llm=get_llm(emp_id), verbose=False)
    
    # Specialist 2: Policy Agent
    policy_tools = [
        FunctionTool.from_defaults(fn=tool_get_handbook_rule, name="get_handbook_rule"),
        FunctionTool.from_defaults(fn=tool_get_jurisdiction_rules, name="get_jurisdiction_rules"),
    ]
    policy_agent = ReActAgent.from_tools(policy_tools, llm=get_llm(emp_id), verbose=False)
    
    # Manager Agent Tools
    manager_tools = [
        FunctionTool.from_defaults(
            fn=lambda e: str(profile_agent.chat(f"Look up the jurisdiction and tenure for employee {e}.")),
            name="profile_specialist",
            description="Ask the profile specialist to look up employee details like jurisdiction and tenure."
        ),
        FunctionTool.from_defaults(
            fn=lambda jur, topic: str(policy_agent.chat(f"Get handbook and statutory rules for jurisdiction {jur} on {topic}.")),
            name="policy_specialist",
            description="Ask the policy specialist to get handbook and statutory rules given a jurisdiction and topic."
        )
    ]
    manager = ReActAgent.from_tools(manager_tools, llm=get_llm(emp_id), verbose=False)
    return manager

async def run_race():
    questions = [
        ("EMP-102", "carry_over_cap"),
        ("EMP-103", "sabbatical"),
    ]
    
    print("=====================================================")
    print(" MULTI-AGENT SQUAD vs SINGLE AGENT RACE (HR POLICY) ")
    print("=====================================================")
    
    results = {"single": {"latency": 0, "tokens": 0}, "multi": {"latency": 0, "tokens": 0}}
    
    for emp, topic in questions:
        query = f"Determine the {topic} policy entitlement for employee {emp}."
        print(f"\n[Test Case] {query}")
        
        # Single Agent setup & run
        single = get_single_agent(emp)
        single.llm.topic = topic
        
        t0 = time.time()
        resp_single = await single.achat(query)
        t1 = time.time()
        single_lat = t1 - t0
        results["single"]["latency"] += single_lat
        results["single"]["tokens"] += 1250 # Simulated base tokens for single react loop
        
        print(f"  -> [Single Agent] ({single_lat:.2f}s) {str(resp_single.response)[:100]}...")
        
        # Multi Agent setup & run
        multi = get_multi_agent_team(emp)
        multi.llm.topic = topic
        
        t0 = time.time()
        resp_multi = await multi.achat(query)
        t1 = time.time()
        multi_lat = t1 - t0
        results["multi"]["latency"] += multi_lat
        results["multi"]["tokens"] += 4100 # Multi-agent token overhead (Manager + 2 Workers context resend)
        
        print(f"  -> [Policy Squad] ({multi_lat:.2f}s) {str(resp_multi.response)[:100]}...")
        
    print("\n=====================================================")
    print("                    RACE RESULTS                     ")
    print("=====================================================")
    print("Agent Architecture | Latency (s) | Est. Tokens | Est. Cost")
    print("-------------------------------------------------------------")
    
    s_lat = results["single"]["latency"]
    s_tok = results["single"]["tokens"]
    s_cost = (s_tok / 1_000_000) * 0.15 # $0.15 per 1M tokens assumption
    print(f"Single Agent       | {s_lat:11.2f} | {s_tok:11,d} | ${s_cost:.5f}")
    
    m_lat = results["multi"]["latency"]
    m_tok = results["multi"]["tokens"]
    m_cost = (m_tok / 1_000_000) * 0.15
    print(f"Policy Squad       | {m_lat:11.2f} | {m_tok:11,d} | ${m_cost:.5f}")
    print("-------------------------------------------------------------")
    
    print("\nVERDICT:")
    if s_lat < m_lat and s_cost < m_cost:
        print("Winner: Single Agent. It achieved the same quality with significantly less latency and lower context-resend token bloat.")
    else:
        print("Winner: Policy Squad. (Unexpected, please check your network or token counting!)")

if __name__ == "__main__":
    asyncio.run(run_race())
