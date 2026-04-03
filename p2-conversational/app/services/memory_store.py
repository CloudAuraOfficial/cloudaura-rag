"""In-memory conversation session store.

Maintains per-session conversation history with configurable window size.
Sessions are stored in memory — lost on restart (stateless container).
"""

import uuid
from collections import OrderedDict
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


class MemoryStore:
    def __init__(self, window: int = 10, max_sessions: int = 100) -> None:
        self._sessions: OrderedDict[str, dict] = OrderedDict()
        self._window = window
        self._max_sessions = max_sessions

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._evict_if_needed()
        logger.info("session_created", session_id=session_id)
        return session_id

    def get_or_create(self, session_id: str | None) -> str:
        if session_id and session_id in self._sessions:
            return session_id
        return self.create_session()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._sessions:
            return
        self._sessions[session_id]["messages"].append(
            {"role": role, "content": content}
        )

    def get_history(self, session_id: str) -> list[dict]:
        if session_id not in self._sessions:
            return []
        messages = self._sessions[session_id]["messages"]
        return messages[-self._window :]

    def get_context_string(self, session_id: str) -> str:
        history = self.get_history(session_id)
        if not history:
            return ""
        parts = []
        for msg in history:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content']}")
        return "\n".join(parts)

    def list_sessions(self) -> list[dict]:
        result = []
        for sid, data in self._sessions.items():
            result.append({
                "session_id": sid,
                "messages": data["messages"],
                "created_at": data["created_at"],
                "message_count": len(data["messages"]),
            })
        return result

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("session_deleted", session_id=session_id)
            return True
        return False

    def _evict_if_needed(self) -> None:
        while len(self._sessions) > self._max_sessions:
            oldest_id, _ = self._sessions.popitem(last=False)
            logger.info("session_evicted", session_id=oldest_id)
