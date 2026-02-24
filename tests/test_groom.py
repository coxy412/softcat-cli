"""Tests for the groom command and update_agent() logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from softcat.agents.manager import AgentInfo, AgentManager
from softcat.cli import cli
from softcat.config import Config
from softcat.core.fabricator import Fabricator


# --- Fixtures ---


@pytest.fixture
def agent_dir(tmp_path: Path) -> Path:
    """Create a minimal agent directory for testing."""
    d = tmp_path / "test-agent"
    d.mkdir()
    (d / "outputs").mkdir()

    (d / "agent.py").write_text("print('hello')\n")
    (d / "agent.py").chmod(0o755)

    (d / "prompt.md").write_text("# Test\nAnalyse {{DATA}} for {{DATE}}.\n")

    config_data = {
        "name": "test-agent",
        "summary": "A test agent",
        "intent": "digest",
        "model": "claude-sonnet-4-5-20250929",
        "schedule": "0 6 * * *",
        "output_format": "markdown",
        "output_destination": "file",
        "data_sources": [{"type": "api", "url_or_path": "https://example.com"}],
        "dependencies": ["anthropic", "httpx"],
    }
    with open(d / "config.yaml", "w") as f:
        yaml.dump(config_data, f)

    (d / "requirements.txt").write_text("anthropic\nhttpx\n")
    (d / ".status").write_text("active")
    (d / ".env").write_text("ANTHROPIC_API_KEY=test-key\n")

    return d


MOCK_CODE_RESPONSE = '''\
#!/usr/bin/env python3
"""SOFT CAT Agent: test-agent"""
import os
from pathlib import Path

def main():
    dry_run = os.environ.get("SOFTCAT_DRY_RUN") == "1"
    template = Path(__file__).parent.joinpath("prompt.md").read_text()
    template = template.replace("{{DATA}}", "sample").replace("{{DATE}}", "today")
    print(template)

if __name__ == "__main__":
    main()
'''

MOCK_FULL_RESPONSE = (
    "===AGENT_CODE===\n"
    + MOCK_CODE_RESPONSE
    + "\n===PROMPT_TEMPLATE===\n"
    "# Improved Test\nAnalyse {{DATA}} for {{DATE}} with care.\n"
)


def _mock_claude_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


# --- Fabricator.refabricate() tests ---


class TestRefabricate:
    """Test the refabricate method on Fabricator."""

    def test_code_only_writes_agent_py(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_CODE_RESPONSE
            )
            result = fab.refabricate(agent_dir)

        assert result == agent_dir
        assert "SOFT CAT Agent" in (agent_dir / "agent.py").read_text()
        # Prompt should be unchanged
        assert "{{DATA}}" in (agent_dir / "prompt.md").read_text()
        assert "Improved" not in (agent_dir / "prompt.md").read_text()

    def test_full_mode_writes_both_files(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_FULL_RESPONSE
            )
            fab.refabricate(agent_dir, regenerate_prompt=True)

        assert "SOFT CAT Agent" in (agent_dir / "agent.py").read_text()
        assert "Improved" in (agent_dir / "prompt.md").read_text()

    def test_creates_backup_files(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        original_code = (agent_dir / "agent.py").read_text()

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_CODE_RESPONSE
            )
            fab.refabricate(agent_dir)

        bak = agent_dir / "agent.py.bak"
        assert bak.exists()
        assert bak.read_text() == original_code

    def test_full_mode_creates_prompt_backup(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        original_prompt = (agent_dir / "prompt.md").read_text()

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_FULL_RESPONSE
            )
            fab.refabricate(agent_dir, regenerate_prompt=True)

        assert (agent_dir / "prompt.md.bak").exists()
        assert (agent_dir / "prompt.md.bak").read_text() == original_prompt

    def test_uses_model_from_config(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_CODE_RESPONSE
            )
            fab.refabricate(agent_dir)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"

    def test_agent_py_is_executable(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        fab = Fabricator(config)

        with patch.object(fab, "client") as mock_client:
            mock_client.messages.create.return_value = _mock_claude_response(
                MOCK_CODE_RESPONSE
            )
            fab.refabricate(agent_dir)

        mode = (agent_dir / "agent.py").stat().st_mode
        assert mode & 0o755 == 0o755


# --- AgentManager.update_agent() tests ---


class TestUpdateAgent:
    """Test update_agent with backup/restore logic."""

    def test_success_cleans_up_backups(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        config.agents_dir = agent_dir.parent
        manager = AgentManager(config)

        with patch("softcat.core.fabricator.Fabricator") as MockFab:
            mock_fab = MockFab.return_value
            mock_fab.refabricate.return_value = agent_dir

            with patch("softcat.core.tester.Tester") as MockTest:
                mock_tester = MockTest.return_value
                mock_tester.test.return_value = MagicMock(passed=True)

                # Create a .bak file to simulate what refabricate does
                (agent_dir / "agent.py.bak").write_text("old code")

                result = manager.update_agent("test-agent")

        assert result is True
        assert not (agent_dir / "agent.py.bak").exists()

    def test_failure_restores_backup(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        config.agents_dir = agent_dir.parent
        manager = AgentManager(config)

        original_code = "print('original')\n"
        (agent_dir / "agent.py").write_text(original_code)

        with patch("softcat.core.fabricator.Fabricator") as MockFab:
            mock_fab = MockFab.return_value

            def fake_refabricate(d, regenerate_prompt=False):
                # Simulate what refabricate does: create backup, write bad code
                (d / "agent.py.bak").write_text(original_code)
                (d / "agent.py").write_text("def broken(\n")
                return d

            mock_fab.refabricate.side_effect = fake_refabricate

            with patch("softcat.core.tester.Tester") as MockTest:
                mock_tester = MockTest.return_value
                mock_tester.test.return_value = MagicMock(passed=False)

                result = manager.update_agent("test-agent")

        assert result is False
        assert (agent_dir / "agent.py").read_text() == original_code
        assert not (agent_dir / "agent.py.bak").exists()

    def test_failure_restores_prompt_backup(self, agent_dir: Path):
        config = Config(anthropic_api_key="test-key")
        config.agents_dir = agent_dir.parent
        manager = AgentManager(config)

        original_prompt = (agent_dir / "prompt.md").read_text()

        with patch("softcat.core.fabricator.Fabricator") as MockFab:
            mock_fab = MockFab.return_value

            def fake_refabricate(d, regenerate_prompt=False):
                (d / "agent.py.bak").write_text((d / "agent.py").read_text())
                (d / "prompt.md.bak").write_text(original_prompt)
                (d / "agent.py").write_text("def broken(\n")
                (d / "prompt.md").write_text("# Bad prompt\n")
                return d

            mock_fab.refabricate.side_effect = fake_refabricate

            with patch("softcat.core.tester.Tester") as MockTest:
                mock_tester = MockTest.return_value
                mock_tester.test.return_value = MagicMock(passed=False)

                result = manager.update_agent("test-agent", regenerate_prompt=True)

        assert result is False
        assert (agent_dir / "prompt.md").read_text() == original_prompt

    def test_nonexistent_agent_returns_false(self, tmp_path: Path):
        config = Config(anthropic_api_key="test-key")
        config._agents_dir = tmp_path
        manager = AgentManager(config)

        result = manager.update_agent("nonexistent")
        assert result is False


# --- CLI groom command tests ---


class TestGroomCommand:
    """Test the groom CLI command."""

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_single_agent(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = AgentInfo(name="my-agent", status="active")
        mock_manager.update_agent.return_value = True
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom", "my-agent"])

        assert result.exit_code == 0
        assert "Grooming my-agent" in result.output
        assert "fur looking fresh" in result.output
        mock_manager.update_agent.assert_called_once_with(
            "my-agent", regenerate_prompt=False
        )

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_with_prompt_flag(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = AgentInfo(name="my-agent", status="active")
        mock_manager.update_agent.return_value = True
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom", "my-agent", "--prompt"])

        assert result.exit_code == 0
        assert "code + prompt" in result.output
        mock_manager.update_agent.assert_called_once_with(
            "my-agent", regenerate_prompt=True
        )

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_all_agents(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.list_agents.return_value = [
            AgentInfo(name="agent-a", status="active"),
            AgentInfo(name="agent-b", status="active"),
        ]
        mock_manager.update_agent.return_value = True
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom"])

        assert result.exit_code == 0
        assert "agent-a" in result.output
        assert "agent-b" in result.output
        assert mock_manager.update_agent.call_count == 2

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_nonexistent_agent(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = None
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom", "nope"])

        assert result.exit_code != 0
        assert "No agent named" in result.output

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_failure_shows_hairball(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.get_agent.return_value = AgentInfo(name="bad-agent", status="active")
        mock_manager.update_agent.return_value = False
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom", "bad-agent"])

        assert "hairball" in result.output

    @patch("softcat.cli.AgentManager")
    @patch("softcat.cli.get_config")
    def test_groom_no_agents(self, mock_get_config, mock_manager_cls):
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.list_agents.return_value = []
        mock_manager_cls.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["groom"])

        assert result.exit_code == 0
        assert "No agents to groom" in result.output
