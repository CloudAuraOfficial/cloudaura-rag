"""Relevance grader unit tests."""

import pytest

from app.services.relevance_grader import RelevanceGrader


class TestParseGrade:
    def setup_method(self):
        self.grader = RelevanceGrader.__new__(RelevanceGrader)

    def test_parse_valid_json(self):
        raw = '{"relevant": true, "confidence": 0.9, "reasoning": "Good match"}'
        grade = self.grader._parse_grade(raw, "chunk1")
        assert grade.relevant is True
        assert grade.confidence == 0.9
        assert "Good match" in grade.reasoning

    def test_parse_json_with_surrounding_text(self):
        raw = 'Here is my evaluation: {"relevant": false, "confidence": 0.2, "reasoning": "Not related"} done.'
        grade = self.grader._parse_grade(raw, "chunk2")
        assert grade.relevant is False
        assert grade.confidence == 0.2

    def test_parse_keyword_fallback_irrelevant(self):
        raw = "This chunk is not relevant to the question."
        grade = self.grader._parse_grade(raw, "chunk3")
        assert grade.relevant is False
        assert grade.confidence == 0.5

    def test_parse_keyword_fallback_relevant(self):
        raw = "This chunk provides useful information about the topic."
        grade = self.grader._parse_grade(raw, "chunk4")
        assert grade.relevant is True

    def test_parse_clamps_confidence(self):
        raw = '{"relevant": true, "confidence": 1.5, "reasoning": "Very good"}'
        grade = self.grader._parse_grade(raw, "chunk5")
        assert grade.confidence == 1.0

    def test_parse_negative_confidence_clamped(self):
        raw = '{"relevant": true, "confidence": -0.3, "reasoning": "Hmm"}'
        grade = self.grader._parse_grade(raw, "chunk6")
        assert grade.confidence == 0.0

    def test_parse_missing_fields_defaults(self):
        raw = '{"relevant": true}'
        grade = self.grader._parse_grade(raw, "chunk7")
        assert grade.relevant is True
        assert grade.confidence == 0.5
