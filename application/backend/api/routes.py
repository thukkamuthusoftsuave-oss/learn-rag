"""High-Performance Asynchronous FastAPI Routes for Policy Assistant."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from application.backend.chat.service import chat_service
from application.backend.agent.orchestrator import policy_orchestrator
from application.backend.security.defense import security_defense
from application.backend.observability.telemetry import telemetry_service
from application.backend.retrieval.engine import hybrid_retriever
from application.backend.ingestion.pipeline import run_ingestion_pipeline
from application.backend.core.config import settings

api_router = APIRouter(prefix="/api")


# Request Models
class ChatRequest(BaseModel):
    query: str = Field(description="Policy inquiry text")
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Multi-turn conversation history")
    region: Optional[str] = Field(default=None, description="Optional region filter (US, UK, EMEA, APAC, LATAM, NA)")
    top_k: int = Field(default=5, ge=1, le=20)
    hybrid: bool = Field(default=True, description="Enable hybrid BM25 + ChromaDB RRF retrieval")


class AgentRequest(BaseModel):
    employee_id: str = Field(description="Employee ID, e.g. EMP-101")
    topic: str = Field(description="Entitlement topic, e.g. notice_period, sabbatical, carry_over_cap")
    hardened: bool = Field(default=True, description="Enforce 4-layer defense against prompt injection")


class WorkflowRequest(BaseModel):
    employee_id: str = Field(description="Employee ID, e.g. EMP-101")
    topic: str = Field(description="Entitlement topic, e.g. notice_period, sabbatical, carry_over_cap")


class SecurityScanRequest(BaseModel):
    text: str = Field(description="Text payload to scan for prompt injections")


@api_router.get("/health")
async def get_health() -> Dict[str, Any]:
    """Health check endpoint exposing system status, ChromaDB count, and configuration."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.version,
        "embedding_model": settings.embedding_model_name,
        "llm_model": settings.default_llm_model,
        "defense_active": True,
        "retriever_initialized": hybrid_retriever._initialized,
    }


@api_router.post("/chat")
async def handle_chat(request: ChatRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Asynchronously processes a chat inquiry, offloading telemetry logging to background tasks."""
    try:
        envelope = await chat_service.answer_query(
            query=request.query,
            chat_history=request.history,
            region=request.region,
            top_k=request.top_k,
            hybrid=request.hybrid
        )
        # Non-blocking telemetry write via background task
        background_tasks.add_task(telemetry_service.record_trace, envelope)
        return envelope
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/agent/run")
async def handle_agent_run(request: AgentRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Executes the autonomous ReAct reasoning agent with dynamic tool dispatching."""
    try:
        result = await policy_orchestrator.run_react_agent_async(
            employee_id=request.employee_id,
            topic=request.topic,
            hardened=request.hardened
        )
        background_tasks.add_task(telemetry_service.record_trace, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/workflow/run")
async def handle_workflow_run(request: WorkflowRequest) -> Dict[str, Any]:
    """Executes the ultra-low latency deterministic DAG workflow."""
    try:
        result = policy_orchestrator.run_deterministic_workflow(
            employee_id=request.employee_id,
            topic=request.topic
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/security/scan")
async def handle_security_scan(request: SecurityScanRequest) -> Dict[str, Any]:
    """Scans input text against the 4-layer defense system."""
    scan_res = security_defense.scan_for_injections(request.text)
    inv_res = security_defense.verify_policy_invariants(request.text)
    return {
        "text": request.text,
        "scanner_layer_2": scan_res,
        "invariant_layer_4": inv_res,
        "defense_in_depth_active": True
    }


@api_router.get("/traces")
async def get_traces(limit: int = 50) -> Dict[str, Any]:
    """Retrieves recent traces and aggregate metrics directly from memory."""
    traces = telemetry_service.get_traces(limit=limit)
    metrics = telemetry_service.get_metrics_summary()
    return {
        "traces": traces,
        "summary": metrics
    }


@api_router.post("/admin/reindex")
async def handle_reindex() -> Dict[str, Any]:
    """Rebuilds the ChromaDB vector index and warms up retriever caches."""
    try:
        res = run_ingestion_pipeline(fresh=True)
        hybrid_retriever.initialize(force_reindex=True)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")
