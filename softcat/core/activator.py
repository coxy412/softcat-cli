"""A — Activate: Deploy the agent — install deps, register cron, first run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from crontab import CronTab
from rich.console import Console

from softcat.agents.runtime import cron_python_ref
from softcat.config import Config
from softcat.core.configurator import DeployConfig

console = Console()


class Activator:
    """A — Activate phase of the S.O.F.T.C.A.T pipeline.

    Installs dependencies, registers the cron job, and does the first live run.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def activate(
        self,
        agent_name: str,
        agent_dir: Path,
        deploy: DeployConfig,
    ) -> bool:
        """Deploy an agent: install deps, set up cron, first run."""

        # Step 1: Create per-agent virtual environment
        self._create_venv(agent_dir)

        # Step 2: Install dependencies into the venv
        requirements = agent_dir / "requirements.txt"
        if requirements.exists():
            console.print("   → installing dependencies...")
            pip_cmd = self._pip_cmd(agent_dir, requirements)
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                console.print(f"[bold red]   pip install failed: {result.stderr[:300]}[/bold red]")
                raise RuntimeError(f"Dependency installation failed for {agent_name}")

        # Step 3: Write .env file for cron environment
        if deploy.env_vars:
            env_file = agent_dir / ".env"
            env_lines = [f'{k}="{v}"' for k, v in deploy.env_vars.items() if v]
            env_file.write_text("\n".join(env_lines) + "\n")
            env_file.chmod(0o600)
            console.print("   → .env written")

        # Step 4: Register cron job
        if deploy.schedule:
            self._register_cron(agent_name, agent_dir, deploy)

        # Step 5: Record activation
        status_file = agent_dir / ".status"
        status_file.write_text("active")

        return True

    def _register_cron(
        self,
        agent_name: str,
        agent_dir: Path,
        deploy: DeployConfig,
    ) -> None:
        """Register a cron job for the agent."""
        try:
            cron = CronTab(user=True)

            # Remove existing job for this agent
            cron.remove_all(comment=f"softcat:{agent_name}")

            # Build the command — use venv python if available
            python = cron_python_ref(agent_dir)
            agent_py = agent_dir / "agent.py"

            # Source .env for API keys, then run agent
            env_source = ""
            if (agent_dir / ".env").exists():
                env_source = "set -a && . .env && set +a && "

            if deploy.healthcheck_url:
                cmd = (
                    f"cd {agent_dir} && {env_source}"
                    f"{python} {agent_py} && "
                    f"curl -fsS -m 10 --retry 5 {deploy.healthcheck_url} > /dev/null 2>&1"
                )
            else:
                cmd = f"cd {agent_dir} && {env_source}{python} {agent_py}"

            job = cron.new(command=cmd, comment=f"softcat:{agent_name}")
            job.setall(deploy.schedule)
            job.enable()

            cron.write()
            console.print(f"   → cron: {deploy.schedule}")

        except Exception as e:
            console.print(f"[yellow]   ⚠ Cron setup failed: {e}[/yellow]")
            console.print("[dim]   You may need to set up scheduling manually.[/dim]")

    def _create_venv(self, agent_dir: Path) -> None:
        """Create a per-agent virtual environment."""
        venv_dir = agent_dir / ".venv"
        if venv_dir.exists():
            console.print("   → venv already exists, skipping creation")
            return

        console.print("   → creating virtual environment...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                console.print(f"[yellow]   ⚠ venv creation failed: {result.stderr[:200]}[/yellow]")
                console.print("[dim]   falling back to system python[/dim]")
        except subprocess.TimeoutExpired:
            console.print("[yellow]   ⚠ venv creation timed out, falling back to system python[/yellow]")

    def _pip_cmd(self, agent_dir: Path, requirements: Path) -> list[str]:
        """Return the pip install command for this agent."""
        venv_pip = agent_dir / ".venv" / "bin" / "pip"
        if venv_pip.exists():
            return [str(venv_pip), "install", "-q", "-r", str(requirements)]
        return [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements)]

    def deactivate(self, agent_name: str) -> bool:
        """Remove an agent's cron job."""
        try:
            cron = CronTab(user=True)
            cron.remove_all(comment=f"softcat:{agent_name}")
            cron.write()

            agent_dir = self.config.agents_dir / agent_name
            status_file = agent_dir / ".status"
            if status_file.exists():
                status_file.write_text("paused")

            return True
        except Exception:
            return False
