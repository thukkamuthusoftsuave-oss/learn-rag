"""Model-free checks for the OpenRouter LLM adapter."""


def test_openrouter_model_slug_uses_chat_metadata():
    """Generic OpenRouter slugs must use chat completions, not completions."""
    from policy_rag.retrieval.engine import OpenRouterLLM

    llm = OpenRouterLLM(
        model="google/gemini-2.5-flash-lite",
        api_base="https://openrouter.ai/api/v1",
        api_key="not-a-real-key",
        context_window=32_768,
        max_tokens=512,
    )

    assert llm.metadata.model_name == "google/gemini-2.5-flash-lite"
    assert llm.metadata.is_chat_model is True
    assert llm.metadata.context_window == 32_768


def test_openrouter_key_controls_mock_status(monkeypatch):
    """The status API must report a mock model only when its own key is absent."""
    from policy_rag import config
    from policy_rag.retrieval import engine

    monkeypatch.setattr(config, "openrouter_api_key", lambda: "test-key")
    assert engine.llm_is_mocked() is False
    assert engine.active_llm_name() == config.LLM_MODEL_NAME
