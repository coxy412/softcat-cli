"""Tests for softcat.agents.runtime helpers."""

import sys
from pathlib import Path

import pytest

from softcat.agents.runtime import build_env, cron_python_ref, resolve_python


class TestResolvePython:
    """Test Python executable resolution."""

    def test_uses_venv_when_present(self, tmp_path: Path):
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()
        (venv_bin / "python").chmod(0o755)

        result = resolve_python(tmp_path)
        assert result == str(venv_bin / "python")

    def test_falls_back_to_system_python(self, tmp_path: Path):
        result = resolve_python(tmp_path)
        assert result == sys.executable

    def test_ignores_partial_venv(self, tmp_path: Path):
        """If .venv exists but bin/python doesn't, fall back."""
        (tmp_path / ".venv").mkdir()
        result = resolve_python(tmp_path)
        assert result == sys.executable


class TestBuildEnv:
    """Test environment building from .env files."""

    def test_loads_env_file(self, tmp_path: Path):
        (tmp_path / ".env").write_text('FOO="bar"\nBAZ=qux\n')
        env = build_env(tmp_path)
        assert env["FOO"] == "bar"
        assert env["BAZ"] == "qux"

    def test_strips_single_quotes(self, tmp_path: Path):
        (tmp_path / ".env").write_text("KEY='value'\n")
        env = build_env(tmp_path)
        assert env["KEY"] == "value"

    def test_extra_overrides(self, tmp_path: Path):
        env = build_env(tmp_path, extra={"MY_VAR": "1"})
        assert env["MY_VAR"] == "1"

    def test_extra_overrides_env_file(self, tmp_path: Path):
        (tmp_path / ".env").write_text("KEY=original\n")
        env = build_env(tmp_path, extra={"KEY": "override"})
        assert env["KEY"] == "override"

    def test_handles_missing_env_file(self, tmp_path: Path):
        env = build_env(tmp_path)
        assert isinstance(env, dict)

    def test_skips_comments_and_blanks(self, tmp_path: Path):
        (tmp_path / ".env").write_text("# comment\n\nFOO=bar\n")
        env = build_env(tmp_path)
        assert env["FOO"] == "bar"
        assert "# comment" not in env


class TestCronPythonRef:
    """Test cron Python path resolution."""

    def test_returns_absolute_for_venv(self, tmp_path: Path):
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        result = cron_python_ref(tmp_path)
        assert result == str(venv_bin / "python")
        assert str(tmp_path) in result  # absolute path

    def test_returns_sys_executable_for_no_venv(self, tmp_path: Path):
        result = cron_python_ref(tmp_path)
        assert result == sys.executable
