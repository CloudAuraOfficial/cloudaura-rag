"""Tests for QueryDecomposer — query parsing logic."""

import pytest

from app.services.query_decomposer import QueryDecomposer


class TestParseResponse:
    def setup_method(self):
        self.decomposer = QueryDecomposer.__new__(QueryDecomposer)

    def test_parse_json_array(self):
        raw = '["What is Docker?", "What is Kubernetes?"]'
        result = self.decomposer._parse_response(raw)
        assert result == ["What is Docker?", "What is Kubernetes?"]

    def test_parse_json_array_with_whitespace(self):
        raw = '  ["Q1?", "Q2?"]  '
        result = self.decomposer._parse_response(raw)
        assert result == ["Q1?", "Q2?"]

    def test_parse_markdown_code_block(self):
        raw = '```json\n["What is Docker?", "How does Docker work?"]\n```'
        result = self.decomposer._parse_response(raw)
        assert len(result) == 2

    def test_parse_numbered_lines(self):
        raw = "1. What is Docker?\n2. How does it work?\n3. What are containers?"
        result = self.decomposer._parse_response(raw)
        assert len(result) == 3
        assert "What is Docker?" in result[0]

    def test_parse_empty_string(self):
        result = self.decomposer._parse_response("")
        assert result == []

    def test_parse_single_line(self):
        raw = "Just a simple question?"
        result = self.decomposer._parse_response(raw)
        assert len(result) == 1

    def test_parse_filters_empty_strings(self):
        raw = '["Q1?", "", "Q2?"]'
        result = self.decomposer._parse_response(raw)
        assert len(result) == 2
