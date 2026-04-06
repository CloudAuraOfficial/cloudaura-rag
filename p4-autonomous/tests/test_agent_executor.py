"""Agent executor unit tests."""

import pytest

from app.services.agent_executor import AgentExecutor


class TestParsePlan:
    def setup_method(self):
        self.executor = AgentExecutor.__new__(AgentExecutor)
        self.executor._max_steps = 5

    def test_parse_json_lines(self):
        raw = '{"thought": "Search", "tool": "retrieve", "args": {"query": "test"}}\n{"thought": "Answer", "tool": "answer", "args": {"answer": "done"}}'
        steps = self.executor._parse_plan(raw)
        assert len(steps) == 2
        assert steps[0]["tool"] == "retrieve"
        assert steps[1]["tool"] == "answer"

    def test_parse_numbered_json(self):
        raw = '1. {"thought": "Search first", "tool": "retrieve", "args": {"query": "arch"}}\n2. {"thought": "Answer", "tool": "answer", "args": {"answer": "result"}}'
        steps = self.executor._parse_plan(raw)
        assert len(steps) == 2

    def test_parse_json_with_prefix_text(self):
        raw = 'Here is my plan:\n{"thought": "Find info", "tool": "retrieve", "args": {"query": "test"}}'
        steps = self.executor._parse_plan(raw)
        assert len(steps) == 1
        assert steps[0]["tool"] == "retrieve"

    def test_parse_json_array(self):
        raw = '[{"thought": "a", "tool": "retrieve", "args": {"query": "q"}}, {"thought": "b", "tool": "answer", "args": {"answer": "a"}}]'
        steps = self.executor._parse_plan(raw)
        assert len(steps) == 2

    def test_parse_garbage_fallback(self):
        raw = "I don't know how to plan this"
        steps = self.executor._parse_plan(raw)
        assert len(steps) >= 1
        assert steps[0]["tool"] == "retrieve"

    def test_parse_empty_string(self):
        steps = self.executor._parse_plan("")
        assert len(steps) >= 1

    def test_parse_mixed_valid_invalid(self):
        raw = '{"thought": "a", "tool": "retrieve", "args": {"query": "q"}}\nnot json\n{"thought": "b", "tool": "answer", "args": {"answer": "ok"}}'
        steps = self.executor._parse_plan(raw)
        assert len(steps) == 2
