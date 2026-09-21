# Enterprise Policy Assistant — Next.js Modern Frontend

A modern, high-aesthetic web interface for the Enterprise Policy Assistant (HR-207), built with **Next.js (App Router)**, **React**, **TypeScript**, and **Tailwind CSS**.

---

## Features

1. **Policy Chat Assistant**:
   - Multi-turn conversational interface with query condensation visualizer.
   - Dynamic jurisdiction filtering (US, UK, EMEA, APAC, LATAM, NA, All).
   - Hybrid RAG toggle (Dense BGE + Sparse BM25 via Reciprocal Rank Fusion).
   - Expandable source citation drawers displaying chunk texts, similarity scores, and section anchors.
   - Live execution envelopes displaying latency (ms), token usage, and security status.

2. **Agent vs. Fixed Workflow Inspector**:
   - Compare autonomous ReAct agent reasoning loops with deterministic single-pass DAG workflows.
   - Step-by-step trajectory viewer with explicit `Thought`, `Action`, and `Observation` inspection.
   - Comparative token usage and latency metrics.

3. **Indirect Prompt Injection Defense Sandbox**:
   - Live adversarial simulation console.
   - Preset attacks (`URGENT AUDIT OVERRIDE`, `GOLDEN PARACHUTE SYSTEM NOTICE`).
   - Toggle between Unhardened Baseline (demonstrating hijack) and Hardened 4-Layer Defense (neutralizing attacks).
   - Visual breakdown across all 4 defense layers:
     - Layer 1: Structural XML Isolation Boundaries
     - Layer 2: Heuristic Regex Pattern Scanner
     - Layer 3: Least-Privilege Sandboxing
     - Layer 4: Policy Invariant Post-Guards

4. **Observability & Analytics Dashboard**:
   - Telemetry overview: Total Queries, Mean Latency, p99 Latency, and Estimated Costs.
   - Real-time Error Taxonomy breakdown (`CORRECT`, `CORRECT_REFUSAL`, `RETRIEVAL_FAILURE`, `GENERATION_FAILURE`).
   - Audit stream table of recent query traces.
   - One-click Vector Store Re-indexing button.

---

## Getting Started

```powershell
# From application/frontend directory
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser. Ensure the FastAPI backend is running on `http://localhost:8000`.
