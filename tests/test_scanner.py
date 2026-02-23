"""Tests for the SOFT CAT Scanner."""

import json
from unittest.mock import MagicMock, patch

import pytest

from softcat.core.scanner import ScanResult, Scanner


class TestScanResult:
    """Test the ScanResult model."""

    def test_minimal_scan_result(self):
        result = ScanResult(
            suggested_name="test-agent",
            summary="A test agent",
        )
        assert result.suggested_name == "test-agent"
        assert result.intent == "custom"
        assert result.complexity == "simple"

    def test_full_scan_result(self):
        result = ScanResult(
            suggested_name="hn-digest",
            summary="Daily HackerNews AI digest",
            intent="digest",
            complexity="moderate",
            tools_needed=["web_fetch"],
            dependencies=["feedparser"],
        )
        assert result.intent == "digest"
        assert "feedparser" in result.dependencies

    def test_str_representation(self):
        result = ScanResult(
            suggested_name="test",
            summary="Test agent",
        )
        text = str(result)
        assert "test" in text
        assert "Test agent" in text


class TestScanner:
    """Test the Scanner class."""

    @patch("softcat.core.scanner.anthropic.Anthropic")
    def test_scan_parses_response(self, mock_anthropic_class):
        """Test that scan correctly parses Claude's JSON response."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "suggested_name": "hn-digest",
                "summary": "Daily HN digest",
                "intent": "digest",
                "data_sources": [],
                "output": {"format": "markdown", "destination": "file"},
                "schedule": {"cadence": "daily", "cron_expression": "0 6 * * *"},
                "tools_needed": [],
                "mcp_servers": [],
                "dependencies": ["feedparser"],
                "complexity": "simple",
                "estimated_tokens_per_run": 1500,
            }))
        ]
        mock_client.messages.create.return_value = mock_response

        from softcat.config import Config
        config = Config(anthropic_api_key="test-key")
        scanner = Scanner(config)
        result = scanner.scan("watch hackernews for AI news daily")

        assert result.suggested_name == "hn-digest"
        assert result.intent == "digest"
        assert "feedparser" in result.dependencies

    @patch("softcat.core.scanner.anthropic.Anthropic")
    def test_scan_handles_code_fences(self, mock_anthropic_class):
        """Test that scan strips markdown code fences from response."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        json_content = json.dumps({
            "suggested_name": "test",
            "summary": "Test",
            "intent": "custom",
            "data_sources": [],
            "output": {"format": "markdown", "destination": "file"},
            "schedule": {"cadence": "daily", "cron_expression": "0 6 * * *"},
            "tools_needed": [],
            "mcp_servers": [],
            "dependencies": [],
            "complexity": "simple",
            "estimated_tokens_per_run": 500,
        })

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=f"```json\n{json_content}\n```")
        ]
        mock_client.messages.create.return_value = mock_response

        from softcat.config import Config
        config = Config(anthropic_api_key="test-key")
        scanner = Scanner(config)
        result = scanner.scan("test agent")

        assert result.suggested_name == "test"
