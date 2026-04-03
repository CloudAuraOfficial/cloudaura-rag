"""Tests for MemoryStore — conversation session management."""

import pytest

from app.services.memory_store import MemoryStore


class TestSessionLifecycle:
    def test_create_session_returns_id(self, memory):
        sid = memory.create_session()
        assert isinstance(sid, str)
        assert len(sid) == 12

    def test_create_multiple_sessions(self, memory):
        s1 = memory.create_session()
        s2 = memory.create_session()
        assert s1 != s2

    def test_get_or_create_existing(self, memory):
        sid = memory.create_session()
        assert memory.get_or_create(sid) == sid

    def test_get_or_create_missing(self, memory):
        sid = memory.get_or_create("nonexistent")
        assert isinstance(sid, str)
        assert len(sid) == 12

    def test_get_or_create_none(self, memory):
        sid = memory.get_or_create(None)
        assert isinstance(sid, str)

    def test_delete_session(self, memory):
        sid = memory.create_session()
        assert memory.delete_session(sid) is True
        assert memory.get_history(sid) == []

    def test_delete_nonexistent(self, memory):
        assert memory.delete_session("nope") is False

    def test_list_sessions(self, memory):
        memory.create_session()
        memory.create_session()
        sessions = memory.list_sessions()
        assert len(sessions) == 2
        for s in sessions:
            assert "session_id" in s
            assert "created_at" in s
            assert "message_count" in s


class TestMessages:
    def test_add_and_get_messages(self, memory):
        sid = memory.create_session()
        memory.add_message(sid, "user", "Hello")
        memory.add_message(sid, "assistant", "Hi there")
        history = memory.get_history(sid)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_window_limits_history(self):
        store = MemoryStore(window=3, max_sessions=10)
        sid = store.create_session()
        for i in range(10):
            store.add_message(sid, "user", f"Message {i}")
        history = store.get_history(sid)
        assert len(history) == 3
        assert history[0]["content"] == "Message 7"

    def test_add_message_to_missing_session(self, memory):
        memory.add_message("missing", "user", "Hello")
        # Should not raise, just no-op

    def test_context_string_empty(self, memory):
        sid = memory.create_session()
        assert memory.get_context_string(sid) == ""

    def test_context_string_formatted(self, memory):
        sid = memory.create_session()
        memory.add_message(sid, "user", "What is Docker?")
        memory.add_message(sid, "assistant", "Docker is a container platform.")
        ctx = memory.get_context_string(sid)
        assert "User: What is Docker?" in ctx
        assert "Assistant: Docker is a container platform." in ctx


class TestEviction:
    def test_evicts_oldest_when_full(self):
        store = MemoryStore(window=10, max_sessions=2)
        s1 = store.create_session()
        store.create_session()
        s3 = store.create_session()
        sessions = store.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert s1 not in ids
        assert s3 in ids
        assert len(sessions) == 2
