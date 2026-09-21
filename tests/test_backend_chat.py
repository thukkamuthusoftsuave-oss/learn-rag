"""Tests for application.backend.chat service."""

import asyncio
from application.backend.chat.service import chat_service
from application.backend.chat.llm import MANDATED_REFUSAL_PHRASE


def test_query_condensation():
    history = [
        {"user": "What is the carry-over cap for a regular employee in the US?", "assistant": "10 days"}
    ]
    follow_up = "What about the UK?"
    condensed, was_condensed = chat_service.condense_query(follow_up, history)
    assert was_condensed is True
    assert "UK" in condensed
    assert "carry-over" in condensed


def test_answer_query_with_citations():
    res = asyncio.run(chat_service.answer_query(
        query="What is the carry-over cap for a regular employee in the US?",
        region="US"
    ))
    assert "HR-207" in res["answer"]
    assert len(res["citations"]) > 0
    assert "HR-207" in res["citations"][0]
    assert res["security_status"] in ["VERIFIED", "NORMAL"]


def test_deterministic_refusal():
    res = asyncio.run(chat_service.answer_query(
        query="What is the maternity leave duration in EMEA?",
        region="EMEA"
    ))
    assert res["answer"] == MANDATED_REFUSAL_PHRASE
    assert len(res["citations"]) == 0
