"""Week 6: Conversational Session Manager.

Maintains multi-turn history, active metadata filters (such as remembered region),
and conversation traces.
"""

from typing import List, Dict, Any, Optional
import uuid


class ChatSession:
    """Represents an active multi-turn conversational session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.history: List[Dict[str, str]] = []
        self.active_region: Optional[str] = None

    def add_turn(self, user_message: str, assistant_message: str, metadata: Dict[str, Any] = None):
        self.history.append({
            "user": user_message,
            "assistant": assistant_message,
            "metadata": metadata or {}
        })
        if metadata and "region" in metadata and metadata["region"]:
            self.active_region = metadata["region"]

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.history)

    def clear(self):
        self.history.clear()
        self.active_region = None
