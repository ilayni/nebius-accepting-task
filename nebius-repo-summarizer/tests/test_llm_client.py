"""Tests for LLM response parsing."""

import pytest

from app.llm_client import _parse_llm_response


class TestParseLLMResponse:
    def test_valid_json(self):
        raw = '{"summary": "A web app", "technologies": ["Python", "Flask"], "structure": "Standard layout"}'
        result = _parse_llm_response(raw)
        assert result["summary"] == "A web app"
        assert result["technologies"] == ["Python", "Flask"]
        assert result["structure"] == "Standard layout"

    def test_json_with_code_fences(self):
        raw = '```json\n{"summary": "A CLI tool", "technologies": ["Go"], "structure": "Single binary"}\n```'
        result = _parse_llm_response(raw)
        assert result["summary"] == "A CLI tool"

    def test_technologies_as_string(self):
        raw = '{"summary": "X", "technologies": "Python, Flask, SQLAlchemy", "structure": "Y"}'
        result = _parse_llm_response(raw)
        assert isinstance(result["technologies"], list)
        assert "Python" in result["technologies"]

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_llm_response("This is not JSON at all")

    def test_missing_summary_raises(self):
        raw = '{"technologies": ["Python"], "structure": "Flat"}'
        with pytest.raises(ValueError, match="missing fields"):
            _parse_llm_response(raw)

    def test_missing_technologies_raises(self):
        raw = '{"summary": "A tool", "structure": "Flat"}'
        with pytest.raises(ValueError, match="missing fields"):
            _parse_llm_response(raw)

    def test_extra_whitespace(self):
        raw = '  \n  {"summary": "X", "technologies": ["Y"], "structure": "Z"}  \n  '
        result = _parse_llm_response(raw)
        assert result["summary"] == "X"
