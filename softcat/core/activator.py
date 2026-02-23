"""A — Activate: Deploy the agent — install deps, register cron, first run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from crontab import CronTab
from rich.console import Console

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

        # Step 1: Install dependencies
        requirements = agent_dir / "requirements.txt"
        if requirements.exists():
            console.print("   → installing dependencies...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                console.print(f"[bold red]   pip install failed: {result.stderr[:300]}[/bold red]")
                raise RuntimeError(f"Dependency installation failed for {agent_name}")

        # Step 2: Write .env file for cron environment
        if deploy.env_vars:
            env_file = agent_dir / ".env"
            env_lines = [f'{k}="{v}"' for k, v in deploy.env_vars.items() if v]
            env_file.write_text("\n".join(env_lines) + "\n")
            env_file.chmod(0o600)
            console.print("   → .env written")

        # Step 3: Register cron job
        if deploy.schedule:
            self._register_cron(agent_name, agent_dir, deploy)

        # Step 4: Record activation
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

            # Build the command
            python = sys.executable
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
