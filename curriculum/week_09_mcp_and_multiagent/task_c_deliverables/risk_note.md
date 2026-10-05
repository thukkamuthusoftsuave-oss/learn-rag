**HRIS Server Third-Party Risk Note**
1. **Who wrote it:** The HR People Ops engineering team.
2. **What it reaches:** The production HRIS PostgreSQL database containing PII and payroll data.
3. **What it logs:** Currently logs all incoming employee ID queries, exposing potentially sensitive investigation patterns.
4. **Stolen Token Impact:** A stolen MCP client token could allow arbitrary enumeration of employee grade bands and leave balances across the entire company.
5. **Decision:** DO NOT SHIP until the token is strictly scoped to the agent's authorized service account limits and query logging is anonymized.
