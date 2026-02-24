"""Tests for the Activator — venv creation and dependency installation."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from softcat.config import Config
from softcat.core.activator import Activator


class TestActivatorVenv:
    """Test per-agent virtual environment creation."""

    @patch("softcat.core.activator.subprocess")
    def test_create_venv_calls_python_m_venv(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        config = Config(anthropic_api_key="test-key")
        activator = Activator(config)

        agent_dir = Path("/tmp/test-agent-venv")
        activator._create_venv(agent_dir)

        call_args = mock_subprocess.run.call_args
        cmd = call_args[0][0]
        assert "-m" in cmd
        assert "venv" in cmd
        assert str(agent_dir / ".venv") in cmd

    def test_skip_existing_venv(self, tmp_path: Path):
        """If .venv already exists, don't try to create it."""
        (tmp_path / ".venv").mkdir()

        config = Config(anthropic_api_key="test-key")
        activator = Activator(config)

        with patch("softcat.core.activator.subprocess") as mock_sub:
            activator._create_venv(tmp_path)
            mock_sub.run.assert_not_called()

    def test_pip_cmd_uses_venv_pip(self, tmp_path: Path):
        """Should use .venv/bin/pip when venv exists."""
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "pip").touch()
        (venv_bin / "pip").chmod(0o755)

        reqs = tmp_path / "requirements.txt"
        reqs.write_text("httpx\n")

        config = Config(anthropic_api_key="test-key")
        activator = Activator(config)
        cmd = activator._pip_cmd(tmp_path, reqs)

        assert str(venv_bin / "pip") in cmd[0]

    def test_pip_cmd_fallback_to_system(self, tmp_path: Path):
        """Without .venv, should use sys.executable -m pip."""
        import sys

        reqs = tmp_path / "requirements.txt"
        reqs.write_text("httpx\n")

        config = Config(anthropic_api_key="test-key")
        activator = Activator(config)
        cmd = activator._pip_cmd(tmp_path, reqs)

        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "pip" in cmd
