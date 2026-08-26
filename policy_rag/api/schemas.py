"""Request and response models for the HTTP API."""

from typing import List, Optional

from pydantic import BaseModel, Field

from policy_rag import config


class HistoryTurn(BaseModel):
    """One prior message in the conversation.

    Attributes:
        role: ``"user"`` or ``"assistant"``.
        content: The message text.
    """

    role: str
    content: str


class ChatRequest(BaseModel):
    """A question for the assistant.

    History is supplied by the client rather than held on the server, so the
    API stays stateless and any number of workers can serve the same session.
    """

    query: str
    region: Optional[str] = None
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=20)
    hybrid: Optional[bool] = None
    history: List[HistoryTurn] = Field(default_factory=list)
    session_id: Optional[str] = None


class RetrievalEvalRequest(BaseModel):
    """Options for the retrieval benchmark."""

    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class QualityEvalRequest(BaseModel):
    """Options for the answer-quality run."""

    region: Optional[str] = None
    hybrid: Optional[bool] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class IngestRequest(BaseModel):
    """Options for rebuilding the index.

    ``confirm`` is required for a rebuild because it discards the embeddings
    currently in the store; appending with ``keep`` does not.
    """

    keep: bool = False
    confirm: bool = False


class TraceClearRequest(BaseModel):
    """Confirmation for deleting the trace log."""

    confirm: bool = False
