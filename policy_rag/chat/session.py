"""Multi-turn conversation state and follow-up rewriting.

Retrieval is stateless: "what about the UK?" retrieves nothing useful on its
own. Before such a turn is retrieved, it is condensed into a standalone
question using the conversation so far, which is the same trick a production
chat-over-documents system uses.

The condensation costs one small LLM call and is only made when there is
history to use. If it fails - no API key, rate limit, empty response - the raw
question is used instead, so a broken rewrite can never take the chat down.
"""

from dataclasses import dataclass, field

from policy_rag import config
from policy_rag.observability.traces import new_run_id

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


@dataclass
class Turn:
    """One message in a conversation.

    Attributes:
        role: ``"user"`` or ``"assistant"``.
        content: The message text.
    """

    role: str
    content: str

    def to_dict(self) -> dict:
        """Returns the turn as a JSON-serialisable dict."""
        return {"role": self.role, "content": self.content}


def coerce_history(history) -> list:
    """Normalises history from any interface into a list of ``Turn``.

    Accepts what the HTTP API receives (dicts), what the CLI keeps (``Turn``
    objects) and ``None``.

    Args:
        history: Sequence of dicts with ``role``/``content``, or ``Turn`` objects.

    Returns:
        List of ``Turn``, silently dropping malformed or empty entries.
    """
    turns = []
    for item in history or []:
        if isinstance(item, Turn):
            turns.append(item)
            continue
        if isinstance(item, dict):
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role in (ROLE_USER, ROLE_ASSISTANT) and content:
                turns.append(Turn(role=role, content=content))
    return turns


def format_history(turns: list, max_turns: int = None) -> str:
    """Renders the most recent turns as plain text for the condense prompt.

    Args:
        turns: Conversation turns, oldest first.
        max_turns: How many trailing turns to include. Defaults to
            ``config.MAX_HISTORY_TURNS``.

    Returns:
        A ``User: ... / Assistant: ...`` transcript, or an empty string.
    """
    max_turns = config.MAX_HISTORY_TURNS if max_turns is None else max_turns
    recent = turns[-max_turns:] if max_turns > 0 else []
    lines = []
    for turn in recent:
        speaker = "User" if turn.role == ROLE_USER else "Assistant"
        # Assistant answers carry citations and tables; the condenser only
        # needs the gist, so they are truncated to keep the prompt small.
        content = turn.content if turn.role == ROLE_USER else turn.content[:400]
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def condense_question(question: str, history: list) -> str:
    """Rewrites a follow-up into a standalone question.

    Args:
        question: The user's latest message.
        history: Conversation turns preceding it.

    Returns:
        The rewritten question, or ``question`` unchanged when there is no
        history, no real LLM configured, or the rewrite fails.
    """
    turns = coerce_history(history)
    if not turns:
        return question

    from policy_rag.retrieval import engine

    if engine.llm_is_mocked():
        # MockLLM would return noise; a wrong rewrite is worse than none.
        return question

    engine.configure_settings()
    prompt = config.CONDENSE_PROMPT_TEMPLATE.format(
        chat_history=format_history(turns),
        question=question,
    )
    try:
        from llama_index.core import Settings

        rewritten = str(Settings.llm.complete(prompt)).strip()
    except Exception:
        return question

    # Guard against a model that returns an explanation, an empty string or a
    # paragraph instead of a question.
    if not rewritten or len(rewritten) > 400:
        return question
    return rewritten.strip('"')


@dataclass
class ChatSession:
    """A conversation with the policy assistant.

    Holds the transcript and the retrieval settings that apply to it, so a CLI
    or notebook caller can just keep asking questions.

    Attributes:
        region: Region metadata filter applied to every turn (may be None).
        top_k: Leaf chunks retrieved per turn.
        hybrid: Whether to use hybrid retrieval.
        session_id: Identifier stamped on this session's traces.
        turns: The transcript, oldest first.
    """

    region: str = None
    top_k: int = None
    hybrid: bool = None
    session_id: str = field(default_factory=lambda: new_run_id("chat"))
    turns: list = field(default_factory=list)

    def ask(self, question: str) -> dict:
        """Asks a question in the context of this conversation.

        Args:
            question: The user's message.

        Returns:
            The answer envelope from ``policy_rag.chat.service.answer``.
        """
        from policy_rag.chat.service import answer

        envelope = answer(
            question,
            region=self.region,
            top_k=self.top_k,
            hybrid=self.hybrid,
            history=self.turns,
            session_id=self.session_id,
        )
        self.turns.append(Turn(ROLE_USER, question))
        self.turns.append(Turn(ROLE_ASSISTANT, envelope["answer"]))
        return envelope

    def reset(self) -> None:
        """Clears the transcript and starts a new session id."""
        self.turns = []
        self.session_id = new_run_id("chat")

    def transcript(self) -> list:
        """Returns the conversation as a list of role/content dicts."""
        return [turn.to_dict() for turn in self.turns]
