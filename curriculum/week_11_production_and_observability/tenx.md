# The 10x Scale Plan

At 10x today's query volume, **the OpenAI RPM (Requests Per Minute) limit breaks first.** 

We are currently at ~1,500 queries/day (peak 30 queries/minute). At 10x (300 queries/minute), we will exceed our current Tier 1 rate limit of 200 RPM for the LLM model, causing systemic HTTP 429 Too Many Requests failures, long before our local ChromaDB or FastAPI server face any CPU/Memory bottlenecks.
