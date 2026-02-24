"""Agent runtime helpers — Python resolution and execution utilities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import IO


def resolve_python(agent_dir: Path) -> str:
    """Return the Python executable for an agent.

    If the agent has a local .venv, use its python. Otherwise fall back
    to the system Python that the softcat CLI is running under.
    """
    venv_python = agent_dir / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def build_env(agent_dir: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build the environment dict for running an agent.

    Loads the agent's .env file (if present) on top of the current
    os.environ, then applies any extra overrides.
    """
    env = dict(os.environ)

    env_file = agent_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                env[key.strip()] = value

    if extra:
        env.update(extra)

    return env


def cron_python_ref(agent_dir: Path) -> str:
    """Return the absolute python path for use in cron commands.

    For agents with a local venv, returns the absolute path to .venv/bin/python.
    For others, returns sys.executable.
    """
    venv_python = agent_dir / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable
