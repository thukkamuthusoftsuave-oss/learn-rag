"""Tests for application.backend.observability telemetry."""

from application.backend.observability.telemetry import telemetry_service


def test_record_trace_and_metrics():
    test_trace = {
        "trace_id": "test-12345",
        "query": "What is the notice period for EMP-101 in UK?",
        "answer": "1 week statutory notice. [[HR-207 Section 4.5]]",
        "retrieved_chunks": [{"section": "HR-207 Section 4.5"}],
        "latency_ms": 45.2,
        "tokens_used": 650,
        "security_status": "VERIFIED"
    }
    telemetry_service.record_trace(test_trace)

    traces = telemetry_service.get_traces(limit=10)
    assert len(traces) > 0

    summary = telemetry_service.get_metrics_summary()
    assert summary["total_queries"] > 0
    assert summary["mean_latency_ms"] > 0
    assert "CORRECT" in summary["error_distribution"]
