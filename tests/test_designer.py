"""Tests for the Designer — multi-turn conversational agent design."""

import json
from unittest.mock import MagicMock, patch

import pytest

from softcat.config import Config
from softcat.core.designer import DESIGN_COMPLETE_MARKER, Designer
from softcat.core.scanner import ScanResult


VALID_DESIGN_JSON = json.dumps({
    "suggested_name": "arxiv-rag-digest",
    "summary": "Weekly digest of RAG papers from arxiv",
    "intent": "digest",
    "data_sources": [
        {"type": "api", "url_or_path": "https://arxiv.org/api", "description": "arxiv API"}
    ],
    "output": {
        "format": "markdown",
        "destination": "file",
        "description": "Weekly markdown summary",
    },
    "schedule": {
        "cadence": "weekly",
        "cron_expression": "0 8 * * 0",
        "timezone": "UTC",
    },
    "tools_needed": [],
    "mcp_servers": [],
    "dependencies": ["anthropic", "httpx", "pyyaml"],
    "complexity": "simple",
    "estimated_tokens_per_run": 2000,
})


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


class TestDesignerParsing:
    """Test the _parse_design method."""

    def test_parses_valid_design(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        text = f"Great, here's the design!\n\n{DESIGN_COMPLETE_MARKER}\n{VALID_DESIGN_JSON}"
        result = designer._parse_design(text)

        assert isinstance(result, ScanResult)
        assert result.suggested_name == "arxiv-rag-digest"
        assert result.intent == "digest"
        assert result.schedule.cron_expression == "0 8 * * 0"
        assert len(result.data_sources) == 1

    def test_parses_design_with_fenced_json(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        text = f"Done!\n\n{DESIGN_COMPLETE_MARKER}\n```json\n{VALID_DESIGN_JSON}\n```"
        result = designer._parse_design(text)

        assert isinstance(result, ScanResult)
        assert result.suggested_name == "arxiv-rag-digest"

    def test_raises_on_invalid_json(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        text = f"{DESIGN_COMPLETE_MARKER}\nnot valid json"
        with pytest.raises(json.JSONDecodeError):
            designer._parse_design(text)


class TestDesignerConversation:
    """Test the multi-turn conversation flow."""

    def test_two_turn_conversation_returns_scan_result(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        # Turn 1: Claude asks a follow-up
        # Turn 2: Claude completes the design
        responses = [
            _mock_response("Interesting! What output format and schedule do you want?"),
            _mock_response(
                f"Here's the design.\n\n{DESIGN_COMPLETE_MARKER}\n{VALID_DESIGN_JSON}"
            ),
        ]

        with patch.object(designer, "client") as mock_client:
            mock_client.messages.create.side_effect = responses
            with patch("softcat.core.designer.Prompt.ask", side_effect=[
                "I want a weekly arxiv RAG digest",
                "markdown file, sunday mornings",
            ]):
                result = designer.design()

        assert isinstance(result, ScanResult)
        assert result.suggested_name == "arxiv-rag-digest"
        assert mock_client.messages.create.call_count == 2

    def test_single_turn_completion(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        with patch.object(designer, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_response(
                f"Got it!\n\n{DESIGN_COMPLETE_MARKER}\n{VALID_DESIGN_JSON}"
            )
            with patch("softcat.core.designer.Prompt.ask", return_value="weekly arxiv digest"):
                result = designer.design()

        assert isinstance(result, ScanResult)
        assert mock_client.messages.create.call_count == 1

    def test_user_types_quit(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        with patch("softcat.core.designer.Prompt.ask", return_value="quit"):
            result = designer.design()

        assert result is None

    def test_user_types_exit(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        with patch("softcat.core.designer.Prompt.ask", return_value="exit"):
            result = designer.design()

        assert result is None

    def test_keyboard_interrupt_returns_none(self):
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        with patch("softcat.core.designer.Prompt.ask", side_effect=KeyboardInterrupt):
            result = designer.design()

        assert result is None

    def test_conversation_history_grows(self):
        """Each turn should add user + assistant messages to history."""
        config = Config(anthropic_api_key="test-key")
        designer = Designer(config)

        responses = [
            _mock_response("Tell me more about the schedule."),
            _mock_response(
                f"Perfect.\n\n{DESIGN_COMPLETE_MARKER}\n{VALID_DESIGN_JSON}"
            ),
        ]

        with patch.object(designer, "client") as mock_client:
            mock_client.messages.create.side_effect = responses
            with patch("softcat.core.designer.Prompt.ask", side_effect=[
                "build a thing",
                "daily at 6am",
            ]):
                designer.design()

        # Check that the first call had 1 message and the second had 3+
        first_call = mock_client.messages.create.call_args_list[0]
        first_msgs = first_call[1]["messages"]
        # Note: messages is a mutable list, so by inspection time it has all entries.
        # Instead, verify the call count and that history was passed correctly.
        assert mock_client.messages.create.call_count == 2
        # The shared messages list ends with: user1, assistant1, user2, assistant2
        assert first_msgs[0] == {"role": "user", "content": "build a thing"}
        assert first_msgs[1] == {"role": "assistant", "content": "Tell me more about the schedule."}
        assert first_msgs[2] == {"role": "user", "content": "daily at 6am"}
