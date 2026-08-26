"""The assistant: the answer service and multi-turn chat sessions.

Submodules are imported on demand so conversation state can be used - and
tested - without loading the vector store and the embedding model:

- ``service`` - ``answer``: the single path every question takes
- ``session`` - ``ChatSession`` and follow-up condensation
"""

__all__ = ["service", "session"]
