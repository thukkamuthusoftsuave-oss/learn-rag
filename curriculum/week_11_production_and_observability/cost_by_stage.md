# Cost Per Query Breakdown (Trace 84f92a)

**Total Cost per Query:** $0.00030

### Split by Stage:
1. **Retrieval (Vector DB Search):** $0.00000 
   *(We run ChromaDB locally, so embedding and retrieval incurs no API cost, only compute time)*
2. **Generation (LLM):** $0.00025
   *(Using gpt-4o-mini API at ~$0.15/1M input tokens. This step dominates our variable costs due to context window size)*
3. **Tools (HRIS Server / API):** $0.00005
   *(Small overhead from executing the external API and standardizing the JSON payload)*

### Analysis
If we need to optimize costs, our first target must be Generation. We can implement Semantic Caching to intercept repeat queries (like "what is the notice period for London") before they ever reach the LLM, reducing the generation cost to $0.00000 for cache hits.
