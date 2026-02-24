"""Tests for the softcat trigger command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from softcat.agents.manager import AgentInfo
from softcat.cli import cli


class TestTriggerCommand:
    """Test the trigger CLI command."""

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_trigger_nonexistent_agent(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = None
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["trigger", "nonexistent"])
        assert result.exit_code != 0
        assert "No agent named" in result.output

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_trigger_runs_agent_successfully(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = AgentInfo(name="test-agent", status="active")
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        with patch("softcat.agents.runtime.resolve_python", return_value="/usr/bin/python3"):
            with patch("softcat.agents.runtime.build_env", return_value={}):
                with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                    result = runner.invoke(cli, ["trigger", "test-agent"])

        assert "Poking test-agent awake" in result.output

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_trigger_works_when_paused(self, mock_get_config, mock_manager_cls):
        """Trigger should work even for napping agents."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = AgentInfo(name="sleepy", status="paused")
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        with patch("softcat.agents.runtime.resolve_python", return_value="/usr/bin/python3"):
            with patch("softcat.agents.runtime.build_env", return_value={}):
                with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                    result = runner.invoke(cli, ["trigger", "sleepy"])

        assert "Poking sleepy awake" in result.output
