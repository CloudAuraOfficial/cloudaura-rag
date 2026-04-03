"""Tests for QueryClassifier — response parsing logic."""

import pytest

from app.services.query_classifier import QueryClassifier
from app.models.schemas import QueryClassification


class TestParseResponse:
    def setup_method(self):
        self.classifier = QueryClassifier.__new__(QueryClassifier)

    def test_parse_valid_json(self):
        raw = '{"category": "simple", "confidence": 0.9, "reasoning": "Direct factual question"}'
        result = self.classifier._parse_response(raw)
        assert result.category == "simple"
        assert result.confidence == 0.9

    def test_parse_complex_category(self):
        raw = '{"category": "complex", "confidence": 0.75, "reasoning": "Needs multiple sources"}'
        result = self.classifier._parse_response(raw)
        assert result.category == "complex"

    def test_parse_no_retrieval(self):
        raw = '{"category": "no_retrieval", "confidence": 0.95, "reasoning": "General knowledge"}'
        result = self.classifier._parse_response(raw)
        assert result.category == "no_retrieval"

    def test_parse_invalid_category_defaults_complex(self):
        raw = '{"category": "unknown", "confidence": 0.5, "reasoning": "Test"}'
        result = self.classifier._parse_response(raw)
        assert result.category == "complex"

    def test_parse_markdown_code_block(self):
        raw = '```json\n{"category": "simple", "confidence": 0.8, "reasoning": "Test"}\n```'
        result = self.classifier._parse_response(raw)
        assert result.category == "simple"

    def test_parse_fallback_keyword_simple(self):
        raw = "I think this is a simple question"
        result = self.classifier._parse_response(raw)
        assert result.category == "simple"

    def test_parse_fallback_keyword_no_retrieval(self):
        raw = "This is no_retrieval type"
        result = self.classifier._parse_response(raw)
        assert result.category == "no_retrieval"

    def test_parse_fallback_default_complex(self):
        raw = "Some random unparseable text"
        result = self.classifier._parse_response(raw)
        assert result.category == "complex"

    def test_parse_clamps_confidence(self):
        raw = '{"category": "simple", "confidence": 1.5, "reasoning": "Over"}'
        result = self.classifier._parse_response(raw)
        assert result.confidence == 1.0

    def test_parse_clamps_negative_confidence(self):
        raw = '{"category": "simple", "confidence": -0.5, "reasoning": "Under"}'
        result = self.classifier._parse_response(raw)
        assert result.confidence == 0.0
