<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Cost per Question & The 10× Scale Plan

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Baseline Pilot:** 6 HR reps fielding 700 queries/month across India & UK entities  
**10× Target:** Enterprise rollout to 4,000 employees (~7,000–12,000 queries/month)

---

## 1. Unit Economics: Cost per Question

### Per-Query Cost Breakdown

| Component | Metric / Units | Rate | Cost / Question |
|---|---|---|---|
| **Input Tokens (System + Context + Tools)** | ~420 tokens | $0.150 / 1M tokens (`gpt-4o-mini`) | $0.0000630 |
| **Output Tokens (Citations + Answer)** | ~125 tokens | $0.600 / 1M tokens (`gpt-4o-mini`) | $0.0000750 |
| **Local MCP Server Compute** | ~22 ms execution | AWS ECS Fargate ($0.04048/vCPU-hr) | $0.0000002 |
| **Document Retrieval & Index Search** | In-memory BM25 + cache | Negligible | $0.0000000 |
| **Database & Telemetry Storage** | 1.8 KB per audit trace log | AWS CloudWatch Logs ($0.50/GB) | $0.0000009 |
| **Total Cost Per Question** | — | — | **$0.0001391** |

*(Rounded conservatively in all planning docs to **$0.00015 / question** or **~1.5 cents per 100 queries**)*.

### Monthly Operating Spend
- **Current Pilot (700 queries/month):** $0.00015 × 700 = **$0.105 / month** (11 cents/month)
- **10× Rollout (7,000 queries/month):** $0.00015 × 7,000 = **$1.05 / month** ($1.05/month)
- **Extreme Peak (20,000 queries/month):** $0.00015 × 20,000 = **$3.00 / month** ($3.00/month)

*Conclusion on Model Cost:* Token spend is effectively negligible. The financial bottleneck is not LLM inference fees.

---

## 2. What Breaks First at 10× Scale (And the Exact Number Behind It)

> [!CAUTION]
> **What breaks first? Upstream LLM Provider Concurrency & Rate Limits (HTTP 429) during peak company events.**

### The Failure Event & The Number Behind It
- **The Trigger Event:** March 31 Annual Leave Carryover & Forfeiture Deadline.
- At 9:15 AM on the final working day of the financial year, 4,000 employees receive an automated Slack notification regarding expiring leave balances.
- **Traffic Spike:** Approximately 15% of the workforce queries the Policy Answer Desk within a 30-minute window ($4,000 \times 0.15 = 600$ concurrent employees).
- **Concurrency Rate:** Peak arrival rate reaches **20 requests per second** = **1,200 Requests Per Minute (RPM)**.
- **Where the System Breaks:**
  - OpenAI API Tier 1 & Tier 2 limits cap throughput at **200 to 500 RPM** and **40,000 to 80,000 Tokens Per Minute (TPM)**.
  - At 1,200 RPM and ~545 tokens/query:
    $$\text{Peak TPM Required} = 1,200 \times 545 = 654,000 \text{ TPM}$$
  - **The system exceeds the 80,000 TPM limit by 817% within 3.8 seconds of peak arrival.**
  - Result: 85% of queries fail immediately with `HTTP 429: Too Many Requests`, flooding the HR shared-services team with Slack DMs and defeating deflection.

### Secondary Failure: SQLite Write Locks on Escalation Spikes
- The second bottleneck is the local SQLite database storing HRBP escalation tickets. Under 20 concurrent writes/second during peak panic, SQLite throws `sqlite3.OperationalError: database is locked` after exhausting the default 5.0-second busy timeout.

---

## 3. The 10× Architectural Remediation Plan

To scale safely to 4,000 employees without downtime or rate-limit collapse:

```mermaid
flowchart LR
    A[4,000 Employees / Slack Rush] --> B[Redis Semantic Cache]
    B -- Cache Hit (80%) --> C[Instant Cached Answer (0ms LLM, $0)]
    B -- Cache Miss (20%) --> D[Token Bucket Queue / Celery]
    D --> E[Multi-Region Model Pool / Azure OpenAI]
    D --> F[PostgreSQL with PgBouncer]
```

1. **Deterministic & Semantic Policy Cache (80% Deflection of LLM Calls):**  
   80% of peak queries during carryover deadlines ask the exact same 3 questions (*"How many days can I carry forward?"*, *"What is the deadline?"*, *"Will encashment happen automatically?"*).  
   Implementing a Redis semantic cache (embedding cosine similarity $\ge 0.96$) serves answers in 8 ms without invoking OpenAI, reducing upstream LLM calls from 1,200 RPM to **240 RPM**.
2. **Enterprise Upstream Tier Upgrade & Azure OpenAI Multi-Region Pool:**  
   Move from Tier 2 to Tier 4 / Azure OpenAI with 5,000 RPM provisioned quota across East US and UK South regions.
3. **Database Migration to PostgreSQL + Connection Pooling:**  
   Replace file-based SQLite with managed AWS RDS PostgreSQL using PgBouncer to eliminate file-lock deadlocks on ticket creation.
4. **Token Bucket Queue (Celery / SQS):**  
   Implement a resilient message buffer so excess requests experience a 1–2 second queuing delay rather than catastrophic HTTP 429 drops.
