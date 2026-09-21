# Week 7: AI Agents vs Fixed Workflows

## 1. Learning Objectives
- Construct a hand-built **ReAct (Reason + Act) Agent** with visible reasoning traces (`Thought` → `Action` → `Observation` → `Final Answer`).
- Construct an equivalent **Deterministic Fixed DAG Workflow** for structured policy lookups.
- Define strictly typed tool contracts using Pydantic and Enums (`get_employee_record`, `get_handbook_rule`, `get_jurisdiction_rules`).
- Race both architectures to produce **The 8 Numbers Benchmark Table** (measuring Pass Rate, Latency, Token Usage, and Cost).
- Apply the **Engineering Decision Rule**: When to deploy an agent vs a fixed workflow.

---

## 2. Theoretical Background

### What is the ReAct Pattern?
The ReAct framework interweaves reasoning traces with action execution:
1. **Thought**: The model plans the next lookup step.
2. **Action**: The model emits a structured tool call.
3. **Observation**: The runtime executes the tool and returns the JSON payload.
4. **Thought / Synthesis**: The model consumes the observation to decide the next step or synthesize the final response.

### Why do Multi-Lap Agents Cost So Much?
In standard ReAct loops, every new lap re-transmits the complete conversation history and all tool schemas over the network. Over a 3-turn reasoning chain, input tokens compound quadratically, driving token consumption **~8x higher** and latency **~3x higher** than a linear pipeline.

### The Engineering Decision Rule
> **Decision Rule**: *Use an agent only when the execution path dynamically varies with input.*

- **Use a Fixed Workflow** when: The business logic is a known Directed Acyclic Graph (DAG) — e.g., Fetch employee → Fetch handbook → Fetch statutory overrides → Synthesize. Workflows are faster, cheaper, and eliminate tool calling hallucination.
- **Use an Autonomous Agent** when: Lookups are unstructured, ambiguous, and non-deterministic — e.g., cross-referencing conflicting informal manager emails with unindexed severance exceptions, or dynamic multi-turn dispute arbitrations requiring clarifying questions.

---

## 3. Code Architecture

- [`tool_registry.py`](file:///d:/learn-rag/curriculum/week_07_agent_vs_fixed_workflow/tool_registry.py): Three strictly disjoint tools with typed parameters.
- [`react_agent.py`](file:///d:/learn-rag/curriculum/week_07_agent_vs_fixed_workflow/react_agent.py): Transparent multi-lap ReAct loop recording thoughts, actions, and observations.
- [`fixed_workflow.py`](file:///d:/learn-rag/curriculum/week_07_agent_vs_fixed_workflow/fixed_workflow.py): High-throughput deterministic DAG execution.
- [`run_race_benchmark.py`](file:///d:/learn-rag/curriculum/week_07_agent_vs_fixed_workflow/run_race_benchmark.py): The benchmark script generating the comparative 8 Numbers Table.

---

## 4. How to Run

```powershell
python curriculum/week_07_agent_vs_fixed_workflow/run_race_benchmark.py
```
