# Week 10: Multi-Agent & A2A — With Evidence, Not Fashion

## What this week is about
“Multi-agent” is one of the most hyped ideas in AI right now. This week we ran the honest experiment: building a small team of specialist agents (the "Policy Squad"), racing it against the single `PolicyOrchestrator` agent on the same HR policy tests, and comparing the results to find out if it's actually worth it.

## The Experiment: Single Agent vs. Policy Squad
We raced the agents on identical test queries (e.g., determining the carry-over cap for EMP-102). 

### The Setup
* **Single Agent**: Has access to all tools (profile lookup, handbook rules, statutory rules).
* **The Policy Squad (Multi-Agent)**: 
  * A *Manager Agent* orchestrating the task.
  * A *Profile Specialist* handling HR DB lookups.
  * A *Policy Specialist* handling handbook and statutory rules.
  * *A2A (Agent-to-Agent)*: The Manager treats the specialists as tools, sending them prompts and receiving their answers.

### Results
| Agent Architecture | Quality | Latency (s) | Est. Tokens | Est. Cost ($0.15/1M) |
|-------------------|---------|-------------|-------------|----------------------|
| **Single Agent**  | High    | ~1-2x       | ~1,250      | ~$0.00018            |
| **Policy Squad**  | High    | ~3-4x       | ~4,100      | ~$0.00061            |

*Note: The specific runtime latency depends heavily on whether OpenRouter or the offline deterministic LLM is utilized. Regardless, the overhead ratio remains proportionately similar due to the number of sequential generation loops required.*

## The Verdict: Single Agent Wins
We are keeping the **Single Agent** architecture. 

**Why?**
The team of agents provided no measurable increase in answer quality for this specific task, but it incurred a massive penalty in both speed and cost. 

### The Hidden Cost of Multi-Agent
Every time the Manager agent hands off a sub-task to a Specialist, and every time the Specialist replies, the *entire context window* has to be re-sent and processed. In our Policy Squad, the Manager asks the Profile Specialist for data (Prompt + Generate), reads it back, then asks the Policy Specialist (Prompt + Generate), and finally generates the answer. This context re-send bloats the tokens exponentially compared to a Single Agent running a standard ReAct loop.

### When would Multi-Agent actually be worth it?
Multi-agent architectures are genuinely useful when:
1. **Parallelization**: Parts of the job are truly independent and can be executed simultaneously (e.g., querying five distinct enterprise databases at the exact same time).
2. **Context Window Isolation**: You are processing massive documents and need to prevent the manager's context from overflowing. You can send a document to a summarization specialist and just get the small summary back.
3. **Conflicting Instructions**: The tasks require fundamentally opposed system prompts (e.g., one agent is instructed to be extremely creatively generative, while another is instructed to act as a harsh, critical auditor).

For simple deterministic tool calling like our HR-207 Policy lookup, the single agent is undeniably superior.
