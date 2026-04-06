"""Hallucination checker unit tests."""

import pytest

from app.services.hallucination_checker import HallucinationChecker


class TestParseCritique:
    def setup_method(self):
        self.checker = HallucinationChecker.__new__(HallucinationChecker)

    def test_parse_valid_json(self):
        raw = '{"faithful": true, "complete": true, "hallucination_free": true, "overall_score": 0.9, "reasoning": "Well supported"}'
        critique = self.checker._parse_critique(raw)
        assert critique.faithful is True
        assert critique.complete is True
        assert critique.hallucination_free is True
        assert critique.overall_score == 0.9

    def test_parse_json_with_prefix(self):
        raw = 'Analysis: {"faithful": false, "complete": true, "hallucination_free": false, "overall_score": 0.3, "reasoning": "Claims not in context"}'
        critique = self.checker._parse_critique(raw)
        assert critique.faithful is False
        assert critique.hallucination_free is False
        assert critique.overall_score == 0.3

    def test_parse_keyword_fallback_unfaithful(self):
        raw = "The answer is not faithful to the provided context and contains hallucinations."
        critique = self.checker._parse_critique(raw)
        assert critique.faithful is False

    def test_parse_keyword_fallback_no_hallucination(self):
        raw = "The answer has no hallucination and is well-grounded."
        critique = self.checker._parse_critique(raw)
        assert critique.hallucination_free is True

    def test_parse_score_clamped(self):
        raw = '{"faithful": true, "complete": true, "hallucination_free": true, "overall_score": 1.5, "reasoning": "Perfect"}'
        critique = self.checker._parse_critique(raw)
        assert critique.overall_score == 1.0

    def test_parse_missing_fields_defaults(self):
        raw = '{"faithful": true}'
        critique = self.checker._parse_critique(raw)
        assert critique.faithful is True
        assert critique.complete is True
        assert critique.overall_score == 0.7
