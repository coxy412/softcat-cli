"""Tests for the meow CLI command."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from softcat.cli import cli
from softcat.core.scanner import ScanResult


VALID_SCAN_RESULT = ScanResult(
    suggested_name="test-agent",
    summary="A test agent",
    intent="digest",
    data_sources=[],
)


class TestMeowCommand:
    """Test the meow CLI command."""

    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_design_only(self, mock_get_config, mock_design):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_design.return_value = VALID_SCAN_RESULT

        runner = CliRunner()
        result = runner.invoke(cli, ["meow", "--design-only"])

        assert result.exit_code == 0
        assert "test-agent" in result.output
        assert "Design complete" in result.output
        mock_design.assert_called_once()

    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_user_quits(self, mock_get_config, mock_design):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_design.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["meow", "--design-only"])

        assert result.exit_code == 0

    @patch("softcat.cli._run_pipeline")
    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_confirm_spawns(self, mock_get_config, mock_design, mock_pipeline):
        mock_config = MagicMock()
        mock_config.default_model = "claude-sonnet-4-5-20250929"
        mock_get_config.return_value = mock_config

        mock_design.return_value = VALID_SCAN_RESULT

        runner = CliRunner()
        result = runner.invoke(cli, ["meow"], input="y\n")

        assert result.exit_code == 0
        mock_pipeline.assert_called_once()
        call_args = mock_pipeline.call_args
        assert call_args[0][1] == "test-agent"  # agent_name

    @patch("softcat.cli._run_pipeline")
    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_decline_no_spawn(self, mock_get_config, mock_design, mock_pipeline):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_design.return_value = VALID_SCAN_RESULT

        runner = CliRunner()
        result = runner.invoke(cli, ["meow"], input="n\n")

        assert result.exit_code == 0
        assert "No agent created" in result.output
        mock_pipeline.assert_not_called()

    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_name_override(self, mock_get_config, mock_design):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_design.return_value = VALID_SCAN_RESULT

        runner = CliRunner()
        result = runner.invoke(cli, ["meow", "--name", "custom-name", "--design-only"])

        assert result.exit_code == 0
        assert "custom-name" in result.output

    @patch("softcat.core.designer.Designer.__init__", return_value=None)
    @patch("softcat.core.designer.Designer.design")
    @patch("softcat.cli.get_config")
    def test_meow_passes_model_to_designer(self, mock_get_config, mock_design, mock_init):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_design.return_value = None  # quit immediately

        runner = CliRunner()
        result = runner.invoke(cli, ["meow", "--model", "claude-opus-4-6", "--design-only"])

        mock_init.assert_called_once_with(mock_config, model="claude-opus-4-6")
