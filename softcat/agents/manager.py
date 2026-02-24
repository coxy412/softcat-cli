"""Agent manager — CRUD operations for spawned agents."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.console import Console

from softcat.config import Config

console = Console()


@dataclass
class AgentInfo:
    """Summary info about a spawned agent."""

    name: str
    status: str = "unknown"
    schedule: str | None = None
    last_run: str | None = None
    output_count: int = 0
    summary: str = ""
    health_url: str | None = None


@dataclass
class AgentOutput:
    """A single output from an agent."""

    filename: str
    timestamp: str
    content: str


class AgentManager:
    """Manages the lifecycle of spawned agents."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.agents_dir = config.agents_dir

    def list_agents(self) -> list[AgentInfo]:
        """List all spawned agents."""
        agents = []

        if not self.agents_dir.exists():
            return agents

        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            if not (agent_dir / "agent.py").exists():
                continue

            info = self._load_agent_info(agent_dir)
            agents.append(info)

        return agents

    def get_agent(self, name: str) -> AgentInfo | None:
        """Get info about a specific agent."""
        agent_dir = self.agents_dir / name
        if not agent_dir.exists() or not (agent_dir / "agent.py").exists():
            return None
        return self._load_agent_info(agent_dir)

    def get_outputs(self, name: str, limit: int = 5) -> list[AgentOutput]:
        """Get recent outputs from an agent."""
        outputs_dir = self.agents_dir / name / "outputs"
        if not outputs_dir.exists():
            return []

        output_files = sorted(outputs_dir.iterdir(), reverse=True)[:limit]
        results = []

        for f in output_files:
            try:
                content = f.read_text()
                stat = f.stat()
                from datetime import datetime, timezone

                ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                results.append(AgentOutput(
                    filename=f.name,
                    timestamp=ts.strftime("%Y-%m-%d %H:%M UTC"),
                    content=content,
                ))
            except Exception:
                continue

        return results

    def pause_agent(self, name: str) -> bool:
        """Pause an agent by removing its cron job and updating status."""
        agent_dir = self.agents_dir / name
        if not agent_dir.exists():
            return False

        # Remove cron job
        try:
            from crontab import CronTab

            cron = CronTab(user=True)
            cron.remove_all(comment=f"softcat:{name}")
            cron.write()
        except Exception:
            pass

        (agent_dir / ".status").write_text("paused")
        return True

    def resume_agent(self, name: str) -> bool:
        """Resume a paused agent."""
        agent_dir = self.agents_dir / name
        if not agent_dir.exists():
            return False

        config_file = agent_dir / "config.yaml"
        if not config_file.exists():
            return False

        with open(config_file) as f:
            agent_config = yaml.safe_load(f) or {}

        schedule = agent_config.get("schedule", "0 6 * * *")

        # Re-register cron
        try:
            from crontab import CronTab

            from softcat.agents.runtime import cron_python_ref

            cron = CronTab(user=True)
            cron.remove_all(comment=f"softcat:{name}")

            python = cron_python_ref(agent_dir)
            agent_py = agent_dir / "agent.py"
            hc_url = agent_config.get("healthcheck_url")

            # Source .env for API keys
            env_source = ""
            if (agent_dir / ".env").exists():
                env_source = "set -a && . .env && set +a && "

            if hc_url:
                cmd = (
                    f"cd {agent_dir} && {env_source}"
                    f"{python} {agent_py} && "
                    f"curl -fsS -m 10 --retry 5 {hc_url} > /dev/null 2>&1"
                )
            else:
                cmd = f"cd {agent_dir} && {env_source}{python} {agent_py}"

            job = cron.new(command=cmd, comment=f"softcat:{name}")
            job.setall(schedule)
            job.enable()
            cron.write()
        except Exception:
            pass

        (agent_dir / ".status").write_text("active")
        return True

    def remove_agent(self, name: str) -> bool:
        """Permanently remove an agent."""
        agent_dir = self.agents_dir / name
        if not agent_dir.exists():
            return False

        # Remove cron job
        try:
            from crontab import CronTab

            cron = CronTab(user=True)
            cron.remove_all(comment=f"softcat:{name}")
            cron.write()
        except Exception:
            pass

        # Remove directory
        shutil.rmtree(agent_dir)
        return True

    def update_agent(self, name: str, regenerate_prompt: bool = False) -> bool:
        """Re-fabricate an agent's code while preserving config and outputs.

        Backs up agent.py (and prompt.md if regenerate_prompt) before calling
        Claude to regenerate. Restores from backup if syntax check fails.
        """
        from softcat.core.fabricator import Fabricator
        from softcat.core.tester import Tester

        agent_dir = self.agents_dir / name
        if not agent_dir.exists():
            return False

        # Fabricator creates .bak files and writes new code
        fabricator = Fabricator(self.config)
        fabricator.refabricate(agent_dir, regenerate_prompt=regenerate_prompt)

        # Syntax check the new code
        tester = Tester(self.config)
        result = tester.test(agent_dir)

        if not result.passed:
            # Restore from backup
            bak = agent_dir / "agent.py.bak"
            if bak.exists():
                (agent_dir / "agent.py").write_text(bak.read_text())
                (agent_dir / "agent.py").chmod(0o755)
                bak.unlink()
            if regenerate_prompt:
                prompt_bak = agent_dir / "prompt.md.bak"
                if prompt_bak.exists():
                    (agent_dir / "prompt.md").write_text(prompt_bak.read_text())
                    prompt_bak.unlink()
            return False

        # Clean up backups on success
        for bak_name in ("agent.py.bak", "prompt.md.bak"):
            bak = agent_dir / bak_name
            if bak.exists():
                bak.unlink()

        return True

    def _load_agent_info(self, agent_dir: Path) -> AgentInfo:
        """Load agent info from its directory."""
        name = agent_dir.name
        info = AgentInfo(name=name)

        # Read status
        status_file = agent_dir / ".status"
        if status_file.exists():
            info.status = status_file.read_text().strip()

        # Read config
        config_file = agent_dir / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = yaml.safe_load(f) or {}
                info.schedule = config.get("schedule")
                info.summary = config.get("summary", "")
                info.health_url = config.get("healthcheck_url")
            except Exception:
                pass

        # Count outputs
        outputs_dir = agent_dir / "outputs"
        if outputs_dir.exists():
            info.output_count = len(list(outputs_dir.iterdir()))

        # Last run (from most recent output)
        if outputs_dir.exists():
            output_files = sorted(outputs_dir.iterdir())
            if output_files:
                from datetime import datetime, timezone

                stat = output_files[-1].stat()
                ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                info.last_run = ts.strftime("%Y-%m-%d %H:%M")

        return info
